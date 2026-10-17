"""Package a built wheel with the guided installer and quick-start documents."""
from pathlib import Path
import tomllib
import zipfile

root = Path(__file__).resolve().parents[1]
version = tomllib.loads((root / 'pyproject.toml').read_text())['project']['version']
wheel = root / 'dist' / f'proofpage-{version}-py3-none-any.whl'
if not wheel.exists():
    raise SystemExit('Build the wheel first: python -m build')
output = root / 'dist' / f'proofpage-{version}-local.zip'
files = [wheel, root / 'scripts/install.py', root / 'README.md', root / 'LICENSE']
files += sorted((root / 'docs').rglob('*'))
with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:
    for path in files:
        if path.is_file():
            name = path.name if path == wheel else path.relative_to(root).as_posix()
            archive.write(path, f'Proofpage-{version}/{name}')
print(output)
