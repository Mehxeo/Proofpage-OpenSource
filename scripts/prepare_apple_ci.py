"""Import credentials into an ephemeral CI Keychain without logging secret values."""
import base64
import os
from pathlib import Path
import secrets
import subprocess

required = ['APPLE_CERTIFICATE_P12_BASE64', 'APPLE_CERTIFICATE_PASSWORD', 'APPLE_ID', 'APPLE_APP_SPECIFIC_PASSWORD', 'APPLE_TEAM_ID', 'APPLE_SIGN_IDENTITY']
for name in required:
    if not os.environ.get(name):
        raise SystemExit('Missing signing setting: ' + name)
folder = Path(os.environ['RUNNER_TEMP'])
keychain = folder / 'proofpage-signing.keychain-db'
certificate = folder / 'proofpage-signing.p12'
certificate.write_bytes(base64.b64decode(os.environ['APPLE_CERTIFICATE_P12_BASE64'], validate=True))
certificate.chmod(0o600)
password = secrets.token_urlsafe(32)

def run(args):
    result = subprocess.run(args, capture_output=True)
    if result.returncode:
        raise SystemExit('Apple signing credential setup failed; verify the configured certificate and account. Secret command arguments were withheld.')

try:
    run(['security', 'create-keychain', '-p', password, str(keychain)])
    run(['security', 'set-keychain-settings', '-lut', '21600', str(keychain)])
    run(['security', 'unlock-keychain', '-p', password, str(keychain)])
    run(['security', 'import', str(certificate), '-P', os.environ['APPLE_CERTIFICATE_PASSWORD'], '-k', str(keychain), '-T', '/usr/bin/codesign', '-T', '/usr/bin/security'])
    run(['security', 'set-key-partition-list', '-S', 'apple-tool:,apple:', '-k', password, str(keychain)])
    # This script runs only on a disposable hosted runner.
    run(['security', 'list-keychains', '-d', 'user', '-s', str(keychain)])
    run(['xcrun', 'notarytool', 'store-credentials', 'proofpage-ci', '--apple-id', os.environ['APPLE_ID'], '--password', os.environ['APPLE_APP_SPECIFIC_PASSWORD'], '--team-id', os.environ['APPLE_TEAM_ID'], '--keychain', str(keychain)])
finally:
    certificate.unlink(missing_ok=True)
print('Ephemeral signing Keychain and notarization profile prepared.')
