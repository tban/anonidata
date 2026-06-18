use tokio::sync::{Mutex, mpsc};
use serde_json::{Value, json};
use tauri::{Emitter, Manager};
use tauri_plugin_shell::ShellExt;
use tauri_plugin_shell::process::{CommandChild, CommandEvent};
use tauri::menu::{MenuBuilder, MenuItemBuilder, SubmenuBuilder, PredefinedMenuItem};

pub mod commands;

pub struct BackendController {
    pub child: CommandChild,
    pub read_rx: Mutex<mpsc::Receiver<Value>>,
}

pub struct AppState {
    pub controller: Mutex<Option<BackendController>>,
}

pub fn get_settings(app: &tauri::AppHandle) -> Value {
    if let Ok(config_dir) = app.path().app_config_dir() {
        let path = config_dir.join("settings.json");
        if path.exists() {
            if let Ok(content) = std::fs::read_to_string(path) {
                if let Ok(json) = serde_json::from_str::<Value>(&content) {
                    if let Some(settings) = json.get("settings") {
                        return settings.clone();
                    }
                }
            }
        }
    }
    // Return default settings
    json!({
        "autoCleanTemp": true,
        "logLevel": "info",
        "maxFileSize": 52428800
    })
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_fs::init())
        .plugin(tauri_plugin_store::Builder::new().build())
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_os::init())
        .setup(|app| {
            // Build the native menu
            let about_item = MenuItemBuilder::new("Acerca de AnoniData")
                .id("show-about-modal")
                .build(app)?;

            let check_updates_item = MenuItemBuilder::new("Buscar actualizaciones")
                .id("check-updates")
                .build(app)?;

            let quit_item = PredefinedMenuItem::quit(app, Some("Salir"))?;

            let app_submenu = SubmenuBuilder::new(app, "AnoniData")
                .item(&about_item)
                .item(&check_updates_item)
                .separator()
                .item(&quit_item)
                .build()?;

            let menu = MenuBuilder::new(app)
                .item(&app_submenu)
                .build()?;

            app.set_menu(menu)?;

            // Spawn the Python sidecar on app startup
            let shell = app.shell();
            let sidecar = shell.sidecar("anonidata-backend")
                .map_err(|e| Box::<dyn std::error::Error>::from(format!("Failed to configure sidecar: {}", e)))?;

            let (mut rx, child) = sidecar.spawn()
                .map_err(|e| Box::<dyn std::error::Error>::from(format!("Failed to spawn sidecar: {}", e)))?;

            // Communication channel for stdout responses
            let (response_tx, response_rx) = mpsc::channel::<Value>(32);

            // Reader task to read stdout/stderr from Python process
            tauri::async_runtime::spawn(async move {
                let mut stdout_buffer = String::new();
                while let Some(event) = rx.recv().await {
                    match event {
                        CommandEvent::Stdout(bytes) => {
                            let chunk = String::from_utf8_lossy(&bytes);
                            stdout_buffer.push_str(&chunk);
                            
                            while let Some(pos) = stdout_buffer.find('\n') {
                                let line = stdout_buffer[..pos].trim().to_string();
                                stdout_buffer = stdout_buffer[pos + 1..].to_string();
                                
                                if !line.is_empty() {
                                    if line.contains('{') && (line.contains("success") || line.contains("status")) {
                                        if let Ok(json) = serde_json::from_str::<Value>(&line) {
                                            let _ = response_tx.send(json).await;
                                        }
                                    } else {
                                        println!("[Python] {}", line);
                                    }
                                }
                            }
                        }
                        CommandEvent::Stderr(bytes) => {
                            let err = String::from_utf8_lossy(&bytes);
                            eprintln!("[Python Error] {}", err);
                        }
                        CommandEvent::Terminated(status) => {
                            println!("[Python Terminated] {:?}", status.code);
                            break;
                        }
                        _ => {}
                    }
                }
            });



            // Save child process controller in state
            app.manage(AppState {
                controller: Mutex::new(Some(BackendController {
                    child,
                    read_rx: Mutex::new(response_rx),
                }))
            });

            Ok(())
        })
        .on_menu_event(|app, event| {
            match event.id().as_ref() {
                "show-about-modal" => {
                    let _ = app.emit("show-about-modal", ());
                }
                "check-updates" => {
                    let _ = app.emit("check-updates", ());
                }
                _ => {}
            }
        })
        .invoke_handler(tauri::generate_handler![
            commands::anonymize,
            commands::detect_only,
            commands::finalize_anonymization,
            commands::check_pdf_type,
            commands::read_pdf_file,
            commands::delete_file,
            commands::load_detections,
            commands::save_detections,
            commands::get_app_version,
            commands::apply_ocr
        ])
        .build(tauri::generate_context!())
        .expect("error while building tauri application")
        .run(|app_handle, event| match event {
            tauri::RunEvent::Exit => {
                // Terminate Python sidecar process cleanly
                if let Some(state) = app_handle.try_state::<AppState>() {
                    if let Ok(mut controller_guard) = state.controller.try_lock() {
                        if let Some(controller) = controller_guard.take() {
                            let _ = controller.child.kill();
                        }
                    }
                }
            }
            _ => {}
        });
}
