# Proofpage: a practical route to a stronger evidence scraper

Research checked October 18, 2026. “Best” needs a measured use case; we should not claim competitors cannot do a feature without testing them.

## Where others already compete

[Firecrawl's official capabilities](https://github.com/firecrawl/firecrawl-docs/blob/main/capabilities.mdx) include document parsing; its [scrape guide](https://github.com/firecrawl/firecrawl-docs/blob/main/v1/advanced-scraping-guide.mdx) documents HTML, structured output and screenshots. [Crawl4AI](https://docs.crawl4ai.com/core/crawler-result/) exposes HTML, media information, screenshots, PDFs and MHTML; its [PDF strategy](https://docs.crawl4ai.com/advanced/pdf-parsing/) extracts document text and optionally images. Format count alone is not a differentiator.

## Product promise

Save the source, see what changed, check what an answer used, and export evidence another person can inspect. Support local research, AI assistants, archival work and model training without forcing everyone into a training workflow.

## Priorities and acceptance criteria

1. **Reliable original-file capture (started).** Current source preserves supplied PNG/JPEG/WebP/PDF bytes, hashes, revisions, downloads and per-file bundles. Next: user-selected public asset downloads through the existing network checks, redirect/DNS validation, budgets and size limits. Record source page and asset URL separately; never copy browser passwords/cookies to a server. Acceptance: exact-byte round trips, authenticated download, expired-access rejection, corrupt-file errors, and clear partial outcomes.
2. **Linked representations.** Attach source pages, files, screenshots, extracted text and captions to one evidence record. Each derived representation records its original hash, extractor/model version and confidence. OCR remains optional and local-first. Acceptance: every quote or region resolves to the exact original revision; no inferred text is labeled original.
3. **Change-aware collection.** Content-addressed file storage, conditional requests and per-origin budgets; compare actual content rather than timestamps. Image/PDF changes should create revision events. Acceptance: unchanged originals do not redownload unnecessarily; failed refreshes preserve prior evidence.
4. **Evidence-aware agents.** MCP tools return bounded excerpts, asset descriptors, page/region references and explicit unsupported/blocked outcomes. A user chooses when originals go to a vision model. Acceptance: no base64 megabytes accidentally inserted into a text context; model citations can be checked offline.
5. **Auditable multimodal datasets.** Package reviewed assets with rights decisions, redaction history, content hashes, caption/transcript provenance and grouped train/test splits. Acceptance: revoked permission blocks managed exports, split leakage checks pass, and another machine can verify every packaged asset.
6. **Easy collection, honest coverage.** One-time pairing, sensible presets, resumable jobs, understandable progress and a downloadable error report. Authentication/challenge handoffs preserve the user's browser session. Acceptance: a new user can install, save a page and a PDF, inspect their originals and export them without a terminal.

## Benchmark before claiming superiority

Maintain a public, licensed fixture set covering static pages, dynamic content, tables, paginated pages, PDFs, images, redirect chains, content changes and access failures. Measure capture completeness, extraction fidelity, original-byte equality, source/citation resolution, duplicate rate, peak RAM, bytes transferred and time to first usable result. Report failures and version/configuration alongside results. Compare equivalent permissions and budgets. The advantage to prove is trustworthy evidence with less manual repair—not an unqualified promise to scrape every website.
