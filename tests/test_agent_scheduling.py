import tempfile
import unittest
from unittest.mock import patch
from proofpage.core import Store
from proofpage.mcp import call


class AgentSchedulingTests(unittest.TestCase):
    def test_source_schedule_pause_and_dedup(self):
        with tempfile.TemporaryDirectory() as home:
            store = Store(home)
            with patch('proofpage.core.validate_url', return_value='https://example.com/report.pdf'):
                source = call(store, 'proofpage_add_source', {'name': 'Report', 'url': 'https://example.com/report.pdf'})
                duplicate = call(store, 'proofpage_add_source', {'name': 'Report again', 'url': source['location']})
            self.assertEqual(source['id'], duplicate['id'])
            self.assertEqual(store.rows('SELECT * FROM runs'), [])
            result = call(store, 'proofpage_schedule_source', {'source_id': source['id'], 'interval_seconds': 3600})
            self.assertEqual(result['state'], 'scheduled')
            self.assertEqual(store.rows('SELECT interval_seconds FROM sources')[0]['interval_seconds'], 3600)
            call(store, 'proofpage_schedule_source', {'source_id': source['id'], 'interval_seconds': 0})
            self.assertEqual(store.rows('SELECT next_run FROM sources')[0]['next_run'], 0)
            for interval in (-1, 1, 299, 31536001, True):
                with self.assertRaises(ValueError):
                    call(store, 'proofpage_schedule_source', {'source_id': source['id'], 'interval_seconds': interval})
            with self.assertRaises(ValueError):
                call(store, 'proofpage_schedule_source', {'source_id': 'missing', 'interval_seconds': 300})
            imported = store.source('Archive', 'import', 'fixture')
            with self.assertRaises(ValueError):
                call(store, 'proofpage_schedule_source', {'source_id': imported['id'], 'interval_seconds': 300})

    def test_destination_validation_is_not_bypassed(self):
        with tempfile.TemporaryDirectory() as home:
            store = Store(home)
            with patch('proofpage.core.validate_url', side_effect=ValueError('Private destination')):
                with self.assertRaises(ValueError):
                    call(store, 'proofpage_add_source', {'name': 'Private', 'url': 'http://127.0.0.1'})
            self.assertEqual(store.rows('SELECT * FROM sources'), [])
