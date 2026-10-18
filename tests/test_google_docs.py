import tempfile
import unittest
from unittest.mock import patch
from proofpage import google_docs, business
from proofpage.core import Store

DOC = 'abc123_def456'
def document(text, revision='r1'):
    def paragraph(value):
        return {'paragraph': {'elements': [{'textRun': {'content': value}}]}}
    table = {'table': {'tableRows': [{'tableCells': [{'content': [paragraph('Monthly plans.')]}]}]}}
    return {'documentId': DOC, 'title': 'Services', 'revisionId': revision, 'tabs': [
        {'tabProperties': {'title': 'Overview'}, 'documentTab': {'body': {'content': [paragraph(text)]}}},
        {'tabProperties': {'title': 'Plans'}, 'documentTab': {'body': {'content': [table]}}}
    ]}

class GoogleDocsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.store = Store(self.tmp.name)

    def test_selection_and_multitab_extraction(self):
        with patch('proofpage.google_docs.fetch_document', side_effect=AssertionError('Selection must not fetch')):
            google_docs.select(self.store, 'https://docs.google.com/document/d/' + DOC + '/edit', 3600, owner_permission=True)
        for invalid in (False, 'true', 1, None):
            with self.assertRaises(ValueError): google_docs.select(self.store, DOC, owner_permission=invalid)
        result = google_docs.extract(document('We build websites.'))
        self.assertIn('We build websites.', result)
        self.assertIn('Monthly plans.', result)
        for value in ('https://evil.example/' + DOC, 'x', 'file:///private/doc'):
            with self.assertRaises(ValueError): google_docs.document_id(value)
        with self.assertRaises(ValueError): google_docs.select(self.store, DOC, True, owner_permission=True)

    def test_sync_dedup_drift_and_failure_preserves(self):
        google_docs.select(self.store, DOC, owner_permission=True)
        with patch('proofpage.google_docs.fetch_document', return_value=document('We build websites.')):
            first = google_docs.sync(self.store, DOC)
            self.assertEqual(google_docs.sync(self.store, DOC)['revision_id'], first['revision_id'])
        from proofpage import training
        with self.assertRaisesRegex(ValueError, 'personal context'):
            training.create_candidate(self.store, first['revision_id'], 'sft', {'messages': [{'role':'user','content':'What do we do?'},{'role':'assistant','content':'We build websites.'}]}, 'We build websites.')
        profile = business.create(self.store, 'Agency')['id']
        business.attach(self.store, profile, first['revision_id'], 'business')
        fact = business.draft(self.store, profile)['facts'][0]
        business.review(self.store, fact['id'], fact['text'], 'approved', True, True)
        with patch('proofpage.google_docs.fetch_document', return_value=document('We build applications.', 'r2')):
            second = google_docs.sync(self.store, DOC)
        self.assertNotEqual(first['revision_id'], second['revision_id'])
        with self.assertRaises(ValueError): business.approved(self.store, profile)
        with patch('proofpage.google_docs.fetch_document', side_effect=RuntimeError('private token')):
            with self.assertRaisesRegex(ValueError, 'Existing evidence was retained'): google_docs.sync(self.store, DOC)
        self.assertNotIn('private token', str(self.store.rows('SELECT * FROM google_documents')))
        self.assertEqual(self.store.rows('SELECT current_revision FROM items')[0]['current_revision'], second['revision_id'])

    def test_unselected_and_wrong_document(self):
        with self.assertRaises(ValueError): google_docs.sync(self.store, DOC)
        google_docs.select(self.store, DOC, owner_permission=True)
        with patch('proofpage.google_docs.fetch_document', return_value={'documentId': 'different'}):
            with self.assertRaises(ValueError): google_docs.sync(self.store, DOC)
        self.assertEqual(self.store.rows('SELECT * FROM items'), [])
