# Signing and notarization

Signing workflows are explicit, manual releases. Ordinary CI produces unsigned previews. A successful build is not proof of signing or notarization. Do not describe a release as signed until its final archive has been verified.

## Mac on the developer's computer

Use the existing **Developer ID Application** certificate with its private key in Keychain. Apple Development certificates cannot sign public distribution builds. Do not export private keys into the repository.

Create a new named notarization profile if the old name is unknown:

```sh
xcrun notarytool store-credentials Proofpage
```

Enter the Apple Developer account, its team ID, and an Apple app-specific password at the prompts. These stay in Keychain; do not paste them into a chat, issue, or source file. Create an app-specific password through your Apple Account security settings if needed.

Build using the identity name or fingerprint reported by `security find-identity -v -p codesigning`:

```sh
PROOFPAGE_SIGN_IDENTITY='Developer ID Application: Your Name (TEAMID)' \
PROOFPAGE_NOTARY_PROFILE=Proofpage \
python3 scripts/build_desktop.py
```

The build signs all bundled Mach-O executables and libraries (including the console MCP helper), enables hardened runtime, submits the app to Apple, requires Accepted, staples the ticket, and requires both ticket validation and Gatekeeper assessment before packaging. An existing built app can be processed with `scripts/sign_macos.py APP --identity IDENTITY --profile Proofpage`, followed by `scripts/build_desktop.py --package-only`.

`--sign-only` validates Developer ID signing but deliberately does **not** claim notarization. It is for diagnostics, not warning-free distribution.

## Mac through GitHub Actions

Create a GitHub environment named `release-signing`, restricted to trusted release branches, ideally with a required reviewer. In that environment configure:

| Type | Name | Value |
| --- | --- | --- |
| Secret | `APPLE_CERTIFICATE_P12_BASE64` | Base64 of a password-protected exported Developer ID certificate **and private key** |
| Secret | `APPLE_CERTIFICATE_PASSWORD` | Password protecting that P12 |
| Secret | `APPLE_ID` | Apple Developer login |
| Secret | `APPLE_APP_SPECIFIC_PASSWORD` | Apple app-specific password |
| Variable | `APPLE_TEAM_ID` | Developer team identifier |
| Variable | `APPLE_SIGN_IDENTITY` | Developer ID Application identity name or fingerprint |

Only export/upload the private key if you choose CI signing; local signing does not require it to leave Keychain. Run **sign-and-notarize-macos** manually from a trusted commit. It imports credentials into a disposable runner Keychain and deletes it after the job. Successful outputs are artifacts, not automatically published releases. Both Mac architectures are built independently.

## Windows through Azure Artifact Signing

An Azure subscription and a **Public Trust** Artifact Signing account with approved identity validation and a certificate profile are required. Account creation and billing require the owner's action. No Windows signing service is assumed to exist.

Create an Entra application with a GitHub OIDC federated credential for:

```text
repo:Mehxeo/Proofpage-OpenSource:environment:release-signing
```

Use audience `api://AzureADTokenExchange`, and grant only the **Artifact Signing Certificate Profile Signer** role for the selected profile. Configure these GitHub `release-signing` environment variables:

- `AZURE_CLIENT_ID`
- `AZURE_TENANT_ID`
- `AZURE_SUBSCRIPTION_ID`
- `AZURE_SIGNING_ENDPOINT` (the endpoint for the account's region)
- `AZURE_SIGNING_ACCOUNT`
- `AZURE_CERTIFICATE_PROFILE`

Run **sign-windows-release** from a trusted commit. It signs and timestamps executable/library files, verifies Authenticode on both launchers, tests the packaged GUI and MCP connection, and repackages the signed files. It uses OIDC, so no Azure password or client secret is needed in GitHub. Review the resulting artifact before publishing it.

Signing establishes a verified publisher; it cannot guarantee that Windows SmartScreen never warns about a new download. Reputation and local security policies still apply. Apple can also retain the ordinary first-download confirmation even for accepted, stapled apps.

Sources: [Apple notarization](https://developer.apple.com/documentation/security/notarizing-macos-software-before-distribution), [Azure signing action](https://github.com/Azure/artifact-signing-action), [Microsoft SmartScreen reputation](https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/smartscreen-reputation).
