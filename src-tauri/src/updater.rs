use serde::Deserialize;
use std::collections::HashMap;
use std::fs::File;
use std::io::{Read, Write};
use tauri::{AppHandle, Manager, Emitter};
use serde_json::json;
use tauri_plugin_dialog::{DialogExt, MessageDialogButtons, MessageDialogKind};

const VERSION_JSON_URL: &str = "https://raw.githubusercontent.com/tban/anonidata/main/version.json";
const BUILD_NUMBER_STR: &str = env!("CARGO_BUILD_NUMBER");

#[derive(Deserialize, Debug)]
struct PlatformInfo {
    filename: String,
    url: String,
    #[serde(default)]
    version: Option<String>,
    #[serde(default)]
    build: Option<u64>,
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

    // 1. Fetch remote version.json with cache buster to prevent CDN/local caching
    let client = reqwest::blocking::Client::builder()
        .timeout(std::time::Duration::from_secs(15))
        .build()
        .map_err(|e| format!("Failed to build HTTP client: {}", e))?;

    let timestamp = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0);
    let version_url_with_cache_buster = format!("{}&t={}", VERSION_JSON_URL, timestamp);

    let response = client.get(&version_url_with_cache_buster)
        .header(reqwest::header::CACHE_CONTROL, "no-cache, no-store, must-revalidate")
        .header(reqwest::header::PRAGMA, "no-cache")
        .header(reqwest::header::EXPIRES, "0")
        .send()
        .map_err(|e| format!("HTTP request failed: {}", e))?;

    if !response.status().is_success() {
        return Err(format!("Server returned error status: {}", response.status()));
    }

    let remote_data: VersionJson = response.json()
        .map_err(|e| format!("Failed to parse version.json: {}", e))?;

    // Determine platform download key
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

    // Use platform-specific version and build if available, otherwise fallback to root-level values
    let target_version = platform_info.version.as_deref().unwrap_or(&remote_data.version);
    let target_build = platform_info.build.unwrap_or(remote_data.build);

    log::info!(
        "Remote version info for platform '{}': {} (Build #{}) [Root: {} (Build #{})]",
        os_key,
        target_version,
        target_build,
        remote_data.version,
        remote_data.build
    );

    // 2. Compare versions
    let mut update_available = false;
    if let Some(ord) = compare_semver(target_version, &current_version) {
        match ord {
            std::cmp::Ordering::Greater => update_available = true,
            std::cmp::Ordering::Equal => {
                if target_build > current_build {
                    update_available = true;
                }
            }
            std::cmp::Ordering::Less => {}
        }
    } else {
        // Fallback simple comparison if semver parsing fails (which shouldn't happen)
        if target_version != &current_version {
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

    log::info!("New version available: {}.", target_version);

    // Replace {VERSION} template in URL if present
    let mut download_url = platform_info.url.replace("{VERSION}", target_version);


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
        .header(reqwest::header::CACHE_CONTROL, "no-cache, no-store, must-revalidate")
        .header(reqwest::header::PRAGMA, "no-cache")
        .header(reqwest::header::EXPIRES, "0")
        .send()
        .map_err(|e| format!("Failed to request installer download: {}", e))?;

    if !download_response.status().is_success() {
        return Err(format!("Installer download server returned: {}", download_response.status()));
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

    // Cerrar el archivo explícitamente para liberar el lock de escritura (crucial en Windows)
    drop(out_file);

    // 6. Execute installer and exit application
    #[cfg(target_os = "windows")]
    {
        log::info!("Spawning Windows installer via cmd start...");
        // Usamos 'cmd /c start' para asegurar que Windows gestione correctamente los permisos UAC (elevación)
        // y desvincule el proceso de instalación del ciclo de vida de la app padre.
        let status = std::process::Command::new("cmd")
            .args(["/c", "start", "", &temp_file_path.to_string_lossy()])
            .spawn();

        match status {
            Ok(_) => {
                log::info!("Installer spawned successfully via cmd. Exiting AnoniData.");
                std::thread::sleep(std::time::Duration::from_millis(500));
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
