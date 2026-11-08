"""Tests for strategy P1 helpers. Each test pins a false result seen in TWAU."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image  # noqa: E402

HAS_FONTTOOLS = importlib.util.find_spec("fontTools") is not None

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

import p1_core  # noqa: E402

WIN = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts" if sys.platform == "win32" else Path("/usr/share/fonts")
HERE = Path(__file__).resolve()
NOTO = WIN / "NotoSans-Regular.ttf"
ARIAL = WIN / "arialbd.ttf"
TWAU = Path(os.environ.get("VIETHOA_FIXTURE_ROOT", "tests/fixtures/twau"))


class UvRounding(unittest.TestCase):
    def test_float32_uv_keeps_every_row(self):
        # Find real float32 UVs that int() truncates one row short; they exist
        # for most atlas heights, and every one must round back to its row.
        traps = 0
        for th in (428, 716, 828, 1004, 1608):
            for row in range(0, th, 4):
                v = float(np.float32(row / th))
                if int(v * th) != row:
                    traps += 1
                self.assertEqual(p1_core.uv_box(0.0, 0.5, v, v, 512, th)[1], row)
        self.assertGreater(traps, 0)  # the trap is real, so int() must never be used


class Dxt5Identity(unittest.TestCase):
    def glyph(self):
        yy, xx = np.mgrid[0:24, 0:24]
        disk = np.clip(255 - (np.hypot(yy - 12, xx - 12) - 8) * 60, 0, 255)
        return disk.astype(np.uint8)

    def roundtrip(self, alpha):
        raw = p1_core.encode_dxt5_alpha(alpha)
        return p1_core.decode_dxt5_alpha(raw, alpha.shape[1], alpha.shape[0])

    def test_roundtrip_passes_although_binary_iou_fails(self):
        want = self.glyph()
        got = self.roundtrip(want)
        binary = ((got > 0) == (want > 0)).mean()
        self.assertLess(binary, 1.0)  # the old rule would have failed this
        res = p1_core.identity_dxt5(got, want)
        self.assertTrue(res["ok"], res)
        self.assertLessEqual(res["max_err"], p1_core.DXT5_MAX_ERR)

    def test_wrong_glyph_fails(self):
        want = self.glyph()
        other = np.zeros_like(want)
        other[2:22, 10:14] = 255
        self.assertFalse(p1_core.identity_dxt5(self.roundtrip(other), want)["ok"])

    def test_shape_mismatch_fails(self):
        want = self.glyph()
        self.assertFalse(p1_core.identity_dxt5(want[:-1], want)["ok"])

    def test_unaligned_plane_is_rejected(self):
        with self.assertRaises(ValueError):
            p1_core.encode_dxt5_alpha(np.zeros((5, 8), dtype=np.uint8))


class Repertoire(unittest.TestCase):
    def test_derived_repertoire_is_134(self):
        rep = p1_core.vn_repertoire()
        self.assertEqual(len(rep), 134)
        self.assertIn("Đ", rep)
        self.assertIn("ự", rep)
        self.assertTrue(all(not c.isascii() for c in rep))


@unittest.skipUnless(HAS_FONTTOOLS and NOTO.is_file() and ARIAL.is_file(), "fontTools and system fonts not available")
class DotShapes(unittest.TestCase):
    def test_round_font_dot_matches_period(self):
        s = p1_core.dot_shapes(NOTO)
        self.assertLess(s["dot_below"], 0.9)
        self.assertLess(abs(s["dot_below"] - s["period"]), 0.15)

    def test_square_font_is_square_by_design(self):
        s = p1_core.dot_shapes(ARIAL)
        self.assertGreater(s["dot_below"], 0.95)
        self.assertGreater(s["period"], 0.95)

    def test_source_select_reads_argv_not_a_builtin_list(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "r.json"
            proc = subprocess.run([sys.executable, str(SCRIPTS / "p1_source_select.py"), str(NOTO),
                                   "--output", str(out)], capture_output=True)
            report = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(proc.returncode, 4)  # no license evidence: PLANNING_ONLY
        self.assertEqual([Path(r["font"]).name for r in report["fonts"]], [NOTO.name])

    def test_missing_coverage_fails(self):
        mono = WIN / "UbuntuMono-Regular.ttf"
        if not mono.is_file():
            self.skipTest("UbuntuMono not installed")
        proc = subprocess.run([sys.executable, str(SCRIPTS / "p1_source_select.py"), str(mono)],
                              capture_output=True)
        self.assertEqual(proc.returncode, 1)


@unittest.skipUnless((TWAU / "all_fonts").is_dir() and (TWAU / "build" / "fonts_p1").is_dir(),
                     "TWAU fixture not available")
class TelltaleRegression(unittest.TestCase):
    def test_rebuild_is_byte_identical_to_accepted_build(self):
        src = TWAU / "sources" / "p1"
        sources = {"Arial_30": [str(WIN / "NotoSans-Regular.ttf"), str(WIN / "NotoSans-Bold.ttf")],
                   "Cantoria_MT": [str(src / "NotoSerif" / "NotoSerif-Regular.ttf"),
                                   str(src / "NotoSerif" / "NotoSerif-Bold.ttf")]}
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            fonts = tmp / "in"
            fonts.mkdir()
            for name in sources:
                (fonts / f"{name}.font").write_bytes((TWAU / "all_fonts" / f"{name}.font").read_bytes())
            (tmp / "s.json").write_text(json.dumps(sources), encoding="utf-8")
            proc = subprocess.run([sys.executable, str(SCRIPTS / "p1_telltale_build.py"),
                                   "--fonts-dir", str(fonts), "--out-dir", str(tmp / "out"),
                                   "--mapping", str(TWAU / "reports" / "fonttv_v09_v3_structural"
                                                    / "vn128_visible_repertoire.json"),
                                   "--sources", str(tmp / "s.json"), "--manifest", str(tmp / "m.json")],
                                  capture_output=True)
            self.assertEqual(proc.returncode, 0, proc.stdout.decode("utf-8", "replace")[-600:])
            for name in sources:
                built = hashlib.sha256((tmp / "out" / f"{name}.font").read_bytes()).hexdigest()
                accepted = hashlib.sha256((TWAU / "build" / "fonts_p1" / f"{name}.font").read_bytes()).hexdigest()
                self.assertEqual(built, accepted, name)


class PipelineHarness(unittest.TestCase):
    def plan(self, steps) -> Path:
        path = Path(tempfile.mkdtemp()) / "plan.json"
        path.write_text(json.dumps({"schema": "fonttv/pipeline-plan/v1", "root": str(HERE.root),
                                    "steps": steps}), encoding="utf-8")
        return path

    def run_plan(self, path: Path, *extra):
        return subprocess.run([sys.executable, str(SCRIPTS / "run_pipeline.py"), "--plan", str(path), *extra],
                              capture_output=True, text=True)

    def test_stops_at_the_first_failure(self):
        ok = ["-c", "print('first ok')"]
        bad = ["-c", "import sys; sys.exit(3)"]
        after = ["-c", "print('should not run')"]
        proc = self.run_plan(self.plan([{"name": "a", "argv": ok}, {"name": "b", "argv": bad},
                                        {"name": "c", "argv": after}]))
        self.assertEqual(proc.returncode, 1)
        self.assertIn("STOP: b exited 3", proc.stdout)
        self.assertNotIn("should not run", proc.stdout)

    def test_allow_makes_a_nonzero_exit_acceptable(self):
        proc = self.run_plan(self.plan([{"name": "triage", "argv": ["-c", "import sys; sys.exit(1)"],
                                        "allow": [0, 1]}]))
        self.assertEqual(proc.returncode, 0)

    def test_dry_run_executes_nothing(self):
        proc = self.run_plan(self.plan([{"name": "never", "argv": ["-c", "print('ran')"]}]), "--dry-run")
        self.assertEqual(proc.returncode, 0)
        self.assertIn("python", proc.stdout)      # the command line was printed
        self.assertNotIn("\nran", proc.stdout)    # but not executed

    def test_flags_are_not_rewritten_into_paths(self):
        proc = self.run_plan(self.plan([{"name": "flag", "argv": ["-c",
                                        "import sys; print('argv', sys.argv[1:])", "--font", "NotoSans-Regular.ttf"]}]))
        self.assertEqual(proc.returncode, 0, proc.stdout)
        self.assertIn("--font", proc.stdout)
        self.assertNotIn("\\--font", proc.stdout)


class ConsumerScanTests(unittest.TestCase):
    def test_discovers_names_the_tree_does_not_contain(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "uiz_Thing.lua").write_bytes(b"Text Font\0\0AvantGarde_LT_Book_40.font\0\0Text Scale")
            out = root / "scan.json"
            proc = subprocess.run([sys.executable, str(SCRIPTS / "p1_consumer_scan.py"),
                                   "--root", str(root), "--json", str(out)], capture_output=True, text=True)
            report = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("AvantGarde_LT_Book_40.font", report["fonts"])
        self.assertEqual(report["fonts"]["AvantGarde_LT_Book_40.font"][0]["member"], "uiz_Thing.lua")

    def test_no_font_name_is_an_input_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "empty.lua").write_bytes(b"nothing to see")
            proc = subprocess.run([sys.executable, str(SCRIPTS / "p1_consumer_scan.py"),
                                   "--root", str(root)], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 2)


@unittest.skipUnless((TWAU / "all_fonts").is_dir(), "TWAU fixture not available")
class FontToolTests(unittest.TestCase):
    MAP = TWAU / "reports" / "fonttv_v09_v3_structural" / "vn128_visible_repertoire.json"

    def test_diff_of_a_font_with_itself_is_empty(self):
        font = TWAU / "build" / "fonts_p1" / "Arial_30.font"
        out = Path(tempfile.mkdtemp()) / "d.json"
        proc = subprocess.run([sys.executable, str(SCRIPTS / "telltale_font_diff.py"),
                               "--before", str(font), "--after", str(font), "--json", str(out)],
                              capture_output=True, text=True)
        report = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(report["counts"]["changed"], 0)
        self.assertEqual(report["counts"]["added"], 0)

    def test_diff_sees_the_replacement(self):
        out = Path(tempfile.mkdtemp()) / "d.json"
        subprocess.run([sys.executable, str(SCRIPTS / "telltale_font_diff.py"),
                        "--before", str(TWAU / "all_fonts" / "Arial_30.font"),
                        "--after", str(TWAU / "build" / "fonts_p1" / "Arial_30.font"),
                        "--json", str(out)], capture_output=True)
        report = json.loads(out.read_text(encoding="utf-8"))
        # 222 encoder-reachable glyphs are re-rendered; Arial_30 only ships 192
        # records, so most change and the rest are added.
        self.assertGreater(report["counts"]["changed"], 100)
        self.assertGreater(report["counts"]["added"], 20)
        self.assertEqual(report["counts"]["removed"], 0)

    def test_uniformity_passes_against_pristine(self):
        out = Path(tempfile.mkdtemp()) / "u.json"
        proc = subprocess.run([sys.executable, str(SCRIPTS / "p1_uniformity_check.py"),
                               "--font", str(TWAU / "build" / "fonts_p1" / "Cantoria_MT.font"),
                               "--original", str(TWAU / "all_fonts" / "Cantoria_MT.font"),
                               "--mapping", str(self.MAP), "--json", str(out)], capture_output=True, text=True)
        report = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(proc.returncode, 0, proc.stdout)
        self.assertEqual(report["status"], "PASS")
        self.assertLessEqual(report["built"]["cap_spread"], report["allowance"])


class ReleaseReadinessTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.proof = self.tmp / "proof.json"
        self.manifest = self.tmp / "manifest.json"

    def run_tool(self):
        return subprocess.run([sys.executable, str(SCRIPTS / "release_readiness.py"),
                               "--proof", str(self.proof), "--manifest", str(self.manifest)],
                              capture_output=True, text=True)

    def write(self, fonts, rights, release):
        self.proof.write_text(json.dumps({"justified_proof_level": "runtime_verified", "verdict": "PASS",
                                          "errors": [], "per_font": fonts}), encoding="utf-8")
        self.manifest.write_text(json.dumps({"fonts": fonts, "rights": rights, "release": release}),
                                 encoding="utf-8")

    def test_lists_every_blocker_when_nothing_is_done(self):
        self.write([{"name": "f.font", "level": "archive_verified", "output_sha256": "a" * 64,
                     "blockers": ["runtime: build_id and screenshots required"]}],
                   {"redistribution": "unverified"}, {})
        proc = self.run_tool()
        self.assertEqual(proc.returncode, 1)
        for needle in ("rights.evidence", "rights.redistribution", "release.clean_install",
                       "release.rollback", "release.signoff"):
            self.assertIn(needle, proc.stdout)

    def test_ready_when_every_item_is_present(self):
        digest = "b" * 64
        self.write([{"name": "f.font", "level": "runtime_verified", "output_sha256": digest, "blockers": []}],
                   {"redistribution": "not_distributed", "evidence": "LICENSE_AUDIT.md",
                    "evidence_sha256": "c" * 64},
                   {"clean_install": {"status": "PASS"}, "rollback": {"status": "PASS"},
                    "signoff": [{"role": "vietnamese_reader", "sha256": [digest]}]})
        proc = self.run_tool()
        self.assertEqual(proc.returncode, 0, proc.stdout)
        self.assertIn("READY_FOR_RELEASE = True", proc.stdout)

    def test_archive_tier_ships_without_runtime_screenshots(self):
        """The ship bar: every font at archive_verified and no blockers is release-ready.

        A per-font runtime screenshot can only be bound to a font whose consumer is
        known, so it must never become a silent default requirement.
        """
        digest = "b" * 64
        self.write([{"name": "f.font", "level": "archive_verified", "output_sha256": digest, "blockers": []}],
                   {"redistribution": "not_distributed", "evidence": "LICENSE_AUDIT.md",
                    "evidence_sha256": "c" * 64},
                   {"clean_install": {"status": "PASS"}, "rollback": {"status": "PASS"},
                    "signoff": [{"role": "vietnamese_reader", "sha256": [digest]}]})
        proc = self.run_tool()
        self.assertEqual(proc.returncode, 0, proc.stdout)
        self.assertIn("READY_FOR_RELEASE = True", proc.stdout)
        self.assertIn("optional tier", proc.stdout)

    def test_strict_bar_demands_runtime_evidence_only_when_asked(self):
        digest = "b" * 64
        self.write([{"name": "f.font", "level": "archive_verified", "output_sha256": digest, "blockers": []}],
                   {"redistribution": "not_distributed", "evidence": "LICENSE_AUDIT.md",
                    "evidence_sha256": "c" * 64},
                   {"clean_install": {"status": "PASS"}, "rollback": {"status": "PASS"},
                    "signoff": [{"role": "vietnamese_reader", "sha256": [digest]}]})
        cmd = [sys.executable, str(SCRIPTS / "release_readiness.py"), "--proof", str(self.proof),
               "--manifest", str(self.manifest), "--require-runtime-evidence"]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("fonts.runtime", proc.stdout)

    def test_font_below_archive_is_a_blocker_on_every_bar(self):
        digest = "b" * 64
        self.write([{"name": "f.font", "level": "structurally_verified", "output_sha256": digest, "blockers": []}],
                   {"redistribution": "not_distributed", "evidence": "LICENSE_AUDIT.md",
                    "evidence_sha256": "c" * 64},
                   {"clean_install": {"status": "PASS"}, "rollback": {"status": "PASS"},
                    "signoff": [{"role": "vietnamese_reader", "sha256": [digest]}]})
        proc = self.run_tool()
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("fonts.verified", proc.stdout)


@unittest.skipUnless(
    (TWAU / "build" / "fonts_p1").is_dir()
    and (TWAU / "all_fonts").is_dir()
    and (TWAU / "build" / "archive_live_v3_snapshot" / "Fables_pc_Project_all.ttarch2").is_file()
    and (TWAU / "build" / "archive_p1" / "Fables_pc_Project_all.ttarch2").is_file(),
    "complete TWAU font/archive fixtures not available")
class TextureReportTests(unittest.TestCase):
    def test_reports_pages_and_growth(self):
        out = Path(tempfile.mkdtemp()) / "t.json"
        proc = subprocess.run([sys.executable, str(SCRIPTS / "p1_texture_report.py"),
                               "--fonts-dir", str(TWAU / "build" / "fonts_p1"),
                               "--original-dir", str(TWAU / "all_fonts"),
                               "--archive-before", str(TWAU / "build" / "archive_live_v3_snapshot"),
                               "--archive-after", str(TWAU / "build" / "archive_p1"),
                               "--json", str(out)], capture_output=True, text=True)
        report = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(len(report["fonts"]), 12)
        self.assertLessEqual(max(f["max_height"] for f in report["fonts"]), 2048)
        self.assertTrue(all(f["byte_growth"] > 1 for f in report["fonts"]))
        self.assertIn("Fables_pc_Project_all.ttarch2", report["archives"])


class ManifestToolTests(unittest.TestCase):
    """The manifest tool's job is to refuse, so that is what gets tested."""

    def test_missing_artefact_is_named_and_refused(self):
        tmp = Path(tempfile.mkdtemp())
        (tmp / "a.font").write_bytes(b"\x00" * 16)
        (tmp / "m.json").write_text('{"schema": "fonttv/encoding-map/v1", "entries": []}')
        proc = subprocess.run([sys.executable, str(SCRIPTS / "p1_manifest.py"),
                               "--project", "p", "--fonts-dir", str(tmp), "--original-dir", str(tmp),
                               "--audit-dir", str(tmp / "x"), "--evidence-dir", str(tmp / "y"),
                               "--readback-dir", str(tmp), "--mapping", str(tmp / "m.json"),
                               "--adapter", str(tmp / "ad.py"), "--container", "c.ttarch2",
                               "--container-sha256", "0" * 64, "--build-anchor", str(tmp / "a.font"),
                               "--out", str(tmp / "out.json")], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("missing audit", proc.stderr)
        self.assertFalse((tmp / "out.json").exists(), "refused run must not write a manifest")

    def test_readback_index_requires_an_entry_per_font(self):
        """A font whose supplying archive is unknown must not be silently accepted."""
        tmp = Path(tempfile.mkdtemp())
        for name in ("a.font", "b.font", "orig.font", "read.font"):
            (tmp / name).write_bytes(b"\x01" * 16)
        (tmp / "audit").mkdir(); (tmp / "audit" / "a.audit.json").write_text('{"verdict": "PASS"}')
        (tmp / "audit" / "b.audit.json").write_text('{"verdict": "PASS"}')
        (tmp / "ev").mkdir()
        for stem in ("a", "b"):
            (tmp / "ev" / f"{stem}.build_manifest.json").write_text("{" + "}")
        (tmp / "mapping.json").write_text('{"schema": "fonttv/encoding-map/v1", "entries": []}')
        (tmp / "ad.py").write_text("")
        (tmp / "index.json").write_text(json.dumps({"a.font": {"container": "c", "sha256": "0" * 64}}))
        proc = subprocess.run([sys.executable, str(SCRIPTS / "p1_manifest.py"),
                               "--project", "p", "--fonts-dir", str(tmp), "--original-dir", str(tmp),
                               "--audit-dir", str(tmp / "audit"), "--evidence-dir", str(tmp / "ev"),
                               "--readback-dir", str(tmp), "--mapping", str(tmp / "mapping.json"),
                               "--adapter", str(tmp / "ad.py"), "--container", "c",
                               "--container-sha256", "0" * 64, "--build-anchor", str(tmp / "a.font"),
                               "--readback-index", str(tmp / "index.json"),
                               "--out", str(tmp / "out.json")], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("b: no entry in the readback index", proc.stderr)


class AttachScreenshotTests(unittest.TestCase):
    """Attribution is by citation, so the refusals carry the weight."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.shots = self.tmp / "shots.json"
        self.evidence = self.tmp / "evidence"
        self.real = _png(Image.new("RGB", (400, 200), (255, 0, 0)), self.tmp / "real.png")

    def run_tool(self, image, cite="uiz_ConsoleButtons.lua names ITC_Kabel_Book.font", **extra):
        argv = {"--image": str(image), "--font": "ITC_Kabel_Book.font", "--cite": cite,
                "--reviewer": "Rurus", "--shots": str(self.shots),
                "--evidence-dir": str(self.evidence)}
        argv.update(extra)
        command = [sys.executable, str(SCRIPTS / "p1_attach_screenshot.py")]
        for key, value in argv.items():
            command += [key, str(value)]
        return subprocess.run(command, capture_output=True, text=True)

    def test_records_the_image_and_the_citation(self):
        proc = self.run_tool(self.real)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        shots = json.loads(self.shots.read_text(encoding="utf-8"))["shots"]
        self.assertEqual(len(shots), 1)
        entry = shots[0]
        self.assertEqual(entry["font"], "ITC_Kabel_Book.font")
        self.assertIn("uiz_ConsoleButtons.lua", entry["why"])
        archived = Path(entry["path"])
        self.assertTrue(archived.is_file())
        self.assertEqual(hashlib.sha256(archived.read_bytes()).hexdigest(), entry["sha256"])
        self.assertEqual(entry["size"], [400, 200])

    def test_refuses_a_placeholder_image(self):
        tiny = _png(Image.new("RGB", (32, 32), (0, 0, 0)), self.tmp / "tiny.png")
        proc = self.run_tool(tiny)
        self.assertEqual(proc.returncode, 1)
        self.assertIn("too small", proc.stderr)
        self.assertFalse(self.shots.exists(), "a refusal must not write the shots file")

    def test_refuses_a_missing_image(self):
        proc = self.run_tool(self.tmp / "absent.png")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("image not found", proc.stderr)

    def test_refuses_an_empty_citation(self):
        proc = self.run_tool(self.real, cite="   ")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("--cite is empty", proc.stderr)

    def test_refuses_a_second_entry_without_replace(self):
        self.assertEqual(self.run_tool(self.real).returncode, 0)
        other = _png(Image.new("RGB", (600, 400), (0, 255, 0)), self.tmp / "other.png")
        proc = self.run_tool(other)
        self.assertEqual(proc.returncode, 1)
        self.assertIn("already has 1 screenshot", proc.stderr)
        self.assertEqual(len(json.loads(self.shots.read_text(encoding="utf-8"))["shots"]), 1)
        command = [sys.executable, str(SCRIPTS / "p1_attach_screenshot.py"),
                   "--image", str(other), "--font", "ITC_Kabel_Book.font", "--cite", "design unique",
                   "--reviewer", "Rurus", "--shots", str(self.shots),
                   "--evidence-dir", str(self.evidence), "--replace"]
        self.assertEqual(subprocess.run(command, capture_output=True, text=True).returncode, 0)
        shots = json.loads(self.shots.read_text(encoding="utf-8"))["shots"]
        self.assertEqual(len(shots), 1)
        self.assertEqual(shots[0]["why"], "design unique")


    def test_mixed_font_naming_is_one_key(self):
        """``X`` and ``X.font`` are the same font: the duplicate check must see that."""
        self.shots.write_text(json.dumps({"schema": "fonttv/screenshots/v1", "shots": [
            {"path": str(self.real), "sha256": "0" * 64, "font": "ITC_Kabel_Book",
             "why": "legacy entry without the extension", "reviewer": "Rurus"}]}), encoding="utf-8")
        proc = self.run_tool(self.real)
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("already has 1 screenshot", proc.stderr)


class PropSlotTests(unittest.TestCase):
    """The slot patcher must refuse anything that is not length-preserving."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        key = bytes.fromhex("b1a26dad8ca8b851")
        self.before = b"PAD" + key + struct.pack("<I", 12) + b"Hello world." + b"TAIL"
        self.off = 3 + 8          # offset of the length field

    def run_tool(self, *extra):
        return subprocess.run([sys.executable, str(SCRIPTS / "ttprop_slots.py"), *extra],
                              capture_output=True, text=True)

    def test_lists_a_slot(self):
        src = self.tmp / "a.prop"; src.write_bytes(self.before)
        proc = self.run_tool(str(src), "--list")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("Hello world.", proc.stdout)
        self.assertIn("1 slot", proc.stdout)

    def test_a_node_region_is_not_one_slot(self):
        """A printable node body swallowed the real slots inside it and hid English."""
        inner_key = bytes.fromhex("b1a26dad8ca8b851")
        inner = inner_key + struct.pack("<I", 5) + b"Door."
        node = b"\x08\x00\x00\x00\x00\x00\x00\x00" + struct.pack("<I", len(inner) + 12) + b"\x01\x00\x00\x00" + inner
        src = self.tmp / "node.prop"
        src.write_bytes(b"PAD" + node)
        proc = self.run_tool(str(src), "--list")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("Door.", proc.stdout)
        self.assertIn("1 slot", proc.stdout)

    def test_a_short_label_without_spaces_is_still_a_slot(self):
        """The space rule hid 'EPISODE': a padded label then looked like a new slot."""
        src = self.tmp / "b.prop"
        src.write_bytes(b"PAD" + bytes.fromhex("d67fe57577e129ab") + struct.pack("<I", 7) + b"EPISODE")
        proc = self.run_tool(str(src), "--list")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("EPISODE", proc.stdout)

    def test_apply_refuses_a_length_change(self):
        src = self.tmp / "a.prop"; src.write_bytes(self.before)
        plan = self.tmp / "plan.json"
        plan.write_text(json.dumps([{"len_off": self.off, "old": "Hello world.", "new": "Chao the gioi."}]),
                        encoding="utf-8")
        proc = self.run_tool(str(src), "--apply", str(plan))
        self.assertEqual(proc.returncode, 1)
        self.assertIn("not length-preserving", proc.stderr)

    def test_apply_writes_and_verifies(self):
        src = self.tmp / "a.prop"; src.write_bytes(self.before)
        plan = self.tmp / "plan.json"
        plan.write_text(json.dumps([{"len_off": self.off, "old": "Hello world.", "new": "Chao the gio"}]),
                        encoding="utf-8")
        out = self.tmp / "b.prop"
        proc = self.run_tool(str(src), "--apply", str(plan), "--out", str(out))
        self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
        self.assertEqual(out.read_bytes()[:self.off + 4], self.before[:self.off + 4])
        self.assertEqual(len(out.read_bytes()), len(self.before))
        again = self.run_tool("--verify", str(src), str(out))
        self.assertEqual(again.returncode, 0, again.stdout)

    def test_verify_catches_a_byte_changed_outside_a_slot(self):
        """Size and slot checks alone passed a file corrupted outside every slot."""
        src = self.tmp / "a.prop"; src.write_bytes(self.before)
        broken = self.tmp / "broken.prop"
        data = bytearray(self.before); data[0] = (data[0] + 1) % 256
        broken.write_bytes(bytes(data))
        proc = self.run_tool("--verify", str(src), str(broken))
        self.assertEqual(proc.returncode, 1)
        self.assertIn("outside any slot", proc.stdout)

    def test_verify_catches_a_doubled_percent(self):
        src = self.tmp / "a.prop"; src.write_bytes(self.before)
        bad = self.tmp / "bad.prop"
        # same 12 bytes inside the slot, only the % doubled: nothing else moves
        bad.write_bytes(self.before.replace(b"Hello world.", b"Hello 100%%."))
        proc = self.run_tool("--verify", str(src), str(bad))
        self.assertEqual(proc.returncode, 1)
        self.assertIn("doubled percent", proc.stdout)


@unittest.skipUnless((TWAU / "build" / "archive_p1").is_dir(), "TWAU fixture not available")
class RealPropPatchTests(unittest.TestCase):
    def test_staged_choice_stats_keeps_every_invariant(self):
        live = TWAU / "build" / "archive_p1" / "Fables_pc_Project_all.ttarch2"
        staged = TWAU / "build" / "archive_p1_choicestats" / "Fables_pc_Project_all.ttarch2"
        if not staged.is_file():
            self.skipTest("choice-stats build not staged")
        tmp = Path(tempfile.mkdtemp())
        tool = TWAU / "tools" / "ttarchext_bin" / "ttarchext.exe"
        for root, tag in ((live, "before"), (staged, "after")):
            d = tmp / tag; d.mkdir()
            subprocess.run([str(tool), "-o", "-f", "choice.prop", "54", str(root), str(d)],
                           check=True, capture_output=True)
        proc = subprocess.run([sys.executable, str(SCRIPTS / "ttprop_slots.py"), "--verify",
                               str(tmp / "before" / "choice.prop"), str(tmp / "after" / "choice.prop"),
                               "--charset", str(TWAU / "scripts")], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stdout)
        self.assertIn("verify: PASS", proc.stdout)


def _png(image, path):
    image.save(path)
    return path


if __name__ == "__main__":
    unittest.main()
