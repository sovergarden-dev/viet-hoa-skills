"""Tests for shaping_audit.py: HarfBuzz .notdef vs cmap-level coverage."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from fontfixtures import HAS_FONTTOOLS, HAS_HARFBUZZ, MARKS, build_font, full_chars, repertoire, word_ascii

SCRIPT = Path(__file__).resolve().parent.parent / "shaping_audit.py"


def run(font: Path) -> tuple[int, dict]:
    proc = subprocess.run([sys.executable, str(SCRIPT), str(font)], capture_output=True)
    return proc.returncode, json.loads(proc.stdout.decode("utf-8"))


@unittest.skipUnless(HAS_FONTTOOLS and HAS_HARFBUZZ, "fontTools + uharfbuzz required: shaping gate NOT_RUN")
class ShapingTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_good_font_passes(self):
        code, result = run(build_font(self.tmp / "good.ttf", full_chars()))
        self.assertEqual(code, 0, result)
        self.assertTrue(result["shaping_ok"] and result["engine_independent_ok"])
        self.assertEqual(result["proof_level"], "structurally_verified")

    def test_precomposed_only_font_is_composed_by_harfbuzz_but_fails_gate(self):
        code, result = run(build_font(self.tmp / "pre.ttf", repertoire() + word_ascii()))
        self.assertEqual(result["hb_notdef_nfd"], 0, "HarfBuzz should compose NFD into precomposed glyphs")
        self.assertTrue(result["shaping_ok"])
        self.assertFalse(result["engine_independent_ok"])
        self.assertIn("U+0301", result["nfd_dropped_marks"])
        self.assertEqual((code, result["verdict"]), (1, "FAIL"))

    def test_missing_glyph_yields_real_notdef(self):
        chars = "".join(c for c in repertoire() if c not in "ợửữựỡ") + word_ascii()
        code, result = run(build_font(self.tmp / "broken.ttf", chars, gpos=False))
        self.assertEqual(code, 1)
        self.assertFalse(result["shaping_ok"])
        self.assertGreater(result["hb_notdef_nfc"], 0)
        self.assertTrue(any(item.startswith("ợ") for item in result["hb_notdef_chars_nfc"]))

    def test_marks_only_font_decomposes_under_harfbuzz(self):
        code, result = run(build_font(self.tmp / "marks.ttf", "AaEeIiOoUuYyĐđ" + MARKS + word_ascii()))
        self.assertEqual(result["hb_notdef_nfc"], 0, "HarfBuzz should decompose NFC into base + marks")
        self.assertFalse(result["engine_independent_ok"])
        self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()
