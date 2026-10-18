import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from proofpage.core import Store
from proofpage import evidence
from proofpage.sdk import Proofpage


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = str(Path(self.tmp.name) / 'workspace')
        self.store = Store(self.home)
        self.source = self.store.source('Pricing fixture', 'import', 'fixture:pricing')
        self.store.save(self.source['id'], 'pricing', 'text', 'Pricing', 'Plan costs $20.', '<p>Plan costs $20.</p>')
        self.rid = self.store.rows('SELECT id FROM revisions')[0]['id']
        self.deps = [{'output_id': 'answer-1', 'revision_id': self.rid, 'start': 0, 'end': 15, 'quote': 'Plan costs $20.'}]
        self.manifest = evidence.record(self.store, [self.rid], self.deps)
        self.path = Path(self.tmp.name) / 'run.json'
        evidence.write(self.manifest, self.path)

    def test_replay_without_workspace_or_network(self):
        Path(self.store.path).unlink()
        with patch('socket.socket', side_effect=AssertionError('Network forbidden')):
            replayed = Proofpage.replay(self.path, self.manifest['sha256'])
        self.assertEqual(replayed['records'][0]['text'], 'Plan costs $20.')

    def test_drift_and_affected_output(self):
        self.assertTrue(evidence.compare(self.store, self.manifest)['ok'])
        self.store.save(self.source['id'], 'pricing', 'text', 'Pricing', 'Plan costs $30.', '<p>Plan costs $30.</p>')
        report = evidence.compare(self.store, self.manifest)
        self.assertFalse(report['ok'])
        self.assertEqual(report['records'][0]['affected_outputs'], ['answer-1'])
        self.assertFalse(report['records'][0]['quotes'][0]['present_in_current'])
        self.assertEqual(evidence.replay(self.path)['records'][0]['text'], 'Plan costs $20.')

    def test_tamper_and_replacement_pin(self):
        modified = copy.deepcopy(self.manifest)
        modified['records'][0]['text'] = 'Fake'
        with self.assertRaises(evidence.EvidenceError): evidence.validate(modified)
        modified = copy.deepcopy(self.manifest)
        modified['name'] = 'Replacement'
        modified['sha256'] = evidence.sha(evidence.canonical({k:v for k,v in modified.items() if k != 'sha256'}))
        with self.assertRaises(evidence.EvidenceError): evidence.validate(modified, self.manifest['sha256'])

    def test_missing_and_invalid_dependencies(self):
        with self.store.db() as db: db.execute('DELETE FROM items')
        self.assertEqual(evidence.compare(self.store, self.manifest)['records'][0]['state'], 'missing')
        with self.assertRaises(evidence.EvidenceError): evidence.record(self.store, [self.rid], self.deps)
        with self.assertRaises(evidence.EvidenceError): evidence.record(self.store, [])

    def test_invalid_quote_and_overwrite(self):
        self.deps[0]['end'] = 2
        with self.assertRaises(evidence.EvidenceError): evidence.record(self.store, [self.rid], self.deps)
        with self.assertRaises(FileExistsError): evidence.write(self.manifest, self.path)

    def test_cli_exit_codes(self):
        command = [sys.executable, '-m', 'proofpage', '--home', self.home, 'evidence', 'check', str(self.path)]
        self.assertEqual(subprocess.run(command, capture_output=True).returncode, 0)
        self.store.save(self.source['id'], 'pricing', 'text', 'Pricing', 'Changed', 'Changed')
        result = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertFalse(json.loads(result.stdout)['ok'])
        self.assertEqual(subprocess.run(command + ['--sha256', 'bad'], capture_output=True).returncode, 2)

    def test_refresh_import_is_explicit_and_offline(self):
        with patch.object(self.store, 'collect', side_effect=AssertionError('No import fetching')):
            self.assertEqual(evidence.refresh(self.store, self.manifest)['refresh'][0]['state'], 'archive_only')

    def test_exact_capture_bytes_and_missing_payload(self):
        import base64
        import zlib
        raw = b'\xff\x00original bytes'
        digest = evidence.sha(raw)
        with self.store.db() as db:
            db.execute('INSERT INTO capture_payloads VALUES(?,?)', (digest, zlib.compress(raw)))
            db.execute('INSERT INTO captures(id,run_id,source_id,url,final_url,requested_at,status,headers,body_sha256,body_bytes,raw_exact,revision_id) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',
                       ('cap', 'run', self.source['id'], 'https://example.com', 'https://example.com', '2026-10-18', 200, '{}', digest, len(raw), 1, self.rid))
        manifest = evidence.record(self.store, [self.rid])
        original = manifest['records'][0]['original']
        self.assertEqual(original['representation'], 'http_body_exact')
        self.assertEqual(base64.b64decode(original['base64']), raw)
        with self.store.db() as db: db.execute('DELETE FROM capture_payloads')
        with self.assertRaises(evidence.EvidenceError): evidence.record(self.store, [self.rid])

    def test_failed_refresh_does_not_claim_freshness(self):
        with self.store.db() as db:
            db.execute("UPDATE sources SET kind='web',location='https://example.com' WHERE id=?", (self.source['id'],))
        manifest = evidence.record(self.store, [self.rid])
        with patch.object(self.store, 'collect', side_effect=ValueError('Cooldown')):
            result = evidence.refresh(self.store, manifest)
        self.assertTrue(result['comparison']['ok'])
        self.assertEqual(result['refresh'][0]['state'], 'deferred')

    def test_bad_manifest_shapes(self):
        for value in ([], None, {'schema': 'unknown'}):
            with self.assertRaises(evidence.EvidenceError): evidence.validate(value)
