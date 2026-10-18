import tempfile
import json
import subprocess
import re
import unittest
from pathlib import Path
from unittest.mock import patch
from proofpage.core import Store
from proofpage.mcp_setup import setup, check
from proofpage.mcp import TOOLS


class MCPSetupTests(unittest.TestCase):
    def test_local_config_contains_actual_workspace(self):
        with tempfile.TemporaryDirectory(prefix='space here ') as directory:
            data = setup(Store(directory))
            self.assertIn(str(Path(directory).resolve()), data['config']['mcpServers']['proofpage']['args'])
            self.assertIn('proofpage_list_sources', data['prompt'])
            self.assertNotIn('Bearer', data['prompt'])

    def test_frozen_config_uses_console_helper(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Store(directory)
            with patch('sys.frozen', True, create=True), patch('sys.executable', '/Applications/Proofpage.app/Contents/MacOS/Proofpage'), patch('sys.platform', 'darwin'):
                entry = setup(store)['config']['mcpServers']['proofpage']
            self.assertEqual(entry['command'], '/Applications/Proofpage.app/Contents/MacOS/Proofpage-MCP')
            self.assertEqual(entry['args'][0], '--home')

    def test_real_stdio_from_unrelated_directory(self):
        with tempfile.TemporaryDirectory(prefix='workspace with spaces ') as home, tempfile.TemporaryDirectory() as cwd:
            store = Store(home)
            store.source('Fixture', 'import', 'fixture:setup')
            entry = setup(store)['config']['mcpServers']['proofpage']
            messages = [
                {'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {'protocolVersion': '2025-06-18'}},
                {'jsonrpc': '2.0', 'method': 'notifications/initialized'},
                {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/list'},
                {'jsonrpc': '2.0', 'id': 3, 'method': 'tools/call', 'params': {'name': 'proofpage_list_sources', 'arguments': {}}},
                {'jsonrpc': '2.0', 'id': 4, 'method': 'tools/call', 'params': {'name': 'proofpage_schedule_source', 'arguments': {'source_id': 'missing', 'interval_seconds': 1}}},
            ]
            result = subprocess.run([entry['command'], *entry['args']], input=''.join(json.dumps(m)+'\n' for m in messages), cwd=cwd, text=True, capture_output=True, timeout=15)
            self.assertEqual(result.returncode, 0, result.stderr)
            rows = [json.loads(line) for line in result.stdout.splitlines()]
            self.assertEqual([r['id'] for r in rows], [1,2,3,4])
            self.assertEqual({t['name'] for t in rows[1]['result']['tools']}, set(TOOLS))
            self.assertEqual(json.loads(rows[2]['result']['content'][0]['text'])[0]['name'], 'Fixture')
            self.assertTrue(rows[3]['result']['isError'])
            self.assertEqual(store.rows('SELECT * FROM runs'), [])
            verified = check(store)
            self.assertTrue(verified['ok'], verified)
            self.assertEqual(verified['sources'], 1)

    def test_skill_tools_exist_and_failures_are_reported(self):
        with tempfile.TemporaryDirectory() as home:
            store = Store(home)
            skill = setup(store)['skill']
            self.assertTrue(skill.startswith('---\nname: proofpage\n'))
            self.assertFalse(set(re.findall(r'proofpage_[a-z_]+', skill)) - set(TOOLS))
            with patch('proofpage.mcp_setup.subprocess.run', side_effect=subprocess.TimeoutExpired('helper', 15)):
                self.assertFalse(check(store)['ok'])
            with patch('proofpage.mcp_setup.subprocess.run', side_effect=FileNotFoundError('helper')):
                self.assertFalse(check(store)['ok'])
