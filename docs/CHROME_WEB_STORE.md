# Chrome Web Store submission

Status: submitted to Google on October 18, 2026 under item `kiiobhppgpjpccapcejhnagfneopcppk`. Dashboard confirmed **Pending review**. Publisher email is verified and all three data-use certifications are saved. Automatic publication after approval is enabled. Not yet approved or publicly installable. Do not advertise an Add to Chrome link until Google provides the published listing.

## Listing copy

Name: Proofpage — Save visible text

Summary: Review visible page text and save it directly to your local Proofpage library. Runs only when you click.

Description:

Keep useful pages in your own evidence library. Preview the text you can read, remove private details, then save directly to the Proofpage desktop app. No uploading to a cloud scraping service.

- Capture on click, including pages you have signed into yourself.
- Review and edit text before saving.
- Pair with your local app using a short-lived code.
- Save directly to Browser pages; changed text becomes a revision.
- Download JSON when your app is offline.
- No password collection, cookie extraction or background browsing.

Requires Proofpage 0.2.2 or later for direct saving. Browser text is user-supplied evidence, not an independently verified server response. The companion does not solve CAPTCHAs. Install the desktop app from https://proofpage.app.

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

Install the extension package and run the open-source Proofpage 0.2.2 app. Open Settings → Connect browser. Enter the displayed port and code in the companion and grant localhost permission. Visit example.com, preview text, confirm the review checkbox, then Save to Proofpage. Open Library and see the Browser pages record. Save again to check deduplication. Disconnect browser in Settings; another Save is rejected. Download JSON remains available without the app.

The ZIP must have manifest.json at its root. Icons (16, 48 and 128 px) are bundled. A genuine Chrome capture screenshot has been uploaded (see `assets/companion-store.png`). Complete publisher verification, contact details, fee and policy declarations in the developer dashboard. Google review and approval are external requirements.
