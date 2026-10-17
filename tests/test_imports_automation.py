import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from proofpage.adapters import parse_entry
from proofpage.backup import backup, restore
from proofpage.core import Store, archive_entries, import_file
from proofpage.imports import create_profile
from proofpage.watch import create_watch, scan_watch


def archive(entries):
    result = io.BytesIO()
    with zipfile.ZipFile(result, 'w') as z:
        for name, content in entries.items():
            z.writestr(name, content)
    return result.getvalue()


def conversation():
    return {'id': 'c1', 'title': 'Two branches', 'create_time': 1234567890, 'current_node': 'b', 'mapping': {
        'root': {'parent': None, 'children': ['a', 'b'], 'message': {'id': 'm1', 'author': {'role': 'user'}, 'content': {'parts': ['Question']}}},
        'a': {'parent': 'root', 'children': [], 'message': {'id': 'm2', 'author': {'role': 'assistant'}, 'content': {'parts': ['First answer']}}},
        'b': {'parent': 'root', 'children': [], 'message': {'id': 'm3', 'author': {'role': 'tool', 'name': 'browser'}, 'content': {'parts': ['Observed tool output']}, 'recipient': 'all'}},
    }}


class ImportAutomationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.store = Store(self.root / 'data')
        self.folder = self.root / 'exports'
        self.folder.mkdir()
        self.profile = create_profile(self.store, 'Personal archive', 'Example', 'personal')

    def tearDown(self):
        self.tmp.cleanup()

    def test_profile_identity_survives_archive_rename_and_separates_accounts(self):
        data = archive({'conversations.json': json.dumps([conversation()])})
        first = import_file(self.store, 'old.zip', data, ['conversations.json'], self.profile['id'])
        again = import_file(self.store, 'new.zip', data, ['conversations.json'], self.profile['id'])
        self.assertEqual((first['added'], again['added']), (1, 0))
        other = create_profile(self.store, 'Work archive', 'Example', 'work')
        work = import_file(self.store, 'old.zip', data, ['conversations.json'], other['id'])
        self.assertEqual(work['added'], 1)
        self.assertNotEqual(first['source_id'], work['source_id'])

    def test_chatgpt_branches_and_tool_role_preserved(self):
        record = parse_entry('conversations.json', json.dumps([conversation()]).encode())[0]
        normalized = record['metadata']['normalized']
        self.assertEqual(record['kind'], 'ai_conversation')
        self.assertEqual(normalized['current_node'], 'b')
        self.assertEqual(normalized['messages'][0]['children'], ['a', 'b'])
        self.assertEqual(normalized['messages'][2]['role'], 'tool')
        self.assertEqual(normalized['messages'][2]['author']['name'], 'browser')
        self.assertEqual(record['source_time'], '1234567890')

    def test_claude_missing_roles_and_attachments_are_not_fabricated(self):
        record = {'uuid': 'c2', 'name': 'Imported conversation', 'chat_messages': [
            {'uuid': 'm1', 'sender': 'human', 'text': 'Question', 'attachments': [{'file_name': 'missing.pdf'}]},
            {'uuid': 'm2', 'content': [{'type': 'text', 'text': 'Unknown speaker'}]},
        ]}
        result = parse_entry('conversations.json', json.dumps([record]).encode())[0]
        messages = result['metadata']['normalized']['messages']
        self.assertEqual(messages[0]['role'], 'human')
        self.assertIsNone(messages[1]['role'])
        self.assertEqual(messages[0]['attachments'], [{'file_name': 'missing.pdf'}])
        self.assertIsNone(messages[1]['parent'])

    def test_linkedin_participants_stay_human(self):
        payload = b'MESSAGE ID,CONVERSATION ID,FROM,TO,CONTENT,DATE,ATTACHMENTS\n1,c1,Alice,Bob,Hello,2020-01-01,https://example.com/file\n'
        row = parse_entry('Messages.csv', payload, 'linkedin')[0]
        self.assertEqual(row['kind'], 'human_message')
        self.assertEqual(row['metadata']['normalized']['sender'], 'Alice')
        self.assertEqual(row['metadata']['normalized']['attachment_references'], 'https://example.com/file')
        self.assertNotIn('assistant', row['text'])

    def test_saved_mapping_preserves_role_without_inferred_ai_kind(self):
        profile = create_profile(self.store, 'Custom app', 'custom', 'one', 'mapping', {'text': 'body', 'id': 'key', 'role': 'speaker'})
        result = import_file(self.store, 'one.json', b'[{"key":1,"body":"Mapped text","speaker":"author"}]', ['one.json'], profile['id'])
        item = self.store.search('Mapped')[0]
        metadata = json.loads(self.store.item(item['id'])['metadata'])
        self.assertEqual(result['added'], 1)
        self.assertEqual(metadata['normalized']['role'], 'author')
        self.assertEqual(item['kind'], 'structured_record')

    def test_watch_settles_resumes_and_revises_changed_file(self):
        watch = create_watch(self.store, self.profile['id'], self.folder, ['notes.md'])
        path = self.folder / 'notes.md'
        path.write_text('Original notes')
        self.assertEqual(scan_watch(self.store, watch['id'], clock=10)['imported'], 0)
        self.assertEqual(scan_watch(self.store, watch['id'], clock=11)['imported'], 0)
        resumed = Store(self.root / 'data')
        self.assertEqual(scan_watch(resumed, watch['id'], clock=13)['imported'], 1)
        self.assertEqual(scan_watch(resumed, watch['id'], clock=20)['imported'], 0)
        path.write_text('Updated notes with new content')
        self.assertEqual(scan_watch(resumed, watch['id'], clock=21)['imported'], 0)
        self.assertEqual(scan_watch(resumed, watch['id'], clock=24)['imported'], 1)
        self.assertEqual(len(self.store.search()), 1)
        self.assertEqual(len(self.store.rows('SELECT * FROM revisions')), 2)

    def test_bad_file_does_not_block_other_files_or_repeat_forever(self):
        watch = create_watch(self.store, self.profile['id'], self.folder, ['bad.json', 'good.md'])
        (self.folder / 'bad.json').write_text('{broken')
        (self.folder / 'good.md').write_text('Good independent evidence')
        scan_watch(self.store, watch['id'], clock=10)
        result = scan_watch(self.store, watch['id'], clock=13)
        self.assertEqual(result['imported'], 1)
        self.assertEqual(result['state'], 'attention')
        runs = len(self.store.rows('SELECT * FROM runs'))
        scan_watch(self.store, watch['id'], clock=20)
        self.assertEqual(len(self.store.rows('SELECT * FROM runs')), runs)

    def test_missing_category_is_reported(self):
        watch = create_watch(self.store, self.profile['id'], self.folder, ['one.md', 'missing.csv'])
        (self.folder / 'archive.zip').write_bytes(archive({'one.md': 'A document'}))
        scan_watch(self.store, watch['id'], clock=10)
        result = scan_watch(self.store, watch['id'], clock=13)
        self.assertEqual(result['state'], 'attention')
        self.assertIn('missing.csv', self.store.rows('SELECT detail FROM watch_files')[0]['detail'])

    def test_watch_pause_and_symlinks(self):
        watch = create_watch(self.store, self.profile['id'], self.folder, ['secret.md'])
        outside = self.root / 'secret.md'
        outside.write_text('Not in selected folder')
        (self.folder / 'secret.md').symlink_to(outside)
        scan_watch(self.store, watch['id'], clock=10)
        self.assertEqual(scan_watch(self.store, watch['id'], clock=13)['imported'], 0)
        with self.store.db() as db:
            db.execute('UPDATE watches SET enabled=0 WHERE id=?', (watch['id'],))
        self.assertEqual(scan_watch(self.store, watch['id'])['state'], 'paused')

    def test_duplicate_zip_names_and_invalid_zip_are_rejected(self):
        with self.assertRaises(ValueError):
            archive_entries('broken.zip', b'not zip')
        payload = io.BytesIO()
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            with zipfile.ZipFile(payload, 'w') as z:
                z.writestr('one.txt', 'one')
                z.writestr('one.txt', 'two')
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            archive_entries('duplicate.zip', payload.getvalue())

    def test_backup_restore_retains_review_and_disables_automation(self):
        import_file(self.store, 'notes.md', b'Backup evidence', ['notes.md'], self.profile['id'])
        item = self.store.search()[0]
        self.store.review(item['current_revision'], True, True)
        dataset = self.store.freeze('Frozen before backup')
        watch = create_watch(self.store, self.profile['id'], self.folder, ['notes.md'])
        destination = self.root / 'backup.sqlite3'
        backup(self.store, destination)
        with self.assertRaises(FileExistsError):
            backup(self.store, destination)
        restore(destination, self.root / 'restored')
        restored = Store(self.root / 'restored')
        self.assertEqual(restored.export(dataset['id']), self.store.export(dataset['id']))
        self.assertEqual(restored.rows('SELECT enabled FROM watches WHERE id=?', (watch['id'],))[0]['enabled'], 0)
        with self.assertRaisesRegex(ValueError, 'new workspace'):
            restore(destination, self.root / 'restored')

    def test_migrations_repeat_without_losing_existing_data(self):
        source = self.store.source('Existing', 'import', 'legacy')
        self.store.save(source['id'], 'id', 'document', 'Legacy', 'Existing data', 'Existing data')
        Store(self.root / 'data')
        Store(self.root / 'data')
        self.assertEqual(len(self.store.rows('SELECT * FROM schema_versions')), 2)
        self.assertEqual(len(self.store.search('Existing')), 1)

    def test_old_revision_review_does_not_change_current_record(self):
        source = self.store.source('Versioned', 'import', 'versioned')
        self.store.save(source['id'], 'one', 'document', 'Title', 'Version one', 'Raw one')
        old = self.store.search()[0]['current_revision']
        self.store.review(old, True, True)
        frozen = self.store.freeze('Original')
        self.store.save(source['id'], 'one', 'document', 'Title', 'Version two', 'Raw two')
        earlier = self.store.revision(old)
        self.assertFalse(earlier['is_current'])
        self.assertEqual(earlier['text'], 'Version one')
        self.assertEqual(earlier['review']['approved'], 1)
        self.store.review(earlier['current_revision'], False, False)
        self.assertEqual(self.store.search()[0]['text'], 'Version two')
        with self.assertRaisesRegex(ValueError, 'no longer'):
            self.store.export(frozen['id'])

    def test_robots_delay_and_authentication_pause(self):
        with patch('proofpage.core.validate_url'):
            source = self.store.source('Docs', 'web', 'https://example.com/docs')
        with self.store.db() as db:
            db.execute('UPDATE sources SET interval_seconds=3600 WHERE id=?', (source['id'],))
        responses = [(200, {}, 'User-agent: *\nCrawl-delay: 600\nAllow: /', ''),
                     (200, {'content-type': 'text/html'}, '<title>Login</title><input type="password">', '')]
        with patch('proofpage.core.fetch', side_effect=responses), patch('proofpage.core.time.time', return_value=100):
            result = self.store.collect(source['id'])
        self.assertEqual(result['state'], 'authentication_required')
        self.assertEqual(self.store.rows('SELECT until FROM cooldowns')[0]['until'], 700)
        self.assertEqual(self.store.rows('SELECT interval_seconds FROM sources WHERE id=?', (source['id'],))[0]['interval_seconds'], 0)
        self.assertEqual(len(self.store.rows('SELECT * FROM observations')), 1)


if __name__ == '__main__':
    unittest.main()
