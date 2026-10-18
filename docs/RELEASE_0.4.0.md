# Proofpage 0.4.0 — native Tauri desktop

Proofpage now opens in its own native Tauri window, with the existing local evidence engine, offline image OCR, PDF extraction, original-file storage and MCP helper bundled inside. Python and a terminal are not required.

- Removed the Local workspace sidebar badge.
- App updates in Settings checks the latest stable GitHub release and offers the matching platform download. This is a guided download-and-replace flow, not automatic installation.
- Existing evidence stays in the same home-folder Proofpage/data directory. Quit the old app before opening this version; back up your workspace first.
- Closing the native window stops the engine after active work completes. Keep the app open for scheduled collection.
- External links open in the default browser; evidence stays in the native window. Downloaded files go to Downloads without overwriting existing files.

Mac releases are signed and notarized before publication. Windows packages remain unsigned and require Microsoft Edge WebView2. Linux requires WebKitGTK 4.1 and a graphical desktop (Ubuntu 22.04+ with libwebkit2gtk-4.1-0).

Chrome Web Store approval is separate from this desktop release. Local MCP works with compatible desktop/coding clients; it is not a ChatGPT web connector. Training workflows prepare reviewed datasets, not model weights.
