# Proof Receipts and archives

A capture receipt records what this workspace observed: URL, observation time, response status, body/header hashes, revision hash, publisher-policy evidence, TLS/peer details and the previous receipt hash. It is signed with a per-workspace Ed25519 key. **It does not prove what the remote server sent, or that the page's statements are true.** A local clock is not an independent timestamp.

Open **Settings** to inspect your public-key fingerprint and check chain integrity. Keep backups private: the signing key is stored in the workspace database and travels with backups. Anyone holding that key can sign as your workspace. The stdlib signing fallback is not constant-time; optional `cryptography` is used when installed.

Signatures and chain links detect altered receipts and missing intermediate links. A trusted saved chain head or external anchor is needed to detect truncation of the tail. A verifier must also establish whether it trusts the included public key; a self-contained bundle alone cannot establish the signer's real-world identity.

## Offline proof bundles

Open a record → **Proof → Download proof bundle**. A per-revision ZIP includes receipts, original body and headers, available rights/policy evidence, anchor proofs and `verify_proof.py`. With Python 3 installed, extract and run:

```sh
python3 verify_proof.py
# Or from a Proofpage Python installation:
proofpage verify proof-bundle.zip
proofpage receipts
```

No extra Python packages are required for bundle verification. Independently verify receipt signatures with OpenSSL using the instructions inside the bundle. Tampered files fail verification. Old captures without receipts are not backfilled with invented historical signing times.

## Optional timestamp anchoring

Off by default. Configure a trusted RFC 3161 timestamp authority and/or OpenTimestamps calendar in Settings. Only a digest of the Merkle root is submitted, not URLs, content or receipts. The service sees your network connection. Anchoring operates in local mode only. A timestamp token needs independent trust/certificate verification; a pending OpenTimestamps submission is not a confirmed Bitcoin timestamp. Upgrade and verify it with the external `ots` client. Restoring a backup pauses anchoring and collection.

## WACZ

Use a source card's WACZ export or `proofpage export-wacz SOURCE_ID --output site.wacz`. It includes WARC records, indexes, page metadata and receipt sidecars. Assets absent from capture cannot be replayed; this is not a full browser session recording. Reconstructed legacy records are labeled. Ed25519 sidecars are not WACZ-Auth signatures. ReplayWeb.page interoperability is separately tracked in the implementation status.
