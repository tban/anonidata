use serde::Deserialize;
use std::collections::HashMap;
use std::fs::File;
use std::io::{Read, Write};
use tauri::{AppHandle, Manager, Emitter};
use serde_json::json;
use tauri_plugin_dialog::{DialogExt, MessageDialogButtons, MessageDialogKind};

const VERSION_JSON_URL: &str = "https://drive.google.com/uc?export=download&id=11wml7BF4ZO17coEiimKNJk_tfIMAvWDq";
const BUILD_NUMBER_STR: &str = env!("CARGO_BUILD_NUMBER");

#[derive(Deserialize, Debug)]
struct PlatformInfo {
    filename: String,
    url: String,
}

#[derive(Deserialize, Debug)]
struct VersionJson {
    version: String,
    #[serde(default)]
    build: u64,
    platforms: HashMap<String, PlatformInfo>,
}

fn compare_semver(remote: &str, local: &str) -> Option<std::cmp::Ordering> {
    let r_ver = semver::Version::parse(remote).ok()?;
    let l_ver = semver::Version::parse(local).ok()?;
    Some(r_ver.cmp(&l_ver))
}

pub fn check_for_updates_in_background(app: AppHandle) {
    std::thread::spawn(move || {
        // Wait a few seconds to let the main window render and avoid blocking immediate startup visual feedback
        std::thread::sleep(std::time::Duration::from_secs(3));
        
        log::info!("Starting background update check...");
        if let Err(e) = run_updater_sync(&app, false) {
            log::error!("Auto-updater error: {}", e);
        }
    });
}

pub fn check_for_updates_manual(app: AppHandle) {
    std::thread::spawn(move || {
        log::info!("Starting manual update check...");
        if let Err(e) = run_updater_sync(&app, true) {
            log::error!("Auto-updater error: {}", e);
            app.dialog()
                .message(&format!("Error al comprobar actualizaciones: {}", e))
                .title("Error de Actualización")
                .kind(MessageDialogKind::Error)
                .blocking_show();
        }
    });
}

