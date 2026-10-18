# Evidence manifest v1

The open format identifier is `proofpage.evidence/v1`. The implementation and
SDKs use the repository's MIT license. There is no server-issued identifier,
account requirement, or proprietary verifier dependency for portable replay.

A manifest is UTF-8 JSON containing `schema`, `name`, `created_at`, `producer`,
`scope`, `records`, `dependencies`, and `sha256`.

`sha256` is the SHA-256 of the manifest with its top-level `sha256` removed,
serialized by Python `json.dumps(sort_keys=True, ensure_ascii=False,
separators=(',', ':'), allow_nan=False)` and encoded as UTF-8. This is the
specified v1 serialization, not a claim of RFC 8785 compatibility. Cross-language
writers must match this serialization, including numeric formatting; readers
may use the supplied open-source verifier. Unknown schema versions are rejected.

Each record identifies a local source, item and immutable revision, with its
revision hash, capture time, text, text SHA-256, stored metadata, and original
bytes (base64 plus SHA-256). `capture` is either stored HTTP observation details
or null. Original representations:

| Value | Meaning |
| --- | --- |
| `http_body_exact` | Stored body bytes from the HTTP capture |
| `http_body_reconstructed` | UTF-8 reconstruction; not exact transport bytes |
| `supplied_file_exact` | Imported file bytes verified against stored asset metadata |
| `external_collector_bytes` | Caller-supplied bytes from another collector |
| `stored_raw_utf8` | Existing revision's raw string encoded as UTF-8 |

A dependency contains `output_id`, `revision_id`, `start`, `end`, and `quote`.
Offsets are half-open Python Unicode code-point indices into the stored text.
The quote must equal that nonempty slice. Dependencies identify supplied input;
they do not prove that a model used or agreed with it. Output IDs are caller
labels, not URLs or filesystem paths. Reusing a label does not overwrite a run.

Files are capped at 64 MiB and may contain private source material. File exports
are created exclusively, with owner-only mode where the OS supports it. They
are not encrypted. Self-contained hashes detect accidental corruption; pin the
manifest checksum through a separately trusted channel to detect replacement.
Existing signed proof bundles remain separate from these input manifests.

Current-revision comparisons require the originating workspace or a backup:
local item IDs are not a cross-workspace identity scheme. Portable replay does
not require the database or network. This format does not represent live browser
state, authentication cookies, model randomness, or model weights.
