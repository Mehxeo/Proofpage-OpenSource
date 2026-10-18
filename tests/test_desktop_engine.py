import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


class DesktopEngineTests(unittest.TestCase):
    def test_engine_readiness_mcp_and_clean_shutdown(self):
        with tempfile.TemporaryDirectory(prefix='proofpage-engine-test-') as directory:
            report = Path(directory) / 'report.json'
            result = subprocess.run([sys.executable, '-m', 'proofpage.desktop_engine', '--smoke-test', str(report)],
                                    input='smoke\nquit\n', text=True, capture_output=True, timeout=40)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('PROOFPAGE_READY http://127.0.0.1:', result.stdout)
            self.assertIn('PROOFPAGE_SMOKE_OK', result.stdout)
            self.assertTrue(json.loads(report.read_text())['ready'])
            self.assertTrue((report.parent / 'workspace/data/proofpage.sqlite3').exists())
            # Reopen the same workspace to prove the shutdown released its lock.
            again = subprocess.run([sys.executable, '-m', 'proofpage.desktop_engine', '--smoke-test', str(report)],
                                   input='', text=True, capture_output=True, timeout=40)
            self.assertEqual(again.returncode, 0, again.stderr)
            self.assertIn('PROOFPAGE_READY', again.stdout)
