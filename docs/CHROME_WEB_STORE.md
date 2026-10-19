# Chrome Web Store submission

Status: companion **0.3.0 is published**, verified October 19, 2026 under item `kiiobhppgpjpccapcejhnagfneopcppk`. [Install from the Chrome Web Store](https://chromewebstore.google.com/detail/proofpage-%E2%80%94-save-page-evi/kiiobhppgpjpccapcejhnagfneopcppk). No Developer mode is required. Publisher email and all three data-use certifications were completed before submission. Automatic publication after approval was enabled.

The public listing returns HTTP 200 with the correct name and version, and Google's public update service serves a CRX3 package whose manifest is version 0.3.0. Published CRX SHA-256: `82c290f5d157daac3c5a9eeb826c39b8fef4f48fcda63ea8c663ec44453f4f38` (18,207 bytes). This verifies public distribution, not a new manual popup-to-app transfer. Chrome blocks automated access to the store's protected pages; no security setting was changed. No new source package was submitted during the availability check.

## Listing copy

Name: Proofpage — Save page evidence

Summary: Review visible page text and save it directly to your local Proofpage library. Runs only when you click.

Description:

Keep useful pages in your own evidence library. Preview the text you can read, remove private details, then save directly to the Proofpage desktop app. No uploading to a cloud scraping service.

- Capture on click, including pages you have signed into yourself.
- Review and edit text before saving.
- Pair with your local app using a short-lived code.
- Save directly to Browser pages; changed text becomes a revision.
- Download JSON when your app is offline.
- No password collection, cookie extraction or background browsing.

Requires Proofpage 0.3.0 or later for direct saving. Browser text is user-supplied evidence, not an independently verified server response. The companion does not solve CAPTCHAs. Install the desktop app from https://proofpage.app.

Category: Tools
Language: English
Website: https://proofpage.app
Support: https://github.com/Mehxeo/Proofpage-OpenSource/issues
Privacy policy: https://proofpage.app/companion-privacy.html

## Permission justifications

- activeTab: access only the tab the user invokes for visible-text preview.
- scripting: run the bundled visible-text extractor in that tab.
- storage: remember the paired localhost port and import-only token in local extension storage, not sync.
- Optional http://127.0.0.1/*: POST the reviewed capture to the user's local Proofpage app. Requested only when connecting; port configurable because the app may use another local port. No remote host access.

No remote code is executed. The extension does not access browser cookies, passwords, payment data or general browsing history. It handles website content and the selected page URL/title only after a user action; selected content could contain personal information and is therefore previewed for review. Disclose website content and Web history (the user-selected page URL/title, not background history access) in the dashboard's data-use form; do not claim that no data is handled. No sale, advertising or unrelated use.

## Reviewer steps

Install the extension package and run the open-source Proofpage 0.3.0 app. Open Settings → Connect browser. Enter the displayed port and code in the companion and grant localhost permission. Visit example.com, preview text, confirm the review checkbox, then Save to Proofpage. Open Library and see the Browser pages record. Save again to check deduplication. Disconnect browser in Settings; another Save is rejected. Download JSON remains available without the app.

The ZIP must have manifest.json at its root. Icons (16, 48 and 128 px) are bundled. A genuine Chrome capture screenshot has been uploaded (see `assets/companion-store.png`). Complete publisher verification, contact details, fee and policy declarations in the developer dashboard. Google review and approval are external requirements.

## Submitted package and verification

On October 18, the previous 0.2.2 review was canceled at the user's request and replaced with 0.3.0. Google accepted the ZIP and confirmed Pending review. Listing copy, purpose and permission explanations now cover reviewed page sections, selected original PNG/JPEG/WebP/PDF files, direct public-file URL saving and desktop-local OCR/PDF extraction. No new Chrome permissions were added. Automatic publication is enabled.

Package: dist/Proofpage-0.3.0-browser-companion.zip
SHA-256: 22da47514fa5cdac62e08c1997990b3c5227b0a32207bda03628d029857aa0d7

The user confirmed the new direct-image control is present in installed Chrome. A fresh 0.3.0 popup-to-app transfer is **not yet verified**: browser security policy blocks automation of extension-internal pages. Automated popup-script and HTTP tests cover import controls, consent, pairing and access restrictions; they do not substitute for this manual Chrome check. Earlier real Chrome page-flow and original-PDF checks are documented in MEDIA_VERIFICATION.md.

For the new direct-file reviewer check, pair with desktop 0.3.0, paste a public PNG/PDF URL in Save web file, confirm permission and save. Confirm an original file appears in Library and its downloaded bytes match the source. Also test a selected local file and a repeated save. Public URL capture does not use browser login sessions. Files are limited to 8 MiB and PDF extraction to 20 pages.

## Next UI update

Companion source 0.3.1 improves capture choices, field spacing and connection guidance. It has not replaced the published 0.3.0 version. No new permissions. The store package and source version must not be confused.
