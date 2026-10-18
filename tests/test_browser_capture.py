import json
import tempfile
import unittest
from pathlib import Path
from proofpage.adapters import parse_entry
from proofpage.core import Store, import_file
from proofpage.imports import create_profile


class BrowserCaptureTests(unittest.TestCase):
    def payload(self, **changes):
        record = dict(proofpage_capture='visible-text-v1', title='Member page', url='https://example.com/members', text='User-reviewed page text.', created_at='2026-10-17T12:00:00Z')
        record.update(changes)
        return json.dumps(record).encode()

    def test_browser_text_is_supplied_not_a_web_receipt(self):
        row = parse_entry('capture.json', self.payload())[0]
        self.assertEqual(row['text'], 'User-reviewed page text.')
        self.assertEqual(row['metadata']['normalized']['attestation'], 'user_supplied')
        self.assertEqual(row['metadata']['normalized']['source_url'], 'https://example.com/members')
        self.assertNotIn('url', row['metadata'])
        with tempfile.TemporaryDirectory() as folder:
            store = Store(Path(folder)/'data')
            profile = create_profile(store, 'Browser', 'Browser companion', 'personal')
            result = import_file(store, 'capture.json', self.payload(), ['capture.json'], profile['id'])
            self.assertEqual(result['added'], 1)
            self.assertEqual(store.rows('SELECT kind FROM sources')[0]['kind'], 'import')
            self.assertEqual(store.rows('SELECT * FROM receipts'), [])
            result = import_file(store, 'capture.json', self.payload(text='Updated text.'), ['capture.json'], profile['id'])
            self.assertEqual(result['added'], 1)
            self.assertEqual(len(store.rows('SELECT * FROM items')), 1)
            self.assertEqual(len(store.rows('SELECT * FROM revisions')), 2)

    def test_invalid_browser_capture_rejected(self):
        for changes in ({'url':'file:///private'}, {'url':None}, {'text':''}, {'text':['bad']}, {'text':'x'*500001}):
            with self.subTest(changes=str(changes)[:60]), self.assertRaises(ValueError):
                parse_entry('capture.json', self.payload(**changes))
