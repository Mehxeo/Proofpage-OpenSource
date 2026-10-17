# Proofpage

[Source](https://github.com/Mehxeo/Proofpage-OpenSource) · [Releases](https://github.com/Mehxeo/Proofpage-OpenSource/releases) · [CI](https://github.com/Mehxeo/Proofpage-OpenSource/actions)

Collect public web evidence and supplied archives, prepare reviewed training datasets, and give existing AI assistants cited evidence through MCP.

Proofpage is MIT-licensed open-source software. Run it on your computer without an account, or operate the included hosted edition with isolated accounts and Stripe subscriptions. See [hosting and billing setup](docs/HOSTING.md).

The local training-and-agent MVP is implemented. Start with the browser workspace, then follow the [training and agent guide](docs/TRAINING_AND_AGENTS.md). See [verified scope and limits](docs/IMPLEMENTATION_STATUS.md) before deploying or relying on a collection result.

## Run

Clone `https://github.com/Mehxeo/Proofpage-OpenSource.git` and enter the checkout, or install the wheel from Releases with `python3 -m pip install /path/to/proofpage-0.1.0-py3-none-any.whl`. Verify downloaded artifacts against the release’s `SHA256SUMS`.

Python 3.11 or newer, with SQLite FTS5 enabled. No third-party runtime dependencies for the local browser application.

```sh
python3 -m proofpage --home .proofpage serve
```

Open http://127.0.0.1:8765. Data stays in the selected directory. Use one server per data directory. Schedules run while the server is open.

For the native desktop client, run `python3 -m proofpage --home .proofpage desktop`. It requires Python's Tkinter module and provides collection, import selection, search, evidence inspection, review, and corpus export. The browser interface additionally exposes schedule controls, activity history, and frozen dataset history. Signed desktop installers are not yet available.

1. Add a public page under Sources and click Collect.
2. Search the Library, then open a record to inspect text, raw evidence, timestamps, coverage, and hashes.
3. Create an account-specific import profile, then import a file or ZIP, preview its entries, and select categories explicitly.
4. Review record revisions and confirm dataset permission. Freeze a clean corpus under Datasets.
5. Export JSONL. Revoking permission blocks future managed exports containing that revision; it cannot recall copies already downloaded.

## CLI

```sh
python3 -m proofpage --home .proofpage collect https://example.com
python3 -m proofpage --home .proofpage search documentation
python3 -m proofpage --home .proofpage profile "Personal LinkedIn" --provider LinkedIn --account personal --adapter linkedin
python3 -m proofpage --home .proofpage import export.zip
python3 -m proofpage --home .proofpage import export.zip --select Messages.csv --profile PROFILE_ID
```

The first import command previews categories; the second imports only selected entries. Use the ID returned by `profile` for `PROFILE_ID`. Reuse a profile for successive archives from the same account, even when the ZIP filename changes. Different accounts use different profiles. Stable supplied IDs create revisions when records change; rows without IDs are deduplicated by content and become separate records when changed. Markdown, text, and HTML documents use their category filename as stable identity.

Adapters are tested with synthetic fixtures: ChatGPT-style mappings preserve nodes, parents, children, roles, tool metadata, and the selected node; Claude-style `chat_messages` preserve supplied roles, content, and attachment references; LinkedIn message CSVs preserve human participants. These are local export adapters, not live account connections. Actual provider variations may require additional fixtures. A saved mapping can name source fields for text, ID, title, role, and timestamp without relabeling human speakers as AI assistants.

## Automatic archive ingestion

In Sources, choose **Watch an export folder**, an existing profile, the local folder, and exact category filenames. Existing files and future arrivals are eligible. The server polls only that folder, waits for files to settle, and records outcomes persistently. It excludes symlinks and subfolders, bounds file counts and sizes, and isolates failed files. It never requests exports from the provider. Pause/resume and file outcomes are available in Sources. A file already in progress can finish after pause.

```sh
python3 -m proofpage --home .proofpage watch /absolute/path/to/exports --profile PROFILE_ID --category Messages.csv --category Connections.csv
python3 -m proofpage --home .proofpage scan WATCH_ID
```

`serve` drives continuous watches and schedules. `scan` performs one scan; a new file settles on a subsequent scan at least two seconds later. Failed files are retried after their size or modification time changes. Missing configured ZIP categories are reported. The native client imports using the same profiles; continuous watching is provided by the server.

## Backups and corpus validation

```sh
python3 -m proofpage --home .proofpage backup /absolute/path/to/new-backup.sqlite3
python3 -m proofpage restore /absolute/path/to/new-backup.sqlite3 /absolute/path/to/new-workspace
python3 -m proofpage validate-dataset /absolute/path/to/corpus.jsonl --sha256 FROZEN_HASH
```

Backups use SQLite's consistent backup API and verify integrity. Existing files and workspaces are never overwritten. Restores pause schedules and folder watches. Backups contain local evidence and should be handled as private data. The reference loader in `proofpage/datasets.py` checks required fields, checksums, exact duplicates, and source-grouped split consistency; it does not train a model.

## Agent access

Launch the stdio server from this checkout:

```sh
python3 -m proofpage --home .proofpage mcp
```

Example client configuration (replace paths with your checkout and Python interpreter):

```json
{
  "mcpServers": {
    "proofpage": {
      "command": "python3",
      "args": ["-m", "proofpage", "--home", "/absolute/path/to/data", "mcp"],
      "cwd": "/absolute/path/to/Proofpage OpenSource"
    }
  }
}
```

Eighteen tools expose source access, configured collection, run status, cited context, freshness, bounded crawling, extraction submissions, draft examples, and revision history. Returned source material is untrusted data, never agent instructions. MCP can collect only an existing source. Initialization and newline-delimited stdio follow the [MCP lifecycle](https://modelcontextprotocol.io/specification/2025-06-18/basic/lifecycle) and [transport specification](https://modelcontextprotocol.io/specification/2025-06-18/basic/transports).

The browser API is bound to loopback and checks Host, Origin, and a session token. Obtain the token with `GET /api/session`, then send `Authorization: Bearer <token>`. Routes are implemented in `proofpage/server.py`; this is a local application, not an internet-facing service.

## Verification

```sh
python3 -m unittest discover -s tests -v
python3 -m compileall -q proofpage
node --check proofpage/static/app.js
```

The tests use isolated temporary databases and deterministic responses. Live website behavior must be verified separately. Hosted model compatibility is tested with a local HTTP fixture, not a paid provider. Restricted/authenticated collection and actual model training jobs are outside this release. Optional offline rendering has a Chromium smoke check.

## Open source and hosted service

The [MIT license](LICENSE) covers both editions. See [Contributing](CONTRIBUTING.md), [Security](SECURITY.md), and [self-hosting/paid-service setup](docs/HOSTING.md). Hosted mode adds invitation-based accounts, recovery, scoped agent keys, usage limits, customer billing, and portable workspace downloads. No price or live payment configuration is assumed.
