# Two executables share one bundled runtime; the console helper keeps MCP stdout intact.
from pathlib import Path
import sys
import certifi
import tomllib

root = Path(SPECPATH).parent
version = tomllib.loads((root / 'pyproject.toml').read_text())['project']['version']
datas = [(str(root / 'proofpage/static'), 'proofpage/static'), (certifi.where(), 'certifi')]
gui = Analysis([str(root / 'desktop/entry.py')], pathex=[str(root)], datas=datas, hiddenimports=['certifi'], excludes=['playwright', 'fastapi', 'uvicorn', 'stripe', 'httpx'])
mcp = Analysis([str(root / 'desktop/mcp_entry.py')], pathex=[str(root)], datas=[], hiddenimports=['certifi'], excludes=['playwright', 'fastapi', 'uvicorn', 'stripe', 'httpx'])
app_exe = EXE(PYZ(gui.pure), gui.scripts, [], exclude_binaries=True, name='Proofpage', console=False, icon=str(root / 'desktop/icon.png'))
mcp_exe = EXE(PYZ(mcp.pure), mcp.scripts, [], exclude_binaries=True, name='Proofpage-MCP', console=True)
collection = COLLECT(app_exe, mcp_exe, gui.binaries, mcp.binaries, gui.datas, mcp.datas, name='Proofpage')
if sys.platform == 'darwin':
    app = BUNDLE(collection, name='Proofpage.app', icon=str(root / 'desktop/icon.png'), bundle_identifier='app.proofpage.desktop', info_plist={'CFBundleShortVersionString': version, 'CFBundleVersion': version})
