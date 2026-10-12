"""Tests for fonttv_audit.py (route A) and regression of the other read-only helpers."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unicodedata
import unittest
from pathlib import Path

from fontfixtures import HAS_FONTTOOLS, build_font, full_chars, repertoire

SCRIPTS = Path(__file__).resolve().parent.parent
AUDIT = SCRIPTS / "fonttv_audit.py"


def run(font: Path, *extra) -> tuple[int, dict]:
    proc = subprocess.run([sys.executable, str(AUDIT), str(font), *map(str, extra)], capture_output=True)
    return proc.returncode, json.loads(proc.stdout.decode("utf-8"))


class RouteGateTests(unittest.TestCase):
    def test_engine_binary_is_not_supported(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake = Path(tmp) / "Menu_48.font"
            fake.write_bytes(b"6VSM" + bytes(64))
            code, result = run(fake)
        self.assertEqual((code, result["verdict"]), (3, "NOT_SUPPORTED"))

    def test_collection_is_not_supported(self):
        with tempfile.TemporaryDirectory() as tmp:
            ttc = Path(tmp) / "family.ttc"
            ttc.write_bytes(b"ttcf" + bytes(64))
            code, result = run(ttc)
        self.assertEqual(code, 3)


@unittest.skipUnless(HAS_FONTTOOLS, "fontTools not installed: route A audit NOT_RUN")
class UnicodeAuditTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.corpus = self.tmp / "corpus.txt"
        self.corpus.write_text(repertoire(), encoding="utf-8")

    def tearDown(self):
        self._tmp.cleanup()

    def test_good_font_passes_structurally_only(self):
        font = build_font(self.tmp / "good.ttf", full_chars())
        code, result = run(font, "--corpus", self.corpus)
        self.assertEqual(code, 0, result.get("missing_codepoints"))
        self.assertTrue(result["coverage_ok"])
        self.assertEqual(result["proof_level"], "structurally_verified")
        self.assertEqual(result["coverage"]["mapping_correct"], "NOT_RUN")
        self.assertEqual(result["coverage"]["runtime_bound"], "NOT_RUN")
        self.assertEqual(result["encoding_contract"], "unicode_cmap")
        self.assertTrue(any("custom or legacy" in item for item in result["does_not_prove"]))
        self.assertTrue(result["has_mark_feature"] and result["has_mkmk_feature"] and result["has_kern_feature"])
        self.assertEqual(result["outline_flavor"], "TrueType glyf")

    def test_missing_precomposed_and_marks_fail(self):
        chars = "".join(c for c in repertoire() if c not in "ợửữựỡ")
        font = build_font(self.tmp / "broken.ttf", chars, gpos=False)
        code, result = run(font, "--corpus", self.corpus)
        self.assertEqual(code, 1)
        self.assertEqual(result["coverage"]["record_present"], "FAIL")
        self.assertIn("U+0323", result["missing_combining_marks"])
        self.assertEqual(result["proof_level"], "inventory_only")

    def test_cmap_entry_with_empty_outline_fails(self):
        font = build_font(self.tmp / "empty.ttf", full_chars(), empty="đ")
        code, result = run(font, "--corpus", self.corpus)
        self.assertEqual(code, 1)
        self.assertEqual(result["coverage"]["record_present"], "PASS")
        self.assertEqual(result["coverage"]["outline_nonempty"], "FAIL")
        self.assertEqual(result["empty_outline_codepoints"], ["U+0111"])

    def test_nfd_corpus_accepted(self):
        font = build_font(self.tmp / "good.ttf", full_chars())
        nfd = self.tmp / "nfd.txt"
        nfd.write_text(unicodedata.normalize("NFD", repertoire()), encoding="utf-8")
        code, result = run(font, "--corpus", nfd)
        self.assertEqual(code, 0)
        self.assertEqual(result["nfd_missing_marks"], [])

    def test_os2_bit57_instead_of_bit29_is_flagged(self):
        font = build_font(self.tmp / "bits.ttf", full_chars(), unicode_bits=(0, 57))
        _, result = run(font, "--corpus", self.corpus)
        self.assertFalse(result["os2_unicode_range"]["bit29_latin_extended_additional"])
        self.assertTrue(result["os2_unicode_range"]["bit57_non_plane0"])
        self.assertEqual(sum("bit 29" in w or "bit 57" in w for w in result["warnings"]), 2)


class HelperRegressionTests(unittest.TestCase):
    def test_other_helpers_still_start(self):
        for name in ("tmpro_audit.py", "tmpro_atlas_audit.py", "tmpro_atlas_pixels_audit.py",
                     "tmpro_binding_audit.py", "addressables_font_audit.py", "custom_encoding_audit.py",
                     "proof_level_check.py", "shaping_audit.py", "fonttv_audit.py"):
            proc = subprocess.run([sys.executable, str(SCRIPTS / name), "--help"], capture_output=True)
            self.assertEqual(proc.returncode, 0, f"{name}: {proc.stderr[-300:]!r}")


if __name__ == "__main__":
    unittest.main()
