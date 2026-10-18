# Google Docs, remote MCP, and client skills

Available in 0.5.0, MIT licensed. Remote HTTP dependencies are optional; local core features
remain dependency-free. A working local test is not proof that a third-party
account or public deployment is connected.

## Google Docs

The Google project is now **In production**, and its branding is verified and
published. Read-only Docs scope verification is still being prepared; that review
must finish before shared sign-in can be offered without an unverified warning
or temporary user cap. Production status alone is not scope approval.

The next desktop build supports bundled Google sign-in so normal users do not
need their own Google Cloud project or JSON file. It is being checked in a
verification build first. The current stable 0.5.0 download still needs the
configuration below. Public install instructions will change when the shared
client is approved and that desktop update is released.

### Source builds and custom clients

The 0.5.0 desktop downloads include the Google OAuth library and OS-vault support.
For a source install, use `python -m pip install -e '.[google]'`.
In your Google Cloud project enable the Google Docs API, configure the OAuth
consent screen/test users, and create an OAuth client of type **Desktop app**.
Download its JSON outside the repository and set `PROOFPAGE_GOOGLE_CLIENT_FILE`
to its absolute path when starting Proofpage. Alternatively, place it at
`~/.config/proofpage/google-oauth.json` for automatic discovery. Never commit this file or paste
credentials into prompts. Public distribution may require Google's verification.

In Business context, click Connect Google Docs. Complete authorization in the
system browser. The connector uses authorization code + PKCE with a loopback
callback, via Google's OAuth library. The requested `documents.readonly` scope
can read the account's Docs; the application only fetches IDs you explicitly
select. This is not per-file OAuth permission or a Drive-wide crawler.

Paste a document URL, choose Manual/Hourly/Six-hourly/Daily, save the selection,
confirm owner permission for local personal-context snapshots, and click Sync. The content appears in the library for profile attachment and
review. Tables and nested tabs are read. Extracted text excludes images, comments,
headers/footers and suggested edits; original returned API JSON is preserved.
Up to 8 MiB is accepted. Failed/empty responses preserve previous evidence.
Automatic schedules require the app/server to remain open. Changed revisions
invalidate approved business context rather than silently altering it.

