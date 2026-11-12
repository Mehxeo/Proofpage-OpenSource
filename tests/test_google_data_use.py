"""Google API raw and derived text must never cross a model/assistant boundary."""
import json
import os
import tempfile
import unittest
from unittest.mock import Mock, patch

from proofpage import agent, business, claims, evidence, evidence_runs, history, mcp, models, service, training
from proofpage.core import Store
from proofpage.data_use import Policy


class GoogleDataUseTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = Store(self.tmp.name)
        self.google = self.store.source('Private business plan', 'import', 'google-doc:fictional-document')
        self.metadata = {'adapter': 'google_docs', 'data_use': 'personal_context_only',
                         'source_url': 'https://docs.google.com/document/d/fictional-document'}
        self.secret = 'Northline plans a private launch in December.'
        self.rid = self.save(self.google, self.secret, self.metadata)
        self.public = self.store.source('Public site', 'import', 'fixture:public')
        self.public_rid = self.save(self.public, 'Northline builds public websites.')

    def save(self, source, text, metadata=None, external='page'):
        self.store.save(source['id'], external, 'text', source['name'], text, text, metadata)
        return self.store.rows('SELECT current_revision FROM items WHERE source_id=? AND external_id=?', (source['id'], external))[0]['current_revision']

    def profile(self, rid):
        profile = business.create(self.store, 'Reviewed business')['id']
        business.attach(self.store, profile, rid, 'business')
        fact = business.draft(self.store, profile)['facts'][0]
        business.review(self.store, fact['id'], fact['text'], 'approved', True, True)
        return profile

    def test_docs_are_readable_locally_but_all_direct_mcp_reads_are_blocked(self):
        item_id = self.store.revision(self.rid)['item_id']
        self.assertEqual(self.store.item(item_id)['text'], self.secret)
        self.assertTrue(self.store.item(item_id)['local_only'])
        cases = {
            'proofpage_get_item': {'item_id': item_id},
            'proofpage_get_evidence': {'item_id': item_id},
            'proofpage_list_changes': {'item_id': item_id},
            'proofpage_get_rights': {'item_id': item_id},
            'proofpage_get_receipt': {'revision_id': self.rid},
            'proofpage_get_source_access': {'source_id': self.google['id']},
            'proofpage_ensure_fresh': {'source_id': self.google['id'], 'max_age_seconds': 86400},
            'proofpage_diff_revisions': {'from_revision_id': self.public_rid, 'to_revision_id': self.rid},
        }
        for name, args in cases.items():
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, 'personal context'):
                mcp.call(self.store, name, args)
        for name, args in [('proofpage_search', {'query': 'Northline'}), ('proofpage_get_context', {'query': 'Northline'}), ('proofpage_list_sources', {})]:
            result = json.dumps(mcp.call(self.store, name, args))
            self.assertNotIn(self.secret, result)
            self.assertNotIn(self.google['name'], result)
            self.assertIn('Public site', result)
        self.assertEqual(len(agent.context(self.store, 'Northline')['excerpts']), 1)

    def test_legacy_traces_and_derivative_provenance_inherit_the_boundary(self):
        trace = self.save(self.public, self.secret, {'observed_events': [
            {'type': 'tool_result', 'result': {'revision_id': self.rid, 'text': self.secret}}]}, 'legacy-trace')
        derivative = self.save(self.public, 'A rewritten private summary.', {'derived_from': [trace]}, 'summary')
        policy = Policy(self.store)
        self.assertTrue(policy.contains(derivative))
        self.assertNotIn(trace, json.dumps(mcp.call(self.store, 'proofpage_search', {'query': 'Northline'})))
        for rid in (self.rid, trace, derivative):
            with self.subTest(rid=rid), self.assertRaisesRegex(ValueError, 'personal context'):
                training.create_candidate(self.store, rid, 'sft', {}, 'unused')
            with self.assertRaisesRegex(ValueError, 'personal context'):
                self.store.review(rid, True, True)

    def test_google_data_never_uses_a_hosted_or_loopback_gateway(self):
        recipe = models.create_recipe(self.store, 'Launch', {'launch': 'Launch plans'})
        second = self.save(self.google, 'Northline plans a private launch in January.', self.metadata)
        for url in ('https://models.example/v1', 'http://127.0.0.1:11434/v1'):
            with self.subTest(url=url), patch.dict(os.environ, {'PROOFPAGE_MODEL_URL': url, 'PROOFPAGE_MODEL_NAME': 'gateway'}), patch('proofpage.offline_models.configuration', return_value={'configured': False, 'detail': 'Configure an offline model.'}), patch('proofpage.models.complete_json') as remote:
                for action in (lambda: models.assist(self.store, self.rid, 'extraction', recipe['id']),
                               lambda: history.model_summary(self.store, self.public_rid, self.rid),
                               lambda: history.model_summary(self.store, second, self.public_rid)):
                    with self.assertRaisesRegex(ValueError, 'offline model'):
                        action()
                remote.assert_not_called()

    def test_google_extraction_uses_offline_engine_and_retains_revision_origin(self):
        recipe = models.create_recipe(self.store, 'Launch', {'launch': 'Launch plans'})
        with patch('proofpage.offline_models.configuration', return_value={'configured': True, 'model': 'local.gguf'}), patch('proofpage.offline_models.complete_json', return_value={'fields': {'launch': {'value': 'December', 'quote': self.secret}}}) as offline, patch('proofpage.models.complete_json') as remote:
            result = models.assist(self.store, self.rid, 'extraction', recipe['id'])
            offline.assert_called_once()
            remote.assert_not_called()
        self.assertEqual(result['revision_id'], self.rid)
        self.assertEqual(result['state'], 'unreviewed')
        with self.assertRaisesRegex(ValueError, 'personal context'):
            mcp.call(self.store, 'proofpage_submit_extraction', {'recipe_id': recipe['id'], 'revision_id': self.rid, 'fields': {}})

    def test_local_review_is_retained_but_context_packs_and_profiles_do_not_leak(self):
        private = self.profile(self.rid)
        public = self.profile(self.public_rid)
        self.assertEqual(len(business.approved(self.store, private)['facts']), 1)
        self.assertFalse(business.get(self.store, private)['facts'][0]['shareable'])
        with self.assertRaisesRegex(ValueError, 'personal context'):
            business.export_pack(self.store, private)
        with self.assertRaisesRegex(ValueError, 'personal context'):
            mcp.call(self.store, 'proofpage_business_context', {'profile_id': private})
        self.assertEqual([p['id'] for p in mcp.call(self.store, 'proofpage_business_profiles', {})], [public])
        self.assertTrue(business.export_pack(self.store, public).startswith(b'PK'))

    def test_legacy_evidence_runs_stay_locally_readable_but_not_exportable(self):
        with patch.object(Policy, 'require_shareable', side_effect=lambda value: value):
            manifest = evidence.record(self.store, [self.rid], [{'output_id': 'old-answer', 'revision_id': self.rid, 'start': 0, 'end': len(self.secret), 'quote': self.secret}])
        run = evidence_runs.save(self.store, manifest)['run_id']
        self.assertIn(self.secret, json.dumps(evidence_runs.replay_context(self.store, run)))
        self.assertEqual(mcp.call(self.store, 'proofpage_list_evidence_runs', {}), [])
        for name in ('proofpage_replay_context', 'proofpage_check_evidence_run'):
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, 'personal context'):
                mcp.call(self.store, name, {'run_id': run})
        with self.assertRaisesRegex(ValueError, 'personal context'):
            service.get(self.store, '/api/evidence-runs/' + run + '/export', {})
        with self.assertRaisesRegex(ValueError, 'personal context'):
            evidence.record(self.store, [self.rid])
        with self.assertRaisesRegex(ValueError, 'personal context'):
            evidence.write(manifest, self.tmp.name + '/blocked.json')

    def test_saved_claim_results_cannot_leave_through_mcp_or_report_exports(self):
        report = claims.create(self.store, [{'url': 'https://example.org/page', 'quote': 'a claim'}])
        result = {'revision_id': self.rid, 'start': 0, 'end': len(self.secret), 'excerpt': self.secret, 'status': 'verified'}
        with self.store.db() as db:
            db.execute('UPDATE claim_items SET result=? WHERE job_id=?', (json.dumps(result), report['id']))
        with self.assertRaisesRegex(ValueError, 'personal context'):
            mcp.call(self.store, 'proofpage_get_quote_check', {'job_id': report['id']})
        with self.assertRaisesRegex(ValueError, 'personal context'):
            claims.export(self.store, report['id'], 'json')
        with patch('proofpage.offline_models.configuration', return_value={'configured': False, 'detail': 'Configure an offline model.'}), patch('proofpage.models.complete_json') as remote:
            with self.assertRaisesRegex(ValueError, 'offline model'):
                claims.model_review(self.store, report['id'], 0)
            remote.assert_not_called()
