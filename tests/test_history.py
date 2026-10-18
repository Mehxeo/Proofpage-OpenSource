import json
import os
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from unittest.mock import patch

from proofpage import history, mcp, service
from proofpage.core import Store


def pricing(price, extra=''):
    return f'<title>Pricing</title><main><p>The Pro plan costs ${price} per month.</p>{extra}<p>' + 'Details about the plan and its features. ' * 8 + '</p></main>'


class DiffTests(unittest.TestCase):
    def test_blocks_words_numbers_and_reconstruction(self):
        old = 'Pricing\nThe Pro plan costs $20 per month.\nCancel anytime.\nTerms apply.'
        new = 'Pricing\nThe Pro plan costs $25 per month.\nTerms apply.\nNew: team support.'
        result = history.diff(old, new)
        self.assertEqual([block['op'] for block in result['blocks']], ['equal', 'replace', 'equal', 'insert'])
        replaced = result['blocks'][1]
        self.assertEqual(''.join(text for op, text in replaced['words'] if op != 'delete'), replaced['new'])
        self.assertEqual(''.join(text for op, text in replaced['words'] if op != 'insert'), replaced['old'])
        self.assertEqual(result['stats']['numbers_changed'], [{'old': '$20', 'new': '$25'}])
        self.assertEqual((result['stats']['lines_added'], result['stats']['lines_changed']), (1, 2))
        self.assertIn('$20 → $25', result['summary'])
        self.assertTrue(history.diff(old, old)['stats']['identical'])
        self.assertEqual(history.diff('', 'Hello world')['stats']['words_added'], 2)

    def test_large_changed_block_falls_back_to_whole_replacement(self):
        old, new = 'word ' * 7000, 'other ' * 7000
        block = history.diff(old, new)['blocks'][0]
        self.assertEqual([op for op, _ in block['words']], ['delete', 'insert'])


class ChangeEventTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = Store(self.temp.name)
        with patch('proofpage.core.validate_url'):
            self.source = self.store.source('Pricing', 'web', 'https://example.com/pricing')

    def tearDown(self):
        self.temp.cleanup()

    def collect(self, status=200, body=None):
        with self.store.db() as db:
            db.execute('DELETE FROM cooldowns')
        page = (status, {'content-type': 'text/html'}, body if body is not None else pricing(20), self.source['location'])
        with patch('proofpage.core.fetch', side_effect=[(404, {}, '', ''), page, (404, {}, '', '')]):
            return self.store.collect(self.source['id'])

    def kinds(self):
        return [row['kind'] for row in history.inbox(self.store)][::-1]

    def test_first_challenge_creates_attention_and_pauses_schedule(self):
        with self.store.db() as db:
            db.execute('UPDATE sources SET interval_seconds=300 WHERE id=?', (self.source['id'],))
        result = self.collect(body='<title>CAPTCHA</title><p>Please complete the captcha</p>')
        self.assertEqual(result['state'], 'challenge_required')
        self.assertTrue(result['attention']['required'])
        self.assertIn('approval', result['attention']['agent_action'])
        self.assertIn('user', result['attention']['training_action'])
        self.assertEqual(self.store.rows('SELECT interval_seconds FROM sources')[0]['interval_seconds'], 0)
        entries = history.inbox(self.store)
        self.assertEqual(len(entries), 1)
        self.assertTrue(entries[0]['detail']['needs_attention'])
        self.collect(body='<title>CAPTCHA</title><p>Please complete the captcha</p>')
        self.assertEqual(len(history.inbox(self.store)), 1)

    def test_content_change_events_and_reverts(self):
        self.collect()
        self.assertEqual(self.kinds(), [])  # the first capture is not a change
        self.collect(body=pricing(20))
        self.assertEqual(self.kinds(), [])  # unchanged content
        self.collect(body=pricing(25))
        change = history.inbox(self.store)[0]
        self.assertEqual(change['kind'], 'content_changed')
        self.assertEqual(change['detail']['stats']['numbers_changed'], [{'old': '$20', 'new': '$25'}])
        self.assertEqual(change['subject_id'], self.store.search()[0]['id'])
        self.collect(body=pricing(20))  # back to the first version
        self.assertEqual(self.kinds(), ['content_changed', 'content_changed'])
        self.assertEqual(len(self.store.rows('SELECT * FROM revisions')), 2)

    def test_imports_do_not_create_change_events(self):
        source = self.store.source('Notes', 'import', 'import:notes')
        self.store.save(source['id'], 'note', 'document', 'Note', 'First text', 'raw')
        self.store.save(source['id'], 'note', 'document', 'Note', 'Second text', 'raw')
        self.assertEqual(self.kinds(), [])

    def test_link_rot_and_collection_problems_are_recorded_once(self):
        self.collect()
        self.collect(404, 'Not found')
        self.collect(404, 'Not found')
        self.assertEqual(self.kinds(), ['link_rot'])
        rot = history.inbox(self.store)[0]['detail']
        self.assertEqual((rot['status'], rot['url']), (404, self.source['location']))
        self.collect()
        self.collect(403, 'Denied')
        self.collect(403, 'Denied')
        self.assertEqual(self.kinds(), ['link_rot', 'collection_problem'])
        self.assertEqual(history.inbox(self.store, 'collection_problem')[0]['detail']['state'], 'access_denied')

    def test_failed_fetches_do_not_fake_rights_drift(self):
        self.collect(body=pricing(20, '<meta name="robots" content="noai">'))
        self.assertEqual(self.store.search()[0]['rights']['train'], 'reserved')
        result = self.collect(403, 'Denied')
        self.assertFalse(result['rights']['recorded'])
        self.assertEqual(self.kinds(), ['collection_problem'])
        self.assertEqual(len(self.store.rows('SELECT * FROM rights_observations')), 1)
        self.assertEqual(len(self.store.rows('SELECT * FROM captures')), 2)

    def test_model_summary_sends_only_changes_and_is_unreviewed(self):
        self.collect()
        self.collect(body=pricing(25))
        newest, oldest = history.timeline(self.store, self.store.search()[0]['id'])['versions']
        received, replies = [], [{'summary': 'The monthly price rose from $20 to $25.', 'notable': ['Pro plan price: $20 → $25']}, {'notable': 'not a list'}]

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                received.append(json.loads(self.rfile.read(int(self.headers['Content-Length']))))
                body = json.dumps({'choices': [{'message': {'content': json.dumps(replies[len(received) - 1])}}]}).encode()
                self.send_response(200)
                self.end_headers()
                self.wfile.write(body)

        with self.assertRaisesRegex(ValueError, 'PROOFPAGE_MODEL_URL'), patch.dict(os.environ, {'PROOFPAGE_MODEL_URL': '', 'PROOFPAGE_MODEL_NAME': ''}):
            history.model_summary(self.store, oldest['revision_id'], newest['revision_id'])
        server = HTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with patch.dict(os.environ, {'PROOFPAGE_MODEL_URL': f'http://127.0.0.1:{server.server_port}/v1', 'PROOFPAGE_MODEL_NAME': 'fixture-model'}):
                timeline = service.get(self.store, f"/api/items/{self.store.search()[0]['id']}/timeline", {})[1]
                self.assertEqual(timeline['model'], {'configured': True, 'model': 'fixture-model', 'detail': timeline['model']['detail']})
                self.assertNotIn('url', timeline['model'])
                with self.assertRaisesRegex(ValueError, 'same text'):
                    history.model_summary(self.store, newest['revision_id'], newest['revision_id'])
                result = service.post(self.store, '/api/change-summary', {'from_revision': oldest['revision_id'], 'to_revision': newest['revision_id']})[1]
                self.assertEqual((result['status'], result['model'], result['notable']), ('unreviewed', 'fixture-model', ['Pro plan price: $20 → $25']))
                prompt = received[0]['messages']
                self.assertIn('untrusted', prompt[0]['content'])
                self.assertIn('$25', prompt[1]['content'])
                self.assertNotIn('Details about the plan', prompt[1]['content'])  # unchanged lines are not sent
                with self.assertRaisesRegex(ValueError, 'unsupported summary'):
                    history.model_summary(self.store, oldest['revision_id'], newest['revision_id'])
                with self.store.db() as db:
                    db.execute('UPDATE revisions SET text=text||? WHERE id=?', ('\npassword: hunter2hunter2', newest['revision_id']))
                with self.assertRaisesRegex(ValueError, 'credentials'):
                    history.model_summary(self.store, oldest['revision_id'], newest['revision_id'])
                self.assertEqual(len(received), 2)  # the credential check stops the request before sending
        finally:
            server.shutdown()
            server.server_close()
            thread.join()
        events = self.store.rows("SELECT state FROM model_events WHERE purpose='change_summary' ORDER BY created_at")
        self.assertEqual([e['state'] for e in events], ['unreviewed', 'failed'])

    def test_inbox_timeline_diff_apis_and_mcp_tools(self):
        self.collect()
        self.collect(body=pricing(25, '<p>New: annual billing.</p>'))
        self.collect(404, 'Not found')
        state = service.get(self.store, '/api/state', {})[1]
        self.assertEqual(state['unread'], 2)
        inbox = service.get(self.store, '/api/inbox', {'kind': ['link_rot']})[1]
        self.assertEqual(([e['kind'] for e in inbox['events']], inbox['unread']['total']), (['link_rot'], 2))
        with self.assertRaisesRegex(ValueError, 'Unknown change type'):
            service.get(self.store, '/api/inbox', {'kind': ['nonsense']})
        item = self.store.search()[0]
        timeline = service.get(self.store, f"/api/items/{item['id']}/timeline", {})[1]
        newest, oldest = timeline['versions']
        self.assertTrue(newest['current'])
        self.assertEqual(newest['previous_revision'], oldest['revision_id'])
        self.assertEqual({row['kind'] for row in timeline['changes']}, {'content_changed', 'link_rot'})
        comparison = service.get(self.store, '/api/diff', {'from': [oldest['revision_id']], 'to': [newest['revision_id']]})[1]
        self.assertTrue(comparison['same_record'])
        self.assertEqual(comparison['stats']['numbers_changed'], [{'old': '$20', 'new': '$25'}])
        self.assertTrue(any('New: annual billing.' in block.get('new', '') for block in comparison['blocks']))
        compact = mcp.call(self.store, 'proofpage_diff_revisions', {'from_revision_id': oldest['revision_id'], 'to_revision_id': newest['revision_id']})
        self.assertNotIn('equal', [change['op'] for change in compact['changes']])
        self.assertIn('untrusted', compact['instruction'])
        since = mcp.call(self.store, 'proofpage_list_changes_since', {'since': '2000-01-01T00:00:00Z'})
        self.assertEqual([c['kind'] for c in since['changes']], ['link_rot', 'content_changed'])
        self.assertEqual(mcp.call(self.store, 'proofpage_list_changes_since', {'since': '2999-01-01'})['changes'], [])
        with self.assertRaisesRegex(ValueError, 'ISO 8601'):
            mcp.call(self.store, 'proofpage_list_changes_since', {'since': 'yesterday'})
        first = inbox['events'][0]['id']
        self.assertEqual(service.post(self.store, '/api/inbox-seen', {'ids': [first]})[1]['total'], 1)
        self.assertEqual(service.post(self.store, '/api/inbox-seen', {'all': True})[1]['total'], 0)
        with self.assertRaisesRegex(ValueError, 'list of change IDs'):
            history.mark_seen(self.store, 'not-a-list')


if __name__ == '__main__':
    unittest.main()
