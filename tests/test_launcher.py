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

    def test_liveness_does_not_terminate_process(self):
        import subprocess
        import sys
        from proofpage.processes import check_process
        child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'])
        try:
            check_process(child.pid)
            self.assertIsNone(child.poll())
        finally:
            child.terminate()
            child.wait(timeout=5)
        with self.assertRaises(ProcessLookupError):
            check_process(child.pid)
