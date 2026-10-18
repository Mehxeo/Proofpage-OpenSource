#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]
use std::{io::{BufRead, BufReader, Write}, process::{Child, Command, Stdio}, sync::{Arc, Mutex}, time::Duration};
use tauri::{WebviewUrl, WebviewWindowBuilder};

fn external(url: &tauri::Url) {
    if matches!(url.scheme(), "https" | "http" | "mailto") { let _ = open::that(url.as_str()); }
}

fn main() {
    let child_slot: Arc<Mutex<Option<Child>>> = Arc::new(Mutex::new(None));
    let setup_slot = child_slot.clone();
    let app = tauri::Builder::default().setup(move |app| {
        let args: Vec<String> = std::env::args().collect();
        let smoke = args.len() == 3 && args[1] == "--smoke-test";
        let engine = std::env::current_exe()?.parent().unwrap().join(if cfg!(windows) { "Proofpage-Engine.exe" } else { "Proofpage-Engine" });
        let mut command = Command::new(engine);
        command.stdin(Stdio::piped()).stdout(Stdio::piped()).stderr(Stdio::null());
        if smoke { command.args(["--smoke-test", &args[2]]); }
        #[cfg(windows)] { use std::os::windows::process::CommandExt; command.creation_flags(0x08000000); }
        let mut child = command.spawn()?;
        let stdout = child.stdout.take().unwrap();
        *setup_slot.lock().unwrap() = Some(child);
        let (tx, rx) = std::sync::mpsc::channel();
        let handle = app.handle().clone();
        std::thread::spawn(move || {
            for line in BufReader::new(stdout).lines().map_while(Result::ok) {
                if line.starts_with("PROOFPAGE_READY ") { let _ = tx.send(line[16..].to_string()); }
                if line == "PROOFPAGE_SMOKE_OK" { handle.exit(0); }
            }
        });
        let address = match rx.recv_timeout(Duration::from_secs(45)) {
            Ok(address) => address,
            Err(_) => {
                if let Some(child) = setup_slot.lock().unwrap().as_mut() { let _ = child.kill(); }
                WebviewWindowBuilder::new(app, "startup-error", WebviewUrl::App("index.html".into()))
                    .title("Proofpage — unable to start").inner_size(620.0, 360.0)
                    .initialization_script("document.addEventListener('DOMContentLoaded',()=>document.getElementById('status').textContent='Could not start the local engine. Close any other running copy of Proofpage, then reopen this app.');")
                    .build()?;
                return Ok(());
            }
        };
        let url: tauri::Url = address.parse()?;
        if url.scheme() != "http" || url.host_str() != Some("127.0.0.1") { return Err("Invalid local engine address".into()); }
        let origin = url.origin();
        let load_slot = setup_slot.clone();
        let window = WebviewWindowBuilder::new(app, "main", WebviewUrl::External(url))
            .title("Proofpage").inner_size(1280.0, 850.0).min_inner_size(760.0, 540.0)
            .on_navigation(move |target| { if target.origin() == origin || target.scheme() == "blob" { true } else { external(target); false } })
            .on_download(|webview, event| {
                match event {
                    tauri::webview::DownloadEvent::Requested { destination, .. } => {
                        if destination.exists() {
                            let original = destination.clone();
                            let stem = original.file_stem().unwrap_or_default().to_string_lossy();
                            let ext = original.extension().map(|x| format!(".{}", x.to_string_lossy())).unwrap_or_default();
                            for number in 1..10000 {
                                let candidate = original.with_file_name(format!("{stem} ({number}){ext}"));
                                if !candidate.exists() { *destination = candidate; break; }
                            }
                            if destination.exists() { return false; }
                        }
                    }
                    tauri::webview::DownloadEvent::Finished { success, .. } => {
                        let text = if success { "File saved to your Downloads folder." } else { "Download failed. Please try again." };
                        let _ = webview.eval(&format!("if(typeof notice==='function') notice({});", serde_json::to_string(text).unwrap()));
                    }
                    _ => {}
                }
                true
            })
            .on_new_window(|url, _| { external(&url); tauri::webview::NewWindowResponse::Deny })
            .on_page_load(move |_, payload| {
                if smoke && payload.event() == tauri::webview::PageLoadEvent::Finished {
                    if let Some(child) = load_slot.lock().unwrap().as_mut() {
                        if let Some(stdin) = child.stdin.as_mut() { let _ = stdin.write_all(b"smoke\n"); }
                    }
                }
            }).build()?;
        let close_slot = setup_slot.clone();
        let handle = app.handle().clone();
        window.on_window_event(move |event| {
            if let tauri::WindowEvent::CloseRequested { api, .. } = event {
                api.prevent_close();
                let slot = close_slot.clone(); let handle = handle.clone();
                std::thread::spawn(move || {
                    let mut guard = slot.lock().unwrap();
                    if let Some(child) = guard.as_mut() {
                        if let Some(stdin) = child.stdin.as_mut() { let _ = stdin.write_all(b"quit\n"); }
                        let _ = child.wait();
                    }
                    handle.exit(0);
                });
            }
        });
        Ok(())
    }).build(tauri::generate_context!());
    match app {
        Ok(app) => app.run(move |handle, event| {
            if let tauri::RunEvent::ExitRequested { code, api, .. } = &event {
                if code.is_none() {
                    api.prevent_exit();
                    let slot = child_slot.clone(); let handle = handle.clone();
                    std::thread::spawn(move || {
                        if let Some(child) = slot.lock().unwrap().as_mut() {
                            if let Some(stdin) = child.stdin.as_mut() { let _ = stdin.write_all(b"quit\n"); }
                            let _ = child.wait();
                        }
                        handle.exit(0);
                    });
                }
            }
            if let tauri::RunEvent::Exit = event {
                if let Some(child) = child_slot.lock().unwrap().as_mut() { let _ = child.kill(); let _ = child.wait(); }
            }
        }),
        Err(error) => {
            if let Some(child) = child_slot.lock().unwrap().as_mut() { let _ = child.kill(); }
            eprintln!("Proofpage could not start: {error}");
            std::process::exit(1);
        }
    }
}
