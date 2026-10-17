"""Exercise the published bundle in a fresh folder, including spaces in paths."""
from pathlib import Path
import os
import subprocess
import sys
import tempfile
import tomllib
import zipfile

root = Path(__file__).resolve().parents[1]
version = tomllib.loads((root / 'pyproject.toml').read_text())['project']['version']
with tempfile.TemporaryDirectory(prefix='proofpage setup ') as temp:
    temp = Path(temp)
    with zipfile.ZipFile(root / 'dist' / f'proofpage-{version}-local.zip') as archive:
        archive.extractall(temp)
    installer = temp / f'Proofpage-{version}' / 'scripts/install.py'
    target = temp / 'My Proofpage'
    command = [sys.executable, str(installer), '--directory', str(target)]
    subprocess.run(command, check=True, cwd=temp)
    launcher = target / ('proofpage.cmd' if os.name == 'nt' else 'proofpage')
    for args in (['--version'], ['doctor'], ['search', 'missing']):
        subprocess.run([str(launcher), *args], check=True, cwd=temp)
    result = subprocess.run(command, cwd=temp, capture_output=True, text=True)
    assert result.returncode != 0 and 'already exists' in result.stderr
    assert (target / 'data/proofpage.sqlite3').exists()
print('Fresh bundle install, CLI, paths with spaces, and overwrite refusal passed.')
