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
from contextlib import contextmanager
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from pathlib import Path

MAX_BYTES = 8 * 1024 * 1024
LOCK = threading.RLock()


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
        def connect():
            sock = socket.create_connection((addresses[0][4][0], port), timeout=20)
            if parsed.scheme == 'https':
                try:
                    from .tls import context as tls_context
                    context = tls_context()
                    sock = context.wrap_socket(sock, server_hostname=parsed.hostname)
                except Exception:
                    sock.close()
                    raise
            connection.sock = sock
        connection.connect = connect
        try:
            connection.request('GET', urllib.parse.urlunsplit(('', '', parsed.path or '/', parsed.query, '')), headers={'User-Agent': 'Proofpage/0.1 (local evidence collector)', 'Accept': 'text/html,text/plain', 'Accept-Encoding': 'identity'})
            response = connection.getresponse()
            if response.status in (301, 302, 303, 307, 308):
                target = urllib.parse.urljoin(url, response.getheader('Location', ''))
                if parsed.scheme == 'https' and urllib.parse.urlsplit(target).scheme != 'https':
                    raise ValueError('HTTPS downgrade redirect refused.')
                url = target
                continue
            body = response.read(MAX_BYTES + 1)
            if len(body) > MAX_BYTES:
                raise ValueError('Response exceeds the 8 MiB collection limit.')
            # Normalize headers so provider capitalization does not change behavior.
            headers = {key.lower(): value for key, value in response.getheaders()}
            return response.status, headers, body.decode('utf-8', errors='replace'), url
        finally:
            connection.close()
    raise ValueError('Redirect limit reached.')


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
            old = db.execute('SELECT id FROM revisions WHERE item_id=? AND hash=?', (item_id, content_hash)).fetchone()
            if old:
                if found['current_revision'] != old['id']:
                    db.execute('UPDATE items SET current_revision=?,title=?,kind=? WHERE id=?', (old['id'], title, kind, item_id))
                    db.execute('DELETE FROM search WHERE item_id=?', (item_id,))
                    db.execute('INSERT INTO search VALUES(?,?,?)', (item_id, title, text))
                    return True
                return False
            revision_id = uuid.uuid4().hex
            db.execute('INSERT INTO revisions VALUES(?,?,?,?,?,?,?,?)', (revision_id, item_id, content_hash, text, raw, json.dumps(metadata), now(), source_time))
            db.execute('INSERT INTO items VALUES(?,?,?,?,?,?) ON CONFLICT(source_id,external_id) DO UPDATE SET kind=excluded.kind,title=excluded.title,current_revision=excluded.current_revision', (item_id, source_id, external_id, kind, title, revision_id))
            db.execute('DELETE FROM search WHERE item_id=?', (item_id,))
            db.execute('INSERT INTO search VALUES(?,?,?)', (item_id, title, text))
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
        try:
            robots_url = urllib.parse.urljoin(source['location'], '/robots.txt')
            rs, rh, robots, _ = fetch(robots_url)
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
                    status, headers, body, final_url = fetch(source['location'], allowed=allowed)
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
        with self.db() as db:
            cooldown = db.execute('SELECT until FROM cooldowns WHERE origin=?', (origin,)).fetchone()
            next_run = max(time.time() + max(60, source['interval_seconds']), cooldown['until'] if cooldown else 0)
            db.execute('UPDATE sources SET state=?,next_run=? WHERE id=?', (state, next_run, source_id))
            if (target_url is None or target_url == root_url) and state in ('authentication_required', 'access_denied', 'challenge_required', 'restricted'):
                db.execute('UPDATE sources SET interval_seconds=0 WHERE id=?', (source_id,))
            db.execute('UPDATE runs SET state=?,finished_at=?,detail=?,added=? WHERE id=?', (state, now(), detail, added, run_id))
            db.execute('INSERT INTO observations VALUES(?,?,?,?,?,?)', (uuid.uuid4().hex, source_id, run_id, state, now(), detail))
        result = self.rows('SELECT * FROM runs WHERE id=?', (run_id,))[0]
        if discovered_urls is not None:
            result['discovered_urls'] = discovered_urls
        return result

    def search(self, query='', include_traces=True):
        if query.strip():
            terms = ' AND '.join('"' + t.replace('"', '""') + '"' for t in query.split())
            return self.rows("SELECT i.*,r.text,r.captured_at,r.source_time,s.name source_name FROM search JOIN items i ON i.id=search.item_id JOIN revisions r ON r.id=i.current_revision JOIN sources s ON s.id=i.source_id WHERE search MATCH ? AND (? OR i.kind!='agent_trace') ORDER BY rank LIMIT 100", (terms, int(include_traces)))
        return self.rows('SELECT i.*,r.text,r.captured_at,r.source_time,s.name source_name FROM items i JOIN revisions r ON r.id=i.current_revision JOIN sources s ON s.id=i.source_id ORDER BY r.captured_at DESC LIMIT 100')

    def item(self, item_id):
        result = self.rows('SELECT i.*,r.*,s.name source_name FROM items i JOIN revisions r ON r.id=i.current_revision JOIN sources s ON s.id=i.source_id WHERE i.id=?', (item_id,))
        if not result:
            raise ValueError('Record not found.')
        result[0]['revisions'] = self.rows('SELECT id,hash,captured_at,source_time FROM revisions WHERE item_id=? ORDER BY captured_at DESC', (item_id,))
        reviews = self.rows('SELECT allowed,approved FROM reviews WHERE revision_id=?', (result[0]['current_revision'],))
        result[0]['review'] = reviews[0] if reviews else {'allowed': 0, 'approved': 0}
        from .quality import findings
        result[0]['findings'] = findings(result[0]['text'])
        return result[0]

    def review(self, revision_id, allowed, approved):
        revisions = self.rows('SELECT id,text FROM revisions WHERE id=?', (revision_id,))
        if not revisions:
            raise ValueError('Revision not found.')
        from .quality import findings
        if approved and any(f['severity'] == 'block' for f in findings(revisions[0]['text'])):
            raise ValueError('This revision contains detected credentials. Grant source permission separately and create a redacted training example.')
        with self.db() as db:
            db.execute('INSERT OR REPLACE INTO reviews VALUES(?,?,?)', (revision_id, int(allowed), int(approved)))

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
        reviews = self.rows('SELECT allowed,approved FROM reviews WHERE revision_id=?', (revision_id,))
        result['review'] = reviews[0] if reviews else {'allowed': 0, 'approved': 0}
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
        dataset_id = uuid.uuid4().hex
        with self.db() as db:
            db.execute('INSERT INTO datasets VALUES(?,?,?,?,?,?)', (dataset_id, name[:200], now(), payload, json.dumps(ids), digest(payload)))
        return {'id': dataset_id, 'records': len(ids), 'hash': digest(payload)}

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
                return [(e.filename, archive.read(e)) for e in entries if Path(e.filename).suffix.lower() in ('.csv', '.json', '.jsonl', '.txt', '.md', '.html')]
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
