import tempfile
import json
import unittest
from unittest.mock import MagicMock, Mock, patch
from proofpage import google_docs, business
from proofpage.core import Store, digest, now

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

    def test_safe_sync_error_is_actionable_and_previous_revision_is_retained(self):
        google_docs.select(self.store, DOC, owner_permission=True)
        with patch('proofpage.google_docs.fetch_document', return_value=document('Original evidence.')):
            revision = google_docs.sync(self.store, DOC)['revision_id']
        error = google_docs.GoogleDocsError('Google authorization expired. Reconnect Google, then retry this document.')
        with patch('proofpage.google_docs.fetch_document', side_effect=error):
            with self.assertRaisesRegex(google_docs.GoogleDocsError, 'Reconnect Google.*Existing evidence was retained'):
                google_docs.sync(self.store, DOC)
        row = self.store.rows('SELECT state,detail FROM google_documents')[0]
        self.assertEqual(row['state'], 'error')
        self.assertIn('Reconnect Google', row['detail'])
        self.assertEqual(self.store.rows('SELECT current_revision FROM items')[0]['current_revision'], revision)

    def test_google_http_failures_show_safe_recovery_without_updating_tokens(self):
        google_docs.select(self.store, DOC, owner_permission=True)
        for status, message in [(401, 'Reconnect Google'), (403, 'Check the link'),
                                (404, 'Check the link'), (429, 'Wait a few minutes'),
                                (503, 'Retry later')]:
            backend = Mock()
            backend.get_password.return_value = '{"refresh_token":"private-fixture-token"}'
            session = MagicMock()
            session.get.return_value.__enter__.return_value.status_code = status
            with patch.object(google_docs, 'vault', return_value=backend), patch('google.oauth2.credentials.Credentials.from_authorized_user_info'), patch('google.auth.transport.requests.AuthorizedSession') as auth:
                auth.return_value.__enter__.return_value = session
                with self.assertRaisesRegex(google_docs.GoogleDocsError, message):
                    google_docs.sync(self.store, DOC)
            backend.set_password.assert_not_called()
            detail = self.store.rows('SELECT detail FROM google_documents')[0]['detail']
            self.assertIn(message, detail)
            self.assertNotIn('private-fixture-token', detail)
            self.assertEqual(self.store.rows('SELECT * FROM items'), [])

    def test_google_snapshots_stay_out_of_corpora_and_model_training(self):
        google_docs.select(self.store, DOC, owner_permission=True)
        with patch('proofpage.google_docs.fetch_document', return_value=document('We build websites.')):
            revision_id = google_docs.sync(self.store, DOC)['revision_id']
        with self.assertRaisesRegex(ValueError, 'personal context'):
            self.store.review(revision_id, True, True)
        from proofpage import models
        with patch('proofpage.models.configuration', return_value={'configured': True}), patch('proofpage.models.complete_json') as complete:
            with self.assertRaisesRegex(ValueError, 'personal context'):
                models.assist(self.store, revision_id, 'sft')
            complete.assert_not_called()

        # Old databases may already contain approvals and frozen corpus rows.
        payload = 'legacy Google corpus\n'
        with self.store.db() as db:
            db.execute('INSERT INTO reviews(revision_id,allowed,approved) VALUES(?,1,1)', (revision_id,))
            db.execute('INSERT INTO datasets VALUES(?,?,?,?,?,?)', ('legacy-google', 'Legacy', now(), payload, json.dumps([revision_id]), digest(payload)))
        with self.assertRaisesRegex(ValueError, 'personal context'):
            self.store.freeze('Google corpus')
        with self.assertRaisesRegex(ValueError, 'personal context'):
            self.store.export('legacy-google')

        profile_id = business.create(self.store, 'Context only')['id']
        business.attach(self.store, profile_id, revision_id, 'business')
        result = business.draft(self.store, profile_id)
        self.assertTrue(result['facts'])
        self.assertTrue(all(not fact['training_allowed'] for fact in result['facts']))
        fact = result['facts'][0]
        business.review(self.store, fact['id'], fact['text'], 'approved', True, True)
        self.assertEqual(len(business.approved(self.store, profile_id)['facts']), 1)
