from __future__ import annotations

from .processes import check_process

import csv
import hashlib
import http.client
import io
import ipaddress
import json
import os
import re
import socket
import ssl
import sqlite3
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
import uuid
import zipfile
import zlib
from contextlib import contextmanager
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from pathlib import Path

MAX_BYTES = 8 * 1024 * 1024
LOCK = threading.RLock()
USER_AGENT = 'Proofpage/0.1 (local evidence collector)'
_RECORDER = threading.local()


@contextmanager
def recording():
    """Collect transport details from the next fetch on this thread: exact bytes, header order, redirects, peer, TLS."""
    meta, previous = {}, getattr(_RECORDER, 'meta', None)
    _RECORDER.meta = meta
    try:
        yield meta
    finally:
        _RECORDER.meta = previous


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


class PageParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts, self.title, self.links = [], [], []
        self.hidden = 0
        self.in_title = False
        self.password = False
        self.main_depth = 0
        self.main_parts = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in ('script', 'style', 'noscript'):
            self.hidden += 1
        if tag == 'title':
            self.in_title = True
        if tag in ('article', 'main'):
            self.main_depth += 1
        if tag == 'input' and attrs.get('type', '').lower() == 'password':
            self.password = True
        if tag == 'a' and attrs.get('href'):
            self.links.append(attrs['href'])

    def handle_endtag(self, tag):
        if tag in ('script', 'style', 'noscript'):
            self.hidden = max(0, self.hidden - 1)
        if tag == 'title':
            self.in_title = False
        if tag in ('article', 'main'):
            self.main_depth = max(0, self.main_depth - 1)

    def handle_data(self, data):
        if self.hidden or not data.strip():
            return
        if self.in_title:
            self.title.append(data.strip())
        else:
            self.parts.append(data.strip())
            if self.main_depth:
                self.main_parts.append(data.strip())

    @property
    def text(self):
        return '\n'.join(self.main_parts or self.parts)


def classify(status, html):
    parser = PageParser()
    parser.feed(html)
    title = ' '.join(parser.title)
    # Challenge/login text is evidence only when the requested body is absent.
    substantive = len(' '.join(parser.main_parts)) >= 160
    if status == 429:
        state = 'rate_limited'
    elif status in (401, 403):
        state = 'authentication_required' if status == 401 else 'access_denied'
    elif status >= 400:
        state = 'http_error'
    elif not substantive and (re.search(r'(verify you are human|just a moment|captcha|security check)', title, re.I)):
        state = 'challenge_required'
    elif not substantive and (parser.password or re.fullmatch(r'\s*(sign in|log in|login)(\s*[|–-].*)?\s*', title, re.I)):
        state = 'authentication_required'
    elif len(parser.text) < 80:
        state = 'insufficient_content'
    else:
        state = 'available'
    return state, title, parser.text


def validate_url(url):
    p = urllib.parse.urlsplit(url)
    if p.scheme not in ('http', 'https') or not p.hostname or p.username or p.password:
        raise ValueError('Use a public HTTP(S) URL without embedded credentials.')
    if p.port not in (None, 80, 443):
        raise ValueError('Only standard web ports are supported.')
    hostname = p.hostname.lower().rstrip('.')
    if hostname == 'linkedin.com' or hostname.endswith('.linkedin.com'):
        raise ValueError('LinkedIn website collection is not enabled. Import an account archive instead.')
    addresses = socket.getaddrinfo(p.hostname, p.port or (443 if p.scheme == 'https' else 80), type=socket.SOCK_STREAM)
    if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):
        raise ValueError('Private, local, and reserved network destinations are not supported.')
    return url


class SafeRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        validate_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch(url, allowed=None):
    initial_host = urllib.parse.urlsplit(url).hostname
    redirects = []
    for _ in range(6):
        validate_url(url)
        if allowed is not None and not allowed(url):
            raise ValueError('Redirect or resource is outside the permitted collection scope.')
        parsed = urllib.parse.urlsplit(url)
        if parsed.hostname != initial_host:
            raise ValueError('Cross-host redirect requires adding the destination as a separate source.')
        port = parsed.port or (443 if parsed.scheme == 'https' else 80)
        addresses = socket.getaddrinfo(parsed.hostname, port, type=socket.SOCK_STREAM)
        if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):
            raise ValueError('Destination resolved to a non-public address.')
        # Connect directly to the validated numeric address, preventing DNS rebinding.
        connection = http.client.HTTPConnection(parsed.hostname, port, timeout=20)
        tls = {}
        def connect():
            sock = socket.create_connection((addresses[0][4][0], port), timeout=20)
            if parsed.scheme == 'https':
                try:
                    from .tls import context as tls_context
                    context = tls_context()
                    sock = context.wrap_socket(sock, server_hostname=parsed.hostname)
                    tls.update(tls_details(sock))
                except Exception:
                    sock.close()
                    raise
            connection.sock = sock
        connection.connect = connect
        try:
            connection.request('GET', urllib.parse.urlunsplit(('', '', parsed.path or '/', parsed.query, '')), headers={'User-Agent': USER_AGENT, 'Accept': 'text/html,text/plain', 'Accept-Encoding': 'identity'})
            response = connection.getresponse()
            if response.status in (301, 302, 303, 307, 308):
                target = urllib.parse.urljoin(url, response.getheader('Location', ''))
                if parsed.scheme == 'https' and urllib.parse.urlsplit(target).scheme != 'https':
                    raise ValueError('HTTPS downgrade redirect refused.')
                redirects.append({'url': url, 'status': response.status, 'location': target})
                url = target
                continue
            body = response.read(MAX_BYTES + 1)
            if len(body) > MAX_BYTES:
                raise ValueError('Response exceeds the 8 MiB collection limit.')
            # Normalize headers so provider capitalization does not change behavior.
            headers = {key.lower(): value for key, value in response.getheaders()}
            meta = getattr(_RECORDER, 'meta', None)
            if meta is not None:
                meta.update(raw=body, header_list=response.getheaders(), redirects=redirects, peer_ip=addresses[0][4][0],
                             http_version='HTTP/1.1' if response.version == 11 else 'HTTP/1.0', reason=response.reason, tls=dict(tls))
            return response.status, headers, body.decode('utf-8', errors='replace'), url
        finally:
            connection.close()
    raise ValueError('Redirect limit reached.')


def tls_details(sock):
    """Certificate fingerprint and identity for provenance; TLS itself does not prove what a server sent."""
    der = sock.getpeercert(binary_form=True)
    cert = sock.getpeercert() or {}
    name = lambda parts: ', '.join('='.join(pair) for group in parts or () for pair in group)
    return {'version': sock.version(), 'cipher': (sock.cipher() or (None,))[0], 'cert_sha256': hashlib.sha256(der).hexdigest() if der else None,
            'subject': name(cert.get('subject')), 'issuer': name(cert.get('issuer')), 'not_after': cert.get('notAfter')}


def tdmrep_result(status, body, detail=''):
    if status == 200:
        try:
            return {'status': 'read', 'data': json.loads(body)}
        except ValueError:
            return {'status': 'invalid'}
    if status in (404, 410):
        return {'status': 'missing'}
    return {'status': 'unavailable', 'detail': detail or (f'unavailable (HTTP {status})' if status else 'unavailable')}


def retry_seconds(value):
    try:
        return max(1, int(value))
    except (ValueError, TypeError):
        try:
            return max(1, int(parsedate_to_datetime(value).timestamp() - time.time()))
        except (ValueError, TypeError, OverflowError):
            return 300


