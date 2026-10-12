from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LOCK_TOOL = ROOT / "writer_lock.py"


class WriterLockTests(unittest.TestCase):
    def test_second_writer_is_refused_and_crash_releases_lock(self) -> None:
        with tempfile.TemporaryDirectory(prefix="bientaptay-writer-lock-") as directory:
            project = Path(directory) / "project.json"
            project.write_text("{}\n", encoding="utf-8")
            holder = subprocess.Popen(
                [sys.executable, str(LOCK_TOOL), "hold", "--project", str(project), "--seconds", "30"],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            try:
                ready = holder.stdout.readline() if holder.stdout is not None else ""
                self.assertTrue(ready.startswith("LOCKED "), ready or (holder.stderr.read() if holder.stderr else ""))
                refused = subprocess.run(
                    [sys.executable, str(LOCK_TOOL), "probe", "--project", str(project)],
                    text=True,
                    capture_output=True,
                )
                self.assertEqual(2, refused.returncode)
                self.assertIn("LOCK-REFUSED", refused.stdout)
            finally:
                holder.terminate()
                holder.communicate(timeout=10)

            reopened = subprocess.run(
                [sys.executable, str(LOCK_TOOL), "probe", "--project", str(project)],
                text=True,
                capture_output=True,
            )
            self.assertEqual(0, reopened.returncode, reopened.stderr or reopened.stdout)
            self.assertIn("LOCKED", reopened.stdout)

    def test_run_holds_lock_and_returns_child_exit_code(self) -> None:
        with tempfile.TemporaryDirectory(prefix="bientaptay-writer-run-") as directory:
            project = Path(directory) / "project.json"
            project.write_text("{}\n", encoding="utf-8")
            result = subprocess.run(
                [
                    sys.executable,
                    str(LOCK_TOOL),
                    "run",
                    "--project",
                    str(project),
                    "--",
                    sys.executable,
                    "-c",
                    "print('CHILD-RAN')",
                ],
                text=True,
                capture_output=True,
            )
            self.assertEqual(0, result.returncode, result.stderr or result.stdout)
            self.assertIn("LOCKED", result.stdout)
            self.assertIn("CHILD-RAN", result.stdout)


if __name__ == "__main__":
    unittest.main()
