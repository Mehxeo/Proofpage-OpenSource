"""Proof Receipts: signed, hash-chained records of what this workspace observed, with optional timestamp anchoring.

A receipt attests that this Proofpage workspace received an HTTP response. TLS has no non-repudiation, so a receipt
cannot prove what a server sent; anchoring adds independent evidence of *when* a batch of receipts existed.
Anchoring is off by default and sends only a SHA-256 digest of a Merkle root.
"""
import io
import json
import secrets
import urllib.parse
import urllib.request
import uuid
import zipfile
import zlib
from datetime import datetime, timezone
from pathlib import Path

from . import ed25519, verify
from .core import LOCK, USER_AGENT, now
from .verify import merkle_leaf, merkle_parent, sha256

ATTESTATION = ('This Proofpage workspace observed this HTTP response at requested_at. TLS does not provide '
               'non-repudiation, so this receipt does not prove what the server sent.')
DEFAULT_CALENDAR = 'https://a.pool.opentimestamps.org'
SETTINGS = {'anchor_tsa_url': '', 'anchor_ots': '0', 'anchor_ots_calendar': DEFAULT_CALENDAR}
ANCHOR_INTERVAL = 24 * 3600
OTS_MAGIC = b'\x00OpenTimestamps\x00\x00Proof\x00\xbf\x89\xe2\xe8\x84\xe8\x92\x94'
SHA256_ALGORITHM = bytes.fromhex('300d06096086480165030402010500')  # AlgorithmIdentifier: sha256 with NULL parameters


def public_key_pem(public_hex):
    import base64
    der = bytes.fromhex('302a300506032b6570032100' + public_hex)  # SubjectPublicKeyInfo for Ed25519
    return '-----BEGIN PUBLIC KEY-----\n' + base64.b64encode(der).decode() + '\n-----END PUBLIC KEY-----\n'


