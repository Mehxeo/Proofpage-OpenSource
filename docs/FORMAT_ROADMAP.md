# Evidence across formats

Proofpage is an evidence workspace for people and AI systems: research, archived sources, source checking, dataset preparation, and agent retrieval. Text is one representation, not the product boundary.

## Implemented

- Public web captures with original payloads, revision history, rights observations, receipts and archive exports.
- User-supplied structured files and conversations, reviewed dataset exports, and cited MCP retrieval.
- Companion 0.2.3 source preview: reviewed links, image references and alt text, and table text alongside page text. Optional categories are editable and off by default; no additional Chrome permissions. The initial store review is still for 0.2.2.

## Next format work

1. Actual image and PDF attachments: retain original bytes, MIME type, content hash, source URL and rights information; show a local preview and explicit storage limits. Never equate an image URL with an archived image.
2. Screenshot evidence: an explicit capture and redaction preview, with user-supplied attestation distinct from server captures.
3. OCR and document extraction: derived text linked to the exact original and extraction version; optional models, visible uncertainty, originals retained.
4. Audio/video: user-supplied media, time-coded transcripts and excerpts, with size limits and explicit consent before external processing.
5. Multimodal training bundles: references to hashed assets, caption/transcript provenance, per-asset rights review, and separate train/evaluation partitions.

These items are roadmap work, not shipped features. Binary downloads need network validation, size limits, safe local rendering and export checks before release. Format support must carry through import, inspection, search, agent retrieval and export—not end at the upload button.
