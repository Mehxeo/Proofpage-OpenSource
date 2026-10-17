"""Bounded, persistent polling of explicitly configured export folders."""
import hashlib
import json
import os
import time
import uuid
from pathlib import Path

from .core import MAX_BYTES, archive_entries, import_file, now

SUPPORTED = {'.zip', '.csv', '.json', '.jsonl', '.txt', '.md', '.html'}


def create_watch(store, profile_id, directory, categories):
    if not store.rows('SELECT 1 FROM import_profiles WHERE id=?', (profile_id,)):
        raise ValueError('Choose an existing import profile.')
    path = Path(directory).expanduser().resolve(strict=True)
    if not path.is_dir():
        raise ValueError('Choose a folder.')
    if not isinstance(categories, list) or not categories or any(not isinstance(c, str) or Path(c).name != c for c in categories):
        raise ValueError('Select exact category file names, such as Messages.csv or conversations.json.')
    watch_id = uuid.uuid4().hex
    with store.db() as db:
        if db.execute('SELECT 1 FROM watches WHERE profile_id=? AND directory=?', (profile_id, str(path))).fetchone():
            raise ValueError('This profile already watches this folder.')
        db.execute('INSERT INTO watches(id,profile_id,directory,categories,created_at) VALUES(?,?,?,?,?)', (watch_id, profile_id, str(path), json.dumps(sorted(set(categories))), now()))
    return store.rows('SELECT * FROM watches WHERE id=?', (watch_id,))[0]


def signature(stat):
    return f'{stat.st_dev}:{stat.st_ino}:{stat.st_size}:{stat.st_mtime_ns}'


def scan_watch(store, watch_id, clock=None):
    timestamp = time.time() if clock is None else clock
    rows = store.rows('SELECT * FROM watches WHERE id=?', (watch_id,))
    if not rows:
        raise ValueError('Watch not found.')
    watch = rows[0]
    if not watch['enabled']:
        return {'state': 'paused', 'imported': 0}
    owner = uuid.uuid4().hex
    with store.db() as db:
        db.execute('BEGIN IMMEDIATE')
        lease = db.execute('SELECT * FROM watch_leases WHERE watch_id=?', (watch_id,)).fetchone()
        if lease and lease['expires'] > timestamp:
            return {'state': 'busy', 'imported': 0}
        db.execute('INSERT OR REPLACE INTO watch_leases VALUES(?,?,?)', (watch_id, owner, timestamp + 300))
    imported, failed, settling, skipped = 0, 0, 0, 0
    state, detail = 'ready', ''
    try:
        directory = Path(watch['directory'])
        if not directory.is_dir() or directory.is_symlink():
            raise ValueError('Watched folder is unavailable or was replaced by a symbolic link.')
        paths = []
        # Enumeration is bounded even when the folder has many irrelevant files.
        with os.scandir(directory) as listing:
            for index, entry in enumerate(listing):
                if index >= 2000:
                    raise ValueError('Folder has more than 2,000 entries; choose a smaller export folder.')
                if entry.is_file(follow_symlinks=False) and Path(entry.name).suffix.lower() in SUPPORTED:
                    paths.append(Path(entry.path))
        if len(paths) > 200:
            raise ValueError('Folder has more than 200 supported files; choose a smaller export folder.')
        categories = set(json.loads(watch['categories']))
        for path in sorted(paths):
            with store.db() as db:
                active = db.execute('SELECT enabled FROM watches WHERE id=?', (watch_id,)).fetchone()
                if not active or not active['enabled']:
                    state = 'paused'
                    break
                db.execute('UPDATE watch_leases SET expires=? WHERE watch_id=? AND owner=?', (timestamp + 300, watch_id, owner))
            stat = path.lstat()
            if path.is_symlink():
                continue
            sig = signature(stat)
            previous = store.rows('SELECT * FROM watch_files WHERE watch_id=? AND path=?', (watch_id, path.name))
            if not previous or previous[0]['signature'] != sig:
                with store.db() as db:
                    db.execute("INSERT INTO watch_files(watch_id,path,signature,first_seen) VALUES(?,?,?,?) ON CONFLICT(watch_id,path) DO UPDATE SET signature=excluded.signature,first_seen=excluded.first_seen,state='settling',detail=''", (watch_id, path.name, sig, timestamp))
                settling += 1
                continue
            previous = previous[0]
            if previous['state'] != 'settling':
                skipped += 1
                continue
            if timestamp - previous['first_seen'] < 2:
                settling += 1
                continue
            content_hash = None
            try:
                if stat.st_size > MAX_BYTES:
                    raise ValueError('File exceeds the 8 MiB import limit.')
                flags = os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0)
                with os.fdopen(os.open(path, flags), 'rb') as handle:
                    if signature(os.fstat(handle.fileno())) != sig:
                        settling += 1
                        continue
                    data = handle.read(MAX_BYTES + 1)
                    if signature(os.fstat(handle.fileno())) != sig:
                        settling += 1
                        continue
                if len(data) > MAX_BYTES:
                    raise ValueError('File exceeds the 8 MiB import limit.')
                content_hash = hashlib.sha256(data).hexdigest()
                entries = archive_entries(path.name, data)
                selected = [name for name, _ in entries if Path(name).name in categories]
                if not selected:
                    result_state, result_detail = 'ignored', 'No configured categories present.'
                else:
                    result = import_file(store, path.name, data, selected, watch['profile_id'])
                    result_state, result_detail = result['state'], json.dumps(result)
                    missing = categories - {Path(name).name for name, _ in entries}
                    if missing and path.suffix.lower() == '.zip':
                        result_state = 'partial'
                        result_detail += '\nConfigured categories absent: ' + ', '.join(sorted(missing))
                    imported += result['added']
                    failed += int(result_state in ('partial', 'failed'))
            except (ValueError, OSError) as exc:
                failed += 1
                result_state, result_detail = 'failed', str(exc)[:500]
            with store.db() as db:
                db.execute('UPDATE watch_files SET content_hash=?,state=?,detail=? WHERE watch_id=? AND path=?', (content_hash, result_state, result_detail, watch_id, path.name))
        if state != 'paused':
            problems = store.rows("SELECT COUNT(*) n FROM watch_files WHERE watch_id=? AND state IN ('failed','partial')", (watch_id,))[0]['n']
            state = 'attention' if problems else 'settling' if settling else 'ready'
        detail = f'{imported} new revisions; {settling} files settling; {failed} failures this scan. Files are checked again after they change.'
    except (ValueError, OSError) as exc:
        state, detail = 'unavailable', str(exc)[:500]
    finally:
        with store.db() as db:
            db.execute("UPDATE watches SET state=CASE WHEN enabled=0 THEN 'paused' ELSE ? END,detail=? WHERE id=?", (state, detail, watch_id))
            db.execute('DELETE FROM watch_leases WHERE watch_id=? AND owner=?', (watch_id, owner))
    return {'state': state, 'imported': imported, 'detail': detail}
