use std::path::{Path, PathBuf};

fn get_target_dir(out_dir: &str) -> Option<PathBuf> {
    let mut path = PathBuf::from(out_dir);
    // target/release/build/anonidata-xxxxx/out -> target/release
    if path.pop() && path.pop() && path.pop() {
        Some(path)
    } else {
        None
    }
}

fn main() {
    // 1. Determine build number
    let profile = std::env::var("PROFILE").unwrap_or_default();
    let is_release = profile == "release";
    let manifest_dir = std::env::var("CARGO_MANIFEST_DIR").unwrap();
    let src_dir = Path::new(&manifest_dir).parent().unwrap().join("src");
    let version_local_path = src_dir.join("version_local.json");
    let build_number_file_path = Path::new(&manifest_dir).join("build_number.txt");

    let mut build_number = 1;

    // Rerun build.rs if build_number.txt or version_local.json change
    println!("cargo:rerun-if-changed=build.rs");
    println!("cargo:rerun-if-changed={}", version_local_path.display());
    println!("cargo:rerun-if-changed={}", build_number_file_path.display());

    if version_local_path.exists() {
        if let Ok(content) = std::fs::read_to_string(&version_local_path) {
            if let Ok(json) = serde_json::from_str::<serde_json::Value>(&content) {
                if let Some(b) = json.get("build").and_then(|v| v.as_u64()) {
                    build_number = b;
                }
            }
        }
    } else {
        if build_number_file_path.exists() {
            if let Ok(content) = std::fs::read_to_string(&build_number_file_path) {
                if let Ok(parsed) = content.trim().parse::<u64>() {
                    build_number = parsed;
                }
            }
        }
        if is_release {
            build_number += 1;
            let _ = std::fs::write(&build_number_file_path, build_number.to_string());
        }
    }

    // Expose build number to Rust compiler
    println!("cargo:rustc-env=CARGO_BUILD_NUMBER={}", build_number);

    // 2. Generate version.json in target directory if this is a release build
    if is_release {
        let version = std::env::var("CARGO_PKG_VERSION").unwrap_or_else(|_| "1.0.0".to_string());
        let url_mac = format!(
            "https://github.com/tban/tbanapps/releases/download/v{}/AnoniData.dmg",
            version
        );
        let url_windows = "https://drive.google.com/uc?export=download&id=1aE8XuzonmI9Bi50Th7vk9FawOHkthf_4&confirm=t".to_string();

        let version_data = serde_json::json!({
            "productName": "AnoniData",
            "version": version,
            "build": build_number,
            "date": chrono::Utc::now().to_rfc3339_opts(chrono::SecondsFormat::Secs, true),
            "platforms": {
                "mac": {
                    "label": "macOS (.dmg)",
                    "filename": "AnoniData.dmg",
                    "arch": "Universal",
                    "url": url_mac
                },
                "windows": {
                    "label": "Windows (.exe)",
                    "filename": "AnoniData.exe",
                    "arch": "x64",
                    "url": url_windows
                }
            }
        });

        if let Some(target_dir) = get_target_dir(&std::env::var("OUT_DIR").unwrap()) {
            let version_json_path = target_dir.join("version.json");
            if let Ok(json_string) = serde_json::to_string_pretty(&version_data) {
                let _ = std::fs::write(&version_json_path, json_string);
                println!("cargo:warning=version.json successfully generated at {:?}", version_json_path);
            }
        }
    }

    tauri_build::build();
}
