"""Reference loader for Proofpage clean-corpus JSONL (not a training job)."""
import hashlib
import json
from pathlib import Path


def load_corpus(path, expected_hash=None):
    path = Path(path)
    if path.stat().st_size > 64 * 1024 * 1024:
        raise ValueError('Reference loader limit is 64 MiB; use a streaming training pipeline for larger corpora.')
    payload = path.read_bytes()
    actual_hash = hashlib.sha256(payload).hexdigest()
    if expected_hash and expected_hash != actual_hash:
        raise ValueError('Dataset checksum does not match its frozen version.')
    records, groups, identifiers, contents = [], {}, set(), set()
    for number, line in enumerate(payload.decode('utf-8').splitlines(), 1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
            for field in ('id', 'revision_id', 'source_id', 'kind', 'text', 'split', 'captured_at'):
                if not isinstance(record.get(field), str) or not record[field].strip():
                    raise ValueError('Missing or empty ' + field)
            if record['split'] not in ('train', 'validation', 'test'):
                raise ValueError('Invalid split')
            if record['id'] in identifiers:
                raise ValueError('Duplicate item ID')
            identifiers.add(record['id'])
            if record['source_id'] in groups and groups[record['source_id']] != record['split']:
                raise ValueError('A source group crosses split boundaries')
            groups[record['source_id']] = record['split']
            text_hash = hashlib.sha256(record['text'].encode()).hexdigest()
            if text_hash in contents:
                raise ValueError('Duplicate corpus text')
            contents.add(text_hash)
            records.append(record)
        except (ValueError, TypeError, AttributeError) as exc:
            raise ValueError(f'Invalid corpus line {number}: {exc}') from exc
    if not records:
        raise ValueError('Dataset is empty.')
    return records
