# Browser companion

Save a page you can read in Chrome straight to your local Proofpage library. Sign in on the website using its own login form or your password manager. Your passwords and session cookies stay in the browser.

## Install

The Chrome Web Store submission is being prepared. **There is no published store listing yet.** Once Google approves the listing, installation will be the usual Add to Chrome button, with no Developer mode. Until then, the [developer ZIP](/downloads/proofpage-browser-companion.zip) is for testing only: extract it, open Chrome’s Extensions page, enable Developer mode, and Load unpacked. Ordinary users can keep using Proofpage’s Import files while waiting for the store release.

## Connect once per app session

Requires Proofpage 0.2.2 or later.

1. Open Proofpage → Settings → Connect browser.
2. Open the companion → Connect to Proofpage. Enter the port and pairing code shown in Settings.
3. Choose Connect and allow the connection to the local app. The code expires in five minutes and can be used once.

The connection can only import reviewed pages. It cannot read, export, or delete your library. Restarting the app or choosing Disconnect browser revokes access. Create a new code to reconnect.

## Save a page

1. Open the page and click the companion → Preview visible text.
2. Review the text and remove anything private. Confirm you are allowed to save it.
3. Click **Save to Proofpage**. It appears in your library under Browser pages. Saving the same text twice does not create a duplicate; changed text becomes a new revision.

No file picker or manual import is needed after pairing. If the app is closed, choose Download JSON instead, then use Import files in Proofpage.

## Login and CAPTCHA interruptions

When direct collection encounters a login or CAPTCHA, Proofpage creates an attention entry in Timeline. Enable notifications in Timeline to receive browser notifications while the workspace is open. Click an alert to open Timeline, then Open website. Scheduled collection of the source page pauses.

For training work, complete the challenge yourself and save the resulting readable page with the companion. For an AI agent, collection results include an attention object explaining the interruption and asking it to obtain your approval for that specific challenge before attempting it in your browser. The agent needs its own browser-control capability; Proofpage does not contain a CAPTCHA solver. Authentication happens on the website, not through a Proofpage password form. Browser imports do not transfer your signed-in session to the direct collector or automatically resume a blocked crawl or quote-check job.

## Evidence and privacy

This is user-supplied browser text, possibly edited, not a raw HTTP response. No web-capture receipt is issued. The source URL and user-reported save time are retained. Hidden elements, form fields, scripts, cookies, images, and iframe contents are excluded. URL query strings and fragments are removed, which can make URLs less specific. Visible content can still contain private information: review before saving.

Imported text is searchable by assistants. Automatic URL-based Claim Check and WACZ export use direct captures, not these imports. Rights review still applies before dataset export.

The companion runs only when clicked. It sends reviewed content only to the paired app on 127.0.0.1, not to Proofpage servers. See the [companion privacy policy](/companion-privacy.html).

## Troubleshooting

If a code fails, create a fresh code in Settings. If Save cannot reach the app, check the port and reconnect after restarting Proofpage. Browser internal pages and protected tabs may be unreadable. Finish loading the page before previewing. Pages over 500,000 text characters must be split.