class Store:
    def __init__(self, directory=None):
        self.directory = Path(directory or os.environ.get('PROOFPAGE_HOME', '~/.proofpage')).expanduser()
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.path = self.directory / 'proofpage.sqlite3'
        with self.db() as db:
            db.executescript('''
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS sources(id TEXT PRIMARY KEY,name TEXT,kind TEXT,location TEXT UNIQUE,state TEXT DEFAULT 'ready',cooldown REAL DEFAULT 0,interval_seconds INTEGER DEFAULT 0,next_run REAL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS runs(id TEXT PRIMARY KEY,source_id TEXT,state TEXT,started_at TEXT,finished_at TEXT,detail TEXT,added INTEGER DEFAULT 0);
            CREATE TABLE IF NOT EXISTS items(id TEXT PRIMARY KEY,source_id TEXT,external_id TEXT,kind TEXT,title TEXT,current_revision TEXT,UNIQUE(source_id,external_id));
            CREATE TABLE IF NOT EXISTS revisions(id TEXT PRIMARY KEY,item_id TEXT,hash TEXT,text TEXT,raw TEXT,metadata TEXT,captured_at TEXT,source_time TEXT,UNIQUE(item_id,hash));
            CREATE TABLE IF NOT EXISTS cooldowns(origin TEXT PRIMARY KEY,until REAL);
            CREATE TABLE IF NOT EXISTS run_owners(run_id TEXT PRIMARY KEY,pid INTEGER);
            CREATE TABLE IF NOT EXISTS budgets(origin TEXT,day TEXT,attempts INTEGER,PRIMARY KEY(origin,day));
            CREATE TABLE IF NOT EXISTS reviews(revision_id TEXT PRIMARY KEY,allowed INTEGER DEFAULT 0,approved INTEGER DEFAULT 0);
            CREATE TABLE IF NOT EXISTS datasets(id TEXT PRIMARY KEY,name TEXT,created_at TEXT,payload TEXT,revision_ids TEXT,hash TEXT);
            CREATE VIRTUAL TABLE IF NOT EXISTS search USING fts5(item_id UNINDEXED,title,text);
            ''')
            for run in db.execute("SELECT r.id,o.pid FROM runs r LEFT JOIN run_owners o ON o.run_id=r.id WHERE r.state='running'").fetchall():
                try:
                    if not run['pid']:
                        raise ProcessLookupError()
                    check_process(run['pid'])
                except ProcessLookupError:
                    db.execute("UPDATE runs SET state='interrupted',finished_at=?,detail='Process stopped before completion; recheck explicitly.' WHERE id=?", (now(), run['id']))
        from .schema import migrate
        with self.db() as db:
            migrate(db)
        os.chmod(self.path, 0o600)

    @contextmanager
    def db(self):
        db = sqlite3.connect(self.path, timeout=30)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def rows(self, sql, args=()):
        with self.db() as db:
            return [dict(r) for r in db.execute(sql, args)]

    def source(self, name, kind, location):
        if kind not in ('web', 'import'):
            raise ValueError('Unsupported source kind.')
        if kind == 'web':
            validate_url(location)
        with self.db() as db:
            db.execute('INSERT OR IGNORE INTO sources(id,name,kind,location) VALUES(?,?,?,?)', (uuid.uuid4().hex, name[:200], kind, location))
        return self.rows('SELECT * FROM sources WHERE location=?', (location,))[0]

    def save(self, source_id, external_id, kind, title, text, raw, metadata=None, source_time=None):
        metadata = metadata or {}
        # Captured time is deliberately excluded from identity and revision hashes.
        content_hash = digest(json.dumps([kind, title, text, raw, metadata, source_time], sort_keys=True))
        with LOCK, self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            found = db.execute('SELECT * FROM items WHERE source_id=? AND external_id=?', (source_id, external_id)).fetchone()
            item_id = found['id'] if found else uuid.uuid4().hex
            previous = found['current_revision'] if found else None
            old = db.execute('SELECT id FROM revisions WHERE item_id=? AND hash=?', (item_id, content_hash)).fetchone()
            if old:
                if previous == old['id']:
                    return False
                # Content returned to an earlier version; that version becomes current again.
                revision_id = old['id']
                db.execute('UPDATE items SET current_revision=?,title=?,kind=? WHERE id=?', (revision_id, title, kind, item_id))
            else:
                revision_id = uuid.uuid4().hex
                db.execute('INSERT INTO revisions VALUES(?,?,?,?,?,?,?,?)', (revision_id, item_id, content_hash, text, raw, json.dumps(metadata), now(), source_time))
                db.execute('INSERT INTO items VALUES(?,?,?,?,?,?) ON CONFLICT(source_id,external_id) DO UPDATE SET kind=excluded.kind,title=excluded.title,current_revision=excluded.current_revision', (item_id, source_id, external_id, kind, title, revision_id))
            db.execute('DELETE FROM search WHERE item_id=?', (item_id,))
            db.execute('INSERT INTO search VALUES(?,?,?)', (item_id, title, text))
        if previous:
            try:
                from .history import record_change
                record_change(self, item_id, previous, revision_id, now())
            except Exception:
                pass  # The revision is saved; a missing inbox entry must not undo it.
        return True

    def collect(self, source_id, target_url=None, render=False):
        sources = self.rows('SELECT * FROM sources WHERE id=?', (source_id,))
        if not sources or sources[0]['kind'] != 'web':
            raise ValueError('Choose an existing web source.')
        source = sources[0]
        root_url = source['location']
        if target_url is not None:
            from .crawl import in_scope
            if not in_scope(root_url, target_url):
                raise ValueError('Requested page is outside this source origin/path scope.')
            source = dict(source, location=target_url)
        origin = urllib.parse.urlsplit(source['location']).hostname.lower().rstrip('.')
        with LOCK, self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            cooldown = db.execute('SELECT until FROM cooldowns WHERE origin=?', (origin,)).fetchone()
            if cooldown and cooldown['until'] > time.time():
                raise ValueError('This host is cooling down. Retry after ' + datetime.fromtimestamp(cooldown['until'], timezone.utc).isoformat())
            if db.execute("SELECT 1 FROM runs WHERE source_id=? AND state='running'", (source_id,)).fetchone():
                raise ValueError('This source already has a collection in progress.')
            day = now()[:10]
            budget = db.execute('SELECT attempts FROM budgets WHERE origin=? AND day=?', (origin, day)).fetchone()
            if budget and budget['attempts'] >= 100:
                raise ValueError('Daily host budget of 100 collection attempts exhausted.')
            db.execute('INSERT INTO budgets VALUES(?,?,1) ON CONFLICT(origin,day) DO UPDATE SET attempts=attempts+1', (origin, day))
            run_id = uuid.uuid4().hex
            db.execute('INSERT INTO runs(id,source_id,state,started_at) VALUES(?,?,?,?)', (run_id, source_id, 'running', now()))
            db.execute('INSERT INTO run_owners VALUES(?,?)', (run_id, os.getpid()))
            db.execute('INSERT INTO run_targets VALUES(?,?)', (run_id, source['location']))
            db.execute('INSERT OR REPLACE INTO cooldowns VALUES(?,?)', (origin, time.time() + 30))
        added, state, detail, discovered_urls = 0, 'failed', '', None
        page, tdmrep, robots_status, robots_body = None, None, None, ''
        robots_url = urllib.parse.urljoin(source['location'], '/robots.txt')
        try:
            rs, rh, robots, _ = fetch(robots_url)
            robots_status, robots_body = rs, robots if rs == 200 else ''
            if rs == 429:
                with self.db() as db:
                    db.execute('INSERT OR REPLACE INTO cooldowns VALUES(?,?)', (origin, time.time() + retry_seconds(rh.get('retry-after'))))
                state, detail = 'rate_limited', 'The robots policy endpoint requested a cooldown.'
            elif rs not in (200, 404):
                state, detail = 'policy_unavailable', 'Could not establish the site collection policy.'
            else:
                rp = urllib.robotparser.RobotFileParser()
                rp.parse(robots.splitlines() if rs == 200 else [])
                crawl_delay = rp.crawl_delay('Proofpage') or rp.crawl_delay('*') or 0
                rate = rp.request_rate('Proofpage') or rp.request_rate('*')
                spacing = max(30, crawl_delay, (rate.seconds / rate.requests) if rate and rate.requests else 0)
                with self.db() as db:
                    db.execute('UPDATE cooldowns SET until=MAX(until,?) WHERE origin=?', (time.time() + spacing, origin))
                if rs == 200 and not rp.can_fetch('Proofpage', source['location']):
                    state, detail = 'restricted', 'The site robots policy excludes this page.'
                else:
                    from .crawl import in_scope
                    allowed = lambda url: in_scope(root_url, url) and (rs != 200 or rp.can_fetch('Proofpage', url))
                    requested_at = now()
                    with recording() as transport:
                        status, headers, body, final_url = fetch(source['location'], allowed=allowed)
                    page = {'url': source['location'], 'final_url': final_url or source['location'], 'requested_at': requested_at,
                            'status': status, 'headers': headers, 'body': body, 'transport': transport}
                    state, title, text = classify(status, body)
                    content_type = headers.get('content-type', '')
                    render_metadata = {}
                    if render and status == 200 and 'text/html' in content_type and state not in ('authentication_required', 'challenge_required'):
                        from .render import render_html
                        original_html = body
                        body, render_metadata = render_html(final_url, body, allowed)
                        render_metadata['original_html'] = original_html
                        state, title, text = classify(status, body)
                    if 'text/plain' in content_type and status == 200:
                        text, title = body, source['name']
                        state = 'available' if body.strip() else 'insufficient_content'
                    elif 'text/html' not in content_type and status == 200:
                        if 'xml' in content_type:
                            from .crawl import discover
                            discovered_urls = discover(body, final_url)
                            state = 'discovery'
                        else:
                            state = 'unsupported_format'
                    if state == 'available':
                        added = int(self.save(source_id, source['location'], 'document', title or source['name'], text, body, {'url': final_url, 'status': status, 'coverage': 'Single observed page; attachments were not acquired.', **render_metadata}))
                        detail = 'Captured requested page.' if added else 'No substantive change.'
                        page['revision_id'] = self.rows('SELECT current_revision FROM items WHERE source_id=? AND external_id=?', (source_id, source['location']))[0]['current_revision']
                        tdmrep = self._tdmrep(origin, source['location'])
                    elif state == 'discovery':
                        detail = f'Discovered {len(discovered_urls)} feed/sitemap links. No article content was inferred.'
                    else:
                        # Do not persist login forms, challenge bodies, or credentials.
                        detail = f'HTTP {status}; requested content was not confirmed. Previous evidence retained.'
                    if status == 429:
                        with self.db() as db:
                            db.execute('INSERT OR REPLACE INTO cooldowns VALUES(?,?)', (origin, time.time() + retry_seconds(headers.get('retry-after'))))
        except Exception as exc:
            state, detail = 'failed', str(exc)[:500]
        rights_result = None
        if page is not None:
            try:
                rights_result = self._record_capture(run_id, source_id, origin, page, state, robots_url, robots_status, robots_body, tdmrep)
            except Exception as exc:
                # Provenance recording must never turn a completed capture into a failure.
                rights_result = {'error': 'Rights and capture details were not recorded: ' + str(exc)[:300]}
        try:
            self._record_events(sources[0], target_url, page, state, detail)
        except Exception:
            pass
        with self.db() as db:
            cooldown = db.execute('SELECT until FROM cooldowns WHERE origin=?', (origin,)).fetchone()
            next_run = max(time.time() + max(60, source['interval_seconds']), cooldown['until'] if cooldown else 0)
            db.execute('UPDATE sources SET state=?,next_run=? WHERE id=?', (state, next_run, source_id))
            if (target_url is None or target_url == root_url) and state in ('authentication_required', 'access_denied', 'challenge_required', 'restricted'):
                db.execute('UPDATE sources SET interval_seconds=0 WHERE id=?', (source_id,))
            db.execute('UPDATE runs SET state=?,finished_at=?,detail=?,added=? WHERE id=?', (state, now(), detail, added, run_id))
            db.execute('INSERT INTO observations VALUES(?,?,?,?,?,?)', (uuid.uuid4().hex, source_id, run_id, state, now(), detail))
        result = self.rows('SELECT * FROM runs WHERE id=?', (run_id,))[0]
        if state in ('authentication_required', 'challenge_required'):
            result['attention'] = {'required': True, 'reason': state, 'url': target_url or source['location'],
                'training_action': 'Ask the user to sign in or complete the challenge, then import reviewed text with the browser companion.',
                'agent_action': 'Ask for approval for this specific challenge before attempting it in the user browser. Sign in on the website; do not send passwords or session cookies to Proofpage.',
                'resume': 'Import the readable page using the companion. Direct collection does not inherit browser login sessions.'}
        if rights_result is not None:
            result['rights'] = rights_result
        if discovered_urls is not None:
            result['discovered_urls'] = discovered_urls
        return result

    def _tdmrep(self, origin, page_url):
        """Read /.well-known/tdmrep.json at most once per site per day; the request counts toward the host budget."""
        day = now()[:10]
        cached = self.rows("SELECT status,body,detail FROM policy_documents WHERE origin=? AND kind='tdmrep' AND substr(fetched_at,1,10)=? ORDER BY fetched_at DESC LIMIT 1", (origin, day))
        if cached:
            return tdmrep_result(cached[0]['status'], cached[0]['body'], cached[0]['detail'])
        budget = self.rows('SELECT attempts FROM budgets WHERE origin=? AND day=?', (origin, day))
        if budget and budget[0]['attempts'] >= 100:
            return {'status': 'not_checked', 'detail': 'not checked (daily host budget reached)'}
        url = urllib.parse.urljoin(page_url, '/.well-known/tdmrep.json')
        status, body, detail = None, '', ''
        with self.db() as db:
            db.execute('INSERT INTO budgets VALUES(?,?,1) ON CONFLICT(origin,day) DO UPDATE SET attempts=attempts+1', (origin, day))
        try:
            status, _, body, _ = fetch(url)
        except Exception as exc:
            detail = ('unavailable: ' + str(exc))[:200] if str(exc) else 'unavailable'
        body = body if status == 200 and isinstance(body, str) else ''
        with self.db() as db:
            db.execute('INSERT INTO policy_documents VALUES(?,?,?,?,?,?,?,?,?)', (uuid.uuid4().hex, origin, 'tdmrep', url, now(), status, digest(body) if body else None, body[:1024 * 1024], detail))
        return tdmrep_result(status, body, detail)

    def _record_events(self, source, target_url, page, state, detail):
        """Inbox entries for pages that disappeared and for sources that stopped working; each is recorded once per transition."""
        from .history import PROBLEM_STATES, event
        requested = target_url or source['location']
        with self.db() as db:
            if page and page['status'] in (404, 410):
                item = db.execute('SELECT i.id,i.title,r.captured_at FROM items i JOIN revisions r ON r.id=i.current_revision WHERE i.source_id=? AND i.external_id=?', (source['id'], requested)).fetchone()
                prior = db.execute('SELECT status FROM captures WHERE url=? ORDER BY requested_at DESC, rowid DESC LIMIT 1 OFFSET 1', (requested,)).fetchone()
                if item and (prior is None or prior['status'] not in (404, 410)):
                    event(db, 'link_rot', item['id'], {'item_id': item['id'], 'title': item['title'], 'source_id': source['id'], 'source_name': source['name'], 'url': requested,
                                                        'status': page['status'], 'last_captured_at': item['captured_at'],
                                                        'summary': f"The page now returns HTTP {page['status']}. Your last captured version is kept."}, now())
                    return
            if state in ('authentication_required', 'challenge_required') and source['state'] != state:
                event(db, 'collection_problem', source['id'], {'source_id': source['id'], 'source_name': source['name'], 'url': requested, 'state': state, 'needs_attention': True,
                    'summary': 'Sign in on the website or complete its challenge, then save the readable page with the browser companion. Scheduled collection is paused for the source page.'}, now())
                return
            if (target_url is None or target_url == source['location']) and state in PROBLEM_STATES and source['state'] in ('available', 'discovery'):
                event(db, 'collection_problem', source['id'], {'source_id': source['id'], 'source_name': source['name'], 'url': requested, 'state': state,
                                                                'previous_state': source['state'], 'summary': detail}, now())

    def _record_capture(self, run_id, source_id, origin, page, state, robots_url, robots_status, robots_body, tdmrep):
        from . import receipts, rights
        transport = page['transport']
        exact = transport.get('raw') is not None
        raw = transport['raw'] if exact else page['body'].encode('utf-8')
        body_sha = hashlib.sha256(raw).hexdigest()
        headers = json.dumps([[key, value] for key, value in (transport.get('header_list') or page['headers'].items()) if key.lower() != 'set-cookie'])
        robots_sha = digest(robots_body) if robots_status == 200 else None
        html = page['body'] if 'html' in (page['headers'] or {}).get('content-type', 'text/html') else ''
        # Error, login, and challenge pages say nothing about the content's rights; reading them would fake drift.
        confirmed = state in ('available', 'discovery')
        observation = rights.observe(page['final_url'], page['headers'], html, robots_body, robots_status, tdmrep) if confirmed else None
        tls = transport.get('tls') or {}
        with LOCK, self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            # Only confirmed content keeps its exact bytes; login forms and challenge pages are never stored.
            if confirmed:
                db.execute('INSERT OR IGNORE INTO capture_payloads VALUES(?,?)', (body_sha, zlib.compress(raw, 6)))
            if robots_sha and not db.execute("SELECT 1 FROM policy_documents WHERE origin=? AND kind='robots' AND sha256=?", (origin, robots_sha)).fetchone():
                db.execute('INSERT INTO policy_documents VALUES(?,?,?,?,?,?,?,?,?)', (uuid.uuid4().hex, origin, 'robots', robots_url, now(), 200, robots_sha, robots_body[:MAX_BYTES], ''))
            capture_id = uuid.uuid4().hex
            db.execute('INSERT INTO captures(id,run_id,source_id,url,final_url,requested_at,status,headers,body_sha256,body_bytes,raw_exact,peer_ip,tls,redirects,revision_id,robots_sha256,http_version,reason) '
                       'VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)', (
                capture_id, run_id, source_id, page['url'], page['final_url'], page['requested_at'], page['status'], headers, body_sha, len(raw), int(exact),
                transport.get('peer_ip'), json.dumps(tls, sort_keys=True), json.dumps(transport.get('redirects') or []), page.get('revision_id'), robots_sha,
                transport.get('http_version'), transport.get('reason')))
            result = {'capture_id': capture_id, 'recorded': False, 'note': 'Publisher signals are recorded only when page content is confirmed.'}
            observation_hash = None
            if confirmed:
                result = dict(rights.record(self, db, capture_id, source_id, page['final_url'], observation, now()), capture_id=capture_id)
                observation_hash = db.execute('SELECT hash FROM rights_observations WHERE id=?', (result['id'],)).fetchone()['hash']
            revision_hash = db.execute('SELECT hash FROM revisions WHERE id=?', (page['revision_id'],)).fetchone()['hash'] if page.get('revision_id') else None
            result['receipt'] = receipts.issue(db, {
                'capture_id': capture_id, 'source_id': source_id, 'run_id': run_id, 'url': page['url'], 'final_url': page['final_url'],
                'requested_at': page['requested_at'], 'status': page['status'], 'headers_sha256': hashlib.sha256(headers.encode('utf-8')).hexdigest(),
                'body_sha256': body_sha, 'body_bytes': len(raw), 'raw_exact': exact, 'body_stored': confirmed,
                'revision_id': page.get('revision_id'), 'revision_hash': revision_hash, 'robots_sha256': robots_sha,
                'rights_observation_hash': observation_hash, 'rights_verdict': {use: observation['verdict'][use] for use in ('train', 'ai_use', 'search')} if observation else None,
                'peer_ip': transport.get('peer_ip'), 'tls': {key: tls.get(key) for key in ('version', 'cert_sha256', 'issuer', 'not_after')} if tls else None,
                'redirects': transport.get('redirects') or [], 'http_version': transport.get('http_version'), 'reason': transport.get('reason')})
            return result

    def search(self, query='', include_traces=True, snippets=False):
        columns = ('i.*,r.text,r.hash,r.captured_at,r.source_time,s.name source_name,s.kind source_kind,COALESCE(v.allowed,0) allowed,COALESCE(v.approved,0) approved,'
                   '(SELECT o.verdict FROM captures c JOIN rights_observations o ON o.capture_id=c.id WHERE c.revision_id=i.current_revision ORDER BY o.observed_at DESC LIMIT 1) rights,'
                   '(SELECT rc.hash FROM receipts rc JOIN captures c ON c.id=rc.capture_id WHERE c.revision_id=i.current_revision ORDER BY rc.seq DESC LIMIT 1) receipt_hash')
        joins = 'JOIN revisions r ON r.id=i.current_revision JOIN sources s ON s.id=i.source_id LEFT JOIN reviews v ON v.revision_id=i.current_revision'
        if query.strip():
            terms = ' AND '.join('"' + t.replace('"', '""') + '"' for t in query.split())
            # Control characters mark matches so the browser can escape text before highlighting it.
            highlight = ",snippet(search,2,char(2),char(3),'…',24) snippet" if snippets else ''
            rows = self.rows(f"SELECT {columns}{highlight} FROM search JOIN items i ON i.id=search.item_id {joins} WHERE search MATCH ? AND (? OR i.kind!='agent_trace') ORDER BY rank LIMIT 100", (terms, int(include_traces)))
        else:
            rows = self.rows(f'SELECT {columns} FROM items i {joins} ORDER BY r.captured_at DESC LIMIT 100')
        for row in rows:
            row['rights'] = json.loads(row['rights']) if row['rights'] else None
        return rows

    def item(self, item_id):
        result = self.rows('SELECT i.*,r.*,s.name source_name FROM items i JOIN revisions r ON r.id=i.current_revision JOIN sources s ON s.id=i.source_id WHERE i.id=?', (item_id,))
        if not result:
            raise ValueError('Record not found.')
        result[0]['revisions'] = self.rows('SELECT id,hash,captured_at,source_time FROM revisions WHERE item_id=? ORDER BY captured_at DESC', (item_id,))
        reviews = self.rows('SELECT allowed,approved,rights_basis,rights_note FROM reviews WHERE revision_id=?', (result[0]['current_revision'],))
        result[0]['review'] = reviews[0] if reviews else {'allowed': 0, 'approved': 0, 'rights_basis': None, 'rights_note': ''}
        from .quality import findings
        from .receipts import revision_proof
        from .rights import revision_rights
        result[0]['findings'] = findings(result[0]['text'])
        result[0]['rights'] = revision_rights(self, result[0]['current_revision'])
        result[0]['proof'] = revision_proof(self, result[0]['current_revision'])
        return result[0]

    def review(self, revision_id, allowed, approved, rights_basis=None, rights_note=None):
        revisions = self.rows('SELECT id,text FROM revisions WHERE id=?', (revision_id,))
        if not revisions:
            raise ValueError('Revision not found.')
        from .quality import findings
        if approved and any(f['severity'] == 'block' for f in findings(revisions[0]['text'])):
            raise ValueError('This revision contains detected credentials. Grant source permission separately and create a redacted training example.')
        # A basis recorded earlier is kept unless a new one is supplied; an empty string clears it.
        existing = (self.rows('SELECT rights_basis,rights_note FROM reviews WHERE revision_id=?', (revision_id,)) or [{}])[0]
        basis = existing.get('rights_basis') if rights_basis is None else (rights_basis or None)
        note = (existing.get('rights_note') or '') if rights_basis is None else (rights_note or '').strip()[:1000]
        if allowed:
            from .rights import check_basis
            check_basis(self, revision_id, basis, note)
        else:
            basis, note = None, ''
        with self.db() as db:
            db.execute('INSERT OR REPLACE INTO reviews(revision_id,allowed,approved,rights_basis,rights_note) VALUES(?,?,?,?,?)', (revision_id, int(allowed), int(approved), basis, note))

    def revision(self, revision_id):
        revisions = self.rows('SELECT * FROM revisions WHERE id=?', (revision_id,))
        if not revisions:
            raise ValueError('Revision not found.')
        revision = revisions[0]
        result = self.item(revision['item_id'])
        result['is_current'] = result['current_revision'] == revision_id
        result.update({key: value for key, value in revision.items() if key != 'id'})
        from .quality import findings
        result['findings'] = findings(result['text'])
        result['current_revision'] = revision_id  # The revision selected for review, never a database update.
        reviews = self.rows('SELECT allowed,approved,rights_basis,rights_note FROM reviews WHERE revision_id=?', (revision_id,))
        result['review'] = reviews[0] if reviews else {'allowed': 0, 'approved': 0, 'rights_basis': None, 'rights_note': ''}
        from .receipts import revision_proof
        from .rights import revision_rights
        result['rights'] = revision_rights(self, revision_id)
        result['proof'] = revision_proof(self, revision_id)
        return result

    def freeze(self, name):
        records = self.rows('SELECT i.id item_id,i.source_id,i.kind,i.title,r.* FROM items i JOIN revisions r ON r.id=i.current_revision JOIN reviews v ON v.revision_id=r.id WHERE v.allowed=1 AND v.approved=1 ORDER BY i.id')
        if not records:
            raise ValueError('Approve at least one revision and confirm permission before freezing a corpus.')
        seen, lines, ids = set(), [], []
        for r in records:
            if not r['text'].strip():
                continue
            key = digest(r['text'])
            if key in seen:
                continue
            seen.add(key)
            ids.append(r['id'])
            bucket = int(digest(r['source_id'])[:8], 16) % 100
            lines.append(json.dumps({'id': r['item_id'], 'revision_id': r['id'], 'kind': r['kind'], 'text': r['text'], 'source_id': r['source_id'], 'source_time': r['source_time'], 'captured_at': r['captured_at'], 'split': 'test' if bucket >= 90 else 'validation' if bucket >= 80 else 'train'}, ensure_ascii=False))
        payload = '\n'.join(lines) + '\n'
        if not ids:
            raise ValueError('Reviewed revisions contain no nonempty corpus text.')
        from . import rights
        snapshot = rights.freeze_snapshot(self, ids)
        dataset_id = uuid.uuid4().hex
        with self.db() as db:
            db.execute('INSERT INTO datasets VALUES(?,?,?,?,?,?)', (dataset_id, name[:200], now(), payload, json.dumps(ids), digest(payload)))
            rights.save_snapshot(db, dataset_id, snapshot)
        return {'id': dataset_id, 'records': len(ids), 'hash': digest(payload), 'rights': rights.snapshot_counts(snapshot)}

    def export(self, dataset_id):
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            dataset = db.execute('SELECT * FROM datasets WHERE id=?', (dataset_id,)).fetchone()
            if not dataset:
                raise ValueError('Dataset not found.')
            training = db.execute('SELECT candidate_ids FROM dataset_manifests WHERE dataset_id=?', (dataset_id,)).fetchone()
            if training:
                for candidate_id in json.loads(training['candidate_ids']):
                    if not db.execute("SELECT 1 FROM candidates WHERE id=? AND status='approved'", (candidate_id,)).fetchone():
                        raise ValueError('Export blocked: an example approval was revoked.')
            for revision_id in json.loads(dataset['revision_ids']):
                permission = db.execute('SELECT * FROM reviews WHERE revision_id=? AND allowed=1', (revision_id,)).fetchone()
                if not permission or (not training and not permission['approved']):
                    raise ValueError('Export blocked: a frozen revision no longer has permission and approval.')
            # A source that now reserves AI training blocks downloads until a rights basis is recorded.
            from .rights import blocked_message, export_blockers
            blocked = export_blockers(self, dataset_id, json.loads(dataset['revision_ids']))
            if blocked:
                raise ValueError(blocked_message(self, blocked))
            if digest(dataset['payload']) != dataset['hash']:
                raise ValueError('Frozen dataset integrity check failed.')
            return dataset['payload']


