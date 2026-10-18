# Google Docs public sign-in verification

Proofpage's project has been moved from Testing to **In production**. Google
Search Console verified `https://proofpage.app/` using the retained public
ownership file. Google then verified the app's branding, which is published.

This is not yet approval of the sensitive Docs permission. The scope submission
requires an actual OAuth/import demo on YouTube and Google's review. Do not
describe Production or brand verification as approval of that scope.

## Scope and data use

Only `https://www.googleapis.com/auth/documents.readonly` is requested. Users
select document URLs, confirm owner permission, then explicitly sync or choose
a local schedule. The app calls `documents.get`; it does not list Drive, edit
Docs, read Gmail, or scan unselected documents. Google grants account-wide read
permission, and this is stated in the interface and privacy policy.

Google snapshots are local personal context. User-reviewed passages may be
exported for the user's own assistant. Google API snapshots are rejected by
the training workflow. Tokens stay in the OS vault; Proofpage's servers do not
receive Google documents or tokens. See the public
[privacy policy](https://proofpage.app/privacy.html).

## Demonstration requirements

Use a dedicated review workspace and Google's published Docs API quickstart
sample, or a fictional document explicitly authorized for testing.
Show Connect Google Docs, the actual consent flow including any unverified-app
notice, the correct app name and OAuth client ID, document selection and owner
permission, Sync, captured text and provenance, and Disconnect. Do not include
private documents, tokens, authorization codes, or unrelated browser tabs in the
video. Upload the real walkthrough as an unlisted YouTube video and provide its
URL in Data Access. All assigned OAuth clients must be covered.

The existing approved connection successfully fetched Google's public quickstart
sample through `documents.get` and extracted its text. No private document was
read and no new Google Doc was created. The preconfigured native build also
passed startup, MCP, OCR, and PDF checks with a separate empty configuration
directory; its packaged report confirmed `google_configuration: bundled`.
Completing a fresh review-workspace authorization and attaching the finished
YouTube demo remain separate requirements. These checks are not a submitted or
approved Google scope review.

The next desktop build supports native-client metadata bundled before signing;
it does not require end-user Google Cloud setup. Keep it in review/staging until
Google approves the scope. Existing stable 0.5.0 downloads are not changed by the
Google Console settings. See [release packaging](CONNECTORS.md#building-official-preconfigured-downloads).

Primary references:

- [Sensitive scope verification](https://developers.google.com/identity/protocols/oauth2/production-readiness/sensitive-scope-verification)
- [Desktop OAuth](https://developers.google.com/identity/protocols/oauth2/native-app)
- [Docs scopes](https://developers.google.com/workspace/docs/api/auth)
