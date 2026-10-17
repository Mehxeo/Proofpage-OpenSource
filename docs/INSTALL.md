# Installing and maintaining Proofpage

For the no-Python desktop app, download the platform archive, extract it, and open Proofpage. Updates replace application files while preserving `~/Proofpage/data`. The desktop previews are unsigned. The instructions below are for the optional Python/CLI installation.

Follow the [quick start](../README.md#install-and-run) for a new installation. The local ZIP bundles a wheel and `scripts/install.py`. Python 3.11+ with SQLite FTS5 and venv is required. Download checksums from the same release and verify the ZIP with `shasum -a 256` (macOS), `sha256sum` (Linux), or `Get-FileHash -Algorithm SHA256` (PowerShell).

## Upgrade without overwriting your evidence

The installer deliberately refuses existing folders. First back up the old workspace:

```sh
~/Proofpage/proofpage backup ~/Proofpage/backups/before-upgrade.sqlite3
```

Stop its server with Ctrl+C. From the newly extracted release, install beside it and restore to a new path:

```sh
python3 scripts/install.py --directory ~/Proofpage-New
~/Proofpage-New/proofpage restore ~/Proofpage/backups/before-upgrade.sqlite3 ~/Proofpage-Restored
~/Proofpage-New/runtime/bin/proofpage --home ~/Proofpage-Restored serve --open
```

The new launcher's default still points to `Proofpage-New/data`; use the explicit `--home` command above for the restored workspace. Restores pause schedules and watched folders; review them before re-enabling them. Keep the old install until you have checked your evidence and exports.

PowerShell equivalents:

```powershell
& "$HOME\Proofpage\proofpage.cmd" backup "$HOME\Proofpage\backups\before-upgrade.sqlite3"
# Stop the old server before continuing.
py -3 scripts/install.py --directory "$HOME\Proofpage-New"
& "$HOME\Proofpage-New\proofpage.cmd" restore "$HOME\Proofpage\backups\before-upgrade.sqlite3" "$HOME\Proofpage-Restored"
& "$HOME\Proofpage-New\runtime\Scripts\proofpage.exe" --home "$HOME\Proofpage-Restored" serve --open
```

## Manual wheel installation

Create and activate a Python virtual environment, then install the wheel from this repository's release:

```sh
python -m pip install /path/to/proofpage-0.1.2-py3-none-any.whl
proofpage doctor
proofpage serve --open
```

Without `--home` or `PROOFPAGE_HOME`, the CLI uses `~/.proofpage`. The guided installer uses its own `data/` folder instead. Use the same workspace path for your browser, CLI, and MCP client.

## Troubleshooting

- Missing `venv` or `ensurepip`: install your Linux distribution's Python venv package, then retry into a new folder.
- Incomplete installation: preserve any data you added; remove only the incomplete install or choose a fresh `--directory`.
- Port busy: stop the old process or use `serve --port 8766 --open`.
- No browser: open the URL printed in the terminal manually.
- Collection blocked: inspect the recorded result. Robots rules, inaccessible pages, cooldowns, and unsupported content are reported rather than bypassed.

CLI installation requires Python. Separate desktop archives bundle Python and a graphical launcher. CI launches the packaged GUI and checks its local API on macOS, Windows, and Linux; this does not verify Gatekeeper or SmartScreen acceptance on an end-user computer.
