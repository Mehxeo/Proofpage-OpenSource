import json
import csv
import uuid
from pathlib import Path

from .adapters import ADAPTERS, parse_entry, validate_mapping
from .core import archive_entries, digest, now


def local_file_profile(store, filename):
    """Simple originals need no account labels; structured exports still do."""
    if (not isinstance(filename, str) or Path(filename).name != filename or
            Path(filename).suffix.lower() not in {'.txt', '.md', '.html', '.htm', '.png', '.jpg', '.jpeg', '.webp', '.pdf'}):
        raise ValueError('Choose an account-specific import profile for conversation exports, JSON, CSV and ZIP archives.')
    provider, account = 'Proofpage local files', 'selected-files'
    profiles = store.rows('SELECT * FROM import_profiles WHERE provider=? AND account=?', (provider, account))
    return profiles[0] if profiles else create_profile(store, 'Local files', provider, account, 'generic')


def create_profile(store, name, provider, account, adapter='auto', mapping=None):
    if not all(isinstance(v, str) and v.strip() for v in (name, provider, account)):
        raise ValueError('Profile name, provider, and account label are required.')
    if adapter not in ADAPTERS:
        raise ValueError('Unknown adapter.')
    if adapter == 'mapping':
        validate_mapping(mapping)
    profile_id = uuid.uuid4().hex
    with store.db() as db:
        if db.execute('SELECT 1 FROM import_profiles WHERE provider=? AND account=?', (provider.strip(), account.strip())).fetchone():
            raise ValueError('This provider/account profile already exists; select it for the next import.')
        db.execute('INSERT INTO import_profiles VALUES(?,?,?,?,?,?,?)', (profile_id, name.strip(), provider.strip(), account.strip(), adapter, json.dumps(mapping or {}), now()))
    return store.rows('SELECT * FROM import_profiles WHERE id=?', (profile_id,))[0]


def import_archive(store, filename, data, selected, profile_id=None):
    entries = archive_entries(filename, data)
    if selected is None:
        raise ValueError('Select categories from the archive preview before importing.')
    if not isinstance(selected, list) or not all(isinstance(n, str) for n in selected):
        raise ValueError('Selected categories must be a list of entry names.')
    selected = set(selected)
    if not selected or not selected.issubset({name for name, _ in entries}):
        raise ValueError('Select valid archive entries.')
    profile = None
    if profile_id:
        profiles = store.rows('SELECT * FROM import_profiles WHERE id=?', (profile_id,))
        if not profiles:
            raise ValueError('Import profile not found.')
        profile = profiles[0]
    location = 'profile:' + profile_id if profile else 'archive:' + Path(filename).name
    source = store.source(profile['name'] if profile else filename, 'import', location)
    added, errors, count = 0, [], 0
    started = now()
    basenames = [Path(name).name for name, _ in entries if name in selected]
    if profile and len(basenames) != len(set(basenames)):
        raise ValueError('Selected categories have duplicate base names; import them under separate profiles.')
    for name, content in entries:
        if name not in selected:
            continue
        try:
            records = parse_entry(name, content, profile['adapter'] if profile else 'auto', json.loads(profile['mapping']) if profile else None)
            for record in records:
                if record['metadata'].get('asset'):
                    from .media import enrich
                    enrich(record, content)
                explicit_id = record['external_id']
                category = Path(name).name if profile else name
                external_id = category + ':' + (str(explicit_id) if explicit_id is not None else digest(record['raw']))
                record['metadata']['profile_id'] = profile_id
                added += int(store.save(source['id'], external_id, record['kind'], record['title'], record['text'], record['raw'], record['metadata'], record['source_time']))
                count += 1
        except (ValueError, UnicodeError, TypeError, AttributeError, csv.Error) as exc:
            errors.append({'entry': name, 'error': str(exc)[:200]})
    state = 'partial' if errors and count else 'failed' if errors else 'available'
    run_id = uuid.uuid4().hex
    detail = json.dumps({'archive': Path(filename).name, 'processed': count, 'errors': errors})
    with store.db() as db:
        db.execute('INSERT INTO runs VALUES(?,?,?,?,?,?,?)', (run_id, source['id'], state, started, now(), detail, added))
        db.execute('UPDATE sources SET state=? WHERE id=?', (state, source['id']))
        db.execute('INSERT INTO observations VALUES(?,?,?,?,?,?)', (uuid.uuid4().hex, source['id'], run_id, state, now(), detail))
    return {'source_id': source['id'], 'run_id': run_id, 'state': state, 'added': added, 'processed': count, 'errors': errors}
