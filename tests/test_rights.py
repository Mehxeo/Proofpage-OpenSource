import io
import json
import tempfile
import unittest
import zipfile
from types import SimpleNamespace
from unittest.mock import patch

from proofpage import compliance, mcp, rights, service, training
from proofpage.core import Store, tls_details

ARTICLE = '<html><head><title>Article</title></head><body><p>' + 'Useful evidence about solar panels. ' * 20 + '</p></body></html>'
LOGIN = '<title>Login</title><input type="password">'


def page(html=ARTICLE, headers=None):
    return (200, {'content-type': 'text/html', **(headers or {})}, html, '')


class SignalTests(unittest.TestCase):
    def observe(self, url='https://example.org/blog/post', headers=None, html='', robots=None, tdmrep=None):
        return rights.observe(url, headers or {}, html, robots, 200 if robots is not None else 404, tdmrep or {'status': 'missing'})

    def test_no_signal_is_unknown_not_permission(self):
        result = self.observe(html='<p>Plain page</p>')
        self.assertEqual(result['verdict'], {'train': 'unknown', 'ai_use': 'unknown', 'search': 'unknown'})
        self.assertIn('Unknown is not permission', result['summary'])
        self.assertEqual(result['checked']['robots.txt'], 'not published')

    def test_content_usage_robots_paths_and_header(self):
        robots = 'User-agent: *\nContent-Usage: train-ai=n\nContent-Usage: /open/ train-ai=y\nAllow: /\n'
        blog = self.observe(robots=robots)
        self.assertEqual(blog['verdict']['train'], 'reserved')
        self.assertEqual(blog['signals'][0]['source'], 'robots.txt line 2')
        self.assertEqual(blog['signals'][0]['raw'], 'Content-Usage: train-ai=n')
        self.assertEqual(self.observe('https://example.org/open/a', robots=robots)['verdict']['train'], 'allowed')
        header = self.observe(headers={'content-usage': 'ai-use=n, search=y'})
        self.assertEqual((header['verdict']['ai_use'], header['verdict']['search']), ('reserved', 'allowed'))

    def test_content_signal_and_rsl(self):
        robots = 'User-Agent: *\nContent-Signal: search=yes, ai-input=no, ai-train=no\nAllow: /\nLicense: https://example.org/rsl.xml\n'
        result = self.observe(robots=robots)
        self.assertEqual(result['verdict'], {'train': 'reserved', 'ai_use': 'reserved', 'search': 'allowed'})
        self.assertIn('rsl', {signal['family'] for signal in result['signals']})

    def test_named_ai_crawlers_only_when_explicit(self):
        wildcard = self.observe(robots='User-agent: *\nDisallow: /private/\n')
        self.assertFalse([s for s in wildcard['signals'] if s['family'] == 'ai_crawler'])
        named = self.observe(robots='User-agent: *\nAllow: /\n\nUser-agent: GPTBot\nUser-agent: PerplexityBot\nDisallow: /\n')
        labels = {s['label']: s['effects'] for s in named['signals'] if s['family'] == 'ai_crawler'}
        self.assertEqual(labels, {'GPTBot blocked': {'train': 'reserved'}, 'PerplexityBot blocked': {'search': 'reserved'}})

    def test_tdmrep_header_meta_and_first_matching_rule(self):
        self.assertEqual(self.observe(headers={'tdm-reservation': '1'})['verdict']['train'], 'reserved')
        self.assertEqual(self.observe(html='<meta name="tdm-reservation" content="0"><p>x</p>')['verdict']['train'], 'allowed')
        rules = [{'location': '/blog/*', 'tdm-reservation': 0}, {'location': '/*', 'tdm-reservation': 1}]
        result = self.observe(tdmrep={'status': 'read', 'data': rules})
        self.assertEqual(result['verdict']['train'], 'allowed')
        self.assertEqual(result['signals'][0]['source'], '/.well-known/tdmrep.json rule 1')
        self.assertEqual(self.observe(tdmrep={'status': 'invalid'})['checked']['/.well-known/tdmrep.json'], 'invalid JSON')

    def test_noai_and_licenses(self):
        self.assertEqual(self.observe(headers={'x-robots-tag': 'noindex, noai'})['verdict']['train'], 'reserved')
        self.assertEqual(self.observe(html='<meta name="robots" content="noai"><p>x</p>')['verdict']['train'], 'reserved')
        cc0 = self.observe(html='<script type="application/ld+json">{"license": "https://creativecommons.org/publicdomain/zero/1.0/"}</script><p>x</p>')
        self.assertEqual((cc0['verdict']['train'], cc0['verdict']['search']), ('allowed', 'unknown'))
        nc = self.observe(html='<a rel="license" href="https://creativecommons.org/licenses/by-nc-sa/4.0/">CC</a>')
        self.assertEqual(nc['verdict']['train'], 'conditional')
        self.assertIn('non-commercial', nc['signals'][0]['note'])

    def test_reservation_wins_over_permission(self):
        result = self.observe(headers={'tdm-reservation': '1'}, html='<link rel="license" href="https://creativecommons.org/publicdomain/zero/1.0/"><p>x</p>')
        self.assertEqual(result['verdict']['train'], 'reserved')

    def test_tls_details_fingerprint(self):
        sock = SimpleNamespace(getpeercert=lambda binary_form=False: b'certificate' if binary_form else {'issuer': ((('commonName', 'Fixture CA'),),), 'notAfter': 'Jan 1 2030'},
                               version=lambda: 'TLSv1.3', cipher=lambda: ('TLS_AES_128_GCM_SHA256', 'TLSv1.3', 128))
        details = tls_details(sock)
        self.assertEqual(details['issuer'], 'commonName=Fixture CA')
        self.assertEqual(len(details['cert_sha256']), 64)


class RightsWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = Store(self.temp.name)
        with patch('proofpage.core.validate_url'):
            self.source = self.store.source('Docs', 'web', 'https://example.org/docs')

    def tearDown(self):
        self.temp.cleanup()

    def collect(self, *responses):
        with self.store.db() as db:
            db.execute('DELETE FROM cooldowns')
        with patch('proofpage.core.fetch', side_effect=list(responses)) as fetch:
            result = self.store.collect(self.source['id'])
        return result, fetch

    def test_capture_policy_documents_and_daily_tdmrep(self):
        robots = (200, {}, 'User-agent: *\nContent-Signal: ai-train=no\nAllow: /\n', '')
        result, fetch = self.collect(robots, page(), (404, {}, '', ''))
        self.assertEqual(result['rights']['train'], 'reserved')
        self.assertEqual(fetch.call_args_list[2].args[0], 'https://example.org/.well-known/tdmrep.json')
        capture = self.store.rows('SELECT * FROM captures')[0]
        self.assertEqual((capture['status'], capture['raw_exact']), (200, 0))
        self.assertTrue(self.store.rows('SELECT 1 FROM capture_payloads WHERE sha256=?', (capture['body_sha256'],)))
        self.assertEqual(self.store.rows('SELECT attempts FROM budgets')[0]['attempts'], 2)
        result, fetch = self.collect(robots, page())
        self.assertEqual(fetch.call_count, 2)  # tdmrep.json is read once per site per day
        self.assertEqual(len(self.store.rows("SELECT * FROM policy_documents WHERE kind='robots'")), 1)

    def test_tdmrep_failure_and_login_pages(self):
        result, _ = self.collect((404, {}, '', ''), page())
        self.assertEqual(result['state'], 'available')
        self.assertEqual(self.store.rows("SELECT detail FROM policy_documents WHERE kind='tdmrep'")[0]['detail'], 'unavailable')
        result, _ = self.collect((404, {}, '', ''), page(LOGIN))
        self.assertEqual(result['state'], 'authentication_required')
        login = self.store.rows('SELECT body_sha256 FROM captures ORDER BY requested_at DESC LIMIT 1')[0]
        self.assertFalse(self.store.rows('SELECT 1 FROM capture_payloads WHERE sha256=?', (login['body_sha256'],)))

    def test_review_gate_basis_freeze_and_drift(self):
        reserved = (200, {}, 'User-agent: GPTBot\nDisallow: /\n', '')
        self.collect(reserved, page(), (404, {}, '', ''))
        revision = self.store.search()[0]['current_revision']
        with self.assertRaisesRegex(ValueError, 'reserves AI training'):
            self.store.review(revision, True, True)
        with self.assertRaisesRegex(ValueError, 'Describe the other'):
            self.store.review(revision, True, True, 'other', '')
        self.store.review(revision, True, True, 'licensed', 'Agreement 42')
        self.store.review(revision, True, True)
        self.assertEqual(self.store.rows('SELECT rights_basis FROM reviews')[0]['rights_basis'], 'licensed')
        frozen = self.store.freeze('Licensed corpus')
        self.assertEqual(frozen['rights'], {'reserved_with_basis': 1})
        self.collect((404, {}, '', ''), page())
        self.assertEqual(self.store.rows('SELECT drifted FROM dataset_rights')[0]['drifted'], 1)
        event = json.loads(self.store.rows("SELECT detail FROM inbox WHERE kind='rights_drift'")[0]['detail'])
        self.assertEqual(event['changes']['train'], ['reserved', 'unknown'])
        self.assertEqual(event['datasets'], [frozen['id']])
        info = self.store.item(self.store.search()[0]['id'])['rights']
        self.assertEqual((info['train'], info['drifted']), ('reserved', True))  # the stricter verdict holds
        self.assertTrue(self.store.export(frozen['id']))  # a basis recorded at freeze keeps downloads open
        self.store.review(revision, False, False)
        self.assertIsNone(self.store.rows('SELECT rights_basis FROM reviews')[0]['rights_basis'])

    def test_reservation_after_approval_blocks_freeze(self):
        self.collect((404, {}, '', ''), page(), (404, {}, '', ''))
        revision = self.store.search()[0]['current_revision']
        self.store.review(revision, True, True)
        self.collect((200, {}, 'User-agent: *\nContent-Usage: train-ai=n\n', ''), page())
        with self.assertRaisesRegex(ValueError, 'without a recorded rights basis'):
            self.store.freeze('Blocked')

    def test_new_reservation_blocks_downloads_until_basis(self):
        self.collect((404, {}, '', ''), page(), (404, {}, '', ''))
        item = self.store.search()[0]
        revision = item['current_revision']
        self.store.review(revision, True, True)
        corpus = self.store.freeze('Corpus')
        candidate = training.create_candidate(self.store, revision, 'sft', {'messages': [{'role': 'user', 'content': 'Topic?'}, {'role': 'assistant', 'content': 'Solar panels.'}]}, 'Useful evidence about solar panels.')
        training.review_candidate(self.store, candidate['id'], 'approved')
        bundle = training.freeze_training(self.store, 'Bundle', [candidate['id']], 'sft')
        self.assertTrue(self.store.export(corpus['id']))
        blocked_counts = lambda: {d['id']: d['rights_blocked'] for d in service.get(self.store, '/api/state', {})[1]['datasets']}
        self.assertEqual(blocked_counts(), {corpus['id']: 0, bundle['id']: 0})
        self.collect((200, {}, 'User-agent: GPTBot\nDisallow: /\n', ''), page())
        self.assertEqual(blocked_counts(), {corpus['id']: 1, bundle['id']: 1})
        self.assertEqual(service.get(self.store, '/api/workbench', {})[1]['datasets'][0]['rights_blocked'], 1)
        with self.assertRaisesRegex(ValueError, r'Export blocked: 1 source revision.*\(Article\)'):
            self.store.export(corpus['id'])
        with self.assertRaisesRegex(ValueError, 'Export blocked'):
            training.export_bundle(self.store, bundle['id'])
        with self.store.db() as db:
            db.execute('DELETE FROM dataset_rights')  # datasets frozen before snapshots existed are checked too
        with self.assertRaisesRegex(ValueError, 'Export blocked'):
            self.store.export(corpus['id'])
        self.store.review(revision, True, True, 'licensed', 'Agreement 7')
        self.assertTrue(self.store.export(corpus['id']))
        self.assertTrue(training.export_bundle(self.store, bundle['id']))
        self.assertEqual(blocked_counts(), {corpus['id']: 0, bundle['id']: 0})

    def test_training_bundle_carries_rights_and_documentation(self):
        self.collect((404, {}, '', ''), page(), (404, {}, '', ''))
        revision = self.store.search()[0]['current_revision']
        self.store.review(revision, True, False)
        candidate = training.create_candidate(self.store, revision, 'sft', {'messages': [{'role': 'user', 'content': 'Topic?'}, {'role': 'assistant', 'content': 'Solar panels.'}]}, 'Useful evidence about solar panels.')
        training.review_candidate(self.store, candidate['id'], 'approved')
        dataset = training.freeze_training(self.store, 'Solar', [candidate['id']], 'sft')
        self.assertEqual(dataset['rights'], {'unknown': 1})
        bundle = training.export_bundle(self.store, dataset['id'])
        self.assertEqual(bundle, training.export_bundle(self.store, dataset['id']))
        archive = zipfile.ZipFile(io.BytesIO(bundle))
        self.assertTrue({'rights.jsonl', 'RIGHTS.md', 'TRAINING_CONTENT_SUMMARY.md', 'DATASET_CARD.md', 'croissant.json'} <= set(archive.namelist()))
        self.assertEqual(json.loads(archive.read('rights.jsonl'))['verdict_at_freeze'], 'unknown')
        self.assertEqual(json.loads(archive.read('croissant.json'))['distribution'][0]['sha256'], dataset['hash'])

    def test_compliance_top_domains_and_mcp(self):
        revisions = []
        for index in range(12):
            with patch('proofpage.core.validate_url'):
                source = self.store.source(f'Site {index}', 'web', f'https://site{index}.example/')
            self.store.save(source['id'], 'page', 'document', f'Page {index}', 'word ' * (10 + index * 10), 'raw', {'url': f'https://site{index}.example/'})
            revisions.append(self.store.search()[0]['current_revision'])
        for revision in revisions:
            self.store.review(revision, True, True)
        frozen = self.store.freeze('Twelve sites')
        docs = compliance.build(self.store, frozen['id'])
        crawled = docs['summary']['sources']['crawled']
        self.assertEqual(crawled['domain_count'], 12)
        self.assertEqual([d['domain'] for d in crawled['top_domains_by_size']], ['site11.example', 'site10.example'])
        self.assertIn('| site11.example |', docs['summary_markdown'])
        self.assertEqual(docs['summary']['rights']['verdicts_at_freeze'], {'not_recorded': 12})
        self.assertTrue(docs['dataset_card'].startswith('---\npretty_name: "Twelve sites"'))
        item = self.store.search()[0]
        value = mcp.call(self.store, 'proofpage_get_rights', {'item_id': item['id']})
        self.assertEqual(value['rights']['state'], 'not_recorded')


if __name__ == '__main__':
    unittest.main()
