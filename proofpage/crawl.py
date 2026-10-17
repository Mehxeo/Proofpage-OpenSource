"""Durable bounded crawl queue, advanced one page at a time without sleeping workers."""
import json
import os
import posixpath
import time
import urllib.parse
import uuid
import xml.etree.ElementTree as ET

from .core import PageParser, now


def canonical(url):
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError('Invalid web URL.')
    hostname = parsed.hostname.lower().rstrip('.')
    port = parsed.port
    netloc = hostname if port in (None, 80 if parsed.scheme == 'http' else 443) else hostname + ':' + str(port)
    return urllib.parse.urlunsplit((parsed.scheme, netloc, parsed.path or '/', parsed.query, ''))


def in_scope(root, url):
    try:
        base, target = urllib.parse.urlsplit(canonical(root)), urllib.parse.urlsplit(canonical(url))
        if (base.scheme, base.netloc) != (target.scheme, target.netloc):
            return False
        prefix = posixpath.dirname(urllib.parse.unquote(base.path).rstrip('/')) + '/'
        if base.path.endswith('/'):
            prefix = urllib.parse.unquote(base.path)
        target_path = posixpath.normpath(urllib.parse.unquote(target.path))
        return target_path == prefix.rstrip('/') or target_path.startswith(prefix)
    except (ValueError, TypeError):
        return False


def discover(body, base):
    if body.lstrip().startswith('<?xml') or body.lstrip().startswith(('<urlset', '<sitemapindex', '<rss', '<feed')):
        try:
            root = ET.fromstring(body)
            links = [node.text for node in root.iter() if node.tag.split('}')[-1] in ('loc', 'link') and node.text]
            links += [node.attrib['href'] for node in root.iter() if node.tag.split('}')[-1] == 'link' and node.attrib.get('href')]
        except ET.ParseError:
            return []
    else:
        parser = PageParser()
        parser.feed(body)
        links = parser.links
    result = []
    for link in links[:1000]:
        try:
            value = canonical(urllib.parse.urljoin(base, link.strip()))
            if value not in result:
                result.append(value)
        except ValueError:
            continue
    return result


def create_job(store, source_id, max_pages=5, max_depth=1, render=False):
    sources = store.rows("SELECT * FROM sources WHERE id=? AND kind='web'", (source_id,))
    if not sources:
        raise ValueError('Choose an existing configured web source.')
    max_pages, max_depth = int(max_pages), int(max_depth)
    if not 1 <= max_pages <= 20 or not 0 <= max_depth <= 3:
        raise ValueError('Crawls allow 1–20 pages and depth 0–3.')
    job_id = uuid.uuid4().hex
    options = {'max_pages': max_pages, 'max_depth': max_depth, 'render': bool(render), 'root': canonical(sources[0]['location'])}
    with store.db() as db:
        db.execute('BEGIN IMMEDIATE')
        active = db.execute("SELECT id FROM crawl_jobs WHERE source_id=? AND state IN ('queued','running')", (source_id,)).fetchone()
        if active:
            raise ValueError('A crawl is already active for this source.')
        db.execute('INSERT INTO crawl_jobs(id,source_id,state,options,created_at,updated_at) VALUES(?,?,?,?,?,?)', (job_id, source_id, 'queued', json.dumps(options), now(), now()))
        db.execute('INSERT INTO crawl_pages(job_id,url,depth) VALUES(?,?,0)', (job_id, sources[0]['location']))
    return get_job(store, job_id)


def get_job(store, job_id):
    rows = store.rows('SELECT * FROM crawl_jobs WHERE id=?', (job_id,))
    if not rows:
        raise ValueError('Collection job not found.')
    job = rows[0]
    job['options'] = json.loads(job['options'])
    job['pages'] = store.rows('SELECT url,depth,state,run_id,detail FROM crawl_pages WHERE job_id=? ORDER BY depth,url', (job_id,))
    return job


def cancel_job(store, job_id):
    get_job(store, job_id)
    with store.db() as db:
        db.execute("UPDATE crawl_jobs SET state='cancelled',updated_at=?,detail='Cancelled. An in-flight request may finish; no further pages will start.' WHERE id=?", (now(), job_id))
    return get_job(store, job_id)


