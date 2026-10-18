# Proofpage 0.5.0 — business context and reproducible evidence

[Download 0.5.0](https://github.com/Mehxeo/Proofpage-OpenSource/releases/tag/v0.5.0) · [Installation help](https://proofpage.app/docs/#start)

This release adds reviewed business profiles, recorded agent inputs, offline replay, output dependencies, Python and Node SDKs, an evidence-check GitHub Action, installable client skills, and optional Google Docs connection support. All remain MIT licensed. The native Tauri downloads include the Python engine, local OCR, PDF extraction, Google OAuth libraries, and OS-vault integration.

Business profiles keep your own material, customer content, references, and writing examples separate. Approve individual source passages before exporting context. Changed revisions make the earlier context stale and require another review. Recorded agent runs preserve the exact supplied excerpts and identify outputs that need review after their inputs change; they do not promise identical model answers or prove which passages a model used.

Local MCP exposes 36 tools. The optional remote MCP resource server is self-hostable and read-only, with OAuth token validation; it requires a compatible authorization provider and your own HTTPS host. No paid or public hosted MCP service is activated by this release. See [developer workflows](DEVELOPER_WORKFLOW.md), [business context](BUSINESS_CONTEXT.md), and [connector setup](CONNECTORS.md).

Google Docs authorization is read-only and tokens stay in the operating system credential vault. Only explicitly selected document IDs are fetched, after owner-permission confirmation. The shared Google project is still in Testing; public users must configure their own Desktop OAuth client. Google API snapshots are limited to personal context and are rejected by this release's training workflow. Training exports for other eligible material prepare datasets; they do not train weights or change ChatGPT/Claude account memory.

## Updating

Back up your private `Proofpage/data` folder, quit the old app, then replace its application files. The existing library stays in your user folder. Settings → App updates checks GitHub and offers the matching platform download; installation remains a download-and-replace flow. Keep the app open for scheduled work. Google tokens are stored separately and are not included in database backups.

Both Mac downloads are Developer ID signed, Apple-notarized, and stapled. A normal first-open download confirmation may still appear. Windows remains unsigned and requires Edge WebView2. Linux requires WebKitGTK 4.1 and a graphical desktop.

## Release verification

- Application and release-tag commit: `d9f4753853d0810f40c328d9c95f9ab688067ea5`.
- [Release CI run 39168109639](https://github.com/Mehxeo/Proofpage-OpenSource/actions/runs/39168109639): all 10 jobs passed, including Python 3.11/3.13, container, source-install, and all four desktop builds. The source suite contains 162 Python tests, plus companion/preferences JavaScript, Node-to-Python integration, and the offline evidence regression example.
- Official MCP client tests exercise real stdio initialization, tool discovery, recorded context, offline replay, business context, and stale-context errors. HTTP tests exercise discovery, authorization challenges, valid signed tokens, and rejected tokens/origins; they are local integration tests, not a live hosted deployment.
- Both final signed Mac apps passed native startup, bundled Google OAuth and keyring imports, SQLite/HTTP/shutdown, the bundled MCP helper, image OCR, and scanned-PDF extraction. Intel also passed native Intel CI; the final signed Intel app was checked locally through Rosetta.
- Apple silicon notarization: `7d2e1702-4b96-45e6-a6d3-4dcbcac93e72` — Accepted.
- Intel notarization: `bdde4461-ead3-4193-be5e-5ce78851006e` — Accepted.
- Developer ID team: `44HHGAZ2C4`.
- All six release artifacts were downloaded anonymously and matched [SHA256SUMS-0.5.0.txt](https://github.com/Mehxeo/Proofpage-OpenSource/releases/download/v0.5.0/SHA256SUMS-0.5.0.txt). Both public Mac ZIPs were re-extracted and passed signature, ticket, and Gatekeeper checks.
- The actual 0.4.0 updater detected live 0.5.0 and returned the correct Apple silicon download. The 0.5.0 updater reported itself current.
- A new WACZ from a bare-host URL rendered in Chrome using the official ReplayWeb.page 2.5.3 viewer. The fix normalizes archive replay URLs while preserving signed receipts. This covers saved page replay, not uncaptured third-party assets or arbitrary interactive websites.
- Production `proofpage.app`, its docs, privacy pages, images, video, and companion download were checked across 17 routes against the deployed source bytes. Its four desktop download links target 0.5.0. Production deployment: `dpl_6aM3uoeL59jQVbD5JwtfFiFMir1c`.

No private Google document content was used for release tests. Examples and UI acceptance used synthetic business material.
