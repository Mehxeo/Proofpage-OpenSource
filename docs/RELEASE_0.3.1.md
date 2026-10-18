# Proofpage 0.3.1

- Redesigned Settings and browser companion setup.
- Saved Light, Dark and Follow system preferences, with cross-tab updates.
- Easier recurring collection: schedule presets and pause controls.
- MCP source creation and scheduling, reliable launch paths, and an in-app connection test.
- Bundled downloadable SKILL.md for supported coding assistants.
- Stricter explicit participant approval for personal training examples.

The local app includes offline image OCR, PDF extraction, original-file storage, evidence receipts and reviewed training exports. Keep the app running for scheduled collection. Proofpage prepares training datasets; it does not train model weights. Local MCP is not a ChatGPT web connector.

Mac archives are Developer ID signed, notarized and stapled before publication. Windows builds are unsigned. Browser companion 0.3.1 is provided as a separate source ZIP; Chrome Web Store approval is a separate process.

## Verification

Runtime commit: `be2f85bca40768149c4b08ac2b4367eee6e2aa3f`. CI run `39104649182` passed on all platforms, including Python 3.11/3.13, guided installation, container, and native packaged-app checks. The suite includes 128 Python tests and preference/companion JavaScript checks.

Both final Mac apps passed strict code-signature verification, Apple notarization, stapling, Gatekeeper assessment, and local startup/MCP/image-OCR/scanned-PDF smoke tests. Intel was also tested natively in CI; final signed Intel verification ran under Rosetta.

- Apple silicon notarization: `b5302bb2-d136-453f-a480-d64a38264568`
- Intel notarization: `c867caa9-667d-4bd2-bc9d-ecf46047ac22`
- Developer ID team: `44HHGAZ2C4`

See SHA256SUMS-0.3.1.txt for final artifact checksums. Chrome Web Store availability is not implied by this desktop release.
