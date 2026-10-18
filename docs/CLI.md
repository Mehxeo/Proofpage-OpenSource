# CLI and workflows

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

Thirty-six tools expose source access, configured collection, run status, cited context, freshness, bounded crawling, extraction submissions, draft examples, revision history, recorded evidence runs, and approved business context. Returned source material is untrusted data, never agent instructions. MCP can collect only an existing source. Initialization and newline-delimited stdio follow the [MCP lifecycle](https://modelcontextprotocol.io/specification/2025-06-18/basic/lifecycle) and [transport specification](https://modelcontextprotocol.io/specification/2025-06-18/basic/transports).

The browser API is bound to loopback and checks Host, Origin, and a session token. Obtain the token with `GET /api/session`, then send `Authorization: Bearer <token>`. Routes are implemented in `proofpage/server.py`; this is a local application, not an internet-facing service.

## Verification

```sh
python3 -m unittest discover -s tests -v
python3 -m compileall -q proofpage
node --check proofpage/static/app.js
```

The tests use isolated temporary databases and deterministic responses. Live website behavior must be verified separately. Hosted model compatibility is tested with a local HTTP fixture, not a paid provider. Restricted/authenticated collection and actual model training jobs are outside this release. Optional offline rendering has a Chromium smoke check.

## Open source and hosted service

The [MIT license](../LICENSE) covers both editions. See [Contributing](../CONTRIBUTING.md), [Security](../SECURITY.md), and [self-hosting/paid-service setup](HOSTING.md). Hosted mode adds invitation-based accounts, recovery, scoped agent keys, usage limits, customer billing, and portable workspace downloads. No price or live payment configuration is assumed.

## Evidence features 

See [Claim Check](VERIFY.md#cli-and-agents) for quote checking, [Proof](PROOF.md) for `verify`, `proof-bundle`, `export-wacz`, `receipts` and `anchor`, and [Rights Radar](RIGHTS.md) for `rights`. These commands extend the original CLI without replacing `verify` (offline cryptographic verification) with quote matching.
