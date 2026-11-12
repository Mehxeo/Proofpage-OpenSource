# Google Docs public sign-in verification

Status checked November 12, 2026: **no explicit approval of the sensitive
`documents.readonly` scope has been verified.** Production audience and verified
branding are separate from scope approval. Do not publish preconfigured stable
downloads or advertise approved shared sign-in until all release gates pass.

An actual consent and fictional-document walkthrough was submitted using the
unlisted [verification demo](https://youtu.be/JzE-JdgmVjA). The earlier note saying
the demo was still unsubmitted was stale. A reviewer message dated October 20
requests Google-data privacy disclosures, protection mechanisms and AI data-use
details. That email does not name the app/project in its body: confirm its project
association in the Verification Center before sending a project-specific reply.
The console's unchanged “under review” badge is not evidence that no action is due.

## Decision and implementation

The maintainer selected **local/offline AI only for Google Docs** on November 12.
No hosted provider or aggregator tier is approved to receive Google API data.

- Keep `documents.readonly` only, explicit document selection, PKCE, ephemeral
  loopback callbacks, owner permission and OS-vault token storage.
- Keep raw API snapshots, extracted text and reviewed business passages local.
- Route optional Google extraction, revision summaries and passage review to
  in-process inference over an existing local GGUF file. Without the optional
  runtime/model, fail closed. Never fall back to an HTTP endpoint, even localhost:
  a gateway can proxy a cloud model.
- Exclude Google origins and tracked derivatives from stdio/HTTP MCP, assistant
  packs, training approval/freezing/downloads, and portable evidence/report exports.
  Recheck legacy evidence runs, traces and saved reports using their provenance.
- Preserve historical revision hashes and local reader/review access. Private
  workspace backups remain possible; tokens are not in them.
- No Google raw, aggregated, de-identified or derived data develops or improves
  foundational/generalized models. Inference does not update weights.

The upcoming 0.5.1 source implements these boundaries. Public 0.5.0 downloads do
not acquire new safeguards from policy or console updates. The privacy page and
connector guides explicitly describe this version boundary.

## Remaining verification work

1. Confirm the October 20 correspondence belongs to this project and inspect newer
   reviewer requests. Authenticated browser control was unavailable on November 12;
   Gmail readback alone cannot confirm console status.
2. Publish/read back the updated privacy policy and developer docs. Prepare the
   exact reviewer reply for owner approval; do not send an unreviewed response.
3. Record an updated real demo of local isolation if Google requires it. Show a
   fictional selected Doc, local reader, blocked hosted/localhost AI sends,
   empty Google MCP results, blocked context/training exports, and optional real
   offline inference if advertised. Do not expose private documents or tokens.
4. Update/resubmit the verification request and reply to the confirmed reviewer
   thread with truthful implementation, policy and demo details.
5. Wait for explicit sensitive-scope approval. Then integrate current main/PR #2
   and complete signing, notarization, packaged acceptance and public-download
   checks before releasing or changing website download links.

Native-client metadata must be bundled **before signing** using
`PROOFPAGE_DESKTOP_GOOGLE_CLIENT_FILE` and `scripts/configure_desktop_google.py`.
Keep client files and account tokens out of Git and review assets. Check the
packaged build reports `google_configuration: bundled` using a clean profile.

Primary references:

- [Workspace data policy](https://developers.google.com/workspace/workspace-api-user-data-developer-policy)
- [Privacy policy verification requirements](https://support.google.com/cloud/answer/13806988?hl=en)
- [Sensitive scope verification](https://developers.google.com/identity/protocols/oauth2/production-readiness/sensitive-scope-verification)
- [Desktop OAuth](https://developers.google.com/identity/protocols/oauth2/native-app)
- [Docs scopes](https://developers.google.com/workspace/docs/api/auth)
