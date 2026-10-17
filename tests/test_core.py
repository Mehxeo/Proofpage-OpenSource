import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
import zipfile
from unittest.mock import patch

from proofpage.core import Store, classify, import_file, preview, retry_seconds, validate_url


ARTICLE = '<title>Authentication documentation</title><main><h1>Sign in</h1>' + '<p>Use an API token to authenticate your application securely.</p>' * 8 + '</main><input type="password">'


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = Store(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_login_vs_article(self):
        self.assertEqual(classify(200, '<title>Sign in</title><input type="password">')[0], 'authentication_required')
        self.assertEqual(classify(200, ARTICLE)[0], 'available')
        self.assertEqual(classify(200, '<title>Just a moment</title>Verify you are human')[0], 'challenge_required')
        self.assertEqual(classify(429, ARTICLE)[0], 'rate_limited')

    def test_failed_capture_preserves_last_good_revision(self):
        with patch('proofpage.core.validate_url'):
            source = self.store.source('Docs', 'web', 'https://example.com/docs')
        good = [(404, {}, '', ''), (200, {'content-type': 'text/html'}, ARTICLE, source['location'])]
        with patch('proofpage.core.fetch', side_effect=good):
            self.assertEqual(self.store.collect(source['id'])['added'], 1)
        before = self.store.search()[0]
        with self.store.db() as db:
            db.execute('DELETE FROM cooldowns')
        bad = [(404, {}, '', ''), (200, {'content-type': 'text/html'}, '<title>Login</title><input type="password">', source['location'])]
        with patch('proofpage.core.fetch', side_effect=bad):
            self.assertEqual(self.store.collect(source['id'])['state'], 'authentication_required')
        after = self.store.search()[0]
        self.assertEqual(before['current_revision'], after['current_revision'])
        self.assertEqual(len(self.store.rows('SELECT * FROM revisions')), 1)

    def test_cooldown_is_shared_between_sources_and_store_instances(self):
        with patch('proofpage.core.validate_url'):
            one = self.store.source('A', 'web', 'https://example.com/a')
            two = self.store.source('B', 'web', 'https://example.com/b')
        with patch('proofpage.core.fetch', return_value=(429, {'retry-after': '600'}, '', '')):
            self.assertEqual(self.store.collect(one['id'])['state'], 'rate_limited')
        second_store = Store(self.temp.name)
        with patch('proofpage.core.fetch') as fetch:
            with self.assertRaisesRegex(ValueError, 'cooling down'):
                second_store.collect(two['id'])
            fetch.assert_not_called()

    def test_archive_selection_dedup_and_human_roles(self):
        data = io.BytesIO()
        with zipfile.ZipFile(data, 'w') as archive:
            archive.writestr('Messages.csv', 'ID,FROM,CONTENT,DATE\n1,Alice,Hello,2020-01-01\n')
            archive.writestr('Connections.csv', 'Name\nBob\n')
        payload = data.getvalue()
        self.assertEqual(len(preview('linkedin.zip', payload)), 2)
        with self.assertRaisesRegex(ValueError, 'Select'):
            import_file(self.store, 'linkedin.zip', payload)
        first = import_file(self.store, 'linkedin.zip', payload, ['Messages.csv'])
        again = import_file(self.store, 'linkedin.zip', payload, ['Messages.csv'])
        self.assertEqual((first['added'], again['added']), (1, 0))
        item = self.store.search('Hello')[0]
        self.assertEqual(item['kind'], 'human_message')
        self.assertEqual(item['source_time'], '2020-01-01')
        self.assertNotEqual(item['captured_at'], item['source_time'])
        self.assertEqual(self.store.search('Bob'), [])

    def test_dataset_frozen_bytes_and_revocation(self):
        source = self.store.source('Notes', 'import', 'notes')
        self.store.save(source['id'], '1', 'document', 'One', 'First version', 'First version')
        old = self.store.search()[0]['current_revision']
        with self.assertRaises(ValueError):
            self.store.freeze('Denied')
        self.store.review(old, True, True)
        dataset = self.store.freeze('Approved')
        frozen = self.store.export(dataset['id'])
        self.store.save(source['id'], '1', 'document', 'One', 'Second version', 'Second version')
        self.assertEqual(frozen, self.store.export(dataset['id']))
        self.assertEqual(json.loads(frozen)['text'], 'First version')
        self.store.review(old, False, True)
        with self.assertRaisesRegex(ValueError, 'no longer'):
            self.store.export(dataset['id'])

    def test_opening_another_client_does_not_interrupt_live_run(self):
        with self.store.db() as db:
            db.execute("INSERT INTO runs(id,state) VALUES('live','running')")
            db.execute('INSERT INTO run_owners VALUES(?,?)', ('live', os.getpid()))
            db.execute("INSERT INTO runs(id,state) VALUES('dead','running')")
        Store(self.temp.name)
        rows = {r['id']: r['state'] for r in self.store.rows('SELECT id,state FROM runs')}
        self.assertEqual(rows, {'live': 'running', 'dead': 'interrupted'})

    def test_private_network_and_linkedin_rejected(self):
        with patch('socket.getaddrinfo', return_value=[(2, 1, 6, '', ('127.0.0.1', 80))]):
            with self.assertRaisesRegex(ValueError, 'Private'):
                validate_url('http://example.com')
        with self.assertRaisesRegex(ValueError, 'LinkedIn'):
            validate_url('https://www.linkedin.com/feed')

    def test_mcp_stdio_handshake_and_search(self):
        messages = [
            {'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {'protocolVersion': '2025-06-18'}},
            {'jsonrpc': '2.0', 'method': 'notifications/initialized'},
            {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/list'},
            {'jsonrpc': '2.0', 'id': 3, 'method': 'tools/call', 'params': {'name': 'proofpage_search', 'arguments': {'query': 'nothing'}}},
        ]
        result = subprocess.run([sys.executable, '-m', 'proofpage', '--home', self.temp.name, 'mcp'], input='\n'.join(map(json.dumps, messages))+'\n', text=True, capture_output=True, check=True)
        rows = [json.loads(line) for line in result.stdout.splitlines()]
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0]['result']['protocolVersion'], '2025-06-18')
        self.assertEqual(len(rows[1]['result']['tools']), 18)
        self.assertFalse(rows[2]['result']['isError'])

    def test_retry_after(self):
        self.assertEqual(retry_seconds('120'), 120)
        self.assertEqual(retry_seconds('172800'), 172800)
        self.assertEqual(retry_seconds('nonsense'), 300)

    def test_return_to_previous_content_updates_search(self):
        source = self.store.source('Notes', 'import', 'notes')
        for text in ('original', 'changed', 'original'):
            self.store.save(source['id'], '1', 'document', 'Note', text, text)
        self.assertEqual(len(self.store.rows('SELECT * FROM revisions')), 2)
        self.assertEqual(self.store.search()[0]['text'], 'original')
        self.assertEqual(self.store.search('changed'), [])


if __name__ == '__main__':
    unittest.main()
