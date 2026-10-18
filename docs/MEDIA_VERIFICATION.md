# Original-file and Chrome verification — October 18, 2026

The installed unpacked companion loaded changed popup files when reopened; no extension-manager automation or reload was used. Chrome still had the previous manifest registration, so these checks verify the current popup behavior, not a fresh store installation of the new manifest.

Validation: 118 Python tests passed; companion JavaScript fixtures and syntax checks passed.

## Real Chrome page flow (0.2.3 code)

A dedicated localhost page had text, one link, one PNG and a table, plus hidden text and a form field. Preview excluded the hidden/form fixture strings. All three optional categories were off by default; selecting them showed the link, image alt text and table cells. Query tokens were absent. Pairing, consent, save, duplicate detection and an edited table save all worked. Database readback confirmed one page item and two revisions. Revoking the pairing rejected another save.

## Original files (0.2.4 source)

- App UI imported a real PNG and PDF into a selected profile.
- PNG preview decoded to 128 × 128 with authenticated fetch. A bare unauthenticated original-file request was rejected.
- Browser downloads of both files matched the supplied bytes and SHA-256 exactly.
- Downloaded PDF ZIP bundle contained the matching original and manifest.
- Installed Chrome popup selected a downloaded PDF; consent enabled save and an existing copy was deduplicated. A newly named test PDF reported success; database readback matched every original byte.
- Regression coverage includes file-signature mismatch, oversized files, unsupported active formats, ZIP entries, revisions, hash tampering, missing review, invalid base64, authentication and revoked pairing.

Limitations: no packaged desktop build or fresh Chrome Web Store installation for these changes yet. The published 0.2.2 desktop app cannot accept the new companion original-file endpoint. Signature checks are not malware scanning. No OCR/PDF text extraction, automatic remote asset downloads or multimodal model training has been implemented. Original-file metadata is searchable; binary content is not extracted into text. The published ZIP and store review remain 0.2.2.
