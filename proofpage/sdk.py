"""Local Python SDK. No network calls except explicit capture/refresh."""
from .core import Store
from . import evidence


class Proofpage:
    def __init__(self, home=None):
        self.store = Store(home)

    def capture(self, url):
        source = self.store.source(url, 'web', url)
        result = self.store.collect(source['id'])
        revisions = self.store.rows('SELECT current_revision FROM items WHERE source_id=? AND external_id=?', (source['id'], url))
        return {'collection': result, 'revision_ids': [r['current_revision'] for r in revisions] if result['state'] == 'available' else []}

    def import_capture(self, url, *, text, original, content_type='text/html', collector='external'):
        """Import a collector result without network access or authenticity claims."""
        import base64
        import json
        from urllib.parse import urlsplit
        parsed = urlsplit(url)
        if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError('Provide an HTTP(S) source URL without credentials.')
        if not isinstance(text, str) or not isinstance(original, bytes) or not original:
            raise ValueError('Provide extracted text and nonempty original bytes.')
        if len(original) > 8 * 1024 * 1024 or len(text.encode('utf-8')) > 8 * 1024 * 1024:
            raise ValueError('Imported text and originals must each be at most 8 MiB.')
        if not isinstance(collector, str) or not 1 <= len(collector) <= 200:
            raise ValueError('Provide a collector name up to 200 characters.')
        if not isinstance(content_type, str) or not 1 <= len(content_type) <= 200:
            raise ValueError('Provide a content type up to 200 characters.')
        source = self.store.source(collector + ' capture', 'import', 'external:' + url)
        metadata = {'adapter': 'external_capture', 'source_url': url, 'collector': collector,
                    'external_original': {'sha256': evidence.sha(original), 'bytes': len(original), 'mime': content_type},
                    'coverage': 'Caller-supplied content, not an authenticated HTTP observation. Collector output may differ from the server response.'}
        raw = json.dumps({'encoding': 'base64', 'data': base64.b64encode(original).decode('ascii')})
        self.store.save(source['id'], url, 'text', parsed.hostname, text, raw, metadata)
        row = self.store.rows('SELECT id,current_revision FROM items WHERE source_id=? AND external_id=?', (source['id'], url))[0]
        return {'item_id': row['id'], 'revision_id': row['current_revision'], 'source_id': source['id']}

    def record(self, revision_ids, *, dependencies=None, name='Evidence run'):
        return evidence.record(self.store, revision_ids, dependencies, name)

    def check(self, manifest):
        return evidence.compare(self.store, manifest)

    def refresh(self, manifest):
        return evidence.refresh(self.store, manifest)

    def record_context(self, query, *, output_id, name='Evidence run'):
        from .evidence_runs import record_context
        return record_context(self.store, query, output_id, name)

    def replay_context(self, run_id):
        from .evidence_runs import replay_context
        return replay_context(self.store, run_id)

    def check_run(self, run_id):
        from .evidence_runs import check
        return check(self.store, run_id)

    def affected_outputs(self, item_id):
        from .evidence_runs import affected
        return affected(self.store, item_id)

    def export_run(self, run_id, path):
        from .evidence_runs import get
        return evidence.write(get(self.store, run_id), path)

    def create_business(self, name):
        from .business import create
        return create(self.store, name)

    def attach_business_source(self, profile_id, revision_id, role):
        from .business import attach
        return attach(self.store, profile_id, revision_id, role)

    def draft_business(self, profile_id):
        from .business import draft
        return draft(self.store, profile_id)

    def business_context(self, profile_id):
        from .business import approved
        return approved(self.store, profile_id)

    def review_business_fact(self, fact_id, text, decision, *, permission=False, acknowledge=False):
        from .business import review
        return review(self.store, fact_id, text, decision, permission, acknowledge)

    def business_training_draft(self, fact_id, prompt):
        from .business import training_draft
        return training_draft(self.store, fact_id, prompt)

    def export_business(self, profile_id):
        from .business import export_pack
        return export_pack(self.store, profile_id)

    replay = staticmethod(evidence.replay)
    write = staticmethod(evidence.write)
