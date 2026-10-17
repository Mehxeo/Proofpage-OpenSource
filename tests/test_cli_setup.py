import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from proofpage.cli import main


class SetupTests(unittest.TestCase):
    def test_doctor_does_not_create_workspace(self):
        with tempfile.TemporaryDirectory() as root:
            target = Path(root) / 'not-created'
            output = io.StringIO()
            with patch('sys.argv', ['proofpage', '--home', str(target), 'doctor']), contextlib.redirect_stdout(output):
                main()
            result = json.loads(output.getvalue())
            self.assertTrue(result['ready'])
            self.assertEqual(result['workspace'], str(target.resolve()))
            self.assertFalse(target.exists())

    def test_no_arguments_show_help(self):
        output = io.StringIO()
        with patch('sys.argv', ['proofpage']), contextlib.redirect_stdout(output):
            main()
        self.assertIn('Capture a public web page', output.getvalue())

    def test_serve_open_passes_browser_option(self):
        with tempfile.TemporaryDirectory() as root:
            with patch('sys.argv', ['proofpage', '--home', root, 'serve', '--open']), patch('proofpage.server.serve') as serve:
                main()
            self.assertEqual(serve.call_args.kwargs, {'open_browser': True})
