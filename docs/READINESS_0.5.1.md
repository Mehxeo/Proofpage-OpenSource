# 0.5.1 release preparation — October 19, 2026

This is pre-release validation. The public app remains 0.5.0. Shared Google Docs
sign-in is waiting for explicit approval of the read-only Docs scope; production
audience or verified branding alone is insufficient. No new signed installer is
published by this preparation work.

## Changes

- Documents, images and PDFs can use **Local files · no account setup**. JSON,
  CSV, ZIP and conversation exports still require an explicit import profile.
  Single supported files are selected in the preview; import remains an explicit
  action. Reimports deduplicate and changed files retain earlier revisions.
- Business context has its own evidence search, a remembered profile choice,
  source/review/share progress, pending/approved/stale filters, source links and
  export readiness. Server-side review, source drift and credential checks remain
  authoritative. Drafts and excluded passages stay out of context retrieval.
- The homepage adds an interactive forest of paper notes, IBM Plex Sans, and four
  real app screenshots. The terminal, original gallery, tour, public Chrome Store
  install link, privacy and Google ownership routes remain available. Upcoming
  screenshots and Google availability are labeled honestly.
- The app now uses locally bundled IBM Plex Sans and the site's paper/forest
  palette. A new first-run screen offers web capture, local files and optional
  Google Docs. Settings has four keyboard-accessible sections, remembers the
  selected section, previews the actual theme, and opens with Command–Comma.
- The homepage airplane drifts along a scroll-driven path. It no longer follows
  the cursor. The initial throw, replay button, shared pause, static reduced
  motion and sleeping frame loop remain. Two screenshots now show the updated
  onboarding and Settings directly from the packaged engine.

## Local acceptance

- 183 Python tests pass, including authenticated simple-file import, revision
  retention, explicit profiles for structured archives, independent profile
  search and approved-only context exports. Existing source permissions, Google
  personal-context restrictions, conversation roles and stale-source gates pass.
- Onboarding and preference JavaScript checks pass. The Node SDK exercises its
  actual Python bridge. The packaged skill validates, and its named MCP tools
  match the server registry.
- A native Apple silicon Tauri review build starts and shuts down cleanly. Its
  bundled MCP, image OCR and scanned-PDF extraction work without system Python.
  This local review build is ad-hoc signed for testing, not notarized for public
  distribution.
- Through the packaged engine's real UI: first capture → inspect evidence;
  plain-file import without account setup; independent business-source search;
  suggest → review one fictional passage → download a one-passage context pack;
  persisted appearance/profile choices; web-assistant fallback; and the local
  MCP check reporting 36 tools all work.
- The setup kit actually downloaded from that UI launches its bundled MCP helper
  from an unrelated project with spaces in its path. The official MCP SDK
  initializes, discovers 36 tools, retrieves only approved context, saves and
  pauses a schedule, and creates a fictional SFT draft without approving it or
  freezing a dataset. Codex and Claude project skill installation work; custom
  file preservation remains covered by the regression suite. These tests do not
  claim a live Claude/ChatGPT account has loaded the configuration.
- The existing approved Google review workspace retained authorization and
  successfully synced only its previously approved fictional demo document.
  Metadata remains `personal_context_only`. No new grant or private-document
  fixture was used. No client metadata, user token or credential is committed.
- After the UI refresh, all 183 Python regressions, preference/onboarding and
  companion checks, the actual Node/Python SDK bridge, JS syntax, skill validation
  and a native Apple silicon Tauri smoke test pass. The bundled MCP helper, OCR
  and scanned-PDF extraction pass. The new font and its OFL license are included
  in the source wheel and desktop assets.
- Browser checks cover a real example.com capture and signed evidence drawer,
  a plain-file import without a profile, persisted Settings section/theme,
  arrow-key section switching, Command–Comma, pairing-code generation, receipt
  verification, update checking, both themes and 320/375px layouts. The actual
  bundled UI loads without console errors. Pointer movement leaves the website
  plane still; scrolling moves it and creates its fading trail.

## Release gates still required

After scope approval, integrate the reviewed changes, verify the final release
version and current CI, inject the maintainer's native Google client metadata,
and sign/notarize both Mac architectures. Require Apple Accepted, stapled tickets,
codesign and Gatekeeper acceptance, native final-package checks, anonymous public
download/hash verification, and matching updater/download links. Windows signing
and Linux requirements must remain accurately disclosed. Keep the public website
on its verified stable downloads until that release is usable.
