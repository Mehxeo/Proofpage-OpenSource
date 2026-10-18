"""Portable, pinned evidence inputs. Replay is deliberately network-free."""
from . import __version__
import base64
import hashlib
import json
import os
import zlib
from pathlib import Path

from .core import now

SCHEMA = 'proofpage.evidence/v1'
MAX_BYTES = 64 * 1024 * 1024


class EvidenceError(ValueError):
    """Invalid, incomplete, or modified evidence."""


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode('utf-8')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def validate(manifest, expected_sha256=None):
    try:
        body = {k: v for k, v in manifest.items() if k != 'sha256'}
        actual = sha(canonical(body))
        if manifest['schema'] != SCHEMA or actual != manifest['sha256']:
            raise EvidenceError('Manifest schema or checksum mismatch.')
        if expected_sha256 is not None and actual != expected_sha256:
            raise EvidenceError('Manifest does not match the trusted SHA-256 pin.')
        if not isinstance(manifest['dependencies'], list):
            raise EvidenceError('Dependencies must be an array.')
        records = manifest['records']
        if not isinstance(records, list) or not records:
            raise EvidenceError('At least one record is required.')
        by_id = {}
        for record in records:
            for key in ('revision_id', 'revision_hash', 'item_id', 'source_id', 'source_kind', 'location', 'external_id', 'captured_at', 'text', 'text_sha256'):
                if not isinstance(record[key], str):
                    raise EvidenceError('Invalid record field: ' + key)
            if record['source_kind'] not in ('web', 'import'):
                raise EvidenceError('Unsupported source kind.')
            if record['capture'] is not None and not isinstance(record['capture'].get('url'), str):
                raise EvidenceError('Invalid capture URL.')
            rid = record['revision_id']
            if rid in by_id or not isinstance(record['text'], str):
                raise EvidenceError('Duplicate revision or invalid text.')
            if sha(record['text'].encode('utf-8')) != record['text_sha256']:
                raise EvidenceError('Text checksum mismatch.')
            raw = base64.b64decode(record['original']['base64'], validate=True)
            if sha(raw) != record['original']['sha256']:
                raise EvidenceError('Original checksum mismatch.')
            by_id[rid] = record
        for dep in manifest['dependencies']:
            record = by_id[dep['revision_id']]
            start, end = dep['start'], dep['end']
            if (type(start) is not int or type(end) is not int or not 0 <= start < end <= len(record['text'])
                    or record['text'][start:end] != dep['quote'] or not isinstance(dep['output_id'], str)
                    or not dep['output_id'].strip()):
                raise EvidenceError('Dependency must point to an exact, nonempty quote and output ID.')
        return manifest
    except (AttributeError, KeyError, TypeError, UnicodeError, OverflowError) as exc:
        raise EvidenceError('Malformed evidence manifest.') from exc


