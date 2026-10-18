# Implementation status

This development branch extends the published v0.1.3 release with the Archival Ink redesign, Rights Radar, Time Machine, Proof Receipts and Claim Check. The existing v0.1.3 Mac downloads remain signed/notarized but do not include these new features. Hosted service launch and billing activation remain deferred.

## Implemented

- Public HTML/plain-text capture, bounded crawling, scheduling, supplied archive imports, preserved conversations, original responses and immutable revisions.
- A responsive light/dark evidence workspace, keyboard command palette, deep links, evidence drawer, onboarding, training review, dataset exports and copied MCP setup.
- Rights observations with source evidence, conservative export gates, drift notifications, dataset cards and draft reporting aids. Unknown signals do not mean permission. [Rights guide](RIGHTS.md).
- Timeline and revision comparisons, including changed numbers, broken links and publisher-rights changes. Optional model summaries require an explicit send.
- Signed, hash-chained capture receipts, optional digest anchoring, per-revision offline proof bundles and WACZ exports. [Proof guide](PROOF.md).
- Quote extraction and editable citation pairing; offline or explicitly authorized collection; exact/close/historical matching; durable progress, cooldowns, cancellation, annotated reports and Markdown/JSON/HTML exports. Optional model review remains unreviewed. [Claim Check](VERIFY.md).
- 27 MCP tools. Agents can search evidence and manage checks, but cannot approve training data or bypass review/export gates.
- Python-included desktop packaging and a bundled MCP helper. Smoke tests cover native startup, HTTP, quote-check routes, bundled verifier source, MCP tools and shutdown.
- Local access protections and optional hosted account isolation/scoped keys/quotas. Hosted anchoring remains disabled. Restoring backups pauses schedules, watches, crawls, quote checks and timestamp anchoring.

## Verification for this branch

- 108 local tests pass, including Unicode quote offsets, citation extraction, drift, blocked/unreachable outcomes, report escaping, explicit model review, durable jobs, cancellation, cooldowns and safe restore, plus the earlier rights/history/receipt/hosted/training checks.
- Receipt tests include RFC 8032 vectors and independent OpenSSL signature/timestamp interoperability. Cryptographic review is not claimed.
- A live example.com quote check in the browser matched a real passage, rejected an invented passage, and opened the captured revision and signed receipt. No paid model request was made.
- Desktop light and 375px mobile dark layouts were inspected; the mobile page had no horizontal document overflow. No browser console errors were observed in the tested flow.
- Python compilation, JavaScript syntax and wheel contents are checked. Packaged macOS startup and MCP smoke tests passed locally; CI runs native desktop checks on Mac ARM/Intel, Windows and Linux.
- ReplayWeb.page interoperability remains unverified: its file chooser did not open in the automated in-app browser. WACZ layout/digests and the offline verifier are tested, but that does not substitute for independent replay.

## Limits

Receipts attest this workspace's observation, not server non-repudiation, truth or a signer's real-world identity. Tail truncation requires a previously trusted head or external anchor to detect. The pure-Python signer is not constant-time. Keep backups private because they contain the signing key. No WACZ-Auth signatures or dataset-wide proof bundle; OpenTimestamps proofs need external upgrade/verification.

Quote matching is lexical and bounded, and citation pairing is heuristic. Model-generated reviews cannot establish truth. Reports describe the evidence searched, with capture dates and explicit unavailable states. See [matching limits](VERIFY.md#limits-and-privacy).

No authenticated source collector, CAPTCHA bypass, universal dynamic-site renderer, GPU training, live hosted service or Windows publisher signing is included. Rights observations and reporting aids do not certify legal compliance. Imported archives can contain private data; revocation cannot recall exports already shared.
