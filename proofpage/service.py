"""Shared workspace API used by local and authenticated hosted transports."""
import base64
import json
import time
from .core import import_file, preview
from .imports import create_profile
from .watch import create_watch, scan_watch
from . import training, crawl, models, agent, history
from .mcp import TOOLS

def response(status, value, content_type='application/json'):
    return status, value, content_type

def with_blockers(store, datasets):
    """Count revisions that currently block each dataset's download (see rights.export_blockers)."""
    from .rights import export_blockers
    for dataset in datasets:
        dataset['rights_blocked'] = len(export_blockers(store, dataset['id'], json.loads(dataset.pop('revision_ids'))))
    return datasets


def get(store, path, query):
    if path == '/api/state':
        return response(200, {'sources': store.rows('SELECT s.*,(SELECT o.verdict FROM rights_observations o WHERE o.source_id=s.id ORDER BY o.observed_at DESC LIMIT 1) rights FROM sources s'), 'profiles': store.rows('SELECT * FROM import_profiles'), 'watches': store.rows('SELECT * FROM watches'), 'runs': store.rows('SELECT * FROM runs ORDER BY started_at DESC LIMIT 30'), 'datasets': with_blockers(store, store.rows('SELECT d.id,d.name,d.created_at,d.hash,d.revision_ids,m.format,(SELECT COUNT(*) FROM dataset_rights x WHERE x.dataset_id=d.id AND x.drifted=1) rights_changed FROM datasets d LEFT JOIN dataset_manifests m ON m.dataset_id=d.id ORDER BY d.created_at DESC')), 'items': store.search(query.get('q', [''])[0], snippets=True),
                                'unread': history.unread_counts(store)['total'], 'total': store.rows('SELECT COUNT(*) n FROM items')[0]['n'], 'approved': store.rows('SELECT COUNT(*) n FROM items i JOIN reviews v ON v.revision_id=i.current_revision WHERE v.approved=1')[0]['n']})
    if path.startswith('/api/watches/'):
        return response(200, store.rows('SELECT path,state,detail FROM watch_files WHERE watch_id=?', (path.rsplit('/', 1)[1],)))
    if path.startswith('/api/items/') and path.endswith('/timeline'):
        try:
            config = models.configuration()
        except ValueError as exc:
            config = {'configured': False, 'detail': str(exc)}
        # The endpoint URL is never sent to the browser here; hosted operators keep theirs private.
        model = {'configured': config['configured'], 'model': config.get('model', ''), 'detail': config['detail']}
        return response(200, dict(history.timeline(store, path.split('/')[3]), model=model))
    if path.startswith('/api/items/'):
        return response(200, store.item(path.rsplit('/', 1)[1]))
    if path == '/api/diff':
        return response(200, history.compare(store, query.get('from', [''])[0], query.get('to', [''])[0]))
    if path.startswith('/api/revisions/'):
        return response(200, store.revision(path.rsplit('/', 1)[1]))
    if path == '/api/workbench':
        try:
            config = models.configuration()
        except ValueError as exc:
            config = {'configured': False, 'detail': str(exc)}
        return response(200, {'candidates': store.rows('SELECT id,revision_id,kind,status,origin,notes,findings,created_at FROM candidates ORDER BY created_at DESC LIMIT 500'),
                              'datasets': with_blockers(store, store.rows('SELECT d.id,d.name,d.created_at,d.hash,d.revision_ids,m.format,m.manifest,(SELECT COUNT(*) FROM dataset_rights x WHERE x.dataset_id=d.id AND x.drifted=1) rights_changed FROM datasets d JOIN dataset_manifests m ON m.dataset_id=d.id ORDER BY d.created_at DESC')),
                              'jobs': store.rows('SELECT * FROM crawl_jobs ORDER BY created_at DESC LIMIT 30'), 'model': config,
                              'recipes': store.rows('SELECT * FROM extraction_recipes'), 'extractions': store.rows('SELECT * FROM extractions ORDER BY created_at DESC LIMIT 30'),
                              'tools': [{'name': name, 'description': description} for name, (description, _) in TOOLS.items()]})
    if path.startswith('/api/compliance/'):
        from .compliance import build
        return response(200, build(store, path.rsplit('/', 1)[1]))
    if path == '/api/inbox':
        return response(200, {'events': history.inbox(store, query.get('kind', [''])[0] or None, query.get('unseen', [''])[0] == '1'), 'unread': history.unread_counts(store)})
    if path.startswith('/api/candidates/'):
        return response(200, training.get_candidate(store, path.rsplit('/', 1)[1]))
    if path.startswith('/api/crawls/'):
        return response(200, crawl.get_job(store, path.rsplit('/', 1)[1]))
    if path.startswith('/api/bundle/'):
        return response(200, training.export_bundle(store, path.rsplit('/', 1)[1]), 'application/zip')
    if path.startswith('/api/export/'):
        return response(200, store.export(path.rsplit('/', 1)[1]), 'application/x-ndjson')
    return response(404, {'error': 'Not found.'})


