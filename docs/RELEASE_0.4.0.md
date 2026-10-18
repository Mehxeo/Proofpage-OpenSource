# Proofpage 0.4.0 — native Tauri desktop

Proofpage now opens in its own native Tauri window, with the existing local evidence engine, offline image OCR, PDF extraction, original-file storage and MCP helper bundled inside. Python and a terminal are not required.

- Removed the Local workspace sidebar badge.
- App updates in Settings checks the latest stable GitHub release and offers the matching platform download. This is a guided download-and-replace flow, not automatic installation.
- Existing evidence stays in the same home-folder Proofpage/data directory. Quit the old app before opening this version; back up your workspace first.
- Closing the native window stops the engine after active work completes. Keep the app open for scheduled collection.
- External links open in the default browser; evidence stays in the native window. Downloaded files go to Downloads without overwriting existing files.

Mac releases are signed and notarized before publication. Windows packages remain unsigned and require Microsoft Edge WebView2. Linux requires WebKitGTK 4.1 and a graphical desktop (Ubuntu 22.04+ with libwebkit2gtk-4.1-0).

Chrome Web Store approval is separate from this desktop release. Local MCP works with compatible desktop/coding clients; it is not a ChatGPT web connector. Training workflows prepare reviewed datasets, not model weights.

## Migration and validation

Your existing evidence library is reused. Appearance preferences previously saved in an external browser are separate from the new native webview; choose them once in Settings.

Runtime commit: `9586cc3381f03d35901984815fdbb5ffa0a4bbdc`. Release CI run: `39145471884`. Source checks cover 132 Python tests plus preference and companion JavaScript checks. Native acceptance verified real Tauri rendering, the in-app update check, all 29 MCP tools, and a byte-for-byte SKILL.md download with collision-safe naming.

Packaged smoke tests load the native webview, verify the bundled MCP helper and perform image OCR and scanned-PDF extraction. All platform CI jobs passed. Both final signed Mac apps passed code-signature verification, ticket validation, Gatekeeper and packaged smoke tests (Intel final testing through Rosetta, plus native Intel CI).

- Apple silicon notarization: `45e0297a-c0ca-498f-b9c8-7bafd6098b73` — Accepted.
- Intel notarization: `8f01f1a2-1c10-460a-81c8-904c3852ccf7` — Accepted.
- Developer ID team: `44HHGAZ2C4`.

Final artifact hashes are in SHA256SUMS-0.4.0.txt.
