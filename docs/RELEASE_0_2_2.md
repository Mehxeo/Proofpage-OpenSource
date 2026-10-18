# v0.2.2 verification

Release source: 8bb6dc4b17ac003eb6b0c2e26cada34fc7394929. CI run 39094104873 passed all ten jobs (Python 3.11/3.13, installers, container, four desktop targets). CI ran 112 Python tests; a subsequent first-CAPTCHA attention regression makes the final local suite 113 passing tests, with no further runtime changes.

The companion fixtures cover visible-text filtering, review consent, edited text, URL sanitization, JSON fallback, pairing and direct save. HTTP integration tests cover extension-origin enforcement, import-only token scope, single-use pairing, attempt limits, wrong-extension rejection, missing review, duplicate saves and revocation. The first-challenge regression checks that a new source creates an attention event, pauses scheduling, returns agent/training instructions and does not repeat the same alert.

In the browser, Settings generated a code with the correct runtime port; Disconnect revoked it and showed confirmation. Public docs show the new pairing workflow and accurately state that the Chrome Web Store listing is pending. Privacy and companion download routes are deployed on proofpage.app.

Apple notarization accepted:
- Apple Silicon: 1174e630-0c34-448e-ab3c-f55509414e43
- Intel: 5de1cd50-91eb-4ad8-ab12-21064883c442

Both signed, stapled apps passed native GUI/HTTP/quote-check/offline-verifier smoke tests and the bundled MCP helper handshake. All nine release files were downloaded anonymously and matched their SHA-256 checksums. Public Mac downloads passed codesign, stapler and Gatekeeper checks. Windows remains unsigned.

Production website deployment: dpl_FdaqvB3d7eR4mzP5TjkcK9FHZkUq, READY with proofpage.app alias.

Real Chrome verification: the unpacked companion paired with an isolated Proofpage app on port 8894, previewed example.com, and saved reviewed text directly. A second save reported “Already saved. Your library is up to date.” The test database contained exactly one item and one revision. Store screenshot: `assets/companion-store.png`.

Limits: Chrome Web Store installation is not verified; the listing was submitted on October 18, 2026 and Google confirmed Pending review, with automatic publication after approval enabled. The developer ZIP still requires Developer mode. Pairing lasts for the app session and must be renewed after restart. Notifications require permission and an open workspace. No CAPTCHA solver or password collector was added; agents receive a browser handoff requiring approval for the specific challenge. Browser imports do not transfer login sessions or automatically resume blocked crawl/quote-check jobs. They remain user-supplied text, not signed HTTP captures.