def archive_entries(filename, data):
    if len(data) > MAX_BYTES:
        raise ValueError('Import exceeds the 8 MiB limit.')
    if filename.lower().endswith('.zip'):
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                entries = [e for e in archive.infolist() if not e.is_dir()]
                if len(entries) > 200 or sum(e.file_size for e in entries) > 32 * 1024 * 1024:
                    raise ValueError('Archive exceeds expanded size or file count limit.')
                if len({e.filename for e in entries}) != len(entries):
                    raise ValueError('Archive contains duplicate entry names.')
                return [(e.filename, archive.read(e)) for e in entries if Path(e.filename).suffix.lower() in ('.csv', '.json', '.jsonl', '.txt', '.md', '.html', '.png', '.jpg', '.jpeg', '.webp', '.pdf')]
        except (zipfile.BadZipFile, RuntimeError, NotImplementedError) as exc:
            raise ValueError('Archive is invalid, encrypted, or uses unsupported compression.') from exc
    return [(filename, data)]


def preview(filename, data):
    from .adapters import parse_entry
    result = []
    for name, content in archive_entries(filename, data):
        try:
            records = parse_entry(name, content)
            result.append({'name': name, 'bytes': len(content), 'records': len(records), 'adapters': sorted({r['metadata']['adapter'] for r in records}), 'error': None})
        except (ValueError, TypeError, AttributeError, csv.Error) as exc:
            result.append({'name': name, 'bytes': len(content), 'records': 0, 'adapters': [], 'error': str(exc)[:200]})
    return result


def import_file(store, filename, data, selected=None, profile_id=None):
    from .imports import import_archive
    return import_archive(store, filename, data, selected, profile_id)