def step_job(store, job_id):
    timestamp = time.time()
    with store.db() as db:
        db.execute('BEGIN IMMEDIATE')
        row = db.execute('SELECT * FROM crawl_jobs WHERE id=?', (job_id,)).fetchone()
        if not row:
            raise ValueError('Collection job not found.')
        job = dict(row)
        if job['state'] not in ('queued', 'running') or job['next_attempt'] > timestamp:
            return {'id': job_id, 'state': job['state']}
        if job['state'] == 'running' and job['lease_until'] > timestamp:
            try:
                os.kill(job['owner'], 0)
                return {'id': job_id, 'state': 'running'}
            except (ProcessLookupError, TypeError):
                pass
        page = db.execute("SELECT * FROM crawl_pages WHERE job_id=? AND state='queued' ORDER BY depth,url LIMIT 1", (job_id,)).fetchone()
        if not page:
            db.execute("UPDATE crawl_jobs SET state='complete',updated_at=? WHERE id=?", (now(), job_id))
            return {'id': job_id, 'state': 'complete'}
        page = dict(page)
        db.execute("UPDATE crawl_jobs SET state='running',owner=?,lease_until=?,updated_at=? WHERE id=?", (os.getpid(), timestamp+180, now(), job_id))
    options = json.loads(job['options'])
    try:
        result = store.collect(job['source_id'], target_url=page['url'], render=options['render'])
    except ValueError as exc:
        host = urllib.parse.urlsplit(options['root']).hostname
        cooldown = store.rows('SELECT until FROM cooldowns WHERE origin=?', (host,))
        delay = max(timestamp+60, cooldown[0]['until'] if cooldown else 0)
        with store.db() as db:
            db.execute("UPDATE crawl_jobs SET state='queued',next_attempt=?,detail=?,updated_at=? WHERE id=? AND state!='cancelled'", (delay, str(exc), now(), job_id))
        return get_job(store, job_id)
    with store.db() as db:
        db.execute('BEGIN IMMEDIATE')
        db.execute('UPDATE crawl_pages SET state=?,run_id=?,detail=? WHERE job_id=? AND url=?', (result['state'], result['id'], result['detail'], job_id, page['url']))
        current = db.execute('SELECT state FROM crawl_jobs WHERE id=?', (job_id,)).fetchone()
        if current['state'] == 'cancelled':
            return {'id': job_id, 'state': 'cancelled'}
        count = db.execute('SELECT COUNT(*) FROM crawl_pages WHERE job_id=?', (job_id,)).fetchone()[0]
        if result['state'] in ('available', 'discovery') and page['depth'] < options['max_depth']:
            if result.get('discovered_urls') is not None:
                links = result['discovered_urls']
            else:
                item = db.execute('SELECT r.raw FROM items i JOIN revisions r ON r.id=i.current_revision WHERE i.source_id=? AND i.external_id=?', (job['source_id'], page['url'])).fetchone()
                links = discover(item['raw'], page['url']) if item else []
            for link in links:
                if count >= options['max_pages']:
                    break
                if canonical(link) != options['root'] and in_scope(options['root'], link):
                    inserted = db.execute('INSERT OR IGNORE INTO crawl_pages(job_id,url,depth) VALUES(?,?,?)', (job_id, link, page['depth']+1)).rowcount
                    count += inserted
        pending = db.execute("SELECT COUNT(*) FROM crawl_pages WHERE job_id=? AND state='queued'", (job_id,)).fetchone()[0]
        blocked = db.execute("SELECT COUNT(*) FROM crawl_pages WHERE job_id=? AND state NOT IN ('available','discovery','queued')", (job_id,)).fetchone()[0]
        state = 'queued' if pending else 'partial' if blocked else 'complete'
        detail = f'{count-pending}/{count} pages checked; {blocked} incomplete. Bound: {options["max_pages"]} pages, depth {options["max_depth"]}. Same origin and configured path scope only.'
        db.execute('UPDATE crawl_jobs SET state=?,updated_at=?,detail=?,lease_until=0 WHERE id=?', (state, now(), detail, job_id))
    return get_job(store, job_id)
