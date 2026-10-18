"""Grounded training examples, explicit review, and reproducible trainer bundles."""
import io
import json
import uuid
import zipfile

from .core import digest, now
from .quality import findings, grouped_splits, redact

KINDS = ('sft', 'preference', 'correction', 'trace', 'evaluation')


def text(value, label, limit=50000):
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValueError(f'{label} must be nonempty text up to {limit} characters.')
    return value


def validate_payload(kind, payload):
    if kind not in KINDS or not isinstance(payload, dict):
        raise ValueError('Choose a supported training example type.')
    if kind == 'sft':
        messages = payload.get('messages')
        if not isinstance(messages, list) or not 2 <= len(messages) <= 100:
            raise ValueError('SFT requires 2–100 messages ending with an assistant response.')
        for message in messages:
            if not isinstance(message, dict) or message.get('role') not in ('system', 'user', 'assistant') or set(message) != {'role', 'content'}:
                raise ValueError('SFT messages require role and content. Tool traces use the trace format.')
            text(message['content'], 'Message')
        if messages[-1]['role'] != 'assistant' or not any(m['role'] == 'user' for m in messages[:-1]):
            raise ValueError('SFT needs user context and a final assistant target.')
        return {'messages': messages}
    if kind == 'preference':
        result = {key: text(payload.get(key), key) for key in ('prompt', 'chosen', 'rejected')}
        if result['chosen'].strip() == result['rejected'].strip():
            raise ValueError('Preferred and rejected responses must differ.')
        return result
    if kind == 'correction':
        return {key: text(payload.get(key), key) for key in ('prompt', 'completion')}
    if kind == 'evaluation':
        return {key: text(payload.get(key), key) for key in ('prompt', 'reference')}
    # Traces are preserved as observed events, never invented reasoning or generic SFT.
    events = payload.get('events')
    if not isinstance(events, list) or not 1 <= len(events) <= 200:
        raise ValueError('Observed traces need 1–200 supplied events.')
    for event in events:
        if not isinstance(event, dict) or event.get('type') not in ('tool_call', 'tool_result', 'message', 'outcome'):
            raise ValueError('Trace events need a supported type.')
    return {'events': events}


def get_candidate(store, candidate_id):
    rows = store.rows('SELECT * FROM candidates WHERE id=?', (candidate_id,))
    if not rows:
        raise ValueError('Training example not found.')
    result = rows[0]
    for key in ('payload', 'citations', 'mapping', 'findings'):
        result[key] = json.loads(result[key])
    return result


def create_candidate(store, revision_id, kind, payload, quote, notes='', origin='manual', mapping=None, redact_sensitive=False, parent_id=None):
    revision = store.revision(revision_id)
    payload = validate_payload(kind, payload)
    quote = text(quote, 'Evidence quote')
    offset = revision['text'].find(quote)
    if offset < 0:
        raise ValueError('The evidence quote must appear verbatim in the selected revision.')
    mapping = mapping or {}
    if revision['kind'] == 'human_message':
        normalized = json.loads(revision['metadata']).get('normalized') or {}
        sender = normalized.get('sender')
        if not sender or mapping.get('target_participant') != sender or not mapping.get('context_confirmed') or not mapping.get('roles_approved'):
            raise ValueError('Human messages require the actual target participant, confirmed context, and explicit role-mapping approval.')
    if kind == 'preference':
        text(notes, 'Preference rationale', 5000)
    if kind == 'trace':
        metadata = json.loads(revision['metadata'])
        observed = metadata.get('observed_events')
        if not observed or payload['events'] != observed:
            raise ValueError('Trace examples must match events actually recorded by Proofpage.')
    if parent_id:
        parent = get_candidate(store, parent_id)
        if parent['revision_id'] != revision_id:
            raise ValueError('Example revisions must reference the same evidence revision.')
    citations = [{'revision_id': revision_id, 'item_id': revision['item_id'], 'source_id': revision['source_id'],
                  'source_hash': revision['hash'], 'start': offset, 'end': offset+len(quote), 'quote': quote,
                  'captured_at': revision['captured_at'], 'source_time': revision['source_time']}]
    if redact_sensitive:
        payload, citations, notes = redact(payload), redact(citations), redact(notes)
    serialized = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    screening = findings(serialized + json.dumps(citations) + notes)
    example_id = uuid.uuid4().hex
    with store.db() as db:
        db.execute('INSERT INTO candidates VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',
                   (example_id, revision_id, kind, serialized, json.dumps(citations), origin[:200], notes[:5000], json.dumps(mapping), json.dumps(screening), 'draft', digest(serialized), now(), parent_id))
    return get_candidate(store, example_id)


