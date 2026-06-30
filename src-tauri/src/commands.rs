use serde_json::{Value, json};
use std::time::Duration;
use tokio::time::timeout;
use tauri::State;
use crate::{AppState, get_settings};
use std::sync::atomic::{AtomicU64, Ordering};

static REQUEST_COUNTER: AtomicU64 = AtomicU64::new(1);

// Helper to write request to sidecar stdin and wait for response on sidecar stdout channel
async fn send_sidecar_request(
    state: State<'_, AppState>,
    mut request: Value,
    timeout_duration: Duration,
) -> Result<Value, String> {
    let request_id = REQUEST_COUNTER.fetch_add(1, Ordering::SeqCst);
    if let Some(obj) = request.as_object_mut() {
        obj.insert("request_id".to_string(), json!(request_id));
    }

    let mut controller_guard = state.controller.lock().await;
    let controller = controller_guard.as_mut().ok_or("Backend sidecar not running")?;
    
    // Acquire exclusive access to the response receiver
    let mut read_rx = controller.read_rx.lock().await;
    
    // Serialize and send request via child.write
    let mut request_str = serde_json::to_string(&request).map_err(|e| e.to_string())?;
    request_str.push('\n');
    controller.child.write(request_str.as_bytes()).map_err(|e| e.to_string())?;
    
    // Read responses from channel until we get a success/error response matching our request_id
    let start_time = std::time::Instant::now();
    while start_time.elapsed() < timeout_duration {
        let remaining = timeout_duration.saturating_sub(start_time.elapsed());
        match timeout(remaining, read_rx.recv()).await {
            Ok(Some(response)) => {
                let resp_id = response.get("request_id").and_then(|id| id.as_u64());
                if resp_id == Some(request_id) {
                    return Ok(response);
                } else {
                    log::warn!(
                        "Discarding unmatched response (expected request_id {}, got {:?}): {:?}",
                        request_id,
                        resp_id,
                        response
                    );
                }
            }
            Ok(None) => return Err("Sidecar connection closed".into()),
            Err(_) => return Err("Timeout waiting for response from backend".into()),
        }
    }
    Err("Timeout waiting for response from backend".into())
}

#[tauri::command]
pub async fn anonymize(
    app: tauri::AppHandle,
    state: State<'_, AppState>,
    files: Vec<String>,
    options: Option<Value>,
) -> Result<Value, String> {
    let settings = get_settings(&app);
    let request = json!({
        "action": "anonymize",
        "files": files,
        "settings": settings,
        "options": options.unwrap_or_else(|| json!({}))
    });
    send_sidecar_request(state, request, Duration::from_secs(300)).await
}

#[tauri::command]
pub async fn detect_only(
    app: tauri::AppHandle,
    state: State<'_, AppState>,
    file_path: String,
    options: Option<Value>,
) -> Result<Value, String> {
    let settings = get_settings(&app);
    let request = json!({
        "action": "detect_only",
        "file": file_path,
        "settings": settings,
        "options": options.unwrap_or_else(|| json!({}))
    });
    send_sidecar_request(state, request, Duration::from_secs(300)).await
}

#[tauri::command]
pub async fn finalize_anonymization(
    app: tauri::AppHandle,
    state: State<'_, AppState>,
    original_file: String,
    detections_path: String,
    approved_indices: Vec<i32>,
    options: Option<Value>,
) -> Result<Value, String> {
    let settings = get_settings(&app);
    let is_image_pdf = options
        .as_ref()
        .and_then(|o| o.get("isImagePdf"))
        .and_then(|b| b.as_bool())
        .unwrap_or(false);
        
    let request = json!({
        "action": "finalize_anonymization",
        "originalFile": original_file,
        "detectionsPath": detections_path,
        "approvedIndices": approved_indices,
        "isImagePdf": is_image_pdf,
        "settings": settings
    });
    send_sidecar_request(state, request, Duration::from_secs(300)).await
}

#[tauri::command]
pub async fn check_pdf_type(
    state: State<'_, AppState>,
    path: String,
) -> Result<Value, String> {
    let request = json!({
        "action": "check_pdf_type",
        "files": vec![path]
    });
    let response = send_sidecar_request(state, request, Duration::from_secs(30)).await?;
    
    if let Some(results) = response.get("results").and_then(|r| r.as_array()) {
        if let Some(first) = results.first() {
            return Ok(first.clone());
        }
    }
    Err("Invalid response from PDF type checker".into())
}

#[tauri::command]
pub fn read_pdf_file(path: String) -> Result<tauri::ipc::Response, String> {
    std::fs::read(path)
        .map(|bytes| tauri::ipc::Response::new(bytes))
        .map_err(|e| e.to_string())
}

#[tauri::command]
pub fn delete_file(path: String) -> Result<bool, String> {
    match std::fs::remove_file(path) {
        Ok(_) => Ok(true),
        Err(e) => {
            log::error!("Failed to delete file: {}", e);
            Ok(false)
        }
    }
}

#[tauri::command]
pub fn load_detections(path: String) -> Result<Value, String> {
    let content = std::fs::read_to_string(path).map_err(|e| e.to_string())?;
    let detections_json: Value = serde_json::from_str(&content).map_err(|e| e.to_string())?;
    Ok(json!({
        "success": true,
        "detections": detections_json
    }))
}

#[tauri::command]
pub fn save_detections(path: String, detections: Value) -> Result<bool, String> {
    let file = std::fs::File::create(path).map_err(|e| e.to_string())?;
    serde_json::to_writer_pretty(file, &detections).map_err(|e| e.to_string())?;
    Ok(true)
}

#[tauri::command]
pub fn get_app_version(app: tauri::AppHandle) -> Result<String, String> {
    Ok(app.package_info().version.to_string())
}

#[tauri::command]
pub async fn apply_ocr(
    state: State<'_, AppState>,
    path: String,
    language: String,
) -> Result<Value, String> {
    let request = json!({
        "action": "apply_ocr",
        "file": path,
        "language": language
    });
    send_sidecar_request(state, request, Duration::from_secs(600)).await
}

#[tauri::command]
pub async fn restart_backend(
    app: tauri::AppHandle,
    state: State<'_, AppState>,
) -> Result<bool, String> {
    let mut controller_guard = state.controller.lock().await;
    
    // Kill the current child if it exists
    if let Some(controller) = controller_guard.take() {
        let _ = controller.child.kill();
        println!("Killed running backend sidecar process due to cancellation");
    }
    
    // Spawn a new sidecar process
    let new_controller = crate::spawn_sidecar(&app)?;
    *controller_guard = Some(new_controller);
    println!("Spawned new backend sidecar process");
    
    Ok(true)
}

#[tauri::command]
pub fn get_file_size(path: String) -> Result<u64, String> {
    let metadata = std::fs::metadata(&path).map_err(|e| e.to_string())?;
    Ok(metadata.len())
}

#[tauri::command]
pub async fn fetch_url_backend(
    state: State<'_, AppState>,
    url: String,
) -> Result<Value, String> {
    let request = json!({
        "action": "fetch_url",
        "url": url
    });
    send_sidecar_request(state, request, Duration::from_secs(30)).await
}
