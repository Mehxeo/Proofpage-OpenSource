import io
import json
import tempfile
import unittest
import zipfile
from unittest.mock import patch
from proofpage import business, mcp, service
from proofpage.core import Store

class BusinessTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.store = Store(self.tmp.name)
        self.source = self.store.source('Services', 'import', 'fixture:services')
        self.store.save(self.source['id'], 'services', 'text', 'Services', 'We build websites for local shops.', 'original')
        self.rid = self.store.rows('SELECT id FROM revisions')[0]['id']
        self.profile = business.create(self.store, 'Agency')['id']
        business.attach(self.store, self.profile, self.rid, 'business')

    def test_review_gate_portable_pack_and_reopen(self):
        profile = business.draft(self.store, self.profile)
        fact = profile['facts'][0]
        with self.assertRaises(ValueError): business.export_pack(self.store, self.profile)
        with self.assertRaises(ValueError): business.review(self.store, fact['id'], fact['text'], 'approved', 'yes', True)
        business.review(self.store, fact['id'], fact['text'], 'approved', True, True)
        reopened = Store(self.tmp.name)
        context = mcp.call(reopened, 'proofpage_business_context', {'profile_id': self.profile})
        self.assertEqual(context['facts'][0]['quote'], 'We build websites for local shops.')
        with zipfile.ZipFile(io.BytesIO(business.export_pack(reopened, self.profile))) as pack:
            self.assertEqual(set(pack.namelist()), {'BUSINESS.md', 'context.json', 'INSTRUCTIONS.md', 'README.md'})
            self.assertEqual(json.loads(pack.read('context.json'))['facts'][0]['revision_id'], self.rid)

    def test_role_change_revokes_approval_and_drafting_is_idempotent(self):
        fact = business.draft(self.store, self.profile)['facts'][0]
        business.review(self.store, fact['id'], fact['text'], 'approved', True, True)
        self.assertEqual(business.draft(self.store, self.profile)['added'], 0)
        business.attach(self.store, self.profile, self.rid, 'reference')
        fact = business.get(self.store, self.profile)['facts'][0]
        self.assertEqual((fact['section'], fact['status']), ('Reference material', 'draft'))
        with self.assertRaises(ValueError): business.approved(self.store, self.profile)

    def test_changed_sources_block_export(self):
        fact = business.draft(self.store, self.profile)['facts'][0]
        business.review(self.store, fact['id'], fact['text'], 'approved', True, True)
        self.store.save(self.source['id'], 'services', 'text', 'Services', 'We now build software for hospitals.', 'new')
        self.assertTrue(business.get(self.store, self.profile)['facts'][0]['stale'])
        with self.assertRaises(ValueError): business.export_pack(self.store, self.profile)

    def test_credentials_block_approval(self):
        fact = business.draft(self.store, self.profile)['facts'][0]
        with self.assertRaises(ValueError): business.review(self.store, fact['id'], 'password=supersecret123', 'approved', True, True)

    def test_bookmark_selection_no_network_or_inference(self):
        html = '<a href="https://example.com/pricing">Competitor</a><a href="javascript:alert(1)">Bad</a><a href="https://u:p@example.com">Credential</a>'
        with patch('socket.socket', side_effect=AssertionError('No network')):
            entries = business.bookmark_preview(html)
            self.assertEqual(len(entries), 1)
            business.import_bookmarks(self.store, html, [0])
        rid = self.store.rows("SELECT current_revision FROM items WHERE kind='bookmark'")[0]['current_revision']
        with self.assertRaises(ValueError): business.attach(self.store, self.profile, rid, 'business')
        with self.assertRaises(ValueError): business.import_bookmarks(self.store, html, [True])

    def test_api_and_reference_role(self):
        business.attach(self.store, self.profile, self.rid, 'customer')
        result = service.post(self.store, '/api/business-draft', {'profile_id': self.profile})[1]
        self.assertEqual(result['facts'][0]['section'], 'Customer context')
        self.assertEqual(service.get(self.store, '/api/business', {})[1][0]['id'], self.profile)

    def test_training_stays_draft(self):
        fact = business.draft(self.store, self.profile)['facts'][0]
        with self.assertRaises(ValueError): business.training_draft(self.store, fact['id'], 'What do we do?')
        business.review(self.store, fact['id'], fact['text'], 'approved', True, True)
        result = business.training_draft(self.store, fact['id'], 'What do we do?')
        self.assertEqual(result['status'], 'draft')
        self.assertEqual(self.store.rows('SELECT * FROM datasets'), [])
