import gzip
import hashlib
import io
import json
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
import zipfile
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from unittest.mock import patch

from proofpage import core, ed25519, mcp, receipts, verify, wacz
from proofpage.backup import backup
from proofpage.core import Store

ARTICLE = '<title>Article</title><main><p>' + 'Evidence worth keeping. ' * 20 + '</p></main>'
VECTORS = [  # RFC 8032 section 7.1
    ('9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60', 'd75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a', '',
     'e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e065224901555fb8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b'),
    ('4ccd089b28ff96da9db6c346ec114e0f5b8a319f35aba624da8cf6ed4fb8a6fb', '3d4017c3e843895a92b70aa74d1b7ebc9c982ccf2ec4968cc0cd55f12af4660c', '72',
     '92a009a9f0d4cab8720e820b5f642540a2b27b5416503f8fb3762223ebdb69da085ac1e43e15996e458f3613d0f11d8c387b2eaeb4302aeeb00d291612bb0c00'),
    ('c5aa8df43f9f837bedb7442f31dcb7b166d38535076f094b85ce3a2e0b4458f7', 'fc51cd8e6218a1a38da47ed00230f0580816ed13ba3303ac5deb911548908025', 'af82',
     '6291d657deec24024827e69c3abe01a30ce548a284743a445e3680d7db5ac3ac18ff9b538d16f290ae67f760984dc6594a7c15e9716ed28dc027beceea1ec40a'),
]
OPENSSL_TS = shutil.which('openssl') and subprocess.run(['openssl', 'ts', '-help'], capture_output=True).returncode in (0, 1)


def fake_fetch(responses):
    """Stand-in for core.fetch that also reports transport details like a real fetch."""
    responses = list(responses)

    def fetch(url, allowed=None):
        status, headers, body, final = responses.pop(0)
        meta = getattr(core._RECORDER, 'meta', None)
        if meta is not None:
            meta.update(raw=body.encode(), header_list=list(headers.items()), redirects=[], peer_ip='93.184.215.14', http_version='HTTP/1.1', reason='OK',
                        tls={'version': 'TLSv1.3', 'cert_sha256': 'ab' * 32, 'issuer': 'commonName=Fixture CA', 'not_after': 'Jan 1 00:00:00 2030 GMT'})
        return status, headers, body, final
    return fetch


class Service:
    """A tiny local HTTP service for timestamp-authority and calendar fixtures."""

    def __init__(self, respond):
        self.requests = []
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                body = self.rfile.read(int(self.headers['Content-Length']))
                outer.requests.append((self.path, self.headers.get('Content-Type'), body))
                status, reply = respond(self.path, body)
                self.send_response(status)
                self.end_headers()
                self.wfile.write(reply)

        self.server = HTTPServer(('127.0.0.1', 0), Handler)
        self.url = f'http://127.0.0.1:{self.server.server_port}'
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *args):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()


class SignatureTests(unittest.TestCase):
    def test_rfc8032_vectors_in_pure_python_and_verifier(self):
        with patch.object(ed25519, '_library', return_value=None):
            for seed, public, message, signature in VECTORS:
                seed, message = bytes.fromhex(seed), bytes.fromhex(message)
                self.assertEqual(ed25519.public_key(seed).hex(), public)
                self.assertEqual(ed25519.sign(seed, message).hex(), signature)
                self.assertTrue(ed25519.verify(bytes.fromhex(public), message, bytes.fromhex(signature)))
                self.assertTrue(verify.ed25519_verify(bytes.fromhex(public), message, bytes.fromhex(signature)))
                self.assertFalse(verify.ed25519_verify(bytes.fromhex(public), message + b'!', bytes.fromhex(signature)))

    def test_merkle_paths_for_every_batch_size(self):
        for size in range(1, 10):
            hashes = [hashlib.sha256(str(i).encode()).hexdigest() for i in range(size)]
            root, paths = receipts.merkle(hashes)
            for receipt_hash, path in zip(hashes, paths):
                self.assertEqual(verify.merkle_root_from_path(receipt_hash, path), root.hex())
            if size > 1:
                self.assertNotEqual(verify.merkle_root_from_path(hashes[0], paths[1]), root.hex())

    def test_timestamp_request_matches_openssl_encoding(self):
        expected = bytes.fromhex('30390201013031300d0609608648016503040201050004202a7afe0753c6ef53a0641bf0da3aecb0942134d9d49f0a3a067b767aca5b2c8b0101ff')
        self.assertEqual(receipts.timestamp_request(hashlib.sha256(b'proofpage').digest()), expected)
        with self.assertRaisesRegex(ValueError, 'could not read'):
            receipts.parse_timestamp_reply(b'\x30\x03\x02\x01', b'x' * 32)
        refused = receipts._der(0x30, receipts._der(0x30, receipts._der_int(2)))
        with self.assertRaisesRegex(ValueError, 'refused'):
            receipts.parse_timestamp_reply(refused, b'x' * 32)


class ReceiptTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = Store(self.temp.name)
        with patch('proofpage.core.validate_url'):
            self.source = self.store.source('Docs', 'web', 'https://example.org/docs')

    def tearDown(self):
        self.temp.cleanup()

    def collect(self, html=ARTICLE, status=200):
        with self.store.db() as db:
            db.execute('DELETE FROM cooldowns')
        page = (status, {'content-type': 'text/html', 'transfer-encoding': 'chunked'}, html, self.source['location'])
        with patch('proofpage.core.fetch', side_effect=fake_fetch([(404, {}, '', ''), page, (404, {}, '', '')])):
            return self.store.collect(self.source['id'])

    def test_every_capture_gets_a_chained_signed_receipt(self):
        first = self.collect()['rights']['receipt']
        second = self.collect(status=403, html='Denied')['rights']['receipt']
        self.assertEqual((first['seq'], second['seq']), (1, 2))
        body = json.loads(self.store.rows('SELECT body FROM receipts WHERE seq=2')[0]['body'])
        self.assertEqual((body['prev_receipt_hash'], body['status'], body['body_stored']), (first['hash'], 403, False))
        self.assertIn('does not prove what the server sent', body['attestation'])
        self.assertTrue(receipts.verify_chain(self.store)['ok'])
        with self.store.db() as db:
            db.execute("UPDATE receipts SET body=replace(body,'\"status\":403','\"status\":200') WHERE seq=2")
        problems = ' '.join(receipts.verify_chain(self.store)['problems'])
        self.assertIn('does not match its hash', problems)
        self.assertIn('signature is not valid', problems)
        with self.store.db() as db:
            db.execute('DELETE FROM receipts WHERE seq=1')
        self.assertIn('chain link', ' '.join(receipts.verify_chain(self.store)['problems']))

    def test_proof_bundle_verifies_offline_and_detects_tampering(self):
        self.collect()
        revision = self.store.search()[0]['current_revision']
        bundle = receipts.proof_bundle(self.store, revision)
        self.assertEqual(bundle, receipts.proof_bundle(self.store, revision))
        with tempfile.TemporaryDirectory() as directory:
            zipfile.ZipFile(io.BytesIO(bundle)).extractall(directory)
            ok = subprocess.run([sys.executable, '-I', 'verify_proof.py'], cwd=directory, capture_output=True, text=True)
            self.assertEqual(ok.returncode, 0, ok.stdout)
            self.assertIn('Ed25519 signature is valid', ok.stdout)
            self.assertIn('content hash recomputes', ok.stdout)
            self.assertTrue((Path(directory) / 'public-key.pem').read_text().startswith('-----BEGIN PUBLIC KEY-----'))
            payload = next(Path(directory).glob('captures/*/body.bin'))
            payload.write_bytes(payload.read_bytes().replace(b'Evidence', b'Fiction'))
            bad = subprocess.run([sys.executable, '-I', 'verify_proof.py'], cwd=directory, capture_output=True, text=True)
            self.assertEqual(bad.returncode, 1)
            self.assertIn('FAIL  receipt 1: captured response body matches its SHA-256', bad.stdout)
        self.assertEqual(mcp.call(self.store, 'proofpage_get_receipt', {'revision_id': revision})['state'], 'signed')
        with self.assertRaisesRegex(ValueError, 'no receipts'):
            legacy = self.store.source('Notes', 'import', 'import:notes')
            self.store.save(legacy['id'], 'n', 'document', 'Note', 'Text', 'raw')
            receipts.proof_bundle(self.store, self.store.rows("SELECT r.id FROM revisions r JOIN items i ON i.id=r.item_id WHERE i.source_id=?", (legacy['id'],))[0]['id'])

    def test_anchoring_is_off_by_default_and_never_contacts_the_network(self):
        self.collect()
        with patch('proofpage.receipts._post', side_effect=AssertionError('network used')):
            self.assertIsNone(receipts.anchor(self.store))
            with self.assertRaisesRegex(ValueError, 'anchoring is off'):
                receipts.anchor(self.store, force=True)
        with self.assertRaisesRegex(ValueError, 'plain HTTP'):
            receipts.save_settings(self.store, {'anchor_tsa_url': 'https://user:pw@tsa.example/'})

    def test_opentimestamps_submission_and_bundle(self):
        self.collect()
        calendar_reply = b'\xf0\x10' + b'c' * 16 + b'\x08\x00\x83\xdf\xe3\x0d\x2e\xf9\x0c\x8e' + b'\x1b' + b'https://fixture.calendar'
        with self.assertRaisesRegex(ValueError, 'HTTPS'):
            receipts.save_settings(self.store, {'anchor_ots': True, 'anchor_ots_calendar': 'http://calendar.example'})
        with Service(lambda path, body: (200, calendar_reply)) as calendar:
            with self.store.db() as db:  # the fixture calendar is plain HTTP on loopback, which settings would refuse
                db.executemany('INSERT INTO settings VALUES(?,?)', [('anchor_ots', '1'), ('anchor_ots_calendar', calendar.url)])
            result = receipts.anchor(self.store, force=True)
            self.assertEqual(calendar.requests[0][0], '/digest')
            self.assertEqual(calendar.requests[0][2].hex(), result['imprint'])
        self.assertEqual(result['ots_state'], 'submitted')
        proof = bytes(self.store.rows('SELECT ots_proof FROM anchors')[0]['ots_proof'])
        self.assertEqual(proof, receipts.OTS_MAGIC + b'\x01\x08' + bytes.fromhex(result['imprint']) + calendar_reply)
        self.assertIsNone(receipts.anchor(self.store))  # at most once a day unless forced
        revision = self.store.search()[0]['current_revision']
        with tempfile.TemporaryDirectory() as directory:
            zipfile.ZipFile(io.BytesIO(receipts.proof_bundle(self.store, revision))).extractall(directory)
            report = verify.verify_path(directory)
            self.assertEqual(report.failures, 0, report.lines)
            self.assertTrue(any('included in anchor' in line for line in report.lines))
            self.assertTrue(list(Path(directory).glob('anchors/*/anchor-root.bin.ots')))
        self.assertEqual(receipts.revision_proof(self.store, revision)['state'], 'anchored')

    @unittest.skipUnless(OPENSSL_TS, 'OpenSSL with the ts command is required for the RFC 3161 interoperability test.')
    def test_rfc3161_anchor_with_an_openssl_timestamp_authority(self):
        self.collect()
        work = Path(self.temp.name) / 'tsa'
        work.mkdir()
        run = lambda *args: subprocess.run(args, cwd=work, check=True, capture_output=True)
        run('openssl', 'req', '-x509', '-newkey', 'ec', '-pkeyopt', 'ec_paramgen_curve:P-256', '-nodes', '-keyout', 'ca.key', '-out', 'ca.crt', '-days', '2', '-subj', '/CN=Fixture Root',
            '-addext', 'basicConstraints=critical,CA:TRUE', '-addext', 'keyUsage=critical,keyCertSign')
        run('openssl', 'req', '-newkey', 'ec', '-pkeyopt', 'ec_paramgen_curve:P-256', '-nodes', '-keyout', 'tsa.key', '-out', 'tsa.csr', '-subj', '/CN=Fixture TSA')
        (work / 'ext.cnf').write_text('basicConstraints=CA:FALSE\nextendedKeyUsage=critical,timeStamping\nkeyUsage=critical,digitalSignature\n')
        run('openssl', 'x509', '-req', '-in', 'tsa.csr', '-CA', 'ca.crt', '-CAkey', 'ca.key', '-CAcreateserial', '-out', 'tsa.crt', '-days', '2', '-extfile', 'ext.cnf')
        (work / 'serial').write_text('01\n')
        (work / 'tsa.cnf').write_text('[ tsa ]\ndefault_tsa = c\n[ c ]\nserial = ./serial\ncrypto_device = builtin\nsigner_cert = ./tsa.crt\nsigner_key = ./tsa.key\n'
                                      'signer_digest = sha256\ndefault_policy = 1.2.3.4.1\ndigests = sha256\naccuracy = secs:1\nordering = no\ntsa_name = no\n'
                                      'ess_cert_id_chain = no\ness_cert_id_alg = sha256\n')

        def respond(path, query):
            (work / 'q.der').write_bytes(query)
            run('openssl', 'ts', '-reply', '-config', 'tsa.cnf', '-queryfile', 'q.der', '-out', 'r.tsr')
            return 200, (work / 'r.tsr').read_bytes()

        with Service(respond) as tsa:
            receipts.save_settings(self.store, {'anchor_tsa_url': tsa.url + '/tsr'})
            result = receipts.anchor(self.store, force=True)
            self.assertEqual(tsa.requests[0][1], 'application/timestamp-query')
        self.assertEqual(result['tsa_state'], 'complete', result['tsa_detail'])
        revision = self.store.search()[0]['current_revision']
        with tempfile.TemporaryDirectory() as directory:
            zipfile.ZipFile(io.BytesIO(receipts.proof_bundle(self.store, revision))).extractall(directory)
            anchor = next(Path(directory).glob('anchors/*'))
            checked = subprocess.run(['openssl', 'ts', '-verify', '-data', str(anchor / 'anchor-root.bin'), '-in', str(anchor / 'anchor-root.bin.tsr'),
                                      '-CAfile', str(work / 'ca.crt'), '-untrusted', str(work / 'tsa.crt')], capture_output=True, text=True)
            self.assertIn('Verification: OK', checked.stdout)
            self.assertEqual(verify.verify_path(directory).failures, 0)

    def test_wacz_export_structure_and_verification(self):
        self.collect()
        with self.store.db() as db:
            db.execute('DELETE FROM cooldowns')
        with patch('proofpage.core.fetch', side_effect=[(404, {}, '', ''), (200, {'content-type': 'text/html'}, ARTICLE + '<p>v2</p>', self.source['location'])]):
            self.store.collect(self.source['id'])  # a mocked capture without transport details is stored as reconstructed text
        data, summary = wacz.export_wacz(self.store, self.source['id'])
        self.assertEqual((summary['records'], summary['exact'], summary['reconstructed'], summary['receipts']), (2, 1, 1, 2))
        archive = zipfile.ZipFile(io.BytesIO(data))
        self.assertTrue(all(info.compress_type == zipfile.ZIP_STORED for info in archive.infolist()))
        self.assertEqual(archive.namelist()[:2], ['datapackage.json', 'datapackage-digest.json'])
        warc = archive.read('archive/data.warc.gz')
        types = []
        for line in archive.read('indexes/index.cdx').decode().splitlines():
            key, stamp, fields = line.split(' ', 2)
            fields = json.loads(fields)
            self.assertEqual((key, len(stamp)), ('org,example)/docs', 14))
            record = gzip.decompress(warc[int(fields['offset']):int(fields['offset']) + int(fields['length'])])
            head, _, block = record.partition(b'\r\n\r\n')
            types.append(head.split(b'\r\n')[1].decode())
            if b'WARC-Type: response' in head:
                self.assertTrue(block.startswith(b'HTTP/1.1 200 OK\r\n'))
                self.assertIn(b'X-Archive-Orig-Transfer-Encoding: chunked', block)
        self.assertEqual(sorted(types), ['WARC-Type: resource', 'WARC-Type: response'])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'site.wacz'
            path.write_bytes(data)
            report = verify.verify_path(path)
            self.assertEqual(report.failures, 0, report.lines)
            self.assertTrue(any('in the archive index' in line for line in report.lines))

    def test_backup_warns_that_it_contains_the_signing_key(self):
        self.collect()
        with tempfile.TemporaryDirectory() as directory:
            self.assertIn('receipt-signing key', backup(self.store, Path(directory) / 'copy.sqlite3')['note'])


if __name__ == '__main__':
    unittest.main()
