# 0.3.0 release verification

Runtime commit: `097f46a773fa6c9ec100cbc03a1834d42743124e`.

- 122 tests, including real OCR on generated PNG and scanned PDF fixtures, selectable PDF text, exact original-file round trips, receipt creation for public files, deduplication, and companion URL review/auth/private-network guards.
- CI run `39100157102` checks Python 3.11/3.13, container, guided source installs, and desktop packages on macOS Apple silicon/Intel, Windows, and Linux.
- Desktop smoke tests launch the native controller, exercise HTTP and MCP, and run image/scanned-PDF OCR through the packaged executable with its bundled models.
- Browser app acceptance collected a public PNG from raw.githubusercontent.com without a prior file download, displayed its original preview, extraction warning, and signed receipt, and enabled Watch hourly.
- The real scheduler was accelerated in an isolated test workspace and automatically re-collected the watched PNG with zero duplicate revisions. The companion's authenticated import-url endpoint also completed a real public fetch.
- JavaScript tests exercise the actual companion script and original file controls. Browser automation refused extension-internal URL navigation; a fresh real Chrome popup test for the 0.3 controls is not claimed. The prior popup file-import test applies to 0.2.4 source, not a fresh store installation.

Mac notarization identifiers and public artifact checksums are recorded with the GitHub release. Windows packages remain unsigned. Chrome Web Store review and desktop release are separate distribution paths.

## Mac signing

Both final CI packages were signed with Developer ID Application UTTAM SUBODH DAS, team `44HHGAZ2C4`, and accepted by Apple:

- Apple silicon: `7e798f1f-7c5a-47cc-a057-18f59874d229`
- Intel: `46225192-3414-4284-89c7-20a04041e664`

`codesign --verify --deep --strict`, `stapler validate`, and `spctl --assess --type execute` passed on both. Both final signed apps passed local GUI startup, original-image OCR, and PDF text extraction; the Intel app ran through Rosetta. The original CI jobs also checked native Intel execution and scanned-PDF OCR.

## Chrome Web Store follow-up

Companion 0.3.0 replaced the prior 0.2.2 submission on October 18, 2026. The dashboard confirmed Pending review with automatic publication enabled. The user confirmed the new direct-image control is visible in Chrome; the fresh 0.3.0 popup transfer remains unverified because extension-internal browser automation is blocked.
