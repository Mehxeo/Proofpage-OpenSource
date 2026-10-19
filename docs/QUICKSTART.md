# Start with one page

## Download and open

[Download Proofpage](/#download) for your computer. Extract the archive and open the app. On Mac, drag Proofpage.app into Applications. On Windows, keep the extracted support files beside Proofpage.exe. The desktop app includes Python; you do not need to install Python or use a terminal.

The desktop download opens your workspace in a native Tauri window. Keep it open for scheduled collection. Source/CLI installations still use your browser. Your evidence is stored separately from the application in your user folder under Proofpage/data.

## Capture your first page

1. Choose **Add source**.
2. Paste a public page URL. The name is optional.
3. Leave **Collect this page now** checked and choose **Save source**.
4. Open **Library**, select the captured page, and inspect Reader, Original, Rights, Versions, and Proof.

If a site blocks collection, the source card explains the outcome. For pages you can read after signing in, use [the browser companion](#browser-capture). Do not paste account passwords into Proofpage.

## Check an AI answer

Open **Check quotes** and paste an answer containing quoted passages and source URLs. Preview the quote/source pairs, correct them if necessary, and start the check. Leave collection off to use only saved pages. A wording match is not a factual truth verdict.

## Use the library with an assistant

Open **Agent access**, copy the setup prompt, and paste it into an assistant that supports local MCP tools. The prompt includes your installed executable and workspace paths. After moving the app, recopy it. [Assistant setup and training exports](#agents).

### Upcoming 0.5.1 onboarding

The review build adds **Settings → Getting started**, with separate paths for
web sources, local files, and optional Google Docs. You can use the library
without connecting an account or adding an AI API key.

In **Agent access**, choose Claude Desktop, Codex / ChatGPT desktop, Claude Code,
or another local client. Copy the matching setup prompt, or download its setup
kit. The kit contains a configuration snippet, instructions, and the workflow
skill in its matching project folder. Merge configuration rather than replacing
other integrations. **Test local server** checks the helper; ask your assistant
to call `proofpage_list_sources` to verify its own connection. An empty list is OK.

For Google Docs, sign in through your system browser, paste a selected document
link, confirm owner permission, and choose **Import document**. One action selects
and syncs it; future refreshes use **Sync**. Shared sign-in is under Google review
and is not yet included in stable 0.5.0 downloads. [Google setup status](#connectors).

## Update safely

Close Proofpage and make a private copy of your Proofpage/data folder before updating. Replace the application, not the data folder, then reopen it. Backups include your private receipt-signing key. Keep the older backup until you have checked the updated library.

## Need help?

[Report a problem](https://github.com/Mehxeo/Proofpage-OpenSource/issues) with your operating system, Proofpage version, and what happened. Remove private page content, passwords, and tokens before sharing logs. For optional CLI installation and advanced backup commands, see [the installation guide](https://github.com/Mehxeo/Proofpage-OpenSource/blob/main/docs/INSTALL.md).


## Check for app updates

Open Settings → App updates → Check for updates. This explicit check contacts GitHub without sending workspace data. When a newer stable release is available, Proofpage offers the download for this computer, or the release page if there is no matching build.

Back up your workspace and quit Proofpage before replacing the app. On Mac, drag the new app into Applications and choose Replace. On Windows/Linux, extract the complete archive into a new app folder. Keep your home-folder Proofpage/data directory: the library lives separately from the application. This is a guided download-and-replace flow, not automatic installation.
