"""Synthetic 5VSM texture-report integration, no proprietary assets."""
import json
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / 'p1_texture_report.py'


def fixture(path, height):
    width = 8
    desc = bytearray(128)
    desc[:8] = struct.pack('<II', 4, 8)
    for offset, value in ((92, width), (88, height), (20, width*height), (8, width*height)):
        struct.pack_into('<I', desc, len(desc)-offset, value)
    texture_header = struct.pack('<II', 136, 1) + desc
    prefix = bytearray(b'5VSM' + bytes(16))
    prefix += struct.pack('<I', 4) + b'Test' + bytes(5)
    prefix += struct.pack('<ii', 56, 1)
    prefix += struct.pack('<III4f5f', 65, 0, 0, 0., 1., 0., 1., 8., float(height), 0., 0., 8.)
    struct.pack_into('<I', prefix, 4, len(prefix) + len(texture_header) - 20)
    path.write_bytes(prefix + texture_header + bytes([255, 0] + [0]*14) * (width*height//16))


class SyntheticReportTests(unittest.TestCase):
    def test_real_parser_growth_and_archive_sizes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            before = root/'before'; after=root/'after'
            before.mkdir(); after.mkdir()
            fixture(before/'Test.font', 4); fixture(after/'Test.font', 8)
            (before/'Test.ttarch2').write_bytes(bytes(10))
            (after/'Test.ttarch2').write_bytes(bytes(20))
            out=root/'report.json'
            result=subprocess.run([sys.executable,str(SCRIPT),'--fonts-dir',str(after),'--original-dir',str(before),'--archive-before',str(before),'--archive-after',str(after),'--json',str(out)],capture_output=True)
            self.assertEqual(result.returncode,0,result.stderr.decode('utf-8','replace'))
            report=json.loads(out.read_text(encoding='utf-8'))
            self.assertEqual(len(report['fonts']),1)
            self.assertEqual(report['fonts'][0]['max_height'],8)
            self.assertEqual(report['fonts'][0]['height_before'],[4])
            self.assertGreater(report['fonts'][0]['byte_growth'],1)
            self.assertEqual(report['archives']['Test.ttarch2']['growth'],2)

if __name__ == '__main__': unittest.main()
