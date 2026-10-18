# Native desktop builds

Proofpage 0.4 uses Tauri 2 for the application window. The existing Python engine, OCR models, PDF libraries and stdio MCP executable are bundled beside it. The web UI remains shared with source/CLI and hosted installations. No Rust commands, Python installation or terminal are needed by Mac end users.

## Build from source

Install a stable Rust toolchain and Python 3.13. On Linux, install Tauri's WebKitGTK 4.1 development prerequisites; Windows builds need the MSVC toolchain and WebView2. Then run:

```sh
python -m pip install -r desktop/requirements-build.txt
python scripts/build_desktop.py
python scripts/desktop_smoke.py
```

Linux CI runs the smoke test under `xvfb-run -a`. Native dependencies and all four runner targets are recorded in `.github/workflows/ci.yml`. Cargo.lock pins Rust dependencies. `scripts/build_desktop.py` packages the Tauri executable as Proofpage and the Python process as Proofpage-Engine, retaining Proofpage-MCP and its libraries. This packaging path is intentional; do not distribute a bare Cargo executable without its engine.

The window uses the authenticated loopback app with no Tauri command capabilities exposed to page JavaScript. External links open in the user's browser. The default local port is 8765. The engine holds the existing workspace lock and stops on the native parent's quit command or closed stdin. Normal window close and Quit wait for shutdown. A separate native webview profile stores appearance settings; browser preferences from the earlier launcher do not automatically migrate.

The default library remains `~/Proofpage/data`. No database relocation is performed. For isolated acceptance only, `PROOFPAGE_DESKTOP_HOME` and `PROOFPAGE_DESKTOP_PORT` override the workspace root and loopback port. The `--smoke-test REPORT` flow uses its own temporary workspace and reports after the actual webview finishes loading.

## Updates and signing

Settings → App updates explicitly contacts GitHub, compares stable versions, and offers only the expected asset URL for this platform. Updates require downloading and replacing the app; this release does not use Tauri's automatic updater plugin or claim unattended installation.

Mac release packaging signs every bundled executable/library plus the app, submits it to Apple, staples the ticket, checks Gatekeeper, and smoke-tests the final signed app. See [SIGNING.md](SIGNING.md). Windows builds remain unsigned. Linux requires WebKitGTK 4.1 at runtime; Windows requires Microsoft Edge WebView2.
