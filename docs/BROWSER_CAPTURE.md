# Browser companion

Save a page you can read in Chrome straight to your local Proofpage library. Sign in on the website using its own login form or your password manager. Your passwords and session cookies stay in the browser.

## Install

[Add to Chrome](https://chromewebstore.google.com/detail/proofpage-%E2%80%94-save-page-evi/kiiobhppgpjpccapcejhnagfneopcppk)

Companion **0.3.0 is published in the Chrome Web Store**. Open the listing in Chrome, choose **Add to Chrome**, then confirm **Add extension**. No Developer mode, extracted folder, or manual ZIP installation is needed. Pin Proofpage from Chrome's Extensions menu if you want its button visible in the toolbar.

Keep the [Proofpage desktop app](https://proofpage.app/#download) open. Use desktop 0.3.0 or later for the published companion's page and original-file features. The app remains separate from the Chrome extension; the extension saves to your computer, not a cloud workspace.

## Connect once per app session

1. Open Proofpage → **Settings → Connect browser**.
2. Open the companion → **Connect your desktop app**. Enter the app port and pairing code shown in Settings.
3. Choose **Connect** and allow the requested connection to the local app. The code expires in five minutes and can be used once.

The connection can only import reviewed content. It cannot read, export, or delete your library. Restarting the app or choosing **Disconnect browser** revokes access. Create a new code to reconnect. Do not share pairing codes or library content in support reports.

## Save a page

1. Open the page and click the companion → **Preview this page**.
2. Review **Page text** and remove anything private. **Include more from this page** optionally adds reviewed links, image references with alt text, and table text; each category is off by default and editable.
3. Confirm **I can save this content and have removed private information.**
4. Click **Save to Proofpage**. It appears in your library under Browser pages. Saving the same text twice does not create a duplicate; changed text becomes a new revision.

After pairing, Save sends the reviewed capture straight to the app. No file picker or manual import is needed. If the app is closed, choose **Download JSON** instead, then use **Import files** in Proofpage.

Optional page sections contain references and table text, not downloaded original images or linked pages. At most 100 links, 50 image references, and 20 tables are previewed. Review resource URLs too: paths can contain personal information.

## Save an original image or PDF

For a public web file, open **Save an image directly from this page**. Preview the page first and choose an image, or paste a public image/PDF URL. Confirm permission, including embedded metadata, then choose **Save web file**. The desktop app fetches the original bytes and extracts text locally. You do not need to download the file to your Downloads folder first.

Public URL collection respects robots policies, public-network restrictions, rate limits, and redirects. It does not use your browser login session. For a sign-in-only file, download it yourself first, then use **Save an image or PDF file** to select, review, and save it. Supported originals are PNG, JPEG, WebP, and PDF, up to 8 MiB. In Library, inspect extracted text, preview images, and download unchanged original bytes or a file-plus-hash bundle. See [Media and automation](MEDIA.md) for PDF/OCR limits.

## Login and CAPTCHA interruptions

When direct collection encounters a login or CAPTCHA, Proofpage creates an attention entry in Timeline. Enable notifications in Timeline to receive browser notifications while the workspace is open. Click an alert to open Timeline, then **Open website**. Scheduled collection of the source page pauses.

For training work, complete the challenge yourself and save the resulting readable page with the companion. For an AI agent, collection results include an attention object explaining the interruption and asking it to obtain your approval for that specific challenge before attempting it in your browser. The agent needs its own browser-control capability; Proofpage does not contain a CAPTCHA solver. Authentication happens on the website, not through a Proofpage password form. Browser imports do not transfer your signed-in session to the direct collector or automatically resume a blocked crawl or quote-check job.

## Evidence and privacy

Page captures are user-supplied browser text, possibly edited, not raw HTTP responses. No web-capture receipt is issued. The source URL and user-reported save time are retained. Hidden elements, form fields, scripts, cookies, and iframe contents are excluded. URL query strings and fragments are removed from the page preview, which can make URLs less specific. Visible text and selected files can still contain private information: review before saving. Original files retain embedded metadata.

Imported text is searchable by assistants. Automatic URL-based Claim Check and WACZ export use direct captures, not browser-text imports. Rights review still applies before dataset export.

The companion runs only when clicked. It sends reviewed content only to the paired app on 127.0.0.1, not to Proofpage servers. See the [companion privacy policy](https://proofpage.app/companion-privacy.html).

## Troubleshooting

If a code fails, create a fresh code in Settings. If Save cannot reach the app, check the port and reconnect after restarting Proofpage. Browser internal pages, the Chrome Web Store itself, and other protected tabs may be unreadable. Finish loading the page before previewing. Pages over 500,000 text characters must be split.

The local companion source is 0.3.1 and contains a newer UI. The published store version is 0.3.0. Loading source with Developer mode is optional development work, not the normal installation flow; do not expect unpublished source changes in the store release.