def review_candidate(store, candidate_id, decision, acknowledge_warnings=False):
    if decision not in ('approved', 'rejected', 'revoked', 'draft'):
        raise ValueError('Invalid review decision.')
    candidate = get_candidate(store, candidate_id)
    with store.db() as db:
        db.execute('BEGIN IMMEDIATE')
        if decision == 'approved':
            if not db.execute('SELECT 1 FROM reviews WHERE revision_id=? AND allowed=1', (candidate['revision_id'],)).fetchone():
                raise ValueError('Confirm permission for the evidence revision before approving this example.')
            if any(f['severity'] == 'block' for f in candidate['findings']):
                raise ValueError('Detected credentials must be redacted before approval. Save a redacted example revision.')
            if candidate['findings'] and not acknowledge_warnings:
                raise ValueError('Review and acknowledge the screening findings before approval.')
        db.execute('UPDATE candidates SET status=? WHERE id=?', (decision, candidate_id))
    return get_candidate(store, candidate_id)


def branch_candidate(store, revision_id, target_id):
    revision = store.revision(revision_id)
    if revision['kind'] != 'ai_conversation':
        raise ValueError('Choose a supplied AI conversation.')
    normalized = json.loads(revision['metadata']).get('normalized') or {}
    nodes = {m['id']: m for m in normalized.get('messages', []) if m.get('id')}
    if target_id not in nodes or nodes[target_id].get('role') != 'assistant':
        raise ValueError('Select an actual source assistant message as the target.')
    chain, visited, current = [], set(), target_id
    while current is not None:
        if current in visited or current not in nodes:
            raise ValueError('The chosen branch has a cycle or missing parent; no training example was created.')
        visited.add(current)
        node = nodes[current]
        role = node.get('role')
        if role is None and not node.get('text'):
            current = node.get('parent')
            continue
        if role not in ('system', 'user', 'assistant'):
            raise ValueError('This branch includes an unmapped or tool role. Preserve it as evidence instead of flattening it into SFT.')
        chain.append({'role': role, 'content': text(node.get('text'), 'Source message')})
        current = node.get('parent')
    chain.reverse()
    return create_candidate(store, revision_id, 'sft', {'messages': chain}, nodes[target_id]['text'],
                            notes='Explicitly selected source branch; review context and target before approval.', origin='source_branch')


def freeze_training(store, name, candidate_ids, kind):
    if kind not in KINDS or not isinstance(candidate_ids, list) or not 1 <= len(candidate_ids) <= 500 or len(candidate_ids) != len(set(candidate_ids)):
        raise ValueError('Select 1–500 unique reviewed examples of one type.')
    candidates, records, seen = [], [], set()
    for candidate_id in candidate_ids:
        candidate = get_candidate(store, candidate_id)
        if candidate['status'] != 'approved' or candidate['kind'] != kind:
            raise ValueError('All selected examples must be approved and have the selected type.')
        if candidate['hash'] in seen:
            continue
        seen.add(candidate['hash'])
        revision = store.revision(candidate['revision_id'])
        candidates.append(candidate)
        records.append({'text': json.dumps(candidate['payload'], sort_keys=True), 'source_id': revision['source_id']})
    groups = grouped_splits(records)
    lines, provenance = [], []
    for candidate, (group, split) in zip(candidates, groups):
        # Evaluations are held out by definition and exported separately.
        split = 'test' if kind == 'evaluation' else split
        lines.append(json.dumps(candidate['payload'], ensure_ascii=False))
        provenance.append({'candidate_id': candidate['id'], 'hash': candidate['hash'], 'split': split, 'group': group,
                           'citations': candidate['citations'], 'origin': candidate['origin'], 'notes': candidate['notes']})
    payload = '\n'.join(lines) + '\n'
    from . import rights
    snapshot = rights.freeze_snapshot(store, sorted({c['revision_id'] for c in candidates}))
    dataset_id = uuid.uuid4().hex
    manifest = {'schema': 'proofpage.training.v1', 'kind': kind, 'created_at': now(), 'payload_sha256': digest(payload),
                'records': provenance, 'split_policy': 'Source groups and 0.85 Jaccard word-shingle neighbors stay together; exact example duplicates removed.',
                'review': 'Human review required; grounded quotes do not automatically prove answer correctness.',
                'screening': 'Heuristic credentials/PII checks, not a comprehensive privacy guarantee.'}
    with store.db() as db:
        db.execute('BEGIN IMMEDIATE')
        for candidate in candidates:
            if not db.execute("SELECT 1 FROM candidates c JOIN reviews r ON r.revision_id=c.revision_id WHERE c.id=? AND c.status='approved' AND r.allowed=1", (candidate['id'],)).fetchone():
                raise ValueError('Permission or approval changed; review the selected examples again.')
        db.execute('INSERT INTO datasets VALUES(?,?,?,?,?,?)', (dataset_id, text(name, 'Dataset name', 200), now(), payload, json.dumps(sorted({c['revision_id'] for c in candidates})), digest(payload)))
        db.execute('INSERT INTO dataset_manifests VALUES(?,?,?,?)', (dataset_id, kind, json.dumps(manifest), json.dumps([c['id'] for c in candidates])))
        rights.save_snapshot(db, dataset_id, snapshot)
    return {'id': dataset_id, 'records': len(candidates), 'hash': digest(payload), 'kind': kind, 'rights': rights.snapshot_counts(snapshot),
            'splits': {split: sum(r['split'] == split for r in provenance) for split in ('train', 'validation', 'test')}}


