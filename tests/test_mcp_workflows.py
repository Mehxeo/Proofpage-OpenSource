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
