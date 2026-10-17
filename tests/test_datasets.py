import json
import tempfile
import unittest
from pathlib import Path

from proofpage.core import Store
from proofpage.datasets import load_corpus


class CorpusTests(unittest.TestCase):
    def test_export_load_checksum_and_split_integrity(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Store(Path(directory) / 'data')
            source = store.source('Test source', 'import', 'test')
            for index in range(2):
                store.save(source['id'], str(index), 'document', 'Test', 'Text ' + str(index), 'Raw ' + str(index))
            for item in store.search():
                store.review(item['current_revision'], True, True)
            dataset = store.freeze('Fixture')
            path = Path(directory) / 'corpus.jsonl'
            path.write_text(store.export(dataset['id']))
            records = load_corpus(path, dataset['hash'])
            self.assertEqual(len(records), 2)
            self.assertEqual(len({r['split'] for r in records}), 1)
            with self.assertRaisesRegex(ValueError, 'checksum'):
                load_corpus(path, 'wrong')
            records[1]['split'] = 'test' if records[0]['split'] != 'test' else 'train'
            path.write_text('\n'.join(map(json.dumps, records)))
            with self.assertRaisesRegex(ValueError, 'crosses split'):
                load_corpus(path)
