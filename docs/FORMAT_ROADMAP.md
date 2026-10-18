# Evidence across formats

Proofpage is an evidence workspace for people and AI systems: research, archived sources, source checking, dataset preparation, and agent retrieval. Text is one representation, not the product boundary.

## Available in 0.3

- Public HTML and plain-text captures with original payloads, revision history, rights observations, receipts, and archive exports.
- PNG, JPEG, WebP, and PDF originals, including ZIP imports, public URL collection, authenticated image previews/downloads, and per-file bundles.
- Local image OCR, selectable PDF text, and OCR for scanned PDF pages. Search and agents can retrieve this derived text. Extraction records page numbers, method, engine version, and original SHA-256.
- Hourly image/PDF URL collection and selected-file folder watches while the app runs.
- Companion page text, editable links/image references/tables, original file imports, and direct public-file URL saving. These newer controls are in the release companion; the initially submitted store package is 0.2.2.

See [Media and automation](MEDIA.md) for exact limits, including 8 MiB originals, 20 PDF pages, local OCR, and extraction failures. Imported files are user-supplied evidence; publicly fetched files also use capture receipts. Search text may contain extraction errors. Original bytes are never replaced by OCR output.

JSONL corpus exports do not embed original file bytes; use file bundles for originals. Files are base64-encoded in revision storage (about 33% overhead), not deduplicated across distinct records. PDF pages are rendered only inside the extraction worker, not embedded in the workspace browser.

## Next priorities

1. Batch asset selection and per-site asset rules with storage budgets, so users can deliberately archive a page's images without collecting every tracking pixel.
2. Page-region OCR review, confidence indicators, and improved reading order for tables and multi-column PDFs.
3. Multimodal training bundles: hashed assets alongside captions and extracted text, per-asset rights review, and train/evaluation split checks.
4. Screenshot capture with an explicit redaction preview and user-supplied attestation.
5. User-supplied audio/video with time-coded transcripts, bounded file sizes, and explicit consent before any external processing.

These next priorities are not shipped features. Measure completeness, exact-byte fidelity, citation resolution, OCR quality, duplicate behavior, latency, and storage on a published test corpus before claiming superiority over other scrapers.
