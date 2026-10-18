"""Private lifecycle bridge for the Tauri window and bundled local engine."""
import json
import os
import sys
import threading
from pathlib import Path
from urllib.request import Request, urlopen
from .core import Store
from .launcher import WorkspaceLock
from .server import serve


def main():
    report = Path(sys.argv[2]).resolve() if len(sys.argv) == 3 and sys.argv[1] == '--smoke-test' else None
    folder = report.parent / 'workspace' if report else Path(os.environ.get('PROOFPAGE_DESKTOP_HOME', str(Path.home() / 'Proofpage'))).expanduser().resolve()
    folder.mkdir(parents=True, exist_ok=True, mode=0o700)
    for name in ('data', 'backups', 'exports'):
        (folder / name).mkdir(exist_ok=True, mode=0o700)
    log = (folder / 'launcher.log').open('a', encoding='utf-8', buffering=1)
    sys.stderr = log
    lock = WorkspaceLock(folder / 'data')
    store = Store(folder / 'data')

    def ready(server):
        address = f'http://127.0.0.1:{server.server_address[1]}'
        print('PROOFPAGE_READY ' + address, flush=True)
        def control():
            tested = False
            try:
                for line in sys.stdin:
                    if line.strip() == 'quit': break
                    if line.strip() == 'smoke' and report and not tested:
                        tested = True
                        with urlopen(address + '/api/session', timeout=10) as response:
                            token = json.load(response)['token']
                        def get(route):
                            with urlopen(Request(address + '/api/' + route, headers={'Authorization': 'Bearer ' + token}), timeout=20) as response:
                                return json.load(response)
                        state = get('state')
                        connection = get('mcp-setup')
                        assert 'proofpage' in connection['skill'].lower()
                        from .mcp_setup import check
                        assert check(store)['ok']
                        from . import verify
                        assert Path(verify.__file__).with_suffix('.py').is_file()
                        # Exercise the bundled OAuth imports, not the build machine's Python.
                        from google_auth_oauthlib.flow import InstalledAppFlow
                        from google.oauth2.credentials import Credentials
                        from . import google_docs
                        import importlib
                        backend = 'macOS' if sys.platform == 'darwin' else 'Windows' if sys.platform == 'win32' else 'SecretService'
                        importlib.import_module('keyring.backends.' + backend)
                        assert google_docs.status(store)['installed']
                        report.write_text(json.dumps({'ready': True, 'gui': True, 'shell': 'tauri', 'records': len(state['items']),
                                                      'offline_verifier': True, 'google_oauth': True, 'mcp': connection['config']['mcpServers']['proofpage']}))
                        print('PROOFPAGE_SMOKE_OK', flush=True)
            except Exception:
                import traceback
                traceback.print_exc()
                if report: report.write_text(json.dumps({'ready': False, 'error': traceback.format_exc()}))
            finally:
                server.shutdown()
        threading.Thread(target=control, daemon=True).start()
    try:
        serve(store, port=0 if report else int(os.environ.get('PROOFPAGE_DESKTOP_PORT', '8765')), on_ready=ready)
    finally:
        lock.close()
        log.close()


if __name__ == '__main__':
    main()
