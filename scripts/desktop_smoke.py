"""Launch the packaged GUI and check its real HTTP API, without a Python child."""
import json
from pathlib import Path
import platform
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
system = platform.system()
if system == 'Darwin':
    app = root / 'build/desktop/Proofpage.app/Contents/MacOS/Proofpage'
else:
    app = root / 'build/desktop/Proofpage' / ('Proofpage.exe' if system == 'Windows' else 'Proofpage')
with tempfile.TemporaryDirectory(prefix='proofpage-desktop-') as directory:
    report = Path(directory) / 'result.json'
    try:
        result = subprocess.run([str(app), '--smoke-test', str(report)], cwd=directory, timeout=90, capture_output=True, text=True)
    finally:
        log = Path.home() / 'Proofpage/launcher.log'
        if log.exists():
            print(log.read_text(encoding='utf-8', errors='replace')[-12000:])
        if report.exists():
            print(report.read_text())
    if result.returncode or not report.exists():
        raise RuntimeError(f'Desktop failed: {result.returncode}\n{result.stdout}\n{result.stderr}')
    data = json.loads(report.read_text())
    assert data['ready'] and data['gui'], data
    assert (report.parent / 'workspace/data/proofpage.sqlite3').exists()
    print('Packaged native GUI, bundled Python, SQLite, HTTP API, and shutdown passed.')
