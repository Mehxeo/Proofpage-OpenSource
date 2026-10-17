<p align="center"><img src="docs/assets/banner.svg" alt="Proofpage — Evidence for your next model" width="100%"></p>

<p align="center">
<a href="https://github.com/Mehxeo/Proofpage-OpenSource/releases/tag/v0.1.1">Download</a> ·
<a href="#install-and-run">Install & run</a> ·
<a href="docs/CLI.md">CLI guide</a> ·
<a href="docs/TRAINING_AND_AGENTS.md">Training & agents</a> ·
<a href="CONTRIBUTING.md">Contribute</a>
</p>

Proofpage turns public web pages and your own exported files into **traceable evidence for AI**. Collect material, inspect the original source, review training examples, and export datasets—or let an existing AI assistant search your evidence through MCP.

**Free to run on your own computer. MIT licensed. No account, subscription, or model API key required for core features.** Works with Python 3.11+ on macOS, Windows, and Linux. This is an early release; signed desktop installers are not available yet.

![Proofpage training workspace](docs/training-workbench.png)

## What you can do

| Your goal | Proofpage gives you |
| --- | --- |
| Collect useful web content | Public page capture, bounded crawling, refresh schedules, and original evidence |
| Bring your own data | ZIP, CSV, JSON, JSONL, Markdown, text, and HTML imports; conversation-aware adapters |
| Prepare training data | Reviewed SFT examples, preference pairs, corrections, evaluations, grouped splits, and frozen exports |
| Give your existing AI sources | MCP tools, cited search results, exact quotes, revision IDs, and capture timestamps |
| Stay in control | Local SQLite storage, permission reviews, backups, and portable exports |

Proofpage **prepares data; it does not train a model**. Collection respects robots rules and does not bypass logins or access controls. Optional model-assisted drafting sends selected content only when you request it and still requires review. See [capabilities and limits](docs/IMPLEMENTATION_STATUS.md).

## Install and run

### 1. Install Python

Install [Python 3.11 or newer](https://www.python.org/downloads/). On Windows, enable **Add Python to PATH** if offered. On Linux, your distribution may also require its `python3-venv` package.

### 2. Download Proofpage

Download **proofpage-0.1.1-local.zip** from the [v0.1.1 release](https://github.com/Mehxeo/Proofpage-OpenSource/releases/tag/v0.1.1) and extract it. Open a terminal in the extracted folder. This bundle contains the installer and the Python wheel; you do not need Git.

**macOS / Linux**

```sh
python3 scripts/install.py
```

**Windows PowerShell**

```powershell
py -3 scripts/install.py
```

The installer creates a dedicated **Proofpage folder inside your user folder**, with an isolated runtime and launchers. It does not change your system Python. To choose a different folder, add `--directory "/path/to/Proofpage"`. Use a new folder; existing installations are never overwritten.

### 3. Open your workspace

Open **Start Proofpage.command** (macOS), **Start Proofpage.cmd** (Windows), or run `~/Proofpage/'Start Proofpage.command'` in a Linux terminal. On macOS you can also run the same terminal command if Finder does not open the launcher.

Your browser opens at **http://127.0.0.1:8765**. Keep the launcher's terminal open while using Proofpage; press **Ctrl+C** there to stop it. If the browser does not open automatically, visit that address manually.

```text
Proofpage/
├── Start Proofpage…   Launch the browser workspace
├── proofpage…         Use the command-line interface
├── data/              Your private evidence and settings
├── backups/           A place to save database backups
├── exports/           A place to save dataset downloads
└── runtime/           Isolated Python environment
```

Backups and exports are saved where you choose; these folders are provided for organization. Keep the installed folder in place because Python environments use absolute paths.

## Your first five minutes

1. Click **Add source**, enter a public page URL, then click **Collect** in Sources.
2. Open the record in **Library** to inspect its text, original evidence, and capture details.
3. Use **Training** to create draft examples, review source permissions, and approve suitable examples.
4. Freeze and export a training bundle. Use **Datasets** for the separate reviewed text-corpus workflow.
5. Open **Agent access** to connect an AI assistant to your local evidence.

For archives, choose **Import files**, create an account-specific profile, preview the file, and select what to keep. [Read the full workflow guide →](docs/TRAINING_AND_AGENTS.md)

## Prefer the terminal?

The same installation includes a CLI. On macOS/Linux:

```sh
~/Proofpage/proofpage --help
~/Proofpage/proofpage doctor
~/Proofpage/proofpage collect https://example.com
~/Proofpage/proofpage search "example"
~/Proofpage/proofpage serve --open
~/Proofpage/proofpage backup ~/Proofpage/backups/evidence.sqlite3
```

On Windows PowerShell, use `& "$HOME\Proofpage\proofpage.cmd"` followed by the same arguments. Collection and search return JSON for scripts. `doctor` checks Python and SQLite FTS5 support and shows the workspace path. [All CLI workflows →](docs/CLI.md)

<details>
<summary><strong>Install from source or use an existing Python environment</strong></summary>

```sh
git clone https://github.com/Mehxeo/Proofpage-OpenSource.git
cd Proofpage-OpenSource
python3 scripts/install.py
```

For development, create a virtual environment instead:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/proofpage --home .proofpage serve --open
```

On Windows, use `py -3` and `.venv\Scripts\python.exe` / `.venv\Scripts\proofpage.exe`. Installing from source may download build tools. The local release bundle installs its wheel without third-party runtime dependencies. Do not assume an unrelated package on PyPI is this project; use this repository's releases.

</details>

## Help, upgrades, and your data

- **Port already in use:** stop the existing server, or run `proofpage serve --port 8766 --open` using your installed launcher.
- **Python or SQLite error:** run `proofpage doctor`. Python must include SQLite FTS5. Install a supported Python distribution if it does not.
- **Upgrade:** make a backup, stop the old server, install the new release into a different folder, and restore the backup into a new workspace. See the [installation guide](docs/INSTALL.md) for exact commands.
- **Uninstall:** stop Proofpage, save any evidence or backups you want to keep, then remove its installation folder. Removing `data/` deletes that workspace's evidence.
- **Questions or bugs:** [open an issue](https://github.com/Mehxeo/Proofpage-OpenSource/issues). For sensitive reports, follow [Security](SECURITY.md).

## Open source

[MIT license](LICENSE) · [Contributing](CONTRIBUTING.md) · [Implementation status](docs/IMPLEMENTATION_STATUS.md) · [CI checks](https://github.com/Mehxeo/Proofpage-OpenSource/actions)

The repository also includes an optional [self-hosted edition](docs/HOSTING.md) with isolated accounts and billing integration. A managed paid service is **not live**. Local use remains free and independent of hosted accounts.
