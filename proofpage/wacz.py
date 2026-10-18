"""Export a source as a WACZ web archive (WARC/1.1 records, CDXJ index, pages, data package) with signed receipts.

Captures with stored exact bytes become `request`/`response` record pairs. Older captures, kept only as decoded
text, become `resource` records labelled as reconstructed. WACZ-Auth signatures are not produced; Proofpage's
Ed25519 receipts are included as sidecar files instead.
"""
import gzip
import http
import io
import json
import urllib.parse
import uuid
import zipfile
import zlib
from pathlib import Path

from . import verify
from .core import USER_AGENT, now
from .verify import sha256


def _warc_date(value):
    return value[:19] + 'Z'


def _timestamp14(value):
    return value[:19].replace('-', '').replace('T', '').replace(':', '')


def surt(url):
    parts = urllib.parse.urlsplit(url)
    host = (parts.hostname or '').lower()
    host = host[4:] if host.startswith('www.') else host
    return ','.join(reversed(host.split('.'))) + ')' + (parts.path or '/').lower() + ('?' + parts.query if parts.query else '')


def _record(warc_type, uri, date, content_type, block, extra=()):
    record_id = f'<urn:uuid:{uuid.uuid4()}>'
    headers = [('WARC-Type', warc_type), ('WARC-Record-ID', record_id), ('WARC-Date', date)]
    headers += [('WARC-Target-URI', uri)] if uri else []
    headers += list(extra) + [('Content-Type', content_type), ('Content-Length', str(len(block)))]
    head = 'WARC/1.1\r\n' + ''.join(f'{name}: {value}\r\n' for name, value in headers) + '\r\n'
    return head.encode('utf-8') + block + b'\r\n\r\n', record_id