def canonical(body):
    return json.dumps(body, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')


# ---------- Keys and receipts ----------

def active_key(db):
    row = db.execute('SELECT * FROM signing_keys WHERE active=1 ORDER BY created_at LIMIT 1').fetchone()
    if row:
        return dict(row)
    seed = secrets.token_bytes(32)
    public = ed25519.public_key(seed).hex()
    key = {'id': public[:16], 'algorithm': 'ed25519', 'public_key': public, 'private_key': seed.hex(), 'created_at': now(), 'active': 1}
    db.execute('INSERT INTO signing_keys(id,algorithm,public_key,private_key,created_at,active) VALUES(?,?,?,?,?,?)', tuple(key.values()))
    return key


def key_info(store):
    with LOCK, store.db() as db:
        db.execute('BEGIN IMMEDIATE')
        key = active_key(db)
    return {'id': key['id'], 'algorithm': 'Ed25519', 'public_key': key['public_key'], 'fingerprint': sha256(bytes.fromhex(key['public_key'])), 'created_at': key['created_at']}


def issue(db, fields):
    """Sign and chain a receipt inside the caller's write transaction."""
    key = active_key(db)
    last = db.execute('SELECT seq,hash FROM receipts ORDER BY seq DESC LIMIT 1').fetchone()
    body = dict(fields, type='proofpage.capture-receipt', version=1, seq=(last['seq'] + 1) if last else 1, prev_receipt_hash=last['hash'] if last else None,
                public_key=key['public_key'], issued_at=now(), attestation=ATTESTATION)
    data = canonical(body)
    digest = sha256(data)
    signature = ed25519.sign(bytes.fromhex(key['private_key']), data).hex()
    db.execute('INSERT INTO receipts(seq,id,capture_id,key_id,body,hash,prev_hash,signature,created_at) VALUES(?,?,?,?,?,?,?,?,?)',
               (body['seq'], uuid.uuid4().hex, fields['capture_id'], key['id'], data.decode('utf-8'), digest, body['prev_receipt_hash'], signature, body['issued_at']))
    return {'seq': body['seq'], 'hash': digest}


def verify_chain(store):
    """Re-check every receipt: contiguous sequence, hash links, body hashes, and signatures."""
    keys = {row['id']: bytes.fromhex(row['public_key']) for row in store.rows('SELECT id,public_key FROM signing_keys')}
    problems, previous, count = [], None, 0
    for row in store.rows('SELECT seq,body,hash,prev_hash,signature,key_id FROM receipts ORDER BY seq'):
        count += 1
        data = row['body'].encode('utf-8')
        if previous and row['seq'] != previous['seq'] + 1:
            problems.append(f"Receipt {row['seq']}: sequence gap after {previous['seq']}.")
        if sha256(data) != row['hash']:
            problems.append(f"Receipt {row['seq']}: stored body does not match its hash.")
        if row['prev_hash'] != (previous['hash'] if previous else None) or json.loads(data).get('prev_receipt_hash') != row['prev_hash']:
            problems.append(f"Receipt {row['seq']}: chain link does not match the previous receipt.")
        if not ed25519.verify(keys.get(row['key_id'], b''), data, bytes.fromhex(row['signature'])):
            problems.append(f"Receipt {row['seq']}: signature is not valid.")
        previous = row
    return {'receipts': count, 'ok': not problems, 'problems': problems[:20], 'head': previous['hash'] if previous else None, 'checked_at': now()}


def revision_proof(store, revision_id):
    rows = store.rows('SELECT r.seq,r.hash,r.created_at,r.anchor_id,r.body,c.status,c.requested_at,c.final_url,c.raw_exact FROM receipts r JOIN captures c ON c.id=r.capture_id '
                      'WHERE c.revision_id=? ORDER BY r.seq DESC LIMIT 50', (revision_id,))
    anchors = {a['id']: a for a in (anchor_status(store, aid) for aid in {r['anchor_id'] for r in rows if r['anchor_id']})}
    receipts = [{'seq': r['seq'], 'hash': r['hash'], 'issued_at': r['created_at'], 'status': r['status'], 'requested_at': r['requested_at'], 'url': r['final_url'],
                 'exact_bytes': bool(r['raw_exact']), 'anchor': anchors.get(r['anchor_id'])} for r in rows]
    public = json.loads(rows[0]['body'])['public_key'] if rows else None
    anchored = [r for r in receipts if r['anchor'] and (r['anchor']['tsa_state'] == 'complete' or r['anchor']['ots_state'] == 'submitted')]
    state = 'none' if not receipts else 'anchored' if anchored else 'anchoring' if any(r['anchor'] for r in receipts) else 'signed'
    return {'state': state, 'receipts': receipts, 'public_key': public, 'fingerprint': sha256(bytes.fromhex(public)) if public else None}


# ---------- Merkle batches ----------

def merkle(hashes):
    """Root and per-leaf inclusion paths. Leaves and nodes are domain-separated; an unpaired node is promoted."""
    level = [merkle_leaf(h) for h in hashes]
    paths, positions = [[] for _ in hashes], list(range(len(hashes)))
    while len(level) > 1:
        for leaf, position in enumerate(positions):
            sibling = position ^ 1
            if sibling < len(level):
                paths[leaf].append({'side': 'left' if sibling < position else 'right', 'hash': level[sibling].hex()})
            positions[leaf] = position // 2
        level = [merkle_parent(level[i], level[i + 1]) if i + 1 < len(level) else level[i] for i in range(0, len(level), 2)]
    return level[0], paths


# ---------- RFC 3161 (DER by hand, standard library only) ----------

def _der(tag, value):
    length = len(value)
    encoded = bytes([length]) if length < 128 else bytes([0x80 | ((length.bit_length() + 7) // 8)]) + length.to_bytes((length.bit_length() + 7) // 8, 'big')
    return bytes([tag]) + encoded + value


def _der_int(value):
    return _der(0x02, value.to_bytes(max(1, (value.bit_length() + 8) // 8), 'big'))


def timestamp_request(imprint, nonce=None, cert_req=True):
    """DER TimeStampReq for a SHA-256 imprint (RFC 3161 section 2.4.1)."""
    body = _der_int(1) + _der(0x30, SHA256_ALGORITHM + _der(0x04, imprint))
    body += _der_int(nonce) if nonce is not None else b''
    body += b'\x01\x01\xff' if cert_req else b''
    return _der(0x30, body)


def _read(data, offset=0):
    tag, length = data[offset], data[offset + 1]
    offset += 2
    if length & 0x80:
        count = length & 0x7f
        length = int.from_bytes(data[offset:offset + count], 'big')
        offset += count
    return tag, data[offset:offset + length], offset + length


def _children(value):
    items, offset = [], 0
    while offset < len(value):
        tag, content, offset = _read(value, offset)
        items.append((tag, content))
    return items


def parse_timestamp_reply(reply, imprint, nonce=None):
    """Check a TimeStampResp: granted status, matching imprint and nonce. Returns the TSA's time and serial number."""
    unreadable = 'The timestamp authority returned a response Proofpage could not read.'
    try:
        parts = _children(_read(reply)[1])
        status = int.from_bytes(_children(parts[0][1])[0][1], 'big')
    except (IndexError, ValueError):
        raise ValueError(unreadable) from None
    if status not in (0, 1):
        raise ValueError(f'The timestamp authority refused the request (status {status}).')
    try:
        signed_data = _children(_children(parts[1][1])[1][1])[0][1]           # ContentInfo -> [0] -> SignedData
        encapsulated = [content for tag, content in _children(signed_data) if tag == 0x30][0]
        econtent = _children(encapsulated)[1][1]                                # [0] EXPLICIT -> OCTET STRING
        tst = _children(_read(_children(econtent)[0][1])[1])                   # TSTInfo fields
        message, serial, generalized = _children(tst[2][1]), tst[3][1].hex(), tst[4][1].decode('ascii')
        nonces = [content for tag, content in tst[5:] if tag == 0x02]
    except (IndexError, ValueError, UnicodeDecodeError):
        raise ValueError(unreadable) from None
    if message[1][1] != imprint:
        raise ValueError('The timestamp token covers a different digest.')
    if nonce is not None and (not nonces or int.from_bytes(nonces[0], 'big') != nonce):
        raise ValueError('The timestamp token nonce does not match the request.')
    when = f'{generalized[0:4]}-{generalized[4:6]}-{generalized[6:8]}T{generalized[8:10]}:{generalized[10:12]}:{generalized[12:14]}Z'
    return {'time': when, 'serial': serial}


def ots_file(imprint, calendar_timestamp):
    """A detached OpenTimestamps proof for a file whose SHA-256 is `imprint`, from one calendar's pending timestamp."""
    return OTS_MAGIC + b'\x01' + b'\x08' + imprint + calendar_timestamp


# ---------- Anchoring ----------

def settings(store):
    values = dict(SETTINGS)
    values.update({row['key']: row['value'] for row in store.rows('SELECT key,value FROM settings')})
    return values


def _service_url(url, label):
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError(f'Enter a plain HTTP(S) address for the {label}, without credentials or a query.')
    return url.rstrip('/')


def save_settings(store, values):
    tsa = (values.get('anchor_tsa_url') or '').strip()
    calendar = (values.get('anchor_ots_calendar') or DEFAULT_CALENDAR).strip()
    clean = {'anchor_tsa_url': _service_url(tsa, 'timestamp authority') if tsa else '',
             'anchor_ots': '1' if values.get('anchor_ots') in (True, '1', 1) else '0',
             'anchor_ots_calendar': _service_url(calendar, 'OpenTimestamps calendar')}
    if clean['anchor_ots'] == '1' and urllib.parse.urlsplit(clean['anchor_ots_calendar']).scheme != 'https':
        raise ValueError('Use an HTTPS OpenTimestamps calendar.')
    with store.db() as db:
        for key, value in clean.items():
            db.execute('INSERT INTO settings VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value', (key, value))
    return settings(store)


def _post(url, data, content_type, accept):
    from .models import NoRedirect
    from .tls import context
    request = urllib.request.Request(url, data=data, headers={'Content-Type': content_type, 'Accept': accept, 'User-Agent': USER_AGENT})
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), urllib.request.HTTPSHandler(context=context()), NoRedirect())
    with opener.open(request, timeout=20) as response:
        body = response.read(1024 * 1024 + 1)
    if len(body) > 1024 * 1024:
        raise ValueError('The anchoring service response is too large.')
    return body


def anchor_status(store, anchor_id):
    rows = store.rows('SELECT id,created_at,first_seq,last_seq,root,imprint,tsa_url,tsa_time,tsa_state,tsa_detail,ots_calendar,ots_state,ots_detail,'
                      'tsa_token IS NOT NULL has_tsa,ots_proof IS NOT NULL has_ots FROM anchors WHERE id=?', (anchor_id,))
    if not rows:
        return None
    row = rows[0]
    row['receipts'] = row['last_seq'] - row['first_seq'] + 1
    return row


def _submit(store, anchor_id):
    row = store.rows('SELECT * FROM anchors WHERE id=?', (anchor_id,))[0]
    imprint = bytes.fromhex(row['imprint'])
    if row['tsa_url'] and row['tsa_state'] in ('submitting', 'failed'):
        nonce = secrets.randbits(63)
        try:
            reply = _post(row['tsa_url'], timestamp_request(imprint, nonce), 'application/timestamp-query', 'application/timestamp-reply')
            info = parse_timestamp_reply(reply, imprint, nonce)
            update = ('complete', f"Timestamped by {urllib.parse.urlsplit(row['tsa_url']).hostname} (serial {info['serial'][:16]})", reply, info['time'])
        except Exception as exc:
            update = ('failed', str(exc)[:300] or 'The timestamp authority could not be reached.', None, None)
        with store.db() as db:
            db.execute('UPDATE anchors SET tsa_state=?,tsa_detail=?,tsa_token=COALESCE(?,tsa_token),tsa_time=COALESCE(?,tsa_time) WHERE id=?', (*update, anchor_id))
    if row['ots_calendar'] and row['ots_state'] in ('submitting', 'failed'):
        try:
            response = _post(row['ots_calendar'] + '/digest', imprint, 'application/x-www-form-urlencoded', 'application/vnd.opentimestamps.v1')
            if not response:
                raise ValueError('The calendar returned an empty timestamp.')
            update = ('submitted', 'Submitted to ' + urllib.parse.urlsplit(row['ots_calendar']).hostname + '. Bitcoin confirmation takes a few hours; run `ots upgrade` on the downloaded proof to complete it.', ots_file(imprint, response))
        except Exception as exc:
            update = ('failed', str(exc)[:300] or 'The calendar could not be reached.', None)
        with store.db() as db:
            db.execute('UPDATE anchors SET ots_state=?,ots_detail=?,ots_proof=COALESCE(?,ots_proof) WHERE id=?', (*update, anchor_id))


def anchor(store, force=False):
    """Anchor receipts issued since the last batch. Runs at most daily unless forced; does nothing while anchoring is off."""
    config = settings(store)
    tsa, ots = config['anchor_tsa_url'], config['anchor_ots'] == '1'
    if not tsa and not ots:
        if force:
            raise ValueError('Timestamp anchoring is off. Add a timestamp authority or turn on OpenTimestamps in Settings first.')
        return None
    with LOCK, store.db() as db:
        db.execute('BEGIN IMMEDIATE')
        last = db.execute('SELECT created_at FROM anchors ORDER BY created_at DESC LIMIT 1').fetchone()
        if not force and last and (datetime.now(timezone.utc) - datetime.fromisoformat(last['created_at'])).total_seconds() < ANCHOR_INTERVAL:
            return None
        retry = [row['id'] for row in db.execute("SELECT id FROM anchors WHERE tsa_state='failed' OR ots_state='failed' ORDER BY created_at DESC LIMIT 5")]
        rows = db.execute('SELECT seq,hash FROM receipts WHERE anchor_id IS NULL ORDER BY seq').fetchall()
        anchor_id = None
        if rows:
            root, _ = merkle([row['hash'] for row in rows])
            anchor_id = uuid.uuid4().hex
            db.execute('INSERT INTO anchors(id,created_at,first_seq,last_seq,root,imprint,tsa_url,tsa_state,ots_calendar,ots_state) VALUES(?,?,?,?,?,?,?,?,?,?)',
                       (anchor_id, now(), rows[0]['seq'], rows[-1]['seq'], root.hex(), sha256(root), tsa or None, 'submitting' if tsa else 'off',
                        config['anchor_ots_calendar'] if ots else None, 'submitting' if ots else 'off'))
            db.execute('UPDATE receipts SET anchor_id=? WHERE anchor_id IS NULL AND seq BETWEEN ? AND ?', (anchor_id, rows[0]['seq'], rows[-1]['seq']))
    for previous in retry:
        _submit(store, previous)
    if anchor_id is None:
        if force and not retry:
            raise ValueError('There are no new receipts to anchor.')
        return anchor_status(store, retry[0]) if retry else None
    _submit(store, anchor_id)
    return anchor_status(store, anchor_id)


def overview(store):
    count = store.rows('SELECT COUNT(*) n, MAX(seq) head FROM receipts')[0]
    unanchored = store.rows('SELECT COUNT(*) n FROM receipts WHERE anchor_id IS NULL')[0]['n']
    anchors = [anchor_status(store, row['id']) for row in store.rows('SELECT id FROM anchors ORDER BY created_at DESC LIMIT 20')]
    return {'key': key_info(store), 'receipts': count['n'], 'unanchored': unanchored, 'anchors': anchors, 'settings': settings(store)}


# ---------- Proof bundles ----------

BUNDLE_README = '''# Proofpage proof bundle

This folder lets anyone check, offline, what a Proofpage workspace observed for one record.

Run `python3 verify_proof.py` here (Python 3.8 or newer, no installation needed). It checks:

- each receipt's Ed25519 signature against `public-key.txt`, and the hash chain between consecutive receipts;
- the captured response body, headers, robots.txt, and rights observation against the hashes the receipts sign;
- that the receipts attest the revision in `revision.json`, whose content hash is recomputed;
- for anchored receipts, the Merkle path from each receipt to `anchors/<id>/anchor-root.bin`.

Signatures can also be checked without Python, using OpenSSL 3:

    xxd -r -p receipts/000001.sig > sig.bin
    openssl pkeyutl -verify -pubin -inkey public-key.pem -rawin -in receipts/000001.json -sigfile sig.bin

Timestamp tokens are checked with standard tools, which the verifier prints:
`openssl ts -verify` for RFC 3161 tokens (`.tsr`) and `ots verify` for OpenTimestamps proofs (`.ots`).

What a receipt proves: this workspace's signing key signed a record of the response it received, and (if anchored)
that the record existed by the timestamp. What it cannot prove: what the server sent. TLS provides no
non-repudiation, so a receipt is evidence from the collector, not from the publisher.
'''


def proof_bundle(store, revision_id):
    rows = store.rows('SELECT r.*,i.kind,i.title,i.current_revision,s.location FROM revisions r JOIN items i ON i.id=r.item_id JOIN sources s ON s.id=i.source_id WHERE r.id=?', (revision_id,))
    if not rows:
        raise ValueError('Revision not found.')
    revision = rows[0]
    receipts = store.rows('SELECT r.* FROM receipts r JOIN captures c ON c.id=r.capture_id WHERE c.revision_id=? ORDER BY r.seq DESC LIMIT 50', (revision_id,))
    if not receipts:
        raise ValueError('This revision has no receipts. Receipts are issued for captures made with Proof Receipts enabled; collect the source again to issue one.')
    files = {}
    metadata = json.loads(revision['metadata'] or '{}')
    record = {'id': revision['id'], 'item_id': revision['item_id'], 'hash': revision['hash'], 'kind': revision['kind'], 'title': revision['title'], 'text': revision['text'],
              'raw': revision['raw'], 'metadata': metadata, 'source_time': revision['source_time'], 'captured_at': revision['captured_at']}
    if verify.revision_hash(record) != revision['hash']:
        # Titles are stored per record, not per revision; an older revision's title may since have changed.
        record = {key: value for key, value in record.items() if key not in ('kind', 'title')}
        record['recomputable'] = False
    files['revision.json'] = json.dumps(record, indent=2, sort_keys=True, ensure_ascii=False).encode('utf-8')
    public = None
    for receipt in sorted(receipts, key=lambda r: r['seq']):
        body = json.loads(receipt['body'])
        public = public or body['public_key']
        files[f"receipts/{receipt['seq']:06d}.json"] = receipt['body'].encode('utf-8')
        files[f"receipts/{receipt['seq']:06d}.sig"] = receipt['signature'].encode('ascii')
        capture = store.rows('SELECT c.headers,p.data FROM captures c LEFT JOIN capture_payloads p ON p.sha256=c.body_sha256 WHERE c.id=?', (body['capture_id'],))[0]
        files[f"captures/{body['capture_id']}/headers.json"] = capture['headers'].encode('utf-8')
        if capture['data'] is not None:
            files[f"captures/{body['capture_id']}/body.bin"] = zlib.decompress(capture['data'])
        if body.get('robots_sha256'):
            policy = store.rows("SELECT body FROM policy_documents WHERE kind='robots' AND sha256=? LIMIT 1", (body['robots_sha256'],))
            if policy:
                files[f"policies/{body['robots_sha256']}.txt"] = policy[0]['body'].encode('utf-8')
        if body.get('rights_observation_hash'):
            observation = store.rows('SELECT verdict,signals,checked FROM rights_observations WHERE hash=? LIMIT 1', (body['rights_observation_hash'],))
            if observation:
                o = observation[0]
                files[f"rights/{body['rights_observation_hash']}.json"] = json.dumps({'verdict': json.loads(o['verdict']), 'signals': json.loads(o['signals']), 'checked': json.loads(o['checked'])}, sort_keys=True).encode('utf-8')
        if receipt['anchor_id']:
            batch = store.rows('SELECT * FROM anchors WHERE id=?', (receipt['anchor_id'],))[0]
            members = [row['hash'] for row in store.rows('SELECT hash FROM receipts WHERE anchor_id=? ORDER BY seq', (batch['id'],))]
            root, paths = merkle(members)
            folder = f"anchors/{batch['id']}"
            files[f'{folder}/anchor-root.bin'] = root
            files[f"{folder}/proof-{receipt['seq']}.json"] = json.dumps({'leaf': receipt['hash'], 'path': paths[members.index(receipt['hash'])], 'root': root.hex()}, indent=2).encode()
            if batch['tsa_token']:
                files[f'{folder}/anchor-root.bin.tsr'] = bytes(batch['tsa_token'])
            if batch['ots_proof']:
                files[f'{folder}/anchor-root.bin.ots'] = bytes(batch['ots_proof'])
    files['public-key.txt'] = (public + '\n').encode('ascii')
    files['public-key.pem'] = public_key_pem(public).encode('ascii')
    files['verify_proof.py'] = verify.source()
    files['README.md'] = BUNDLE_README.encode('utf-8')
    manifest = {'schema': 'proofpage.proof-bundle.v1', 'revision_id': revision_id, 'title': revision['title'], 'url': metadata.get('url') or revision['location'],
                'receipts': sorted(name for name in files if name.startswith('receipts/') and name.endswith('.json')),
                'files': {name: sha256(data) for name, data in sorted(files.items())}}
    files['manifest.json'] = json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False).encode('utf-8')
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name, data in sorted(files.items()):
            info = zipfile.ZipInfo(name, date_time=(2020, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, data)
    return buffer.getvalue()
