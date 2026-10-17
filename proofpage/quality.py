"""Deterministic screening aids review; this is not a complete PII detector."""
import re

PATTERNS = [
    ('private_key', 'block', re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----[\s\S]*?-----END (?:RSA |EC |OPENSSH )?PRIVATE KEY-----')),
    ('api_key', 'block', re.compile(r'\b(?:sk-[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|AKIA[A-Z0-9]{16})\b')),
    ('credential', 'block', re.compile(r'(?i)\b(?:api[_ -]?key|password|access[_ -]?token|authorization)["\x27]?\s*[:=]\s*["\x27]?(?:Bearer\s+)?[A-Za-z0-9_./+\-=]{8,}')),
    ('email', 'warning', re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b')),
    ('phone', 'warning', re.compile(r'(?<!\w)(?:\+\d{1,3}[ .-]?)?\(?\d{3}\)?[ .-]\d{3}[ .-]\d{4}(?!\w)')),
    ('instruction_in_source', 'warning', re.compile(r'(?i)(ignore (?:all |the )?(?:previous|prior) instructions|reveal (?:your |the )?(?:system prompt|api key))')),
]


def findings(text):
    return [{'code': name, 'severity': severity, 'count': len(matches)}
            for name, severity, pattern in PATTERNS if (matches := list(pattern.finditer(text)))]


def redact(value):
    if isinstance(value, str):
        for name, severity, pattern in PATTERNS:
            if name != 'instruction_in_source':
                value = pattern.sub('[REDACTED_' + name.upper() + ']', value)
        return value
    if isinstance(value, dict):
        return {key: redact(item) for key, item in value.items()}
    if isinstance(value, list):
        return [redact(item) for item in value]
    return value


def shingles(text):
    words = re.findall(r'\w+', text.lower())[:10000]
    return {' '.join(words[i:i+5]) for i in range(max(0, len(words)-4))} or {text.strip().lower()}


def grouped_splits(records):
    """Union source groups and near-duplicate examples before assigning splits."""
    parents = list(range(len(records)))
    def root(i):
        while parents[i] != i:
            parents[i] = parents[parents[i]]
            i = parents[i]
        return i
    fingerprints = [shingles(r['text']) for r in records]
    for i, record in enumerate(records):
        for j in range(i):
            same_source = record['source_id'] == records[j]['source_id']
            union = fingerprints[i] | fingerprints[j]
            similar = len(fingerprints[i] & fingerprints[j]) / max(1, len(union)) >= .85
            if same_source or similar:
                parents[root(i)] = root(j)
    from .core import digest
    groups = {}
    for i, record in enumerate(records):
        groups.setdefault(root(i), []).append(record['source_id'])
    assignment = {}
    for index, sources in groups.items():
        key = digest('|'.join(sorted(set(sources))))
        bucket = int(key[:8], 16) % 100
        assignment[index] = (key, 'test' if bucket >= 90 else 'validation' if bucket >= 80 else 'train')
    if assignment and not any(split == 'train' for _, split in assignment.values()):
        first = min(assignment, key=lambda key: assignment[key][0])
        assignment[first] = (assignment[first][0], 'train')
    return [assignment[root(i)] for i in range(len(records))]
