use std::process::Child;
use std::sync::Mutex;
use tauri::Manager;

pub struct BackendState {
    pub process: Mutex<Option<Child>>,
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .setup(|app| {
            if cfg!(debug_assertions) {
                app.handle().plugin(
                    tauri_plugin_log::Builder::default()
                        .level(log::LevelFilter::Info)
                        .build(),
                )?;
            }

            let child = std::process::Command::new("uv")
                .args(["run", "uvicorn", "backend.main:app", "--port", "8000"])
                .current_dir("../../")
                .spawn()
                .expect("Failed to spawn the Python ML backend");

            app.manage(BackendState {
                process: Mutex::new(Some(child)),
            });

            Ok(())
        })
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::Destroyed = event {
                if window.label() == "main" {
                    if let Ok(mut lock) = window.state::<BackendState>().process.lock() {
                        if let Some(mut child) = lock.take() {
                            let _ = child.kill();
                        }
                    }
                }
            }
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
