import asyncio
import importlib.util
import tempfile
import unittest
from pathlib import Path

from proofpage.core import Store
from proofpage import business
from proofpage.mcp_setup import setup
from proofpage.skill_install import install

class SkillInstallTests(unittest.TestCase):
    def test_install_preserve_and_idempotent(self):
        with tempfile.TemporaryDirectory() as project:
            for client in ('codex', 'claude'):
                result = install(project, client)
                self.assertEqual(result['state'], 'installed')
                self.assertEqual(install(project, client)['state'], 'already_installed')
                target = Path(result['path']); target.write_text('User custom skill')
                with self.assertRaises(ValueError): install(project, client)
                self.assertEqual(target.read_text(), 'User custom skill')

@unittest.skipUnless(importlib.util.find_spec('mcp'), 'optional official MCP SDK')
class MCPWorkflowTests(unittest.TestCase):
    def test_downloaded_codex_kit_reads_google_context_and_rejects_training(self):
        import io
        import json
        import tomllib
        import zipfile
        from unittest.mock import patch
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
        from proofpage import google_docs
        from proofpage.mcp_setup import kit
        with tempfile.TemporaryDirectory(prefix='google context ') as home, tempfile.TemporaryDirectory() as project:
            store = Store(home)
            identifier = 'fictional_google_demo'
            google_docs.select(store, identifier, owner_permission=True)
            doc = {'documentId': identifier, 'title': 'Fictional studio', 'body': {'content': [
                {'paragraph': {'elements': [{'textRun': {'content': 'We build websites for local shops.'}}]}}
            ]}}
            with patch('proofpage.google_docs.fetch_document', return_value=doc):
                revision = google_docs.sync(store, identifier)['revision_id']
            profile = business.create(store, 'Fictional studio')['id']
            business.attach(store, profile, revision, 'business')
            fact = business.draft(store, profile)['facts'][0]
            business.review(store, fact['id'], fact['text'], 'approved', True, True)
            with zipfile.ZipFile(io.BytesIO(kit(store, 'codex'))) as archive:
                entry = tomllib.loads(archive.read('mcp-config.toml').decode())['mcp_servers']['proofpage']
                target = Path(project) / '.agents/skills/proofpage/SKILL.md'
                target.parent.mkdir(parents=True)
                target.write_bytes(archive.read('.agents/skills/proofpage/SKILL.md'))
            self.assertEqual(install(project, 'codex')['state'], 'already_installed')
            async def exercise():
                params = StdioServerParameters(command=entry['command'], args=entry['args'], cwd=project)
                async with stdio_client(params) as (read, write):
                    async with ClientSession(read, write) as session:
                        initialized = await session.initialize()
                        self.assertIn('personal context', initialized.instructions)
                        profiles = await session.call_tool('proofpage_business_profiles', {})
                        self.assertEqual(json.loads(profiles.content[0].text)[0]['id'], profile)
                        context = await session.call_tool('proofpage_business_context', {'profile_id': profile})
                        self.assertFalse(context.isError)
                        self.assertEqual(json.loads(context.content[0].text)['facts'][0]['text'], fact['text'])
                        rejected = await session.call_tool('proofpage_draft_example', {
                            'revision_id': revision, 'kind': 'sft',
                            'payload': {'messages': [{'role': 'user', 'content': 'What do we do?'}, {'role': 'assistant', 'content': 'We build websites.'}]},
                            'quote': 'We build websites for local shops.', 'notes': '',
                        })
                        self.assertTrue(rejected.isError)
                        self.assertIn('personal context', rejected.content[0].text)
            asyncio.run(exercise())

    def test_official_client_record_replay_business_and_error(self):
        import json
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
        with tempfile.TemporaryDirectory(prefix='proofpage spaced ') as home, tempfile.TemporaryDirectory() as cwd:
            store = Store(home)
            source = store.source('Fixture', 'import', 'fixture:business')
            store.save(source['id'], 'services', 'text', 'Services', 'We build websites for local shops.', 'original')
            revision = store.rows('SELECT id FROM revisions')[0]['id']
            profile = business.create(store, 'Agency')['id']
            business.attach(store, profile, revision, 'business')
            fact = business.draft(store, profile)['facts'][0]
            business.review(store, fact['id'], fact['text'], 'approved', True, True)
            entry = setup(store)['config']['mcpServers']['proofpage']
            async def exercise():
                params = StdioServerParameters(command=entry['command'], args=entry['args'], cwd=cwd)
                async with stdio_client(params) as (read, write):
                    async with ClientSession(read, write) as session:
                        await session.initialize()
                        tools = await session.list_tools()
                        names = {t.name for t in tools.tools}
                        self.assertIn('proofpage_record_context', names)
                        self.assertNotIn('proofpage_business_approve', names)
                        result = await session.call_tool('proofpage_record_context', {'query': 'websites', 'output_id': 'answer', 'name': 'Test'})
                        self.assertFalse(result.isError)
                        recorded = json.loads(result.content[0].text)
                        run_id = recorded['recording']['run_id']
                        replay = await session.call_tool('proofpage_replay_context', {'run_id': run_id})
                        self.assertEqual(json.loads(replay.content[0].text)['excerpts'][0]['quote'], recorded['excerpts'][0]['text'])
                        context = await session.call_tool('proofpage_business_context', {'profile_id': profile})
                        self.assertEqual(json.loads(context.content[0].text)['facts'][0]['text'], fact['text'])
                        store.save(source['id'], 'services', 'text', 'Services', 'We build applications now.', 'changed')
                        stale = await session.call_tool('proofpage_business_context', {'profile_id': profile})
                        self.assertTrue(stale.isError)
                        drift = await session.call_tool('proofpage_check_evidence_run', {'run_id': run_id})
                        self.assertFalse(json.loads(drift.content[0].text)['ok'])
                        invalid = await session.call_tool('proofpage_record_context', {'query': 'websites'})
                        self.assertTrue(invalid.isError)
            asyncio.run(exercise())
