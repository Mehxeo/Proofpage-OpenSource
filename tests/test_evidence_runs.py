import base64
import json
import tempfile
import unittest
from unittest.mock import patch

from proofpage.core import Store
from proofpage import evidence, evidence_runs, mcp, service


class EvidenceRunTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = Store(self.tmp.name)
        self.source = self.store.source('Pricing', 'import', 'fixture:pricing')
        self.store.save(self.source['id'], 'pricing', 'text', 'Pricing', 'The plan costs $20 per month.', 'original')
        self.item = self.store.rows('SELECT * FROM items')[0]

    def record(self):
        return mcp.call(self.store, 'proofpage_record_context', {'query': 'plan', 'output_id': 'answer-1', 'name': 'Pricing answer'})

    def test_record_reopen_replay_and_reverse_dependencies(self):
        result = self.record()
        run_id = result['recording']['run_id']
        self.store = Store(self.tmp.name)
        self.assertTrue(evidence_runs.check(self.store, run_id)['ok'])
        self.assertEqual(evidence_runs.affected(self.store, self.item['id'])['affected_outputs'], [])
        self.store.save(self.source['id'], 'pricing', 'text', 'Pricing', 'The plan costs $30 per month.', 'new original')
        with patch('socket.socket', side_effect=AssertionError('No network')):
            replay = mcp.call(self.store, 'proofpage_replay_context', {'run_id': run_id})
            affected = mcp.call(self.store, 'proofpage_affected_outputs', {'item_id': self.item['id']})
        self.assertEqual(replay['excerpts'][0]['quote'], result['excerpts'][0]['text'])
        self.assertEqual(affected['affected_outputs'][0]['output_id'], 'answer-1')
        self.assertFalse(affected['affected_outputs'][0]['quotes'][0]['present_in_current'])
        self.assertFalse(mcp.call(self.store, 'proofpage_check_evidence_run', {'run_id': run_id})['ok'])

    def test_empty_invalid_and_missing(self):
        self.assertIsNone(evidence_runs.record_context(self.store, 'zzzzzz', 'answer', 'Empty')['recording'])
        self.assertEqual(evidence_runs.list_runs(self.store), [])
        for output in ('', 'x' * 201, None):
            with self.assertRaises(ValueError): evidence_runs.record_context(self.store, 'plan', output, 'name')
        with self.assertRaises(ValueError): evidence_runs.get(self.store, 'missing')

    def test_api_exports_and_tampered_database(self):
        result = service.post(self.store, '/api/record-context', {'query': 'plan', 'output_id': 'answer'})[1]
        run_id = result['recording']['run_id']
        self.assertEqual(len(service.get(self.store, '/api/evidence-runs', {})[1]), 1)
        exported = service.get(self.store, '/api/evidence-runs/' + run_id + '/export', {})[1]
        manifest = evidence.validate(json.loads(exported), result['recording']['sha256'])
        self.assertEqual(manifest['dependencies'][0]['output_id'], 'answer')
        with self.store.db() as db:
            db.execute("UPDATE evidence_runs SET sha256='bad' WHERE id=?", (run_id,))
        with self.assertRaises(ValueError): evidence_runs.replay_context(self.store, run_id)

    def test_original_import_bytes(self):
        raw = b'%PDF-1.4\nfixture bytes'
        metadata = {'asset': {'mime': 'application/pdf', 'sha256': evidence.sha(raw), 'bytes': len(raw)}}
        self.store.save(self.source['id'], 'pdf', 'pdf', 'Report', 'Extracted text', json.dumps({'data': base64.b64encode(raw).decode()}), metadata)
        rid = self.store.rows("SELECT current_revision FROM items WHERE external_id='pdf'")[0]['current_revision']
        original = evidence.record(self.store, [rid])['records'][0]['original']
        self.assertEqual(original['representation'], 'supplied_file_exact')
        self.assertEqual(base64.b64decode(original['base64']), raw)

    def test_failed_save_is_atomic(self):
        manifest = evidence.record(self.store, [self.item['current_revision']])
        manifest['dependencies'] = [{'revision_id': 'missing'}]
        with self.assertRaises(ValueError): evidence_runs.save(self.store, manifest)
        self.assertEqual(evidence_runs.list_runs(self.store), [])

    def test_external_collector_import_and_manifest(self):
        from proofpage.sdk import Proofpage
        client = Proofpage(self.tmp.name)
        with patch('socket.socket', side_effect=AssertionError('No network')):
            imported = client.import_capture('https://example.com/report', text='Report evidence', original=b'<main>Report evidence</main>', collector='fixture/1')
        manifest = client.record([imported['revision_id']])
        row = manifest['records'][0]
        self.assertEqual(row['original']['representation'], 'external_collector_bytes')
        self.assertIsNone(row['capture'])
        self.assertEqual(base64.b64decode(row['original']['base64']), b'<main>Report evidence</main>')
        with self.assertRaises(ValueError): client.import_capture('https://user:secret@example.com', text='text', original=b'raw')
