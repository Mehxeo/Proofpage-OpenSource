"""Bounded, user-supplied binary evidence. Never execute or infer extracted text."""
import base64
import hashlib
import json
import struct
import threading
_EXTRACTION_SLOT = threading.BoundedSemaphore(1)
from pathlib import Path

EXTENSIONS = {'.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.webp': 'image/webp', '.pdf': 'application/pdf'}
MAX_FILE = 8 * 1024 * 1024


def file_record(name, data):
    suffix = Path(name).suffix.lower()
    mime = EXTENSIONS[suffix]
    if not data or len(data) > MAX_FILE:
        raise ValueError('Files must be nonempty and at most 8 MiB.')
    valid = (mime == 'image/png' and data.startswith(b'\x89PNG\r\n\x1a\n') and len(data) >= 33 and data[12:16] == b'IHDR') or (
        mime == 'image/jpeg' and data.startswith(b'\xff\xd8\xff') and data.endswith(b'\xff\xd9')) or (
        mime == 'image/webp' and len(data) >= 20 and data[:4] == b'RIFF' and data[8:12] == b'WEBP') or (
        mime == 'application/pdf' and data.startswith(b'%PDF-') and b'%%EOF' in data[-2048:])
    if not valid:
        raise ValueError('File contents do not match the PNG, JPEG, WebP or PDF extension.')
    dimensions = {}
    if mime == 'image/png':
        width, height = struct.unpack('>II', data[16:24])
        if not width or not height or width * height > 40000000:
            raise ValueError('PNG dimensions exceed the 40 megapixel preview limit.')
        dimensions = {'width': width, 'height': height}
    info = {'filename': Path(name).name, 'mime': mime, 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest(), **dimensions}
    return {'external_id': 'original-file', 'title': Path(name).name,
            'kind': 'image' if mime.startswith('image/') else 'pdf',
            'text': f"File: {Path(name).name}\nType: {mime}\nOriginal bytes: {len(data)}\nNo OCR or document text has been extracted.",
            'raw': json.dumps({'encoding': 'base64', 'data': base64.b64encode(data).decode()}, sort_keys=True),
            'source_time': None, 'metadata': {'adapter': 'binary_file', 'entry': Path(name).name, 'asset': info,
                'coverage': 'Original user-supplied file bytes. No source authenticity claim, OCR, PDF text extraction or malware scan. Embedded metadata may contain private information.'}}


def original(store, revision_id):
    rows = store.rows('SELECT raw,metadata FROM revisions WHERE id=?', (revision_id,))
    if not rows:
        raise ValueError('File revision not found.')
    info = json.loads(rows[0]['metadata']).get('asset')
    if not info or info.get('mime') not in EXTENSIONS.values():
        raise ValueError('Revision has no supported original file.')
    payload = json.loads(rows[0]['raw'])
    data = base64.b64decode(payload['data'], validate=True)
    if len(data) != info['bytes'] or hashlib.sha256(data).hexdigest() != info['sha256']:
        raise ValueError('Original file integrity check failed.')
    return data, info


def bundle(store, revision_id):
    import io
    import zipfile
    data, info = original(store, revision_id)
    buffer = io.BytesIO()
    suffix = next(ext for ext, mime in EXTENSIONS.items() if mime == info['mime'])
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('original' + suffix, data)
        archive.writestr('manifest.json', json.dumps({**info, 'revision_id': revision_id,
            'file': 'original' + suffix, 'attestation': 'user_supplied'}, indent=2))
        extraction = json.loads(store.rows('SELECT metadata FROM revisions WHERE id=?', (revision_id,))[0]['metadata']).get('extraction')
        if extraction:
            archive.writestr('extraction.json', json.dumps(extraction, indent=2))
            archive.writestr('extracted.txt', extraction.get('text', ''))
        archive.writestr('README.txt', 'Original user-supplied file. Verify its SHA-256 against manifest.json.\nThis hash detects changes; it does not prove authorship, source authenticity, or permission.\n')
    return buffer.getvalue()


def enrich(record, data):
    """Attach derived text; keep original bytes/hash untouched. Failures retain the file."""
    import subprocess
    import sys
    import tempfile
    if not record['metadata'].get('asset'):
        return record
    with tempfile.TemporaryDirectory(prefix='proofpage-extract-') as folder:
        source, output = Path(folder) / 'input', Path(folder) / 'output.json'
        source.write_bytes(data)
        if getattr(sys, 'frozen', False):
            helper = Path(sys.executable).with_name('Proofpage-MCP.exe' if sys.platform == 'win32' else 'Proofpage-MCP')
            command = [str(helper), '--extract-worker']
        else:
            command = [sys.executable, '-m', 'proofpage.media_worker']
        try:
            with _EXTRACTION_SLOT:
                subprocess.run(command + [str(source), str(output), record['metadata']['asset']['mime']],
                           check=True, timeout=90, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           **({'creationflags': subprocess.CREATE_NO_WINDOW} if sys.platform == 'win32' else {}))
            result = json.loads(output.read_text(encoding='utf-8'))
        except (OSError, ValueError, subprocess.SubprocessError):
            result = {'status': 'unavailable', 'text': '', 'pages': [], 'warning': 'Extraction failed or exceeded 90 seconds. Original retained.'}
    record['metadata']['extraction'] = {**result, 'original_sha256': record['metadata']['asset']['sha256']}
    record['metadata']['coverage'] = 'Original file retained. Locally extracted text is derived, unreviewed evidence; no malware scan or source authenticity guarantee.'
    record['text'] = result['text'] or f"File: {record['title']}\nNo text extracted. {result.get('warning', '')}"
    return record
