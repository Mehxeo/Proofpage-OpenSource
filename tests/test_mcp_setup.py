import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from proofpage.core import Store
from proofpage.mcp_setup import setup


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
