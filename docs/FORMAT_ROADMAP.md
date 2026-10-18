# Evidence across formats

Proofpage is an evidence workspace for people and AI systems: research, archived sources, source checking, dataset preparation, and agent retrieval. Text is one representation, not the product boundary.

## Implemented

- Public web captures with original payloads, revision history, rights observations, receipts and archive exports.
- User-supplied structured files and conversations, reviewed dataset exports, and cited MCP retrieval.
- Companion 0.2.3 source preview: reviewed links, image references and alt text, and table text alongside page text. Optional categories are editable and off by default; no additional Chrome permissions. The initial store review is still for 0.2.2.

## Original files implemented in the source build

PNG, JPEG, WebP and PDF originals can now be imported individually or inside ZIP archives. The app stores the exact bytes in its revision database, with SHA-256, filename, MIME type and size. Images have authenticated local previews; PDFs download to a separate reader. Original downloads and per-file ZIP bundles include byte integrity checks. Database backups carry the originals. This is user-supplied evidence, not a server-signed receipt.

The next companion (0.2.4 source) also lets you select a downloaded image/PDF and send its original bytes to the paired app. No new Chrome permissions. The installed 0.2.2 app does not implement this new endpoint; use the current source app until a new desktop release is packaged.

Limits: 8 MiB per upload, basic file-signature checks rather than malware scanning, no OCR/PDF text extraction, no automatic remote image download, and no multimodal training bundle yet. PDF rendering is deliberately outside the workspace. File metadata may contain private information. Search currently indexes file metadata, not image or PDF contents. JSONL corpus exports do not embed original file bytes; use the file bundle for originals. Binary files are base64-encoded in revision storage (about 33% overhead), not yet deduplicated across distinct records.

## Next format work

1. Expand original image/PDF support: retain original bytes, MIME type, content hash, source URL and rights information; show a local preview and explicit storage limits. Never equate an image URL with an archived image.
2. Screenshot evidence: an explicit capture and redaction preview, with user-supplied attestation distinct from server captures.
3. OCR and document extraction: derived text linked to the exact original and extraction version; optional models, visible uncertainty, originals retained.
4. Audio/video: user-supplied media, time-coded transcripts and excerpts, with size limits and explicit consent before external processing.
5. Multimodal training bundles: references to hashed assets, caption/transcript provenance, per-asset rights review, and separate train/evaluation partitions.

These items are roadmap work, not shipped features. Binary downloads need network validation, size limits, safe local rendering and export checks before release. Format support must carry through import, inspection, search, agent retrieval and export—not end at the upload button.
