"""Sign, notarize, staple, and verify an app using existing Keychain credentials."""
import argparse
import json
from pathlib import Path
import subprocess
import tempfile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('app', type=Path)
parser.add_argument('--identity', required=True, help='Developer ID Application identity name or SHA-1')
parser.add_argument('--sign-only', action='store_true', help='Verify the signature without submitting to Apple; not a notarized release')
parser.add_argument('--profile', help='Existing notarytool Keychain profile name; never a password')
args = parser.parse_args()
if not args.sign_only and not args.profile:
    parser.error('--profile is required for notarization')
app = args.app.resolve()
if app.suffix != '.app' or not app.is_dir():
    parser.error('Expected a built .app directory')

def run(command):
    subprocess.run(command, check=True)

# Remove build-machine metadata from this generated app only, before signing.
run(['xattr', '-cr', str(app)])
magic = {b'\xfe\xed\xfa\xce', b'\xce\xfa\xed\xfe', b'\xfe\xed\xfa\xcf', b'\xcf\xfa\xed\xfe', b'\xca\xfe\xba\xbe', b'\xbe\xba\xfe\xca', b'\xca\xfe\xba\xbf'}
for path in sorted(app.rglob('*')):
    if path.is_symlink() or not path.is_file():
        continue
    with path.open('rb') as handle:
        macho = handle.read(4) in magic
    if macho:
        run(['codesign', '--force', '--options', 'runtime', '--timestamp', '--sign', args.identity, str(path)])
for path in sorted(app.rglob('*.framework'), key=lambda p: len(p.parts), reverse=True):
    if not path.is_symlink():
        run(['codesign', '--force', '--options', 'runtime', '--timestamp', '--sign', args.identity, str(path)])
run(['codesign', '--force', '--options', 'runtime', '--timestamp', '--sign', args.identity, str(app)])
run(['codesign', '--verify', '--deep', '--strict', '--verbose=2', str(app)])
if args.sign_only:
    print('Developer ID signing verified. Notarization and Gatekeeper release checks remain pending.')
    raise SystemExit(0)
with tempfile.TemporaryDirectory(prefix='proofpage-notarize-') as directory:
    archive = Path(directory) / 'Proofpage.zip'
    run(['ditto', '-c', '-k', '--sequesterRsrc', '--keepParent', str(app), str(archive)])
    import os
    keychain = os.environ.get('PROOFPAGE_NOTARY_KEYCHAIN')
    extra = ['--keychain', keychain] if keychain else []
    response = subprocess.run(['xcrun', 'notarytool', 'submit', str(archive), '--keychain-profile', args.profile, '--wait', '--output-format', 'json', *extra], check=True, capture_output=True, text=True)
    receipt = json.loads(response.stdout)
    print(json.dumps({'submission_id': receipt.get('id'), 'status': receipt.get('status')}))
    if receipt.get('status') != 'Accepted':
        raise SystemExit('Apple did not accept this app. Inspect the submission log before distributing it.')
run(['xcrun', 'stapler', 'staple', str(app)])
run(['xcrun', 'stapler', 'validate', str(app)])
run(['spctl', '--assess', '--type', 'execute', '--verbose=2', str(app)])
print('Developer ID signature, notarization, stapled ticket, and Gatekeeper assessment verified.')