fn run_updater_sync(app: &AppHandle, manual: bool) -> Result<(), String> {
    let current_version = app.package_info().version.to_string();
    let current_build: u64 = BUILD_NUMBER_STR.parse().unwrap_or(0);
    
    log::info!("Current version: {} (Build #{})", current_version, current_build);

    // 1. Fetch remote version.json
    let client = reqwest::blocking::Client::builder()
        .timeout(std::time::Duration::from_secs(15))
        .build()
        .map_err(|e| format!("Failed to build HTTP client: {}", e))?;

    let response = client.get(VERSION_JSON_URL)
        .send()
        .map_err(|e| format!("HTTP request failed: {}", e))?;

    if !response.status().is_success() {
        return Err(format!("Server returned error status: {}", response.status()));
    }

    let remote_data: VersionJson = response.json()
        .map_err(|e| format!("Failed to parse version.json: {}", e))?;

    log::info!("Remote version: {} (Build #{})", remote_data.version, remote_data.build);

    // 2. Compare versions
    let mut update_available = false;
    if let Some(ord) = compare_semver(&remote_data.version, &current_version) {
        match ord {
            std::cmp::Ordering::Greater => update_available = true,
            std::cmp::Ordering::Equal => {
                if remote_data.build > current_build {
                    update_available = true;
                }
            }
            std::cmp::Ordering::Less => {}
        }
    } else {
        // Fallback simple comparison if semver parsing fails (which shouldn't happen)
        if remote_data.version != current_version {
            update_available = true;
        }
    }

    if !update_available {
        log::info!("Application is up-to-date.");
        if manual {
            app.dialog()
                .message("La aplicación está actualizada a la última versión.")
                .title("Actualización")
                .kind(MessageDialogKind::Info)
                .blocking_show();
        }
        return Ok(());
    }

    log::info!("New version available: {}.", remote_data.version);

    // 3. Determine platform download key
    let os_key = if cfg!(target_os = "macos") {
        "mac"
    } else if cfg!(target_os = "windows") {
        "windows"
    } else {
        log::warn!("Unsupported operating system for auto-updater.");
        return Ok(());
    };

    let platform_info = match remote_data.platforms.get(os_key) {
        Some(info) => info,
        None => {
            return Err(format!("Remote version.json does not contain info for OS: {}", os_key));
        }
    };

    // Replace {VERSION} template in URL if present
    let mut download_url = platform_info.url.replace("{VERSION}", &remote_data.version);

    // Convert Google Drive view URLs to direct download URLs
    if download_url.contains("drive.google.com/open?id=") {
        download_url = download_url.replace("/open?id=", "/uc?export=download&id=");
        download_url = download_url.replace("&usp=drive_fs", "");
        download_url = format!("{}&confirm=t", download_url);
    }

    let filename = &platform_info.filename;

    log::info!("Download URL: {}", download_url);

    // 4. Prompt user using native dialog
    let message_text = format!(
        "Una nueva versión de AnoniData está disponible (v{} Build #{}).\n¿Deseas descargarla e instalarla ahora?",
        remote_data.version, remote_data.build
    );

    let confirmed = app.dialog()
        .message(message_text)
        .title("Actualización Disponible")
        .kind(MessageDialogKind::Info)
        .buttons(MessageDialogButtons::YesNo)
        .blocking_show();

    if !confirmed {
        log::info!("User declined the update.");
        return Ok(());
    }

    // 5. Download the installer to a temporary location
    let temp_dir = app.path().temp_dir()
        .map_err(|e| format!("Failed to get temp directory: {}", e))?;
    let temp_file_path = temp_dir.join(filename);

    log::info!("Downloading installer to {:?}", temp_file_path);

    let mut download_response = client.get(&download_url)
        .send()
        .map_err(|e| format!("Failed to request installer download: {}", e))?;

    if !download_response.status().is_success() {
        return Err(format!("Installer download server returned: {}", download_response.status()));
    }

    if let Some(content_type) = download_response.headers().get(reqwest::header::CONTENT_TYPE) {
        if content_type.to_str().unwrap_or("").starts_with("text/html") {
            log::info!("Intercepted Google Drive HTML warning page. Attempting bypass...");
            let text = download_response.text().map_err(|e| e.to_string())?;
            
            let mut uuid = "";
            if let Some(pos) = text.find("name=\"uuid\" value=\"") {
                let start = pos + 19;
                if let Some(end) = text[start..].find("\"") {
                    uuid = &text[start..start + end];
                }
            }
            
            let mut confirm = "t";
            if let Some(pos) = text.find("name=\"confirm\" value=\"") {
                let start = pos + 22;
                if let Some(end) = text[start..].find("\"") {
                    confirm = &text[start..start + end];
                }
            }
            
            let mut file_id = "";
            if let Some(pos) = download_url.find("id=") {
                let start = pos + 3;
                if let Some(end) = download_url[start..].find('&') {
                    file_id = &download_url[start..start + end];
                } else {
                    file_id = &download_url[start..];
                }
            }
            
            if !file_id.is_empty() {
                let bypass_url = format!("https://drive.usercontent.google.com/download?id={}&export=download&confirm={}&uuid={}", file_id, confirm, uuid);
                log::info!("Retrying download with bypass URL: {}", bypass_url);
                download_response = client.get(&bypass_url).send().map_err(|e| format!("Failed bypass request: {}", e))?;
                
                if !download_response.status().is_success() {
                    return Err(format!("Bypass download failed: {}", download_response.status()));
                }
            } else {
                return Err("Failed to extract file ID from Google Drive URL".to_string());
            }
        }
    }

    let total_size = download_response.content_length().unwrap_or(0);
    
    let mut out_file = File::create(&temp_file_path)
        .map_err(|e| format!("Failed to create temporary file: {}", e))?;

    let _ = app.emit("updater-start", json!({"total": total_size}));

    let mut downloaded: u64 = 0;
    let mut buffer = [0; 16384]; // 16KB chunks

    loop {
        let bytes_read = download_response.read(&mut buffer)
            .map_err(|e| format!("Error during download: {}", e))?;
        
        if bytes_read == 0 {
            break; // EOF
        }

        out_file.write_all(&buffer[..bytes_read])
            .map_err(|e| format!("Error writing file: {}", e))?;

        downloaded += bytes_read as u64;

        if total_size > 0 {
            let percentage = (downloaded as f64 / total_size as f64) * 100.0;
            let _ = app.emit("updater-progress", json!({
                "downloaded": downloaded,
                "total": total_size,
                "percentage": percentage
            }));
        }
    }

    log::info!("Download completed successfully.");

    // 6. Execute installer and exit application
    #[cfg(target_os = "windows")]
    {
        log::info!("Spawning Windows installer...");
        let status = std::process::Command::new(&temp_file_path)
            .spawn();

        match status {
            Ok(_) => {
                log::info!("Installer spawned successfully. Exiting AnoniData.");
                app.exit(0);
            }
            Err(e) => {
                return Err(format!("Failed to execute installer: {}", e));
            }
        }
    }

    #[cfg(target_os = "macos")]
    {
        log::info!("Opening macOS DMG installer...");
        let status = std::process::Command::new("open")
            .arg(&temp_file_path)
            .spawn();

        match status {
            Ok(_) => {
                log::info!("DMG opened successfully. Exiting AnoniData.");
                app.exit(0);
            }
            Err(e) => {
                return Err(format!("Failed to open DMG: {}", e));
            }
        }
    }

    #[cfg(not(any(target_os = "windows", target_os = "macos")))]
    {
        log::warn!("Auto-installation not supported on this platform.");
    }

    Ok(())
}