def export_bundle(store, dataset_id):
    payload = store.export(dataset_id)
    rows = store.rows('SELECT manifest FROM dataset_manifests WHERE dataset_id=?', (dataset_id,))
    if not rows:
        raise ValueError('This is a legacy corpus export. Export it as JSONL.')
    manifest = json.loads(rows[0]['manifest'])
    lines = payload.splitlines()
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
        files = {'manifest.json': json.dumps(manifest, indent=2), 'data.jsonl': payload,
                 'README.md': '# Proofpage training bundle\n\nReview manifest.json for sources, permissions, origin and split counts.\nUse train.jsonl for fitting, validation.jsonl for tuning, and test.jsonl only for evaluation.\nEmpty splits are possible with small source-group counts. Add independent sources instead of splitting a conversation across partitions.\nThis export does not itself train a model.\n',
                 'validate.py': BUNDLE_VALIDATOR}
        for split in ('train', 'validation', 'test'):
            selected = [line for line, record in zip(lines, manifest['records']) if record['split'] == split]
            files[split + '.jsonl'] = '\n'.join(selected) + ('\n' if selected else '')
        files.update(rights_files(store, dataset_id, manifest))
        for name, contents in sorted(files.items()):
            info = zipfile.ZipInfo(name, date_time=(2020, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, contents)
    return buffer.getvalue()


RIGHTS_README = '''# Rights at freeze

Each line of `rights.jsonl` records, for one example's source revision, the publisher's machine-readable
AI-training signal when this bundle was frozen and any rights basis a reviewer recorded.

- `reserved`: the publisher reserved AI training. Included only with a recorded basis.
- `conditional`: a published license or terms apply.
- `allowed`: an explicit permission signal was published.
- `unknown`: no machine-readable signal was found. This is not permission.
- `user_supplied`: from an archive you supplied; no publisher signal applies.
- `not_recorded`: captured before Proofpage recorded publisher signals.

Rights can change after freezing. Proofpage flags datasets whose sources later changed their signals, and blocks
new downloads when a source now reserves AI training and no rights basis is recorded.
`TRAINING_CONTENT_SUMMARY.md`, `DATASET_CARD.md`, and `croissant.json` are drafts to complete before publishing.
This is not legal advice.

'''


def rights_files(store, dataset_id, manifest):
    from .compliance import build
    snapshot = {row['revision_id']: row for row in store.rows('SELECT revision_id,verdict,basis FROM dataset_rights WHERE dataset_id=?', (dataset_id,))}
    ids = [record['candidate_id'] for record in manifest['records']]
    revision_of = {row['id']: row['revision_id'] for row in store.rows(f"SELECT id,revision_id FROM candidates WHERE id IN ({','.join('?' * len(ids))})", ids)} if ids else {}
    lines, counts = [], {}
    for candidate_id in ids:
        revision_id = revision_of.get(candidate_id)
        entry = snapshot.get(revision_id, {})
        verdict = entry.get('verdict', 'not_recorded')
        counts[verdict] = counts.get(verdict, 0) + 1
        lines.append(json.dumps({'candidate_id': candidate_id, 'revision_id': revision_id, 'verdict_at_freeze': verdict, 'rights_basis': entry.get('basis')}, sort_keys=True))
    docs = build(store, dataset_id)
    return {'rights.jsonl': '\n'.join(lines) + ('\n' if lines else ''),
            'RIGHTS.md': RIGHTS_README + ''.join(f'- {verdict}: {count}\n' for verdict, count in sorted(counts.items())),
            'TRAINING_CONTENT_SUMMARY.md': docs['summary_markdown'], 'DATASET_CARD.md': docs['dataset_card'],
            'croissant.json': json.dumps(docs['croissant'], indent=2, sort_keys=True) + '\n'}


BUNDLE_VALIDATOR = '''"""Validate a frozen Proofpage bundle before training (Python standard library)."""
import hashlib, json
from pathlib import Path
root = Path(__file__).parent
manifest = json.loads((root / 'manifest.json').read_text())
payload = (root / 'data.jsonl').read_bytes()
assert hashlib.sha256(payload).hexdigest() == manifest['payload_sha256'], 'Checksum mismatch'
rows = payload.decode().splitlines()
assert len(rows) == len(manifest['records']), 'Record count mismatch'
groups = {}
for line, record in zip(rows, manifest['records']):
    json.loads(line)
    group, split = record['group'], record['split']
    assert group not in groups or groups[group] == split, 'Group crosses splits'
    groups[group] = split
for split in ('train', 'validation', 'test'):
    expected = [line for line, r in zip(rows, manifest['records']) if r['split'] == split]
    assert (root / (split + '.jsonl')).read_text().splitlines() == expected, 'Split file mismatch'
print('Valid:', len(rows), 'examples;', manifest['kind'])
'''
