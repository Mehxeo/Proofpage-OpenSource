import base64
import json
import secrets
import socketserver
import threading
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .core import MAX_BYTES, Store, import_file, preview
from .imports import create_profile
from .watch import create_watch, scan_watch
from . import training, crawl, models, agent

STATIC = Path(__file__).resolve().parent / 'static'


class LocalHTTPServer(ThreadingHTTPServer):
    def server_bind(self):
        # HTTPServer otherwise performs reverse DNS, which can stall offline Macs.
        socketserver.TCPServer.server_bind(self)
        self.server_name = 'localhost'
        self.server_port = self.server_address[1]


def serve(store=None, port=8765, open_browser=False, on_ready=None):
    store = store or Store()
    token = secrets.token_urlsafe(32)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            pass

        def send(self, status, value, content_type='application/json'):
            body = value if isinstance(value, bytes) else json.dumps(value).encode() if content_type == 'application/json' else value.encode()
            self.send_response(status)
            self.send_header('Content-Type', content_type + '; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
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

        def do_GET(self):
            if not self.authorized():
                return
            url = urllib.parse.urlsplit(self.path)
            path = url.path
            try:
                if path in ('/', '/app.js', '/workbench.js', '/style.css'):
                    name = 'index.html' if path == '/' else path[1:]
                    types = {'index.html': 'text/html', 'app.js': 'text/javascript', 'workbench.js': 'text/javascript', 'style.css': 'text/css'}
                    return self.send(200, (STATIC / name).read_text(encoding='utf-8'), types[name])
                if path == '/api/session':
                    return self.send(200, {'token': token})
                if self.headers.get('Authorization') != 'Bearer ' + token:
                    return self.send(401, {'error': 'Local session required.'})
                query = urllib.parse.parse_qs(url.query)
                from .service import get
                return self.send(*get(store, path, query))
            except (ValueError, OSError) as exc:
                self.send(400, {'error': str(exc)})

        def do_POST(self):
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
                from .service import post
                return self.send(*post(store, self.path, data))
            except (ValueError, KeyError, TypeError, OSError) as exc:
                self.send(400, {'error': str(exc)})

    stop = threading.Event()

    def scheduler():
        pending = {}
        last_watch = {}
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
                watches = sorted(store.rows('SELECT id FROM watches WHERE enabled=1'), key=lambda w: last_watch.get(w['id'], 0))
                jobs += [('watch:' + w['id'], lambda wid: scan_watch(store, wid), w['id']) for w in watches]
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
