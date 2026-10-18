# Two executables share one bundled runtime; the console helper keeps MCP stdout intact.
from pathlib import Path
import sys
import certifi
from PyInstaller.utils.hooks import collect_all
media_datas, media_binaries, media_hidden = [], [], []
for package in ("rapidocr", "pypdfium2", "pypdfium2_raw", "onnxruntime"):
    d, b, h = collect_all(package)
    media_datas += d
    media_binaries += b
    media_hidden += h
import tomllib

root = Path(SPECPATH).parent
version = tomllib.loads((root / 'pyproject.toml').read_text())['project']['version']
# verify.py ships as source: proof bundles and WACZ exports embed it as the standalone offline verifier.
datas = [(str(root / 'proofpage/static'), 'proofpage/static'), (str(root / 'proofpage/verify.py'), 'proofpage'), (certifi.where(), 'certifi')]
gui = Analysis([str(root / 'desktop/entry.py')], pathex=[str(root)], datas=datas + media_datas, binaries=media_binaries, hiddenimports=['certifi'] + media_hidden, excludes=['playwright', 'fastapi', 'uvicorn', 'stripe', 'httpx'])
mcp = Analysis([str(root / 'desktop/mcp_entry.py')], pathex=[str(root)], datas=media_datas, binaries=media_binaries, hiddenimports=['certifi'] + media_hidden, excludes=['playwright', 'fastapi', 'uvicorn', 'stripe', 'httpx'])
app_exe = EXE(PYZ(gui.pure), gui.scripts, [], exclude_binaries=True, name='Proofpage', console=False, icon=str(root / 'desktop/icon.png'))
mcp_exe = EXE(PYZ(mcp.pure), mcp.scripts, [], exclude_binaries=True, name='Proofpage-MCP', console=True)
collection = COLLECT(app_exe, mcp_exe, gui.binaries, mcp.binaries, gui.datas, mcp.datas, name='Proofpage')
if sys.platform == 'darwin':
    app = BUNDLE(collection, name='Proofpage.app', icon=str(root / 'desktop/icon.png'), bundle_identifier='app.proofpage.desktop', info_plist={'CFBundleShortVersionString': version, 'CFBundleVersion': version})
