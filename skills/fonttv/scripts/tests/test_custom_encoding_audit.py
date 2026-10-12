"""Tests for custom_encoding_audit.py: capability boundary, adapter protocol, binding, evidence, waivers."""
from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import unicodedata
import unittest
from pathlib import Path

from ftvf_fixture import FTVF_ADAPTER, ORIGINAL, REMAPPED, TELLTALE_ADAPTER, VN_SLOTS, NOT_MEASURED, build, file_sha, write_evidence

HERE = Path(__file__).resolve().parent
SCRIPT = HERE.parent / "custom_encoding_audit.py"
sys.path.insert(0, str(HERE.parent))
from custom_encoding_audit import semantic_digest  # noqa: E402
FIX = HERE / "fixtures"
MAPPING = FIX / "vn128_excerpt.json"
LEGACY = FIX / "inventory_legacy_records.json"
EXTERNAL_B = FIX / "inventory_remapped.json"
FONT_A = FIX / "fixture-A-original-records.font"
FONT_B = FIX / "fixture-B-remapped.font"
TEXT = FIX / "roundtrip.txt"
FAKE = "ab" * 32


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def run(*args) -> tuple[int, dict]:
    proc = subprocess.run([sys.executable, str(SCRIPT), *map(str, args)], capture_output=True)
    return proc.returncode, json.loads(proc.stdout.decode("utf-8"))


def run_ext_a(*args):
    return run(*args, "--font-file", FONT_A, "--evidence-root", FIX)


def run_ext_b(*args):
    return run(*args, "--font-file", FONT_B, "--evidence-root", FIX)


def entry(result: dict, id_: int) -> dict:
    return next(row for row in result["entries"] if row["id"] == id_)


class TempDirCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def write_json(self, name: str, data) -> Path:
        path = self.tmp / name
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return path

    def inventory(self, source: Path = EXTERNAL_B) -> dict:
        return copy.deepcopy(json.loads(source.read_text(encoding="utf-8")))

    def mapping(self, entries=(("đ", 178),)) -> Path:
        return self.write_json("m.json", {"schema": "fonttv/encoding-map/v1",
                                          "entries": [{"char": c, "id": i} for c, i in entries]})

    def ftvf(self, records, name: str = "font.ftvf", native: str = "cp1252") -> Path:
        path = self.tmp / name
        path.write_bytes(build(records, native))
        return path

    def adapter_run(self, font: Path, *args, adapter: Path = FTVF_ADAPTER, pin: str | None = None, slots=None):
        extra = []
        if slots is not None:
            extra = ["--identity-evidence", f"build_manifest={write_evidence(self.tmp / 'bm.json', font.read_bytes(), slots)}"]
        return run(*args, "--adapter-script", adapter, "--adapter-sha256", pin or file_sha(adapter), "--font-file", font, *extra)

    def custom_adapter(self, body: str) -> Path:
        path = self.tmp / "adapter.py"
        path.write_text(
            "import argparse, hashlib, json, sys\nfrom pathlib import Path\n"
            "ap = argparse.ArgumentParser()\n"
            "for flag in ('--input', '--output', '--invocation-id', '--protocol'): ap.add_argument(flag)\n"
            "a = ap.parse_args()\ndata = Path(a.input).read_bytes()\ndigest = hashlib.sha256(data).hexdigest()\n"
            "adapter = {'name': 'custom', 'version': '1', 'supported': True, 'input_sha256': digest,\n"
            "           'inventory_method': 'test', 'capabilities': ['records', 'metrics', 'ink']}\n"
            "inv = {'schema': 'fonttv/font-inventory/v1', 'font': Path(a.input).name, 'sha256': digest, 'adapter': adapter,\n"
            "       'invocation': {'id': a.invocation_id, 'protocol': a.protocol}, 'lookup': 'hash',\n"
            "       'records': [{'id': 178, 'ink_pixels': 344, 'x_advance': 32}]}\n" + body, encoding="utf-8")
        return path