def export_wacz(store, source_id):
    sources = store.rows('SELECT * FROM sources WHERE id=?', (source_id,))
    if not sources or sources[0]['kind'] != 'web':
        raise ValueError('Choose a web source to export.')
    source = sources[0]
    captures = store.rows('SELECT c.*,p.data payload,i.title FROM captures c JOIN capture_payloads p ON p.sha256=c.body_sha256 '
                          'LEFT JOIN revisions r ON r.id=c.revision_id LEFT JOIN items i ON i.id=r.item_id WHERE c.source_id=? ORDER BY c.requested_at,c.rowid', (source_id,))
    captured_revisions = {c['revision_id'] for c in store.rows('SELECT revision_id FROM captures WHERE source_id=? AND revision_id IS NOT NULL', (source_id,))}
    legacy = [r for r in store.rows('SELECT r.id,r.raw,r.metadata,r.captured_at,i.title,i.external_id FROM revisions r JOIN items i ON i.id=r.item_id WHERE i.source_id=? ORDER BY r.captured_at', (source_id,))
              if r['id'] not in captured_revisions]
    if not captures and not legacy:
        raise ValueError('This source has no captured content to archive yet.')

    warc, index, pages = io.BytesIO(), [], []
    created = now()

    def write(record):
        offset = warc.tell()
        member = gzip.compress(record, mtime=0)
        warc.write(member)
        return offset, len(member)

    info = 'software: Proofpage 0.2.0\r\nformat: WARC File Format 1.1\r\nconformsTo: https://iipc.github.io/warc-specifications/specifications/warc-format/warc-1.1/\r\n' \
           f'description: Captures of {source["name"]} ({source["location"]}) exported by Proofpage.\r\n'
    write(_record('warcinfo', None, _warc_date(created), 'application/warc-fields', info.encode('utf-8'), [('WARC-Filename', 'data.warc.gz')])[0])

    for capture in captures:
        payload = zlib.decompress(capture['payload'])
        url, date = capture['final_url'], _warc_date(capture['requested_at'])
        headers = json.loads(capture['headers'])
        mime = next((value.split(';')[0].strip() for name, value in headers if name.lower() == 'content-type'), 'application/octet-stream')
        digest = 'sha256:' + sha256(payload)
        if capture['raw_exact']:
            reason = capture['reason'] or (http.HTTPStatus(capture['status']).phrase if capture['status'] in http.HTTPStatus._value2member_map_ else '')
            lines = [f"{capture['http_version'] or 'HTTP/1.1'} {capture['status']} {reason}"]
            # The body is stored de-chunked, so the original framing header is preserved under an archive name.
            lines += [f"{'X-Archive-Orig-Transfer-Encoding' if name.lower() == 'transfer-encoding' else name}: {value}" for name, value in headers]
            block = ('\r\n'.join(lines) + '\r\n\r\n').encode('latin-1', 'replace') + payload
            record, response_id = _record('response', url, date, 'application/http;msgtype=response', block,
                                          [('WARC-Payload-Digest', digest), ('WARC-Block-Digest', 'sha256:' + sha256(block))] + ([('WARC-IP-Address', capture['peer_ip'])] if capture['peer_ip'] else []))
            offset, length = write(record)
            parts = urllib.parse.urlsplit(url)
            request = (f"GET {parts.path or '/'}{'?' + parts.query if parts.query else ''} HTTP/1.1\r\nHost: {parts.netloc}\r\nUser-Agent: {USER_AGENT}\r\n"
                       'Accept: text/html,text/plain\r\nAccept-Encoding: identity\r\n\r\n').encode('latin-1', 'replace')
            write(_record('request', url, date, 'application/http;msgtype=request', request, [('WARC-Concurrent-To', response_id)])[0])
        else:
            record, _ = _record('resource', url, date, mime, payload, [('WARC-Payload-Digest', digest), ('WARC-Proofpage-Reconstructed', 'decoded text; exact bytes were not stored')])
            offset, length = write(record)
        index.append((surt(url), _timestamp14(capture['requested_at']), {'url': url, 'mime': mime, 'status': str(capture['status']), 'digest': digest,
                                                                           'length': str(length), 'offset': str(offset), 'filename': 'data.warc.gz'}))
        pages.append({'id': capture['id'], 'url': url, 'ts': date, 'title': capture['title'] or source['name']})

    for revision in legacy:
        url = json.loads(revision['metadata'] or '{}').get('url') or revision['external_id']
        payload, date = revision['raw'].encode('utf-8'), _warc_date(revision['captured_at'])
        digest = 'sha256:' + sha256(payload)
        record, _ = _record('resource', url, date, 'text/html; charset=utf-8', payload, [('WARC-Payload-Digest', digest), ('WARC-Proofpage-Reconstructed', 'decoded text captured before exact bytes were stored')])
        offset, length = write(record)
        index.append((surt(url), _timestamp14(revision['captured_at']), {'url': url, 'mime': 'text/html', 'status': '200', 'digest': digest, 'length': str(length), 'offset': str(offset), 'filename': 'data.warc.gz'}))
        pages.append({'id': revision['id'], 'url': url, 'ts': date, 'title': revision['title']})

    files = {'archive/data.warc.gz': warc.getvalue(),
             'indexes/index.cdx': ''.join(f'{key} {stamp} {json.dumps(fields, sort_keys=True)}\n' for key, stamp, fields in sorted(index, key=lambda e: (e[0], e[1]))).encode('utf-8'),
             'pages/pages.jsonl': ('\n'.join([json.dumps({'format': 'json-pages-1.0', 'id': 'pages', 'title': 'All Pages'})] + [json.dumps(page) for page in pages]) + '\n').encode('utf-8')}
    receipts = store.rows(f"SELECT seq,body,signature FROM receipts WHERE capture_id IN ({','.join('?' * len(captures))}) ORDER BY seq", [c['id'] for c in captures]) if captures else []
    if receipts:
        for receipt in receipts:
            files[f"proofpage/receipts/{receipt['seq']:06d}.json"] = receipt['body'].encode('utf-8')
            files[f"proofpage/receipts/{receipt['seq']:06d}.sig"] = receipt['signature'].encode('ascii')
        public = json.loads(receipts[0]['body'])['public_key']
        files['proofpage/public-key.txt'] = (public + '\n').encode('ascii')
        from .receipts import public_key_pem
        files['proofpage/public-key.pem'] = public_key_pem(public).encode('ascii')
        files['proofpage/verify_proof.py'] = verify.source()
        files['proofpage/README.md'] = (b'Signed Proofpage receipts for the captures in this archive. Run `python3 proofpage/verify_proof.py <this file>.wacz` '
                                        b'to check the archive digests, the receipt signatures, and that each receipt\'s response body is in the index.\n')
    package = {'profile': 'data-package', 'wacz_version': '1.1.1', 'title': source['name'], 'description': f"Captures of {source['location']} exported by Proofpage.",
               'created': created, 'software': 'Proofpage 0.2.0', 'mainPageURL': source['location'], 'mainPageDate': pages[-1]['ts'] if pages else _warc_date(created),
               'resources': [{'name': Path(name).name, 'path': name, 'hash': 'sha256:' + sha256(data), 'bytes': len(data)} for name, data in sorted(files.items())]}
    files['datapackage.json'] = json.dumps(package, indent=2).encode('utf-8')
    files['datapackage-digest.json'] = json.dumps({'path': 'datapackage.json', 'hash': 'sha256:' + sha256(files['datapackage.json'])}, indent=2).encode('utf-8')
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_STORED) as archive:
        for name in ['datapackage.json', 'datapackage-digest.json'] + sorted(n for n in files if n not in ('datapackage.json', 'datapackage-digest.json')):
            archive.writestr(zipfile.ZipInfo(name, date_time=(2020, 1, 1, 0, 0, 0)), files[name])
    return buffer.getvalue(), {'records': len(index), 'exact': sum(1 for c in captures if c['raw_exact']), 'reconstructed': len(index) - sum(1 for c in captures if c['raw_exact']), 'receipts': len(receipts)}
