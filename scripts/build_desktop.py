"""Build a platform-native, Python-included desktop download."""
from pathlib import Path
import platform
import os
import shutil
import subprocess
import sys
import tomllib

root = Path(__file__).resolve().parents[1]
version = tomllib.loads((root / 'pyproject.toml').read_text())['project']['version']
system = platform.system().lower()
arch = platform.machine().lower().replace('amd64', 'x86_64').replace('aarch64', 'arm64')
if '--package-only' not in sys.argv:
    args = [sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean',
            '--distpath', str(root / 'build/desktop'), '--workpath', str(root / 'build/pyinstaller'),
            str(root / 'desktop/Proofpage.spec')]
    build_env = dict(os.environ, PYINSTALLER_CONFIG_DIR=str(root / 'build/pyinstaller-cache'))
    subprocess.run(args, check=True, cwd=root, env=build_env)
    if system == 'darwin':
        identity = os.environ.get('PROOFPAGE_SIGN_IDENTITY')
        profile = os.environ.get('PROOFPAGE_NOTARY_PROFILE')
        if bool(identity) != bool(profile):
            raise SystemExit('Both PROOFPAGE_SIGN_IDENTITY and PROOFPAGE_NOTARY_PROFILE are required for signed builds.')
        if identity:
            subprocess.run([sys.executable, str(root / 'scripts/sign_macos.py'), str(root / 'build/desktop/Proofpage.app'), '--identity', identity, '--profile', profile], check=True)
        else:
            subprocess.run(['xattr', '-cr', str(root / 'build/desktop/Proofpage.app')], check=True)
            subprocess.run(['codesign', '--force', '--deep', '--sign', '-', str(root / 'build/desktop/Proofpage.app')], check=True)
output = root / 'dist'
output.mkdir(exist_ok=True)
name = f'Proofpage-{version}-{system}-{arch}'
if system == 'darwin':
    # ditto preserves .app symlinks, permissions, and metadata.
    subprocess.run(['ditto', '-c', '-k', '--sequesterRsrc', '--keepParent', str(root / 'build/desktop/Proofpage.app'), str(output / (name + '.zip'))], check=True)
elif system == 'windows':
    shutil.copy(root / 'desktop/START-HERE.txt', root / 'build/desktop/Proofpage/START-HERE.txt')
    shutil.make_archive(str(output / name), 'zip', root / 'build/desktop', 'Proofpage')
else:
    shutil.copy(root / 'desktop/START-HERE.txt', root / 'build/desktop/Proofpage/START-HERE.txt')
    shutil.make_archive(str(output / name), 'gztar', root / 'build/desktop', 'Proofpage')
print(f'Built {name}')
