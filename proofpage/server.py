from pathlib import Path
import base64
import json
import secrets
import re
import socketserver
import threading
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from .assets import STATIC, read_asset
from .core import MAX_BYTES, Store, import_file, preview
from .imports import create_profile
from .watch import create_watch, scan_watch
from . import training, crawl, models, agent, claims


class LocalHTTPServer(ThreadingHTTPServer):
    def server_bind(self):
        # HTTPServer otherwise performs reverse DNS, which can stall offline Macs.
        socketserver.TCPServer.server_bind(self)
        self.server_name = 'localhost'
        self.server_port = self.server_address[1]


def serve(store=None, port=8765, open_browser=False, on_ready=None):
    store = store or Store()
    token = secrets.token_urlsafe(32)
    companion = {}
    companion_lock = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            pass

        def send(self, status, value, content_type='application/json'):
            body = value if isinstance(value, bytes) else json.dumps(value).encode() if content_type == 'application/json' else value.encode()
            self.send_response(status)
            textual = content_type.startswith('text/') or content_type in ('application/json', 'image/svg+xml')
            self.send_header('Content-Type', content_type + ('; charset=utf-8' if textual else ''))
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Security-Policy', "default-src 'self'; img-src 'self' blob:; script-src 'self'; style-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
            if getattr(self, 'companion_origin', None):
                self.send_header('Access-Control-Allow-Origin', self.companion_origin)
                self.send_header('Vary', 'Origin')
                self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
                self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
            self.end_headers()
            self.wfile.write(body)

        def authorized(self):
            if self.headers.get('Host') != f'127.0.0.1:{port}':
                self.send(403, {'error': 'Invalid host.'})
                return False
            origin = self.headers.get('Origin')
            if origin and origin != f'http://127.0.0.1:{port}':
                self.send(403, {'error': 'Invalid origin.'})
                return False
            if self.headers.get('Sec-Fetch-Site') == 'cross-site':
                self.send(403, {'error': 'Cross-site access denied.'})
                return False
            return True

        def extension_request(self):
            origin = self.headers.get('Origin', '')
            if (self.headers.get('Host') != f'127.0.0.1:{port}' or
                    not re.fullmatch(r'chrome-extension://[a-p]{32}', origin)):
                self.send(403, {'error': 'Extension origin required.'})
                return False
            self.companion_origin = origin
            return True

        def do_OPTIONS(self):
            if self.path not in ('/api/companion/pair', '/api/companion/import', '/api/companion/import-file', '/api/companion/import-url'):
                return self.send(403, {'error': 'Not allowed.'})
            if self.extension_request():
                self.send(200, {})

        def companion_post(self):
            if not self.extension_request():
                return
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= (12 * 1024 * 1024 if self.path == '/api/companion/import-file' else 3000000):
                    raise ValueError('Page exceeds the import limit.')
                data = json.loads(self.rfile.read(length))
                if not isinstance(data, dict):
                    raise ValueError('Expected a JSON object.')
                with companion_lock:
                    if self.path == '/api/companion/pair':
                        companion['attempts'] = companion.get('attempts', 0) + 1
                        if (companion['attempts'] > 10 or time.time() > companion.get('expires', 0) or
                                not secrets.compare_digest(str(data.get('code', '')), companion.get('code', '!'))):
                            return self.send(403, {'error': 'Code expired or incorrect. Create a new code in Settings.'})
                        companion.pop('code', None)
                        companion['expires'] = 0
                        companion['origin'] = self.companion_origin
                        companion['token'] = secrets.token_urlsafe(32)
                        return self.send(200, {'token': companion['token']})
                    if (companion.get('origin') != self.companion_origin or
                            not secrets.compare_digest(self.headers.get('Authorization', ''), 'Bearer ' + companion.get('token', '!'))):
                        return self.send(401, {'error': 'Connect the companion again in Proofpage Settings.'})
                    if data.get('reviewed') is not True:
                        raise ValueError('Review this page before importing.')
                    if self.path == '/api/companion/import-url':
                        from .core import validate_url
                        url = validate_url(str(data.get('url', '')))
                        source = store.source('Saved web file', 'web', url)
                        result = store.collect(source['id'])
                        return self.send(200, result)
                    from .adapters import parse_entry
                    from .imports import import_archive
                    filename = 'page.json'
                    if self.path == '/api/companion/import-file':
                        from .media import EXTENSIONS
                        filename = str(data.get('filename', ''))
                        if Path(filename).name != filename or Path(filename).suffix.lower() not in EXTENSIONS:
                            raise ValueError('Choose a PNG, JPEG, WebP or PDF file.')
                        payload = base64.b64decode(data.get('data', ''), validate=True)
                    else:
                        capture = data.get('capture')
                        if not isinstance(capture, dict) or capture.get('proofpage_capture') != 'visible-text-v1':
                            raise ValueError('Expected a visible page capture.')
                        payload = json.dumps(capture).encode()
                    # Validate original bytes before creating a source or persisting anything.
                    parse_entry(filename, payload)
                    profiles = store.rows("SELECT id FROM import_profiles WHERE provider='browser-companion' AND account='local'")
                    profile_id = profiles[0]['id'] if profiles else create_profile(store, 'Browser pages', 'browser-companion', 'local')['id']
                    result = import_archive(store, filename, payload, [filename], profile_id)
                    return self.send(200, result)
            except (ValueError, KeyError, TypeError, OSError) as exc:
                return self.send(400, {'error': str(exc)})

        def do_GET(self):
            if not self.authorized():
                return
            url = urllib.parse.urlsplit(self.path)
            path = url.path
            try:
                if path == '/':
                    return self.send(200, (STATIC / 'index.html').read_text(encoding='utf-8'), 'text/html')
                if not path.startswith('/api/'):
                    asset = read_asset(path)
                    return self.send(200, *asset) if asset else self.send(404, {'error': 'Not found.'})
                if path == '/api/session':
                    return self.send(200, {'token': token})
                if self.headers.get('Authorization') != 'Bearer ' + token:
                    return self.send(401, {'error': 'Local session required.'})
                if path == '/api/google-docs':
                    from .google_docs import status
                    return self.send(200, status(store))
                if path == '/api/updates':
                    from .updates import check
                    return self.send(200, check())
                if path == '/api/mcp-setup':
                    from .mcp_setup import setup
                    return self.send(200, setup(store))
                if path == '/api/assistant-kit':
                    from .mcp_setup import kit
                    client = urllib.parse.parse_qs(url.query).get('client', [''])[0]
                    return self.send(200, kit(store, client), 'application/zip')
                query = urllib.parse.parse_qs(url.query)
                from .service import get
                return self.send(*get(store, path, query))
            except (ValueError, OSError) as exc:
                self.send(400, {'error': str(exc)})

        def do_POST(self):
            if self.path in ('/api/companion/pair', '/api/companion/import', '/api/companion/import-file', '/api/companion/import-url'):
                return self.companion_post()
            if not self.authorized():
                return
            if self.headers.get('Authorization') != 'Bearer ' + token:
                return self.send(401, {'error': 'Local session required.'})
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if length < 0 or length > MAX_BYTES * 2:
                    raise ValueError('Request exceeds import limit.')
                data = json.loads(self.rfile.read(length))
                if not isinstance(data, dict):
                    raise ValueError('Expected a JSON object.')
                if self.path == '/api/mcp-check':
                    from .mcp_setup import check
                    return self.send(200, check(store))
                if self.path.startswith('/api/google-docs/'):
                    from . import google_docs
                    operation = self.path.rsplit('/', 1)[1]
                    try:
                        if operation == 'select': result = google_docs.select(store, data.get('document'), data.get('interval', 0), data.get('owner_permission'))
                        elif operation == 'sync': result = google_docs.sync(store, data.get('document'))
                        elif operation in ('connect', 'disconnect'): result = getattr(google_docs, operation)(store)
                        else: raise ValueError('Unknown operation.')
                        return self.send(200, result)
                    except google_docs.GoogleDocsError as exc:
                        return self.send(400, {'error': str(exc)})
                    except Exception:
                        return self.send(400, {'error': 'Google Docs operation did not complete. Check setup, access, and OS credential vault; previous evidence is preserved.'})
                if self.path == '/api/companion-code':
                    with companion_lock:
                        companion['code'] = secrets.token_hex(6).upper()
                        companion['expires'] = time.time() + 300
                        companion['attempts'] = 0
                        return self.send(200, {'code': companion['code'], 'port': port})
                if self.path == '/api/companion-revoke':
                    with companion_lock:
                        companion.clear()
                    return self.send(200, {'revoked': True})
                from .service import post
                return self.send(*post(store, self.path, data))
            except (ValueError, KeyError, TypeError, OSError) as exc:
                self.send(400, {'error': str(exc)})

    stop = threading.Event()

    def scheduler():
        pending = {}
        last_watch = {}
        last_anchor_check = 0
        with ThreadPoolExecutor(max_workers=4, thread_name_prefix='proofpage') as pool:
            while not stop.wait(5):
                for key, future in list(pending.items()):
                    if future.done():
                        try:
                            future.result()
                        except Exception as exc:
                            if key.startswith('web:'):
                                with store.db() as db:
                                    db.execute('UPDATE sources SET next_run=? WHERE id=?', (time.time() + 60, key[4:]))
                        del pending[key]
                jobs = [('web:' + s['id'], store.collect, s['id']) for s in store.rows("SELECT id FROM sources WHERE kind='web' AND interval_seconds>0 AND next_run<=? ORDER BY next_run", (time.time(),))]
                jobs += [('crawl:' + c['id'], lambda cid: crawl.step_job(store, cid), c['id']) for c in store.rows("SELECT id FROM crawl_jobs WHERE state IN ('queued','running') AND next_attempt<=? ORDER BY updated_at", (time.time(),))]
                jobs += [('claim:' + c['id'], lambda cid: claims.step(store, cid), c['id']) for c in store.rows("SELECT id FROM claim_checks WHERE state='queued' AND next_attempt<=? AND lease_until<=? ORDER BY created_at", (time.time(), time.time()))]
                from . import google_docs
                jobs += [('google:' + d['document_id'], lambda did: google_docs.sync(store, did), d['document_id']) for d in store.rows('SELECT document_id FROM google_documents WHERE interval_seconds>0 AND next_run<=?', (time.time(),))]
                watches = sorted(store.rows('SELECT id FROM watches WHERE enabled=1'), key=lambda w: last_watch.get(w['id'], 0))
                jobs += [('watch:' + w['id'], lambda wid: scan_watch(store, wid), w['id']) for w in watches]
                if time.time() - last_anchor_check > 600 and 'anchor' not in pending:
                    # Anchoring is off unless configured, and runs at most daily; this only checks.
                    from .receipts import anchor
                    last_anchor_check = time.time()
                    pending['anchor'] = pool.submit(anchor, store)
                for key, operation, identifier in jobs:
                    if len(pending) >= 8:
                        break
                    if key not in pending:
                        pending[key] = pool.submit(operation, identifier)
                        if key.startswith('watch:'):
                            last_watch[identifier] = time.time()

    server = LocalHTTPServer(('127.0.0.1', port), Handler)
    port = server.server_address[1]
    if on_ready is not None:
        on_ready(server)
    if open_browser:
        import webbrowser
        webbrowser.open(f'http://127.0.0.1:{server.server_address[1]}')
    scheduler_thread = threading.Thread(target=scheduler, daemon=True)
    scheduler_thread.start()
    print(f'Proofpage is running at http://127.0.0.1:{port}', flush=True)
    try:
        server.serve_forever()
    finally:
        stop.set()
        server.server_close()
        scheduler_thread.join()
