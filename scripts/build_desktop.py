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
args = [sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean', '--windowed',
        '--name', 'Proofpage', '--paths', str(root), '--collect-data', 'certifi',
        '--hidden-import', 'certifi', '--add-data', f'{root / "proofpage/static"}:proofpage/static',
        '--distpath', str(root / 'build/desktop'), '--workpath', str(root / 'build/pyinstaller'),
        '--specpath', str(root / 'build'), '--icon', str(root / 'desktop/icon.png')]
if system == 'darwin':
    args += ['--osx-bundle-identifier', 'app.proofpage.desktop']
args += [str(root / 'desktop/entry.py')]
build_env = dict(os.environ, PYINSTALLER_CONFIG_DIR=str(root / 'build/pyinstaller-cache'))
subprocess.run(args, check=True, cwd=root, env=build_env)
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
