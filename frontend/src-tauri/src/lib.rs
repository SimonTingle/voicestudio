use std::net::TcpStream;
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use tauri::Manager;

pub struct BackendState {
    pub process: Mutex<Option<Child>>,
}

/// Returns true if something is already listening on 127.0.0.1:port
fn port_in_use(port: u16) -> bool {
    TcpStream::connect(("127.0.0.1", port)).is_ok()
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .setup(|app| {
            app.handle().plugin(tauri_plugin_dialog::init())?;
            if cfg!(debug_assertions) {
                app.handle().plugin(
                    tauri_plugin_log::Builder::default()
                        .level(log::LevelFilter::Info)
                        .build(),
                )?;
            }

            // Only spawn if the backend isn't already running (e.g. manual `uv run`)
            let skip_spawn = std::env::var("TAURI_SKIP_BACKEND").is_ok() || port_in_use(8000);
            let child = if skip_spawn {
                log::info!("Backend already running or skipped natively — skipping spawn");
                None
            } else {
                log::info!("Spawning Python ML backend on :8000");
                Some(
                    Command::new("uv")
                        .args(["run", "uvicorn", "backend.main:app", "--port", "8000"])
                        .current_dir("../../")
                        .stdout(Stdio::null())
                        .stderr(Stdio::null())
                        .spawn()
                        .expect("Failed to spawn the Python ML backend"),
                )
            };

            app.manage(BackendState {
                process: Mutex::new(child),
            });

            Ok(())
        })
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::Destroyed = event {
                if window.label() == "main" {
                    if let Ok(mut lock) = window.state::<BackendState>().process.lock() {
                        if let Some(mut child) = lock.take() {
                            log::info!("Terminating Python ML backend (pid {})", child.id());
                            let _ = child.kill();
                            let _ = child.wait(); // reap zombie
                        }
                    }
                }
            }
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
