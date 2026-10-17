from pathlib import Path
import tempfile
import unittest
from proofpage.launcher import WorkspaceLock


class LauncherTests(unittest.TestCase):
    def test_duplicate_app_refused_and_lock_released(self):
        with tempfile.TemporaryDirectory() as directory:
            first = WorkspaceLock(Path(directory))
            try:
                with self.assertRaises(RuntimeError):
                    WorkspaceLock(Path(directory))
            finally:
                first.close()
            second = WorkspaceLock(Path(directory))
            second.close()
