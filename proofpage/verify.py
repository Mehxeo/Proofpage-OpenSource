"""Verify a Proofpage proof bundle (.zip) or web archive (.wacz) offline, with only the Python standard library.

Usage: python3 verify_proof.py PATH   (a bundle ZIP, a WACZ file, or an extracted bundle folder)

This file is self-contained on purpose: Proofpage copies it into every proof bundle so anyone can check the
evidence without installing Proofpage. Exit status is 0 only when every check passes.
"""
import hashlib
import json
import sys
import tempfile
import zipfile
from pathlib import Path

# ---------- Ed25519 verification (RFC 8032) ----------
_P = 2 ** 255 - 19
_L = 2 ** 252 + 27742317777372353535851937790883648493
_D = -121665 * pow(121666, _P - 2, _P) % _P
_I = pow(2, (_P - 1) // 4, _P)


def _add(a, b):
    x, y = (a[1] - a[0]) * (b[1] - b[0]) % _P, (a[1] + a[0]) * (b[1] + b[0]) % _P
    t, z = 2 * a[3] * b[3] * _D % _P, 2 * a[2] * b[2] % _P
    e, f, g, h = y - x, z - t, z + t, y + x
    return (e * f % _P, g * h % _P, f * g % _P, e * h % _P)


def _mul(s, point):
    result = (0, 1, 1, 0)
    while s:
        if s & 1:
            result = _add(result, point)
        point = _add(point, point)
        s >>= 1
    return result


def _x(y, sign):
    if y >= _P:
        return None
    x2 = (y * y - 1) * pow(_D * y * y + 1, _P - 2, _P) % _P
    if x2 == 0:
        return None if sign else 0
    x = pow(x2, (_P + 3) // 8, _P)
    if (x * x - x2) % _P:
        x = x * _I % _P
    if (x * x - x2) % _P:
        return None
    return _P - x if (x & 1) != sign else x


def _point(data):
    y = int.from_bytes(data, 'little')
    sign, y = y >> 255, y & ((1 << 255) - 1)
    x = _x(y, sign)
    return None if x is None else (x, y, 1, x * y % _P)


_GY = 4 * pow(5, _P - 2, _P) % _P
_G = (_x(_GY, 0), _GY, 1, _x(_GY, 0) * _GY % _P)


def ed25519_verify(public, message, signature):
    if len(public) != 32 or len(signature) != 64:
        return False
    a, r, s = _point(public), _point(signature[:32]), int.from_bytes(signature[32:], 'little')
    if a is None or r is None or s >= _L:
        return False
    h = int.from_bytes(hashlib.sha512(signature[:32] + public + message).digest(), 'little') % _L
    left, right = _mul(s, _G), _add(r, _mul(h, a))
    return (left[0] * right[2] - right[0] * left[2]) % _P == 0 and (left[1] * right[2] - right[1] * left[2]) % _P == 0


# ---------- Shared definitions (must match Proofpage) ----------
def sha256(data):
    return hashlib.sha256(data).hexdigest()


def merkle_leaf(receipt_hash):
    return hashlib.sha256(b'\x00' + bytes.fromhex(receipt_hash)).digest()


def merkle_parent(left, right):
    return hashlib.sha256(b'\x01' + left + right).digest()


def merkle_root_from_path(receipt_hash, path):
    node = merkle_leaf(receipt_hash)
    for step in path:
        sibling = bytes.fromhex(step['hash'])
        node = merkle_parent(sibling, node) if step['side'] == 'left' else merkle_parent(node, sibling)
    return node.hex()


def revision_hash(revision):
    fields = [revision['kind'], revision['title'], revision['text'], revision['raw'], revision['metadata'], revision['source_time']]
    return sha256(json.dumps(fields, sort_keys=True).encode())


class Report:
    def __init__(self):
        self.lines, self.failures = [], 0

    def check(self, ok, message):
        self.lines.append(('PASS  ' if ok else 'FAIL  ') + message)
        self.failures += 0 if ok else 1

    def note(self, message):
        self.lines.append('NOTE  ' + message)


def _receipts(root, folder, public_hex, report):
    """Verify every signed receipt in `folder`; returns {seq: (body, hash)}."""
    found = {}
    for path in sorted((root / folder).glob('*.json')):
        data = path.read_bytes()
        signature_path = path.with_suffix('.sig')
        body = json.loads(data)
        digest = sha256(data)
        signature = bytes.fromhex(signature_path.read_text().strip()) if signature_path.exists() else b''
        report.check(body.get('public_key') == public_hex, f'{folder}/{path.name}: signed by the bundled public key')
        report.check(ed25519_verify(bytes.fromhex(public_hex), data, signature), f'{folder}/{path.name}: Ed25519 signature is valid (receipt {digest[:16]}…)')
        found[body['seq']] = (body, digest)
    seqs = sorted(found)
    for before, after in zip(seqs, seqs[1:]):
        if after == before + 1:
            report.check(found[after][0].get('prev_receipt_hash') == found[before][1], f'receipt {after} links to receipt {before} in the hash chain')
    return found


def verify_bundle(root):
    report = Report()
    manifest = json.loads((root / 'manifest.json').read_text())
    public_hex = (root / 'public-key.txt').read_text().strip()
    report.note(f"Workspace key fingerprint {sha256(bytes.fromhex(public_hex))}")
    for name, expected in sorted(manifest.get('files', {}).items()):
        path = root / name
        report.check(path.exists() and sha256(path.read_bytes()) == expected, f'{name}: matches the bundle manifest')
    receipts = _receipts(root, 'receipts', public_hex, report)
    revision = json.loads((root / 'revision.json').read_text()) if (root / 'revision.json').exists() else None
    if revision:
        report.check(revision_hash(revision) == revision['hash'], f"revision.json: content hash recomputes to {revision['hash'][:16]}…")
    for seq, (body, digest) in sorted(receipts.items()):
        label = f'receipt {seq}'
        report.note(f"{label}: {body['status']} for {body['final_url']} observed {body['requested_at']}")
        capture = root / 'captures' / body['capture_id']
        if (capture / 'body.bin').exists():
            payload = (capture / 'body.bin').read_bytes()
            report.check(sha256(payload) == body['body_sha256'] and len(payload) == body['body_bytes'], f'{label}: captured response body matches its SHA-256')
            if not body.get('raw_exact'):
                report.note(f'{label}: body was reconstructed from decoded text, not the exact bytes received')
        else:
            report.note(f'{label}: response body not included (only confirmed content is stored)')
        if (capture / 'headers.json').exists():
            report.check(sha256((capture / 'headers.json').read_bytes()) == body['headers_sha256'], f'{label}: response headers match their SHA-256')
        if body.get('robots_sha256'):
            policy = root / 'policies' / (body['robots_sha256'] + '.txt')
            report.check(policy.exists() and sha256(policy.read_bytes()) == body['robots_sha256'], f'{label}: robots.txt matches its SHA-256')
        if body.get('rights_observation_hash'):
            rights = root / 'rights' / (body['rights_observation_hash'] + '.json')
            report.check(rights.exists() and sha256(rights.read_bytes()) == body['rights_observation_hash'], f'{label}: rights observation matches its SHA-256')
        if revision and body.get('revision_id') == revision['id']:
            report.check(body.get('revision_hash') == revision['hash'], f'{label}: attests this revision')
        for proof_path in sorted((root / 'anchors').glob(f'*/proof-{seq}.json')):
            proof = json.loads(proof_path.read_text())
            anchor_root = (proof_path.parent / 'anchor-root.bin').read_bytes().hex()
            report.check(proof['leaf'] == digest and merkle_root_from_path(digest, proof['path']) == anchor_root, f'{label}: included in anchor {proof_path.parent.name} (Merkle root {anchor_root[:16]}…)')
            if (proof_path.parent / 'anchor-root.bin.tsr').exists():
                report.note(f'{label}: check the RFC 3161 token with: openssl ts -verify -data {proof_path.parent}/anchor-root.bin -in {proof_path.parent}/anchor-root.bin.tsr -CAfile <your TSA certificate chain>')
            if (proof_path.parent / 'anchor-root.bin.ots').exists():
                report.note(f'{label}: check the OpenTimestamps proof with: ots verify {proof_path.parent}/anchor-root.bin.ots (run ots upgrade first if it is pending)')
    report.note('Receipts attest what this Proofpage workspace observed. TLS does not let anyone prove what a server sent.')
    return report


def verify_wacz(root):
    report = Report()
    package = (root / 'datapackage.json').read_bytes()
    digest_file = json.loads((root / 'datapackage-digest.json').read_text())
    report.check(digest_file.get('hash') == 'sha256:' + sha256(package), 'datapackage.json matches datapackage-digest.json')
    for resource in json.loads(package).get('resources', []):
        path = root / resource['path']
        report.check(path.exists() and resource['hash'] == 'sha256:' + sha256(path.read_bytes()) and resource['bytes'] == path.stat().st_size, f"{resource['path']}: matches datapackage.json")
    digests = set()
    index = root / 'indexes' / 'index.cdx'
    for line in index.read_text().splitlines() if index.exists() else []:
        digests.add(json.loads(line.split(' ', 2)[2]).get('digest', ''))
    if (root / 'proofpage' / 'public-key.txt').exists():
        public_hex = (root / 'proofpage' / 'public-key.txt').read_text().strip()
        for seq, (body, _) in sorted(_receipts(root / 'proofpage', 'receipts', public_hex, report).items()):
            if body.get('raw_exact') and body['status'] == 200:
                report.check('sha256:' + body['body_sha256'] in digests, f'receipt {seq}: its response body is in the archive index')
    else:
        report.note('No Proofpage receipts are included in this archive.')
    report.note('WACZ-Auth signatures are not used; Proofpage receipts are signed separately with Ed25519.')
    return report


def verify_path(path):
    path = Path(path)
    with tempfile.TemporaryDirectory() as temporary:
        root = path
        if path.is_file():
            with zipfile.ZipFile(path) as archive:
                for member in archive.namelist():
                    target = (Path(temporary) / member).resolve()
                    if not str(target).startswith(str(Path(temporary).resolve())):
                        raise ValueError('Archive contains an unsafe path: ' + member)
                archive.extractall(temporary)
            root = Path(temporary)
        if (root / 'datapackage.json').exists():
            return verify_wacz(root)
        if (root / 'manifest.json').exists():
            return verify_bundle(root)
        raise ValueError('Not a Proofpage proof bundle or WACZ file.')


def source():
    """This file's source, for embedding in bundles; frozen desktop builds ship it next to the compiled module."""
    path = Path(__file__)
    for candidate in (path, path.with_suffix('.py')):
        if candidate.suffix == '.py' and candidate.exists():
            return candidate.read_bytes()
    raise ValueError('The offline verifier is missing from this installation.')


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    target = argv[0] if argv else Path(__file__).resolve().parent
    report = verify_path(target)
    print('\n'.join(report.lines))
    print(f"\n{'VERIFIED' if not report.failures else 'NOT VERIFIED'}: {report.failures} failed check(s).")
    return 0 if not report.failures else 1


if __name__ == '__main__':
    sys.exit(main())