Google API snapshots are for personal context in this release; the Training
workflow rejects them. Google Workspace data cannot be used to train shared or
general-purpose models. Only retain snapshots with express owner permission.
See [Google Workspace data policy](https://developers.google.com/workspace/workspace-api-user-data-developer-policy)
and [Google API content terms](https://developers.google.com/terms#section_5_content).

Tokens are stored only in an OS vault: macOS Keychain, Windows Credential Locker,
or Linux Secret Service. The connector fails closed when those backends are
unavailable; no plaintext fallback. Credentials are scoped to the workspace path
and are excluded from database backups. Moving a workspace requires reconnecting.
Disconnect removes local credentials and pauses schedules; previously imported
evidence stays. Revoke the account grant in Google permissions separately.

CLI equivalents:

```sh
proofpage --home ./workspace google-docs status
proofpage --home ./workspace google-docs connect
proofpage --home ./workspace google-docs select --document DOC_ID --interval 3600 --owner-permission
proofpage --home ./workspace google-docs sync --document DOC_ID
proofpage --home ./workspace google-docs disconnect
```

Google auth is local-only. Hosted workspace routes cannot trigger desktop consent
or access the host's OS vault. A custom client selected through the environment
or the existing home-folder configuration takes precedence over bundled metadata.
`PROOFPAGE_CONFIG_DIRECTORY` can select a separate configuration directory for a
portable profile; the default remains `~/.config/proofpage`. User authorization
is still tied to the workspace path in the OS vault.
Moving the OAuth project to Production does not retrofit a client into existing
0.5.0 downloads. Shared sign-in needs the updated desktop build as well as Google's
scope approval.

### Building official preconfigured downloads

Release maintainers can set `PROOFPAGE_DESKTOP_GOOGLE_CLIENT_FILE` to their Google
**Desktop app** client JSON when running `scripts/build_desktop.py`. They may also
run the following on an extracted CI build, **before code signing**:

```sh
python scripts/configure_desktop_google.py /path/to/Proofpage.app --client-file /private/path/native-client.json
```

Use the extracted `Proofpage` directory on Windows/Linux. The helper validates
Google endpoints and loopback redirects, rejects web/service-account configs,
rejects user tokens/private keys, and copies only native app metadata. It is
idempotent for an identical client and refuses replacing a different identity.
Never commit the client JSON or place it in source bundles. Native app metadata
identifies the app and is recoverable from its distributable; it is not a user's
authorization. PKCE protects each authorization exchange, and user tokens stay
in the OS vault. Redistributed forks should configure their own Google app.

Finish with signature/notarization and packaged checks using a clean home folder;
the report must show `google_configuration: bundled`. That proves the release is
not accidentally relying on the maintainer's home-folder setup file. Review
builds do not imply Google's approval, and unverified sign-in is not promoted to
stable users.

## Remote MCP for web assistants

Install `python -m pip install -e '.[mcp-http]'`. Configure an OAuth authorization
server that supports the intended client's discovery/registration flow, PKCE,
and JWT access tokens with the resource URL as audience. Your provider must
issue the `proofpage:read` scope and a stable subject for your account.
No authorization provider, public host or client registration is provisioned
by this repository. This service is the OAuth **resource server**, not a login
provider. Using a generic OIDC provider without compatible client registration
is insufficient for some web assistants.

```sh
export PROOFPAGE_MCP_URL=https://mcp.your-domain.example/mcp
export PROOFPAGE_MCP_ISSUER=https://your-issuer.example/
export PROOFPAGE_MCP_JWKS_URL=https://your-issuer.example/.well-known/jwks.json
export PROOFPAGE_MCP_SUBJECT=YOUR_ACCOUNT_SUBJECT
proofpage --home /path/to/dedicated-workspace mcp-http --port 8910
```

These are deployment identifiers, not tokens. Run an HTTPS reverse proxy in front
of `127.0.0.1:8910`, preserving the public Host and paths including
`/.well-known/oauth-protected-resource/mcp`. Configure request limits and avoid
logging Authorization headers. Do not expose the desktop UI port as a substitute.
Use a dedicated workspace containing only material you intend to share.

The official MCP SDK handles Streamable HTTP, initialization, tools, resource
metadata, and authentication challenges. Tokens require RS256/ES256 signatures
from the configured JWKS, exact issuer, matching resource audience, expiry,
`proofpage:read`, and the exact configured subject. Missing/wrong tokens fail.
Only five read tools are exposed: business profile listing, approved business
context, bounded evidence search, recorded-context replay, and run listing.
No collection, approval, filesystem paths, credential changes or training writes.
This is a single-owner workspace server, not a multi-tenant team service.

Add the **public** URL in a web assistant's supported custom connector flow and
complete its OAuth consent. Feature availability and admin restrictions vary by
client/account. Verify by listing profiles and retrieving a known approved
profile; never report success based on configuration alone. This supplies context
to conversations/tools, not automatic account memory or weight personalization.

The existing `/agent` hosted bridge remains separate and uses Proofpage agent
keys; it is not a substitute for this OAuth connector.

## Skills that install without clobbering work

```sh
proofpage install-skill --project /path/to/project --client codex
proofpage install-skill --project /path/to/project --client claude
```

The installer writes `.agents/skills/proofpage/SKILL.md` or
`.claude/skills/proofpage/SKILL.md`, recognizes an identical existing installation,
and refuses to overwrite custom content. A skill provides workflow guidance;
it does not establish MCP connectivity. Use Agent access's configuration and
Test MCP connection separately. The shipped skill names only existing tools.

## Verification and boundaries

Automated tests exercise the real stdio server through the official MCP client:
initialize, discovery, record/replay, approved context, drift and invalid arguments.
HTTP tests exercise the official SDK with signed fixture JWTs: missing/expired/
wrong-subject/wrong-audience/wrong-scope tokens, allowed reads, absent write tools,
and cross-origin denial. Google fixtures cover multi-tab/table extraction,
selection, deduplication, revision drift and failed refresh preservation.

Live Google account consent and ChatGPT/Claude connector installation still
require a configured OAuth project, public deployment, and user consent. Tests
with fixture tokens do not verify your provider's registration or consent flow.

Primary references:
- https://developers.google.com/identity/protocols/oauth2/native-app
- https://developers.google.com/workspace/docs/api/reference/rest/v1/documents/get
- https://github.com/modelcontextprotocol/python-sdk
- https://help.openai.com/en/articles/12584461-developer-mode-and-full-mcp-connectors-in-chatgpt
- https://support.claude.com/en/articles/11175166-get-started-with-custom-connectors-using-remote-mcp
