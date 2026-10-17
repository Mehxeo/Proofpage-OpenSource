# Proofpage implementation status

Updated October 17, 2026. The focused local MVP covers collection → evidence → reviewed training bundles, plus tool access for existing AI assistants. The originally referenced full specification/80-point acceptance document was not supplied; this is not a claim that every broader milestone or provider integration is complete.

## Open-source and hosted edition

Both editions now carry the MIT license, with contribution/security documentation, an initialized local Git repository, CI, source and wheel distributions, and Docker Compose/TLS deployment files. Hosted mode adds per-account SQLite isolation, invitation signup, scrypt passwords, recovery codes, secure sessions/CSRF checks, expiring scoped agent keys, transactional quotas, shared destination budgets, scheduled collection, portable database downloads, and audit events. Stripe Checkout, Customer Portal, signed/idempotent webhooks, and authoritative subscription reconciliation are implemented behind configuration. No price is invented and no live account is charged.

Current full suite: **55 tests pass**, including account isolation, key scopes/revocation, recovery, request boundaries, storage exhaustion, scheduler quotas, portable restore, real Stripe SDK signature parsing, checkout retry idempotency, and out-of-order/canceled billing state. Browser sign-in and hosted account controls were checked with a labeled synthetic account. The container was not run because Docker daemon access is unavailable. No public repository, cloud deployment, live Stripe configuration, or real sandbox settlement is claimed. See [hosting instructions](HOSTING.md).

## Implemented

- Public HTML/plain-text collection, bounded same-origin/path crawling, feed/sitemap discovery, durable page checkpoints, cancellation, schedules, truthful access outcomes, robots rules, public-address pinning, shared cooldowns and daily budgets.
- Optional isolated offline Chromium rendering of captured inline JavaScript. Network-dependent resources are blocked and reported. Original HTML is preserved.
- Supplied archives, account-specific profiles, selective ZIP imports, preserved ChatGPT branches/roles and Claude/LinkedIn structures, saved field mappings, settled-file folder watches, receipts, and pause/restart recovery.
- Immutable source revisions, original evidence, capture/source timestamps, SQLite lexical search, cited context chunks, and explicit source freshness checks.
- Browser training workbench: SFT, preference pairs, corrections, evaluations, and observed tool traces; actual conversation branch selection; explicit human-message role mapping; exact source quotes; immutable draft revisions; review and revocation.
- Heuristic credential/PII screening and draft redaction. Credentials block approval until redacted; warnings require acknowledgment. Original evidence is not changed.
- Frozen, reproducible ZIP bundles with trainer JSONL, source manifests, exact deduplication, near-duplicate/source-group partitions, checksums, and standalone validation. Source or example revocation blocks future exports.
- Optional local/hosted OpenAI-compatible model drafting and schema-defined extraction. Transmission requires an explicit action; model output remains unreviewed. No model is downloaded automatically.
- Eighteen stdio MCP tools for source access, collection, retrieval, freshness, crawl management, extraction, and draft submission. No approval/export tools. Observed tool events can be preserved without inventing reasoning.
- Local HTTP session/origin/host protection, CLI, basic native Tk client, additive migrations, backup/restore with automation paused, and installable Python wheel. New training/agent workbench features are in the browser UI.

## Verification

- The original 41 local workflow tests cover: prior collection/import/watch/archive/backup checks plus training grounding, review gates, redaction, immutable edits, warning acknowledgment, duplicate/source grouping, bundle reproducibility/tamper detection, revocation, exact context offsets, observed traces, extraction schema/quotes, local model HTTP round trip, crawl scope/restart/cancellation, and render-failure reporting.
- HTTP integration exercises import → draft → permission → approval → freeze → ZIP download → revoke → denied export, alongside existing corpus/session protection checks.
- A real stdio MCP subprocess performs initialization and tool calls. `examples/agent_client.py` provides an executable cited-context client.
- Chromium smoke check executes inline JavaScript and confirms an attempted network request is blocked. Optional dependencies were installed in `.venv` on this Mac.
- Browser UI verification selects a synthetic source conversation branch, inspects its user/assistant-only draft, explicitly approves it, and freezes a bundle. Synthetic data is labeled. Earlier live collection verified example.com and folder import receipts.
- Python compilation, both JavaScript syntax checks, and wheel packaging pass. This is local macOS verification, not a signed or cross-platform release.

## Practical limits

No authenticated/OAuth source collector, LinkedIn website collector, CAPTCHA bypass, signed installer, live public deployment, or GPU training service is included. Import adapters have synthetic fixture coverage, not universal provider-export compatibility. Dynamic sites requiring external JavaScript/API requests remain incomplete. Crawl limits and unresolved pages are reported rather than hidden. Wall classification and privacy screening are heuristic.

SFT/preference/correction bundles use trainer-friendly shapes; observed traces and evaluation rows need the receiving trainer/evaluator's adapter. Independent dataset exports do not share a global split registry; check overlap before combining them. Model suggestions and matched quotes still require factual review. Hosted/local LLM behavior was tested through a protocol fixture, not a real inference model. No paid model calls or actual model-training runs were performed.

Source permission is user-confirmed, not independently adjudicated. Revocation cannot recall downloaded copies. Original archives may contain private data. Watches and crawl scheduling run only while the server is running; an in-flight action may finish after pause/cancel. Restore cancels queued crawls and pauses schedules/watches. See [workflow and setup](TRAINING_AND_AGENTS.md).
