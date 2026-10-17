"""Fixture-tested import adapters. Never infer unsupplied roles or attachments."""
import csv
import io
import json
from pathlib import Path

ADAPTERS = ('auto', 'generic', 'linkedin', 'chatgpt', 'claude', 'mapping')


def field(record, *names):
    return next((record[name] for name in names if record.get(name) is not None), None)


def text_content(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return '\n'.join(text_content(part) for part in content if isinstance(part, (str, dict)))
    if isinstance(content, dict):
        return text_content(content.get('parts', content.get('text', '')))
    return ''


def normalize_chatgpt(record):
    nodes = record.get('mapping')
    if not isinstance(nodes, dict) or not nodes:
        raise ValueError('Expected a conversation mapping with source node IDs.')
    messages = []
    for node_id, node in nodes.items():
        if not isinstance(node, dict):
            raise ValueError('Conversation node is not an object.')
        msg = node.get('message')
        if msg is not None and not isinstance(msg, dict):
            raise ValueError('Conversation message is not an object.')
        author = (msg or {}).get('author') or {}
        messages.append({
            'id': node_id, 'message_id': (msg or {}).get('id'),
            'parent': node.get('parent'), 'children': node.get('children', []),
            'role': author.get('role'), 'author': author,
            'text': text_content((msg or {}).get('content')),
            'content': (msg or {}).get('content'),
            'timestamp': (msg or {}).get('create_time'),
            'recipient': (msg or {}).get('recipient'),
            'metadata': (msg or {}).get('metadata', {}),
        })
    missing = sorted({str(m['parent']) for m in messages if m['parent'] is not None and m['parent'] not in nodes})
    return {'messages': messages, 'current_node': record.get('current_node'), 'missing_parent_ids': missing, 'branching': 'Source node relationships preserved; no branch flattened into a training example.'}


def normalize_claude(record):
    source = record.get('chat_messages')
    if not isinstance(source, list):
        raise ValueError('Expected a chat_messages array.')
    messages = []
    for msg in source:
        if not isinstance(msg, dict):
            raise ValueError('Conversation message is not an object.')
        messages.append({'id': msg.get('uuid'), 'role': msg.get('sender'),
                         'text': msg.get('text') or text_content(msg.get('content')),
                         'timestamp': msg.get('created_at'), 'parent': msg.get('parent_uuid'),
                         'content': msg.get('content'), 'attachments': msg.get('attachments', []),
                         'files': msg.get('files', [])})
    return {'messages': messages, 'branching': 'Only supplied relationships retained; absent parents are unknown.'}


def validate_mapping(mapping):
    if not isinstance(mapping, dict) or not mapping.get('text'):
        raise ValueError('A mapping needs a text field name.')
    if set(mapping) - {'id', 'text', 'title', 'role', 'timestamp', 'participant', 'conversation_id'}:
        raise ValueError('Unknown mapping field.')
    if any(not isinstance(value, str) or not value or len(value) > 200 for value in mapping.values()):
        raise ValueError('Mapping values must be source field names.')
    return mapping


def parse_entry(name, data, adapter='auto', mapping=None):
    if adapter not in ADAPTERS:
        raise ValueError('Unknown adapter.')
    text = data.decode('utf-8-sig')
    suffix = Path(name).suffix.lower()
    if suffix == '.csv':
        records = list(csv.DictReader(io.StringIO(text)))
    elif suffix == '.jsonl':
        records = [json.loads(line) for line in text.splitlines() if line.strip()]
    elif suffix == '.json':
        value = json.loads(text)
        records = value if isinstance(value, list) else [value]
    elif suffix in ('.txt', '.md', '.html'):
        records = [{'text': text}]
    else:
        raise ValueError('Unsupported file format.')
    if len(records) > 10000:
        raise ValueError('Entry exceeds 10,000 records.')
    output = []
    for record in records:
        obj = record if isinstance(record, dict) else {}
        actual = adapter
        if actual == 'auto':
            actual = 'chatgpt' if isinstance(obj.get('mapping'), dict) else 'claude' if isinstance(obj.get('chat_messages'), list) else 'generic'
        raw = json.dumps(record, ensure_ascii=False, sort_keys=True)
        normalized = None
        external_id = field(obj, 'id', 'uuid', 'ID', 'MESSAGE ID')
        title = field(obj, 'title', 'name', 'SUBJECT', 'Subject') or Path(name).stem
        source_time = field(obj, 'created_at', 'create_time', 'DATE', 'Date')
        kind = 'structured_record'
        body = '\n'.join(f'{key}: {value}' for key, value in obj.items()) if obj else raw
        if actual in ('chatgpt', 'claude'):
            normalized = normalize_chatgpt(obj) if actual == 'chatgpt' else normalize_claude(obj)
            kind = 'ai_conversation'
            body = '\n\n'.join(f"[{m.get('role') or 'unknown'}] {m['text']}" for m in normalized['messages'])
        elif actual == 'linkedin':
            if suffix != '.csv':
                raise ValueError('The LinkedIn archive adapter currently supports supplied CSV entries only.')
            if 'message' in Path(name).stem.lower():
                kind = 'human_message'
                normalized = {'sender': field(obj, 'FROM', 'From', 'SENDER'),
                              'recipients': field(obj, 'TO', 'To', 'RECIPIENTS'),
                              'conversation_id': field(obj, 'CONVERSATION ID', 'Conversation ID'),
                              'text': field(obj, 'CONTENT', 'Content'),
                              'attachment_references': field(obj, 'ATTACHMENTS', 'Attachments'),
                              'roles': 'Human participants; no assistant mapping.'}
        elif actual == 'mapping':
            mapping = validate_mapping(mapping)
            if not isinstance(record, dict) or mapping['text'] not in obj:
                raise ValueError('Mapped text field is missing from a record.')
            normalized = {key: obj.get(value) for key, value in mapping.items()}
            body = str(normalized['text'])
            external_id = normalized.get('id')
            title = normalized.get('title') or title
            source_time = normalized.get('timestamp')
            # A role field is preserved without declaring the speaker an AI assistant.
        elif suffix == '.csv' and 'message' in Path(name).stem.lower():
            kind = 'human_message'
        if suffix in ('.txt', '.md', '.html'):
            kind, body = 'document', text
            # One selected file is a document with stable identity across edits.
            external_id = 'document'
            if suffix == '.html':
                from .core import classify
                state, title, body = classify(200, text)
                if state != 'available':
                    raise ValueError('HTML entry does not contain confirmed content.')
        output.append({'external_id': external_id, 'title': str(title), 'kind': kind,
                       'text': body, 'raw': raw, 'source_time': str(source_time) if source_time is not None else None,
                       'metadata': {'adapter': actual, 'entry': Path(name).name,
                                    'normalized': normalized,
                                    'coverage': 'Supplied fields only. Missing roles, branches and attachments remain unknown. Attachment references do not imply acquired content.'}})
    return output