def post(store, path, data):
    if path == '/api/sources':
        result = store.source(data['name'], 'web', data['url'])
    elif path == '/api/profiles':
        result = create_profile(store, data['name'], data['provider'], data['account'], data.get('adapter', 'auto'), data.get('mapping'))
    elif path == '/api/watches':
        result = create_watch(store, data['profile_id'], data['directory'], data['categories'])
    elif path == '/api/watch-toggle':
        with store.db() as db:
            db.execute("UPDATE watches SET enabled=?,state=? WHERE id=?", (int(data['enabled'] is True), 'ready' if data['enabled'] is True else 'paused', data['watch_id']))
        result = {'saved': True}
    elif path == '/api/watch-scan':
        result = scan_watch(store, data['watch_id'])
    elif path == '/api/collect':
        result = store.collect(data['source_id'], render=data.get('render', False) is True)
    elif path == '/api/crawl':
        result = crawl.create_job(store, data['source_id'], data.get('max_pages', 5), data.get('max_depth', 1), data.get('render', False))
    elif path == '/api/crawl-cancel':
        result = crawl.cancel_job(store, data['job_id'])
    elif path == '/api/context':
        result = agent.context(store, data['query'], data.get('source_ids'), data.get('max_chars', 12000))
    elif path == '/api/freshness':
        result = agent.ensure_fresh(store, data['source_id'], data.get('max_age_seconds', 86400))
    elif path == '/api/candidate':
        result = training.create_candidate(store, data['revision_id'], data['kind'], data['payload'], data['quote'], data.get('notes', ''), mapping=data.get('mapping'), redact_sensitive=data.get('redact', False), parent_id=data.get('parent_id'))
    elif path == '/api/branch-example':
        result = training.branch_candidate(store, data['revision_id'], data['target_id'])
    elif path == '/api/candidate-review':
        result = training.review_candidate(store, data['candidate_id'], data['decision'], data.get('acknowledge', False) is True)
    elif path == '/api/training-freeze':
        result = training.freeze_training(store, data['name'], data['candidate_ids'], data['kind'])
    elif path == '/api/recipe':
        result = models.create_recipe(store, data['name'], data['fields'])
    elif path == '/api/model-assist':
        result = models.assist(store, data['revision_id'], data['purpose'], data.get('recipe_id'))
    elif path == '/api/schedule':
        interval = int(data['interval_seconds'])
        if interval != 0 and interval < 300:
            raise ValueError('Schedules must be at least five minutes apart.')
        with store.db() as db:
            db.execute('UPDATE sources SET interval_seconds=?,next_run=? WHERE id=? AND kind=\'web\'', (interval, time.time() + interval, data['source_id']))
        result = {'saved': True}
    elif path in ('/api/preview', '/api/import'):
        content = base64.b64decode(data['data'], validate=True)
        if path == '/api/import' and not data.get('profile_id'):
            raise ValueError('Choose an account-specific import profile.')
        result = preview(data['filename'], content) if path == '/api/preview' else import_file(store, data['filename'], content, data['selected'], data['profile_id'])
    elif path == '/api/review':
        store.review(data['revision_id'], data['allowed'] is True, data['approved'] is True, data.get('rights_basis'), data.get('rights_note'))
        result = {'saved': True}
    elif path == '/api/change-summary':
        result = history.model_summary(store, data['from_revision'], data['to_revision'])
    elif path == '/api/inbox-seen':
        result = history.mark_seen(store, None if data.get('all') is True else data.get('ids'))
    elif path == '/api/freeze':
        result = store.freeze(data['name'])
    else:
        return response(404, {'error': 'Not found.'})
    return response(200, result)
