"""Origin-based boundary for Google Workspace data, including saved derivatives.

The local reader and private backups may retain this material. Assistant transports,
portable context, and training must not expose it. Older revision hashes stay intact.
"""
import json


LOCAL_ONLY = ('personal_context_only', 'local_only')
MESSAGE = ('Google Docs data is personal context for this computer only. It cannot be '
           'shared through MCP, assistant context packs, portable evidence, or training. '
           'Use the local reader or an explicitly configured offline model.')


def _marked(value):
    if not isinstance(value, dict):
        return False
    return (value.get('adapter') == 'google_docs' or value.get('data_use') in LOCAL_ONLY
            or str(value.get('location', '')).startswith('google-doc:'))


class Policy:
    """One read snapshot per operation; propagate restrictions through provenance."""
    def __init__(self, store):
        rows = store.rows('SELECT r.id,r.item_id,r.metadata,i.source_id,s.location '
                          'FROM revisions r JOIN items i ON i.id=r.item_id '
                          'JOIN sources s ON s.id=i.source_id') if store is not None else []
        self.revisions, self.items, self.sources, self.tokens = set(), set(), set(), set()
        pending = []
        for row in rows:
            metadata = json.loads(row['metadata'])
            if _marked(metadata) or row['location'].startswith('google-doc:'):
                self.sources.add(row['source_id'])
                self.tokens.add(row['location'])
                source_url = metadata.get('source_url')
                if source_url:
                    self.tokens.add(source_url)
                self._add(row)
            else:
                pending.append((row, metadata))
        # Includes legacy observed-tool traces and explicit derived_from revision IDs.
        # Revisit earlier rows when a later derivative becomes restricted.
        changed = True
        while changed:
            changed = False
            remaining = []
            for row, metadata in pending:
                if row['source_id'] in self.sources or row['item_id'] in self.items or self.contains(metadata):
                    self._add(row)
                    changed = True
                else:
                    remaining.append((row, metadata))
            pending = remaining

    def _add(self, row):
        self.revisions.add(row['id'])
        self.items.add(row['item_id'])
        self.tokens.update((row['id'], row['item_id'], row['source_id'])
                           if row['source_id'] in self.sources else (row['id'], row['item_id']))

    def contains(self, value):
        if isinstance(value, dict):
            if _marked(value):
                return True
            return any(self.contains(v) for v in value.values())
        if isinstance(value, (list, tuple)):
            return any(self.contains(v) for v in value)
        if isinstance(value, str):
            if value in self.tokens or value.startswith('google-doc:'):
                return True
            # Raw database JSON in older metadata, reports and manifests.
            if value.startswith(('{', '[')):
                try:
                    return self.contains(json.loads(value))
                except (ValueError, RecursionError):
                    pass
        return False

    def require_shareable(self, value):
        if self.contains(value):
            raise ValueError(MESSAGE)
        return value


def require_training(store, revision_id):
    if Policy(store).contains(revision_id):
        raise ValueError('Google Docs data is personal context only and cannot be used in training datasets or training drafts.')
