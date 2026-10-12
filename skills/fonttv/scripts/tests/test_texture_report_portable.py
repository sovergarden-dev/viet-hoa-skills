"""Portable failure-path tests; no game assets or user paths."""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / 'p1_texture_report.py'

class PortableTextureTests(unittest.TestCase):
    def test_invalid_font_cannot_report_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'broken.font').write_bytes(b'5VSM' + bytes(60))
            proc = subprocess.run([sys.executable, str(SCRIPT), '--fonts-dir', str(root)], capture_output=True)
            self.assertEqual(proc.returncode, 2, proc.stdout.decode('utf-8', 'replace'))

    def test_missing_explicit_archive_directory_is_input_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'broken.font').write_bytes(b'5VSM' + bytes(60))
            proc = subprocess.run([sys.executable, str(SCRIPT), '--fonts-dir', str(root), '--archive-before', str(root / 'missing'), '--archive-after', str(root)], capture_output=True)
            self.assertEqual(proc.returncode, 2)
            self.assertIn(b'archive', proc.stderr.lower())

class ReportContractTests(unittest.TestCase):
    def test_invalid_original_must_fail(self):
        import importlib.util
        from unittest.mock import patch
        spec = importlib.util.spec_from_file_location('texture_report_test', SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            after = root / 'after'; before = root / 'before'
            after.mkdir(); before.mkdir()
            (after / 'one.font').write_bytes(b'test')
            (before / 'one.font').write_bytes(b'bad')
            row = dict(font='one.font', bytes=4, records=1, pages=[{'height':4}], pixels=16, max_height=4)
            with patch.object(module, 'font_row', side_effect=[row, ValueError('invalid original')]):
                self.assertEqual(module.main(['--fonts-dir',str(after),'--original-dir',str(before)]),2)

if __name__ == '__main__':
    unittest.main()