def record(store, revision_ids, dependencies=None, name='Evidence run'):
    records = []
    # A single SQLite read transaction keeps revisions/captures consistent.
    with store.db() as db:
        db.execute('BEGIN')
        for rid in dict.fromkeys(revision_ids):
            row = db.execute('SELECT r.*,i.source_id,i.external_id,s.location,s.kind source_kind FROM revisions r JOIN items i ON i.id=r.item_id JOIN sources s ON s.id=i.source_id WHERE r.id=?', (rid,)).fetchone()
            if row is None:
                raise EvidenceError('Revision not found: ' + str(rid))
            row = dict(row)
            capture = db.execute('SELECT * FROM captures WHERE revision_id=? ORDER BY requested_at DESC,id DESC LIMIT 1', (rid,)).fetchone()
            original = row['raw'].encode('utf-8')
            representation = 'stored_raw_utf8'
            capture_info = None
            metadata = json.loads(row['metadata'])
            asset = metadata.get('asset') or metadata.get('external_original')
            if asset:
                payload = json.loads(row['raw'])
                original = base64.b64decode(payload['data'], validate=True)
                if sha(original) != asset['sha256'] or len(original) != asset['bytes']:
                    raise EvidenceError('Original file integrity check failed.')
                representation = 'external_collector_bytes' if metadata.get('external_original') else 'supplied_file_exact'
            if capture:
                capture = dict(capture)
                payload = db.execute('SELECT data FROM capture_payloads WHERE sha256=?', (capture['body_sha256'],)).fetchone()
                if payload is None:
                    raise EvidenceError('Original capture payload is missing.')
                original = zlib.decompress(payload['data'])
                if sha(original) != capture['body_sha256']:
                    raise EvidenceError('Stored capture checksum mismatch.')
                representation = 'http_body_exact' if capture['raw_exact'] else 'http_body_reconstructed'
                capture_info = {k: capture[k] for k in ('id', 'url', 'final_url', 'requested_at', 'status', 'headers')}
            records.append({'revision_id': rid, 'revision_hash': row['hash'], 'item_id': row['item_id'],
                            'source_id': row['source_id'], 'source_kind': row['source_kind'],
                            'location': row['location'], 'external_id': row['external_id'],
                            'captured_at': row['captured_at'], 'metadata': json.loads(row['metadata']),
                            'text': row['text'], 'text_sha256': sha(row['text'].encode('utf-8')),
                            'original': {'representation': representation, 'base64': base64.b64encode(original).decode('ascii'), 'sha256': sha(original)},
                            'capture': capture_info})
    manifest = {'schema': SCHEMA, 'name': name, 'created_at': now(), 'records': records,
                'dependencies': json.loads(json.dumps(dependencies or [])), 'producer': 'Proofpage ' + __version__ + ' evidence/v1',
                'scope': 'Pinned external inputs; not model-output determinism or publisher authentication.'}
    manifest['sha256'] = sha(canonical(manifest))
    if len(canonical(manifest)) > MAX_BYTES:
        raise EvidenceError('Manifest exceeds 64 MiB; record fewer revisions.')
    return validate(manifest)


def write(manifest, path):
    validate(manifest)
    data = canonical(manifest) + b'\n'
    if len(data) > MAX_BYTES:
        raise EvidenceError('Manifest exceeds 64 MiB.')
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, 'wb') as handle:
        handle.write(data)
    return manifest['sha256']


def replay(path, expected_sha256=None):
    with Path(path).open('rb') as handle:
        raw = handle.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise EvidenceError('Manifest exceeds 64 MiB.')
    try:
        return validate(json.loads(raw), expected_sha256)
    except (ValueError, RecursionError) as exc:
        raise EvidenceError(str(exc)) from exc


def compare(store, manifest):
    from .history import diff
    validate(manifest)
    results = []
    for old in manifest['records']:
        rows = store.rows('SELECT r.* FROM items i JOIN revisions r ON r.id=i.current_revision WHERE i.id=?', (old['item_id'],))
        current = rows[0] if rows else None
        state = 'missing' if current is None else 'unchanged' if current['hash'] == old['revision_hash'] and sha(current['text'].encode('utf-8')) == old['text_sha256'] else 'changed'
        deps = [d for d in manifest['dependencies'] if d['revision_id'] == old['revision_id']]
        results.append({'revision_id': old['revision_id'], 'location': old['location'], 'state': state,
                        'current_revision_id': current['id'] if current else None,
                        'affected_outputs': sorted({d['output_id'] for d in deps}) if state != 'unchanged' else [],
                        'quotes': [{'output_id': d['output_id'], 'quote': d['quote'], 'present_in_current': bool(current and d['quote'] in current['text'])} for d in deps],
                        'diff': diff(old['text'], current['text']) if current and state == 'changed' else None})
    return {'ok': all(r['state'] == 'unchanged' for r in results), 'records': results,
            'scope': 'Current local workspace only; refresh explicitly to check the live web.'}


def refresh(store, manifest):
    validate(manifest)
    outcomes = []
    seen = set()
    for row in manifest['records']:
        capture = row['capture']
        key = (row['source_id'], capture['url'] if capture else row['location'])
        if key in seen:
            continue
        seen.add(key)
        if row['source_kind'] != 'web':
            outcomes.append({'source_id': key[0], 'state': 'archive_only'})
            continue
        try:
            outcomes.append(store.collect(key[0], target_url=key[1]))
        except ValueError as exc:
            outcomes.append({'source_id': key[0], 'state': 'deferred', 'detail': str(exc)})
    return {'refresh': outcomes, 'comparison': compare(store, manifest)}