class AdapterExecutedTests(TempDirCase):
    """Only records re-derived by a pinned adapter in this run can reach mapping_verified."""

    def test_adapter_rederived_records_with_evidence_pass(self):
        font = self.ftvf(REMAPPED)
        code, result = self.adapter_run(font, "--mapping", MAPPING, "--text", TEXT, slots=VN_SLOTS)
        self.assertEqual((code, result["verdict"], result["proof_level"]), (0, "PASS", "mapping_verified"), result.get("errors"))
        self.assertEqual((result["inventory_origin"], result["records_rederived"], result["proof_cap"]),
                         ("adapter_executed", True, "mapping_verified"))
        ex = result["adapter_execution"]
        self.assertEqual((ex["exit_code"], ex["script_sha256"], ex["protocol"], ex["input_unchanged"]),
                         (0, file_sha(FTVF_ADAPTER), "fonttv-adapter/v1", True))
        self.assertRegex(ex["invocation_id"], r"^[0-9a-f]{32}$")
        self.assertEqual(result["inputs"]["inventory_sha256"], ex["generated_inventory_sha256"])
        self.assertTrue(any("build_manifest: evidence cli-0 verified" in n for n in entry(result, 178)["identity_evidence"]))
        self.assertTrue(any("python_codec:cp1252" in n for n in entry(result, 100)["identity_evidence"]))
        self.assertEqual(result["roundtrip"]["status"], "PASS")

    def test_each_run_gets_a_new_invocation_id(self):
        font = self.ftvf(REMAPPED)
        ids = {self.adapter_run(font, "--mapping", MAPPING, slots=VN_SLOTS)[1]["adapter_execution"]["invocation_id"] for _ in range(2)}
        self.assertEqual(len(ids), 2)

    def test_v7_original_bytes_fail_from_parsed_records(self):
        font = self.ftvf(ORIGINAL)
        code, result = self.adapter_run(font, "--mapping", MAPPING)
        self.assertEqual((code, result["verdict"]), (1, "FAIL"))
        row = entry(result, 178)
        self.assertEqual((row["record_present"], row["mapping_correct"], row["outline_nonempty"], row["actual_identity"]),
                         ("PASS", "FAIL", "FAIL", "²"))

    def test_evidence_cannot_create_records_or_ink(self):
        font = self.ftvf([r for r in ORIGINAL if r["id"] != 255])
        code, result = self.adapter_run(font, "--mapping", MAPPING, slots=VN_SLOTS)
        self.assertEqual(code, 1)
        self.assertEqual(entry(result, 255)["record_present"], "FAIL")
        self.assertEqual(entry(result, 178)["outline_nonempty"], "FAIL")

    def test_uv_without_measured_ink_is_incomplete(self):
        records = [dict(r, ink_pixels=NOT_MEASURED) if r["id"] == 178 else r for r in REMAPPED]
        code, result = self.adapter_run(self.ftvf(records), "--mapping", MAPPING, slots=VN_SLOTS)
        self.assertEqual((code, entry(result, 178)["ink_status"]), (4, "UV_ONLY"))

    def test_adapter_hash_mismatch_is_input_error(self):
        code, result = self.adapter_run(self.ftvf(REMAPPED), "--mapping", MAPPING, pin=FAKE)
        self.assertEqual((code, result["verdict"]), (2, "INPUT_ERROR"))
        self.assertIn("not the pinned", result["error"])

    def test_missing_adapter_is_input_error(self):
        code, result = self.adapter_run(self.ftvf(REMAPPED), "--mapping", MAPPING, adapter=self.tmp / "nope.py", pin=FAKE)
        self.assertEqual((code, result["verdict"]), (2, "INPUT_ERROR"))

    def test_adapter_nonzero_exit_fails(self):
        adapter = self.custom_adapter("sys.exit(1)\n")
        code, result = self.adapter_run(self.ftvf(REMAPPED), "--mapping", MAPPING, adapter=adapter)
        self.assertEqual((code, result["verdict"], result["adapter_execution"]["exit_code"]), (1, "FAIL", 1))

    def test_unsupported_format_is_not_supported(self):
        forged = self.tmp / "forged.font"
        forged.write_bytes(b"bytes do not contain any parseable font records")
        code, result = self.adapter_run(forged, "--mapping", MAPPING)
        self.assertEqual((code, result["verdict"]), (3, "NOT_SUPPORTED"))
        self.assertIn("magic mismatch", result["reason"])
        bad_version = self.tmp / "v2.ftvf"
        bad_version.write_bytes(build(REMAPPED, version=2))
        self.assertEqual(self.adapter_run(bad_version, "--mapping", MAPPING)[0], 3)

    def test_telltale_adapter_parses_real_v3_font(self):
        fixture_root = Path(os.environ.get("VIETHOA_FIXTURE_ROOT", "tests/fixtures/twau"))
        font = fixture_root / "build/fonts_patched/Rockwell_Std_Condensed_48_bold.font"
        if not font.is_file():
            self.skipTest("TWAU fixture not available")
        out = self.tmp / "inventory.json"
        proc = subprocess.run([sys.executable, str(TELLTALE_ADAPTER), "--input", str(font), "--output", str(out),
                               "--invocation-id", "twau-real", "--protocol", "fonttv-adapter/v1"], capture_output=True)
        self.assertEqual(proc.returncode, 0, proc.stderr.decode("utf-8", "replace"))
        inv = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(inv["adapter"]["name"], "telltale-5vsm")
        self.assertEqual(inv["invocation"]["id"], "twau-real")
        self.assertEqual(len(inv["records"]), 256)
        by_id = {row["id"]: row for row in inv["records"]}
        self.assertEqual(inv["adapter"]["metadata"]["texture_layout"], "collapsed_to_referenced_page")
        self.assertEqual(inv["adapter"]["metadata"]["page_heights"][0], 2048)
        self.assertGreater(by_id[178]["ink_pixels"], 0)
        self.assertGreater(by_id[143]["ink_pixels"], 0)
        self.assertEqual(by_id[178]["x_advance"], 32.0)

    def test_telltale_adapter_uses_descriptor_sizes_for_original_multipage_font(self):
        fixture_root = Path(os.environ.get("VIETHOA_FIXTURE_ROOT", "tests/fixtures/twau"))
        font = fixture_root / "all_fonts/Rockwell_Std_48_bold.font"
        if not font.is_file():
            self.skipTest("TWAU fixture not available")
        out = self.tmp / "inventory-original.json"
        proc = subprocess.run([sys.executable, str(TELLTALE_ADAPTER), "--input", str(font), "--output", str(out),
                               "--invocation-id", "twau-original", "--protocol", "fonttv-adapter/v1"], capture_output=True)
        self.assertEqual(proc.returncode, 0, proc.stderr.decode("utf-8", "replace"))
        inv = json.loads(out.read_text(encoding="utf-8"))
        meta = inv["adapter"]["metadata"]
        self.assertEqual(meta["texture_layout"], "descriptor_sized_pages")
        self.assertEqual(meta["page_heights"], [988, 228])

    def test_telltale_adapter_does_not_invent_ink_for_ambiguous_multipage_payload(self):
        fixture_root = Path(os.environ.get("VIETHOA_FIXTURE_ROOT", "tests/fixtures/twau"))
        font = fixture_root / "build/fonts_patched/Rockwell_Std_48_bold.font"
        if not font.is_file():
            self.skipTest("TWAU fixture not available")
        out = self.tmp / "inventory-ambiguous.json"
        proc = subprocess.run([sys.executable, str(TELLTALE_ADAPTER), "--input", str(font), "--output", str(out),
                               "--invocation-id", "twau-ambiguous", "--protocol", "fonttv-adapter/v1"], capture_output=True)
        self.assertEqual(proc.returncode, 0, proc.stderr.decode("utf-8", "replace"))
        inv = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(inv["adapter"]["metadata"]["texture_layout"], "ambiguous_multipage_no_ink")
        self.assertNotIn("ink", inv["adapter"]["capabilities"])
        self.assertTrue(all("ink_pixels" not in row for row in inv["records"]))

    def test_telltale_adapter_supports_non_512_single_page(self):
        fixture_root = Path(os.environ.get("VIETHOA_FIXTURE_ROOT", "tests/fixtures/twau"))
        font = fixture_root / "all_fonts/default.font"
        if not font.is_file():
            self.skipTest("TWAU fixture not available")
        out = self.tmp / "inventory-default.json"
        proc = subprocess.run([sys.executable, str(TELLTALE_ADAPTER), "--input", str(font), "--output", str(out),
                               "--invocation-id", "twau-default", "--protocol", "fonttv-adapter/v1"], capture_output=True)
        self.assertEqual(proc.returncode, 0, proc.stderr.decode("utf-8", "replace"))
        inv = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(inv["adapter"]["metadata"]["page_widths"], [256])
        self.assertEqual(inv["adapter"]["metadata"]["page_heights"], [256])
        self.assertIn("ink", inv["adapter"]["capabilities"])

    def test_telltale_adapter_rejects_truncated_stream(self):
        font = self.tmp / "Menu.font"
        font.write_bytes(b"5VSM" + bytes(60))
        code, result = self.adapter_run(font, "--mapping", MAPPING, adapter=TELLTALE_ADAPTER)
        self.assertNotEqual(code, 0)
        self.assertNotEqual(result.get("proof_level"), "mapping_verified")

    def test_output_without_schema_or_provenance_fails(self):
        for body in ("inv['schema'] = 'x'\n", "adapter['version'] = ''\n", "inv.pop('invocation')\n"):
            adapter = self.custom_adapter(body + "Path(a.output).write_text(json.dumps(inv))\n")
            code, result = self.adapter_run(self.ftvf(REMAPPED), "--mapping", self.mapping(), adapter=adapter)
            self.assertNotEqual(code, 0, body)
            self.assertNotEqual(result.get("proof_level"), "mapping_verified", body)

    def test_output_input_sha_other_than_font_fails(self):
        adapter = self.custom_adapter("adapter['input_sha256'] = inv['sha256'] = '" + FAKE + "'\n"
                                      "Path(a.output).write_text(json.dumps(inv))\n")
        code, result = self.adapter_run(self.ftvf(REMAPPED), "--mapping", self.mapping(), adapter=adapter, slots={178: "đ"})
        self.assertEqual((code, result["inventory"]["binding_status"]), (1, "FAIL"))

    def test_reusing_an_old_inventory_is_rejected(self):
        font = self.ftvf(REMAPPED)
        old = self.tmp / "old-inventory.json"
        adapter = self.custom_adapter("inv['invocation']['id'] = 'previous-run'\nPath(a.output).write_text(json.dumps(inv))\n")
        code, result = self.adapter_run(font, "--mapping", self.mapping(), adapter=adapter, slots={178: "đ"})
        self.assertEqual((code, result["verdict"]), (1, "FAIL"))
        self.assertIn("invocation id", result["error"])
        old.write_text("{}", encoding="utf-8")
        copier = self.custom_adapter(f"import shutil\nshutil.copyfile(r'{old}', a.output)\n")
        code, result = self.adapter_run(font, "--mapping", self.mapping(), adapter=copier, slots={178: "đ"})
        self.assertEqual(code, 1)
        self.assertNotEqual(result.get("proof_level"), "mapping_verified")

    def test_adapter_supplied_evidence_is_rejected(self):
        adapter = self.custom_adapter("inv['evidence'] = []\nPath(a.output).write_text(json.dumps(inv))\n")
        code, result = self.adapter_run(self.ftvf(REMAPPED), "--mapping", self.mapping(), adapter=adapter)
        self.assertEqual(code, 1)
        self.assertIn("must not carry identity evidence", result["error"])

    def test_adapter_modifying_input_fails(self):
        adapter = self.custom_adapter("Path(a.output).write_text(json.dumps(inv))\nPath(a.input).write_bytes(data + b'x')\n")
        code, result = self.adapter_run(self.ftvf(REMAPPED), "--mapping", self.mapping(), adapter=adapter)
        self.assertEqual((code, result["adapter_execution"]["input_unchanged"]), (1, False))

    def test_adapter_without_output_fails(self):
        adapter = self.custom_adapter("pass\n")
        code, result = self.adapter_run(self.ftvf(REMAPPED), "--mapping", self.mapping(), adapter=adapter)
        self.assertEqual(code, 1)
        self.assertIn("fresh inventory", result["error"])

    def test_evidence_for_other_font_is_unverified(self):
        font = self.ftvf(REMAPPED)
        other = write_evidence(self.tmp / "other.json", b"other bytes", {178: "đ"})
        code, result = run("--mapping", self.mapping(), "--adapter-script", FTVF_ADAPTER, "--adapter-sha256", file_sha(FTVF_ADAPTER),
                           "--font-file", font, "--identity-evidence", f"build_manifest={other}")
        self.assertEqual(code, 1, "native cp1252 still resolves 178 to '²'")
        self.assertEqual(result["inventory"]["evidence"][0]["status"], "WRONG_FONT")

    def test_evidence_contradicting_native_identity_of_parsed_bytes_fails(self):
        adapter = self.custom_adapter("adapter['native_encoding'] = {'name': 'cp1252', 'resolver': 'byte'}\n"
                                      "inv['records'][0].update(glyph_identity='²', identity_source=['native_encoding'])\n"
                                      "Path(a.output).write_text(json.dumps(inv))\n")
        code, result = self.adapter_run(self.ftvf(REMAPPED), "--mapping", self.mapping(), adapter=adapter, slots={178: "đ"})
        self.assertEqual((code, entry(result, 178)["mapping_correct"]), (1, "FAIL"))

    def test_conformance_reference_adapter_parses_what_fixture_wrote(self):
        font = self.ftvf(REMAPPED)
        out = self.tmp / "inv.json"
        proc = subprocess.run([sys.executable, str(FTVF_ADAPTER), "--input", str(font), "--output", str(out),
                               "--invocation-id", "abc", "--protocol", "fonttv-adapter/v1"], capture_output=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        inv = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual([(r["id"], r["x_advance"], r["ink_pixels"]) for r in inv["records"]],
                         [(r["id"], r["x_advance"], r["ink_pixels"]) for r in REMAPPED])
        self.assertEqual(inv["adapter"]["input_sha256"], file_sha(font))
        self.assertNotIn("glyph_identity", inv["records"][0])


class ExternalInventoryTests(TempDirCase):
    """External inventories are declarations: never mapping_verified, never exit 0 as a semantic audit."""

    def test_hermes_repro_forged_font_inventory_and_evidence(self):
        forged = self.tmp / "forged.font"
        forged.write_bytes(b"bytes do not contain any parseable font records")
        digest = file_sha(forged)
        evidence = write_evidence(self.tmp / "evidence.json", forged.read_bytes(), {178: "đ"})
        inv = self.write_json("inventory.json", {
            "schema": "fonttv/font-inventory/v1", "font": "forged.font", "sha256": digest, "lookup": "hash",
            "adapter": {"name": "forger", "version": "1", "supported": True, "input_sha256": digest,
                        "inventory_method": "typed by hand", "capabilities": ["records", "glyph_identity", "ink", "metrics"]},
            "evidence": [{"id": "bm", "type": "build_manifest", "path": "evidence.json", "sha256": file_sha(evidence)}],
            "records": [{"id": 178, "glyph_identity": "đ", "identity_source": ["build_manifest"], "identity_evidence": ["bm"],
                         "ink_pixels": 999, "x_advance": 32}]})
        code, result = run("--mapping", self.mapping(), "--inventory", inv, "--font-file", forged)
        self.assertEqual((code, result["verdict"], result["proof_level"]), (4, "INCOMPLETE", "inventory_only"))
        self.assertEqual((result["inventory_origin"], result["records_rederived"], result["proof_cap"]),
                         ("external", False, "inventory_only"))
        code, result = run("--mapping", self.mapping(), "--inventory", inv, "--font-file", forged,
                           "--accept-external-inventory-for-planning")
        self.assertEqual((code, result["verdict"], result["proof_level"]), (4, "PLANNING_ONLY", "inventory_only"))

    def test_fully_consistent_external_inventory_is_not_mapping_verified(self):
        code, result = run_ext_b("--mapping", MAPPING, "--inventory", EXTERNAL_B)
        self.assertEqual((code, result["verdict"], result["proof_level"]), (4, "INCOMPLETE", "inventory_only"))
        self.assertEqual(result["inventory"]["binding_status"], "PASS")
        self.assertTrue(any("external inventory is a declaration" in w for w in result["warnings"]))

    def test_identity_evidence_flag_is_for_adapter_runs_only(self):
        code, result = run_ext_b("--mapping", MAPPING, "--inventory", EXTERNAL_B, "--identity-evidence", f"build_manifest={MAPPING}")
        self.assertEqual(code, 2)

    def test_v7_legacy_records_still_fail(self):
        code, result = run_ext_a("--mapping", MAPPING, "--inventory", LEGACY)
        self.assertEqual((code, result["verdict"]), (1, "FAIL"))
        dcroat = entry(result, 178)
        self.assertEqual((dcroat["record_present"], dcroat["mapping_correct"], dcroat["outline_nonempty"]), ("PASS", "FAIL", "FAIL"))
        self.assertEqual(entry(result, 143)["mapping_correct"], "UNVERIFIED")
        self.assertTrue(any("0.57x base 'd'" in w for w in result["warnings"]))

    def test_roundtrip_and_encoder_drift(self):
        good = self.tmp / "encoded.bin"
        good.write_bytes(bytes([255, 32, 178, 32, 143, 32, 155, 32, 167, 32, 100, 117, 101]))
        code, result = run_ext_b("--mapping", MAPPING, "--inventory", EXTERNAL_B, "--text", TEXT, "--encoded", good)
        self.assertEqual((code, result["roundtrip"]["status"]), (4, "PASS"))
        self.assertTrue(result["roundtrip"]["nfd_input_same_ids"])
        drifted = self.tmp / "drifted.bin"
        drifted.write_bytes(bytes([208]) + good.read_bytes()[1:])
        code, result = run_ext_b("--mapping", MAPPING, "--inventory", EXTERNAL_B, "--text", TEXT, "--encoded", drifted)
        self.assertEqual((code, result["roundtrip"]["encoded_first_difference"]), (1, 0))
        code, legacy = run_ext_a("--mapping", MAPPING, "--inventory", LEGACY, "--text", TEXT)
        self.assertEqual(legacy["roundtrip"]["font_lookup_mismatches"][0], {"position": 0, "id": 255, "expected": "Đ", "actual": "ÿ"})

    def test_unencodable_character_fails(self):
        text = self.tmp / "t.txt"
        text.write_text("ơ", encoding="utf-8")
        code, result = run_ext_b("--mapping", MAPPING, "--inventory", EXTERNAL_B, "--text", text)
        self.assertEqual((code, result["roundtrip"]["unencodable"][0]["codepoints"]), (1, "U+01A1"))


class FontBindingTests(TempDirCase):
    def assert_not_verified(self, code, result):
        self.assertNotEqual(code, 0)
        self.assertNotEqual(result.get("proof_level"), "mapping_verified")

    def test_null_inventory_hash_fails(self):
        inv = self.inventory()
        inv["sha256"] = None
        code, result = run_ext_b("--mapping", MAPPING, "--inventory", self.write_json("inv.json", inv))
        self.assert_not_verified(code, result)
        self.assertEqual(code, 1)
        self.assertFalse(result["inventory"]["font_hash_matches"])

    def test_forged_inventory_hash_fails(self):
        inv = self.inventory()
        inv["sha256"] = inv["adapter"]["input_sha256"] = FAKE
        code, result = run_ext_b("--mapping", MAPPING, "--inventory", self.write_json("inv.json", inv))
        self.assertEqual(code, 1)

    def test_font_file_other_than_inventory_fails(self):
        code, result = run("--mapping", MAPPING, "--inventory", EXTERNAL_B, "--font-file", FONT_A, "--evidence-root", FIX)
        self.assertEqual(code, 1)

    def test_declared_hash_without_adapter_input_binding_fails(self):
        inv = self.inventory()
        del inv["adapter"]["input_sha256"]
        code, result = run_ext_b("--mapping", MAPPING, "--inventory", self.write_json("inv.json", inv))
        self.assertEqual((code, result["inventory"]["adapter_input_matches"]), (1, False))

    def test_missing_font_file_argument_is_input_error(self):
        code, result = run("--mapping", MAPPING, "--inventory", EXTERNAL_B)
        self.assertEqual((code, result["verdict"]), (2, "INPUT_ERROR"))

    def test_inventory_naming_another_font_fails(self):
        inv = self.inventory()
        inv["font"] = "Other_Font.font"
        code, result = run_ext_b("--mapping", MAPPING, "--inventory", self.write_json("inv.json", inv))
        self.assertEqual((code, result["inventory"]["name_consistent"]), (1, False))


class IdentityEvidenceTests(TempDirCase):
    """Evidence checks run in both origins; external results stay capped."""

    RECORD = {"id": 178, "glyph_identity": "đ", "identity_source": ["build_manifest"], "identity_evidence": ["bm"],
              "ink_pixels": 344, "x_advance": 32}

    def external(self, records, slots=None, native="cp1252"):
        font = self.tmp / "inline.font"
        font.write_bytes(b"inline font")
        adapter = {"name": "fixture", "version": "1", "supported": True, "input_sha256": sha(b"inline font"),
                   "inventory_method": "test", "capabilities": ["records", "glyph_identity", "ink", "metrics"]}
        if native:
            adapter["native_encoding"] = {"name": native, "resolver": "byte"}
        inv = {"schema": "fonttv/font-inventory/v1", "font": font.name, "sha256": sha(b"inline font"),
               "adapter": adapter, "lookup": "hash", "records": records}
        if slots is not None:
            ev = write_evidence(self.tmp / "manifest.json", b"inline font", slots)
            inv["evidence"] = [{"id": "bm", "type": "build_manifest", "path": "manifest.json", "sha256": file_sha(ev)}]
        return run("--mapping", self.mapping(), "--inventory", self.write_json("inv.json", inv), "--font-file", font,
                   "--evidence-root", self.tmp)

    def test_build_manifest_claim_without_artifact_is_unverified(self):
        code, result = self.external([{**self.RECORD, "identity_evidence": []}])
        self.assertEqual((code, entry(result, 178)["mapping_correct"]), (4, "UNVERIFIED"))

    def test_evidence_file_missing_or_tampered_is_unverified(self):
        write_evidence(self.tmp / "manifest.json", b"inline font", {178: "đ"})
        for mutate, status in ((lambda p: p.unlink(), "MISSING"), (lambda p: p.write_text("{}"), "HASH_MISMATCH")):
            font = self.tmp / "inline.font"
            font.write_bytes(b"inline font")
            ev = write_evidence(self.tmp / "manifest.json", b"inline font", {178: "đ"})
            inv = {"schema": "fonttv/font-inventory/v1", "font": font.name, "sha256": sha(b"inline font"), "lookup": "hash",
                   "adapter": {"name": "f", "version": "1", "supported": True, "input_sha256": sha(b"inline font"),
                               "inventory_method": "t", "capabilities": ["records", "glyph_identity", "ink", "metrics"]},
                   "evidence": [{"id": "bm", "type": "build_manifest", "path": "manifest.json", "sha256": file_sha(ev)}],
                   "records": [self.RECORD]}
            path = self.write_json("inv.json", inv)
            mutate(ev)
            code, result = run("--mapping", self.mapping(), "--inventory", path, "--font-file", font, "--evidence-root", self.tmp)
            self.assertEqual((code, result["inventory"]["evidence"][0]["status"]), (4, status))

    def test_evidence_contradicting_record_fails(self):
        code, result = self.external([self.RECORD], slots={178: "²"})
        self.assertEqual((code, entry(result, 178)["mapping_correct"]), (1, "FAIL"))

    def test_native_encoding_claim_contradicted_by_codec_fails(self):
        code, result = self.external([{**self.RECORD, "identity_source": ["native_encoding"]}])
        self.assertEqual((code, entry(result, 178)["mapping_correct"]), (1, "FAIL"))

    def test_ai_vision_alone_is_not_identity_proof(self):
        code, result = self.external([{**self.RECORD, "identity_source": ["ai_vision"]}], slots={178: "đ"})
        self.assertEqual((code, entry(result, 178)["mapping_correct"]), (4, "UNVERIFIED"))


class InventoryInvariantTests(TempDirCase):
    def test_duplicate_char_id_fails(self):
        inv = self.inventory()
        inv["records"].insert(10, dict(next(r for r in inv["records"] if r["id"] == 178)))
        code, result = run_ext_b("--mapping", MAPPING, "--inventory", self.write_json("dup.json", inv))
        self.assertEqual((code, result["inventory"]["duplicate_ids"]), (1, [178]))

    def test_unsorted_ids_fail_for_binary_search_in_adapter_output(self):
        font = self.ftvf(list(reversed(REMAPPED)))
        code, result = self.adapter_run(font, "--mapping", MAPPING, slots=VN_SLOTS)
        self.assertEqual((code, result["inventory"]["strictly_ascending"]), (1, False))

    def test_non_injective_mapping_fails(self):
        mapping = json.loads(MAPPING.read_text(encoding="utf-8"))
        mapping["entries"].append({"char": "ơ", "id": 178})
        code, result = self.adapter_run(self.ftvf(REMAPPED), "--mapping", self.write_json("map.json", mapping), slots=VN_SLOTS)
        self.assertEqual(code, 1)
        self.assertTrue(any("non_injective" in e for e in result["errors"]))


METRICS_WAIVER = {"id": 178, "check": "metrics_valid", "reason": "tight menu cell", "approved_by": "reviewer A",
                  "approver_type": "human", "scope": "x_advance on pause-menu font only"}


class WaiverPolicyTests(TempDirCase):
    def slot(self, **override):
        return self.ftvf([r if r["id"] != 178 else {**r, **override} for r in REMAPPED])

    def test_semantic_and_ink_waivers_are_input_errors(self):
        allow = self.write_json("allow.json", [{"id": 178, "check": "mapping_correct", "reason": "waive wrong"},
                                               {"id": 178, "check": "outline_nonempty", "reason": "waive empty"}])
        code, result = self.adapter_run(self.ftvf(ORIGINAL), "--mapping", MAPPING, "--allowlist", allow)
        self.assertEqual((code, result["verdict"], result["proof_level"]), (2, "INPUT_ERROR", None))
        for check in ("record_present", "mapping_correct", "outline_nonempty"):
            allow = self.write_json("allow.json", [METRICS_WAIVER | {"check": check}])
            self.assertEqual(self.adapter_run(self.ftvf(REMAPPED), "--mapping", MAPPING, "--allowlist", allow, slots=VN_SLOTS)[0], 2)

    def test_metrics_waiver_needs_approver_scope_and_human(self):
        for field, value in (("approved_by", None), ("scope", " "), ("reason", ""), ("approver_type", "ai")):
            waiver = dict(METRICS_WAIVER)
            if value is None:
                waiver.pop(field)
            else:
                waiver[field] = value
            code, _ = self.adapter_run(self.slot(x_advance=0), "--mapping", MAPPING,
                                       "--allowlist", self.write_json("a.json", [waiver]), slots=VN_SLOTS)
            self.assertEqual(code, 2, field)

    def test_full_metrics_waiver_is_kept_in_the_report(self):
        code, result = self.adapter_run(self.slot(x_advance=0), "--mapping", MAPPING,
                                        "--allowlist", self.write_json("a.json", [METRICS_WAIVER]), slots=VN_SLOTS)
        self.assertEqual((code, result["proof_level"]), (0, "mapping_verified"), result.get("errors"))
        row = entry(result, 178)
        self.assertEqual((row["metrics_valid"], row["metrics_valid_original"]), ("WAIVED", "FAIL"))
        waived = result["waived"][0]
        self.assertEqual((waived["approved_by"], waived["scope"], waived["was"]), ("reviewer A", "x_advance on pause-menu font only", "FAIL"))

    def test_metrics_waiver_cannot_rescue_wrong_identity(self):
        code, result = self.adapter_run(self.ftvf([{**r, "x_advance": 0} if r["id"] == 178 else r for r in ORIGINAL]),
                                        "--mapping", MAPPING, "--allowlist", self.write_json("a.json", [METRICS_WAIVER]))
        self.assertEqual((code, result["verdict"]), (1, "FAIL"))

    def test_unused_waiver_is_reported(self):
        code, result = self.adapter_run(self.ftvf(REMAPPED), "--mapping", MAPPING,
                                        "--allowlist", self.write_json("a.json", [METRICS_WAIVER]), slots=VN_SLOTS)
        self.assertEqual((code, result["waived"]), (0, []))
        self.assertTrue(any("unused waiver" in w for w in result["warnings"]))


class ContractVariantTests(TempDirCase):
    def test_cp1258_codec_encodes_base_plus_combining(self):
        records = []
        for byte in range(256):
            try:
                char = bytes([byte]).decode("cp1258")
            except UnicodeDecodeError:
                continue
            if unicodedata.category(char) != "Cc":
                records.append({"id": byte, "ink_pixels": 0 if char.isspace() else 100,
                                "x_advance": 0 if unicodedata.combining(char) else 20})
        font = self.ftvf(records, native="cp1258")
        text = self.tmp / "t.txt"
        text.write_text("Việt Nam", encoding="utf-8")
        encoded = self.tmp / "e.bin"
        encoded.write_bytes(bytes([0x56, 0x69, 0xEA, 0xF2, 0x74, 0x20, 0x4E, 0x61, 0x6D]))
        code, result = self.adapter_run(font, "--codec", "cp1258", "--text", text, "--encoded", encoded)
        self.assertEqual((code, result["proof_level"]), (0, "mapping_verified"), (result.get("errors"), result.get("roundtrip")))
        self.assertEqual(result["encoding_contract"]["compose_policy"], "base_plus_combining")

    def test_multi_byte_sequence_mapping(self):
        mapping = self.write_json("m.json", {"schema": "fonttv/encoding-map/v1", "passthrough": "ascii_printable",
                                             "entries": [{"char": "á", "ids": [97, 249], "glyphs": ["a", "\u0301"]}]})
        font = self.ftvf([{"id": 97, "x_advance": 20, "ink_pixels": 90}, {"id": 249, "x_advance": 0, "ink_pixels": 12}])
        text = self.tmp / "t.txt"
        text.write_text("á", encoding="utf-8")
        code, result = self.adapter_run(font, "--mapping", mapping, "--text", text, slots={249: "\u0301"})
        self.assertEqual(code, 0, result.get("roundtrip"))
        self.assertEqual({row["id"] for row in result["entries"]}, {97, 249})


class DigestStabilityTests(TempDirCase):
    """The stored-report digest must not move when the same run is spelled differently.

    TWAU: the same font audited with an absolute corpus path and with a relative
    one produced different digests, so proof_level_check reported "stale report"
    for a byte-identical rerun. A proof must not depend on where the project sits.
    """

    def _run(self, cwd: Path, mapping, font, text, encoded) -> dict:
        cmd = [sys.executable, str(SCRIPT), "--mapping", str(mapping),
               "--adapter-script", str(FTVF_ADAPTER), "--adapter-sha256", file_sha(FTVF_ADAPTER),
               "--font-file", str(font), "--text", str(text), "--encoded", str(encoded)]
        proc = subprocess.run(cmd, capture_output=True, cwd=str(cwd))
        return json.loads(proc.stdout.decode("utf-8"))

    def test_digest_is_independent_of_path_spelling(self):
        font = self.ftvf(REMAPPED)
        text = self.tmp / "corpus.txt"
        text.write_text("đ", encoding="utf-8")
        encoded = self.tmp / "corpus.bin"
        encoded.write_bytes(b"\xb2")
        mapping = self.mapping()
        absolute = self._run(self.tmp, mapping, font, text, encoded)
        relative = self._run(self.tmp, mapping.name, font.name, text.name, encoded.name)
        # The two runs were genuinely spelled differently ...
        self.assertEqual(absolute["roundtrip"]["text_file"], str(text))
        self.assertEqual(relative["roundtrip"]["text_file"], text.name)
        # ... and the digest ignores that, because it is a proof and not a log.
        self.assertEqual(semantic_digest(absolute), semantic_digest(relative))

    def test_digest_still_moves_when_content_changes(self):
        font = self.ftvf(REMAPPED)
        text = self.tmp / "corpus.txt"
        text.write_text("đ", encoding="utf-8")
        encoded = self.tmp / "corpus.bin"
        encoded.write_bytes(b"\xb2")
        mapping = self.mapping()
        first = self._run(self.tmp, mapping, font, text, encoded)
        text.write_text("đđ", encoding="utf-8")
        second = self._run(self.tmp, mapping, font, text, encoded)
        self.assertNotEqual(semantic_digest(first), semantic_digest(second))


class FailClosedTests(TempDirCase):
    def test_unsupported_external_adapter_block_is_not_supported(self):
        inv = {"schema": "fonttv/font-inventory/v1", "adapter": {"name": "telltale", "supported": False, "reason": "unknown header"}, "records": []}
        self.assertEqual(run_ext_b("--mapping", MAPPING, "--inventory", self.write_json("u.json", inv))[0], 3)

    def test_unknown_inventory_schema_is_not_supported(self):
        self.assertEqual(run_ext_b("--mapping", MAPPING, "--inventory", self.write_json("s.json", {"schema": "x"}))[0], 3)

    def test_missing_inputs_are_input_errors(self):
        self.assertEqual(run_ext_b("--mapping", MAPPING, "--inventory", self.tmp / "missing.json")[0], 2)
        self.assertEqual(run("--mapping", MAPPING, "--inventory", EXTERNAL_B, "--font-file", self.tmp / "missing.font")[0], 2)

    def test_refuses_to_overwrite_input(self):
        target = self.write_json("inv.json", self.inventory())
        proc = subprocess.run([sys.executable, str(SCRIPT), "--mapping", str(MAPPING), "--inventory", str(target),
                               "--font-file", str(FONT_B), "--output", str(target)], capture_output=True)
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(json.loads(target.read_text(encoding="utf-8"))["schema"], "fonttv/font-inventory/v1")

    def test_no_shell_or_dynamic_code_in_implementation(self):
        banned = re.compile(r"shell\s*=\s*True|os\.system|os\.popen|\beval\(|\bexec\(|subprocess\.getoutput|subprocess\.getstatusoutput")
        sources = [p for p in HERE.parent.rglob("*.py") if "tests" not in p.parts]
        self.assertGreaterEqual(len(sources), 9)
        hits = [f"{p.name}:{n}" for p in sources for n, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1)
                if banned.search(line)]
        self.assertEqual(hits, [])


if __name__ == "__main__":
    unittest.main()
