# v0.2.1 verification

Release tag: `7c108d76d6cc1f579da9b50344b556197d6f4565`. All 10 cross-platform jobs in CI run 39093471821 passed. The Python suite has 110 passing tests; the browser companion JavaScript fixture tests cover review consent, text filtering, user redaction, URL sanitization, error handling, and extension permissions. Its import tests prove user-supplied provenance, revision continuity, invalid-input rejection, and absence of fabricated web receipts.

Live browser checks: a new example.org source collected with the optional name left blank; two quote checks returned exact wording and not found; all two receipts in the isolated demo workspace passed chain verification. The 390px layout had no document overflow and quote navigation worked. Docs search narrowed to the correct topic; screenshot enlargement opened and Escape dismissed it; no console errors were observed in the checked app and homepage flows.

Both Mac architectures passed Apple notarization and native packaged-app smoke tests, including GUI, HTTP API, quote checking, offline verifier, and MCP helper. All nine release assets were downloaded anonymously and checksum-compared, and the downloaded Macs rechecked for signature/ticket/Gatekeeper validity. Windows is unsigned. Source packages and the optional browser companion are included.

Homepage and docs deployed to `proofpage.app` via production deployment `dpl_HjNVUAEdpyAx8siDFAgTfjDnVLfG`. Public docs and companion ZIP returned successfully; the site companion download matches the release file.

Limits: browser companion extraction/export is fixture-tested, not certified against every Chrome/Edge version or authenticated site. It is an unpacked optional extension. Users sign in and complete challenges themselves; no credential collection or automatic CAPTCHA bypass is implemented. Imports are user-supplied text, not direct web captures. No new claim of universal website coverage or factual truth verification is made.
