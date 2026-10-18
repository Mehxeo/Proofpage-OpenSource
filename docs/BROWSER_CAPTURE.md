# Browser capture

Use the optional browser companion for pages you can read in your own browser, including pages behind your own login. Sign in on the website itself, and complete any CAPTCHA yourself. The companion does not solve challenges, collect passwords, or copy session cookies.

## Install the companion

Download [the companion ZIP](/downloads/proofpage-browser-companion.zip), extract it, then open Chrome or Edge's Extensions page. Turn on Developer mode and choose **Load unpacked**, selecting the extracted folder containing manifest.json. This is an optional unpacked extension, not a Chrome Web Store listing. No Python is required.

## Save a page

1. Open the page and sign in normally if needed.
2. Open the Proofpage companion and choose **Preview visible text**.
3. Review the text. Delete anything private or unnecessary. Form fields, cookies, scripts, hidden elements, query strings, and URL fragments are not copied, but visible page content can still contain private information.
4. Confirm you have permission to save it, then choose **Download for Proofpage**.
5. In Proofpage, choose **Import files**, create or select an account profile using automatic format detection, select the JSON file, check its preview entry, and import.

## What this evidence means

The import is explicitly user-supplied browser text. It may have been edited. The source URL and user-reported save time are retained in Original/Provenance, but are not independently verified. It is not a raw server response and does not receive a web-capture receipt. No images, iframe contents, or browser cookies are included. The URL's query and fragment are omitted to avoid copying login tokens; this can make the URL less specific.

Imported text is searchable by your assistant through the evidence library. Automatic URL-based Claim Check and WACZ export use direct web captures, not these imports. Rights review still applies before dataset export. Only save and share content you are allowed to use.

## Troubleshooting

Browser internal pages and some protected tabs cannot be read by extensions. Finish loading or signing in before opening the companion. If no text is found, use the website's own export or save a text file for import. Pages over 500,000 text characters must be split. The companion runs only when clicked and has no background collector or network endpoint.
