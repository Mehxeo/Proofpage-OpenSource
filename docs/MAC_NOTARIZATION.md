# Mac notarization — v0.1.3

Verified October 17, 2026 (America/New_York).

The existing CI-built Mac artifacts from commit `1e3df38fb73037dadc81a758040b3bc3b6bb4285` were Developer ID signed with hardened runtime, submitted to Apple, stapled, and repackaged. Source code was not changed by signing. Windows signing is still pending.

| Architecture | Apple submission | Result |
| --- | --- | --- |
| Apple silicon | `347ba7f5-65c1-42f9-a908-5dd5ec53914a` | Accepted |
| Intel | `0f2de564-2b58-46ba-aa87-c2f4b2618e6c` | Accepted |

Both apps passed `codesign --verify --deep --strict`, `stapler validate`, and `spctl --assess --type execute`, with `source=Notarized Developer ID`. Both notarized GUI executables and MCP helpers were launched successfully on the signing Mac; the Intel build ran through the host's Intel compatibility support. Real local API calls, MCP initialization, listing all 18 tools, and listing sources succeeded. This complements the original native CI tests on each architecture.

## Published Mac archive checksums

- `Proofpage-0.1.3-darwin-arm64.zip`: `09cf863473702d17d09c26e3ea19162d370543ff6a4ba80e0347657a25da8a38`
- `Proofpage-0.1.3-darwin-x86_64.zip`: `f04ed63fd155201988f56cbb77eb011b7f83533e757b594613fb4ae83864f404`

Download the current files and SHA256SUMS from [v0.1.3](https://github.com/Mehxeo/Proofpage-OpenSource/releases/tag/v0.1.3). Older unsigned copies have different hashes. The release remains a preview; normal first-download confirmations and organization-specific security policies may still apply.

## v0.2.0

Both architecture builds from successful CI run 39091698926 (application source df6bf4b) were signed with Developer ID Application: UTTAM SUBODH DAS (44HHGAZ2C4), submitted to Apple, accepted, stapled, and passed Gatekeeper assessment.

- ARM64 submission: `15a7071e-19e5-4b03-836f-f0dad9051578` — Accepted.
- Intel submission: `f1c8921a-17be-4942-8d63-b8385c25dfa0` — Accepted.

The final signed packages also pass native GUI/HTTP and bundled MCP smoke checks locally (Intel via Rosetta). Release asset hashes are published in `SHA256SUMS`.
