"""Tests for proof_level_check.py: only real, hash-matching artifacts raise the proof level."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "proof_level_check.py"
TEMPLATE = Path(__file__).resolve().parents[2] / "templates" / "manifest.template.json"
GATES = ("coverage", "outline_ink", "metrics", "structural_validator", "semantic_mapping", "preservation_diff")
FAKE = "ab" * 32


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class Evidence:
    """Evidence tree whose semantic report was produced by a real adapter run.

    The stored report is a cache. proof_level_check --verify-files re-executes
    the same adapter, so this fixture has to be a font that adapter can parse.
    """

    def __init__(self, root: Path, output: bytes | None = None):
        from ftvf_fixture import FTVF_ADAPTER, REMAPPED, build, file_sha, write_evidence
        self.root = root
        self.adapter = FTVF_ADAPTER
        self.adapter_sha = file_sha(FTVF_ADAPTER)
        self.original = b"original font bytes"
        self.output = build(REMAPPED) if output is None else output
        self.out = sha(self.output)
        self.mapping = self.write("contract/vn128.json", json.dumps(
            {"schema": "fonttv/encoding-map/v1", "entries": [{"char": "đ", "id": 178}]}).encode())
        self.write("build/Menu.font", self.output)
        self.write("readback/Menu.font", self.output)
        evidence = write_evidence(root / "build/glyph-manifest.json", self.output, {178: "đ"})
        self.evidence = "build/glyph-manifest.json"
        self.evidence_sha = file_sha(evidence)
        self.shot = self.write("proof/pause.png", b"png bytes")
        self.rights = self.write("LICENSE_AUDIT.md", b"rights verified")
        self.clean = self.write("qa/clean_install.json", b'{"ok": true}')
        self.rollback = self.write("qa/rollback.json", b'{"ok": true}')
        self.sign = [self.write(f"signoff/{r}.json", r.encode()) for r in ("reader", "typo")]
        self.reports = {g: self.write(f"qa/{g}.json", self.audit_report(g)) for g in GATES if g != "semantic_mapping"}
        proc = subprocess.run([sys.executable, str(SCRIPT.parent / "custom_encoding_audit.py"),
                               "--mapping", str(root / "contract/vn128.json"),
                               "--adapter-script", str(FTVF_ADAPTER), "--adapter-sha256", self.adapter_sha,
                               "--font-file", str(root / "build/Menu.font"),
                               "--identity-evidence", f"build_manifest={evidence}",
                               "--output", str(root / "qa/semantic_mapping.json")], capture_output=True)
        if proc.returncode != 0:
            raise RuntimeError(proc.stdout.decode("utf-8", "replace")[:1500])
        self.reports["semantic_mapping"] = sha((root / "qa/semantic_mapping.json").read_bytes())

    def write(self, rel: str, data: bytes) -> str:
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return sha(data)

    def audit_report(self, gate: str, **override) -> bytes:
        report = {"schema": "fonttv/custom-encoding-audit/v1", "verdict": "PASS", "proof_level": "mapping_verified",
                  "identity_evidence_policy": "fonttv/identity-evidence/v2",
                  "inputs": {"mapping_sha256": self.mapping, "font_sha256": self.out},
                  "inventory": {"declared_font_sha256": self.out, "font_hash_matches": True,
                                "adapter_input_matches": True, "binding_status": "PASS"},
                  "inventory_origin": "adapter_executed", "records_rederived": True,
                  "adapter_execution": {"protocol": "fonttv-adapter/v1", "script_sha256": "cd" * 32,
                                        "invocation_id": "0f" * 16, "exit_code": 0,
                                        "generated_inventory_sha256": "ef" * 32, "input_unchanged": True}}
        report.update(override)
        return json.dumps({**report, "gate": gate}).encode()

    def manifest(self, claimed: str = "runtime_verified") -> dict:
        gates = [{"gate": g, "status": "PASS", "font_sha256": self.out, "report": f"qa/{g}.json",
                  "report_sha256": self.reports[g]} for g in GATES]
        gates[4]["mapping_sha256"] = self.mapping
        return {
            "schema": "fonttv/manifest/v1", "project": "fixture", "status": "NEEDS_REVIEW",
            "claimed_proof_level": claimed, "build": {"build_id": "build-1"},
            "encoding": {"mapping_source": "contract/vn128.json", "mapping_sha256": self.mapping,
                         "adapter_path": str(self.adapter), "adapter_sha256": self.adapter_sha,
                         "identity_evidence": [{"type": "build_manifest", "path": self.evidence, "sha256": self.evidence_sha}]},
            "rights": {"modification": "verified", "redistribution": "not_distributed",
                       "evidence": "LICENSE_AUDIT.md", "evidence_sha256": self.rights},
            "fonts": [{
                "name": "Menu.font", "consumer": "pause menu", "route": "B_custom_encoding",
                "input_sha256": sha(self.original), "output_sha256": self.out, "output_path": "build/Menu.font",
                "change": "remapped", "gates": gates,
                "archive": {"container": "ui.archive", "readback_method": "extract from live container",
                            "readback_path": "readback/Menu.font", "readback_sha256": self.out},
                "runtime": {"build_id": "build-1", "reviewer_type": "human", "verdict": "PASS",
                            "screenshots": [{"path": "proof/pause.png", "sha256": self.shot, "font_sha256": self.out}]},
            }],
            "release": {
                "clean_install": {"status": "PASS", "report": "qa/clean_install.json", "report_sha256": self.clean},
                "rollback": {"status": "PASS", "report": "qa/rollback.json", "report_sha256": self.rollback},
                "signoff": [
                    {"role": "vietnamese_reader", "reviewer_type": "human", "sha256": [self.out],
                     "record": "signoff/reader.json", "record_sha256": self.sign[0]},
                    {"role": "typography_reviewer", "reviewer_type": "human", "sha256": [self.out],
                     "record": "signoff/typo.json", "record_sha256": self.sign[1]}]},
        }


class Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.ev = Evidence(self.tmp / "evidence")

    def tearDown(self):
        self._tmp.cleanup()

    def check(self, data: dict, verify: bool = True) -> tuple[int, dict]:
        path = self.tmp / "manifest.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        args = [sys.executable, str(SCRIPT), str(path)] + (["--verify-files", str(self.ev.root)] if verify else [])
        proc = subprocess.run(args, capture_output=True)
        return proc.returncode, json.loads(proc.stdout.decode("utf-8"))

    def font(self, data: dict) -> dict:
        return data["fonts"][0]

    def gate(self, data: dict, name: str) -> dict:
        return next(g for g in self.font(data)["gates"] if g["gate"] == name)


class VerifiedEvidenceTests(Base):
    def test_all_files_real_and_matching_pass(self):
        code, result = self.check(self.ev.manifest())
        self.assertEqual((code, result["justified_proof_level"], result["evidence_mode"]),
                         (0, "release_verified", "files_rehashed"), result)
        self.assertGreaterEqual(result["rehashed_artifacts"], 14)
        code, result = self.check(self.ev.manifest("release_verified") | {"status": "APPROVED"})
        self.assertEqual((code, result["justified_proof_level"]), (0, "release_verified"), result)

    def test_hermes_repro_all_evidence_missing_fails(self):
        data = {
            "schema": "fonttv/manifest/v1", "claimed_proof_level": "runtime_verified",
            "encoding": {"mapping_source": "missing-map.json", "mapping_sha256": FAKE},
            "fonts": [{
                "name": "x.font", "route": "B_custom_encoding", "input_sha256": FAKE, "output_sha256": FAKE,
                "output_path": "missing.font", "change": "remapped",
                "gates": [{"gate": g, "status": "PASS", "font_sha256": FAKE, "report": f"missing-{g}.json",
                           "report_sha256": FAKE, "mapping_sha256": FAKE} for g in GATES],
                "archive": {"container": "c", "readback_method": "m", "readback_path": "missing-readback.font", "readback_sha256": FAKE},
                "runtime": {"build_id": "b", "reviewer_type": "human", "verdict": "PASS",
                            "screenshots": [{"path": "missing.png", "sha256": FAKE, "font_sha256": FAKE}]}}]}
        code, result = self.check(data)
        self.assertEqual((code, result["verdict"], result["justified_proof_level"]), (1, "FAIL", "inventory_only"))
        self.assertTrue(any("missing.font missing" in e for e in result["errors"]))

    def test_missing_output_fails(self):
        (self.ev.root / "build/Menu.font").unlink()
        code, result = self.check(self.ev.manifest())
        self.assertEqual((code, result["justified_proof_level"]), (1, "inventory_only"))

    def test_missing_gate_report_is_not_pass(self):
        (self.ev.root / "qa/metrics.json").unlink()
        code, result = self.check(self.ev.manifest("structurally_verified"))
        self.assertEqual((code, result["justified_proof_level"]), (1, "inventory_only"))
        self.assertTrue(any("metrics report: file missing" in b for b in result["per_font"][0]["blockers"]))

    def test_gate_report_hash_mismatch_fails(self):
        (self.ev.root / "qa/coverage.json").write_bytes(b"tampered")
        code, result = self.check(self.ev.manifest("structurally_verified"))
        self.assertEqual(code, 1)
        self.assertTrue(any("coverage report" in e and "hashes to" in e for e in result["errors"]))

    def test_semantic_report_with_other_mapping_or_verdict_fails(self):
        bound = {"font_hash_matches": True, "adapter_input_matches": True, "binding_status": "PASS"}
        for override in ({"inputs": {"mapping_sha256": FAKE, "font_sha256": self.ev.out}}, {"verdict": "FAIL"},
                         {"proof_level": "structurally_verified"},
                         {"inventory": {"declared_font_sha256": FAKE, **bound}},
                         {"inputs": {"mapping_sha256": self.ev.mapping, "font_sha256": FAKE}},
                         {"inventory": {"declared_font_sha256": self.ev.out, **bound, "adapter_input_matches": False}},
                         {"identity_evidence_policy": None}):
            ev = Evidence(self.tmp / f"ev-{len(list(self.tmp.iterdir()))}")
            ev.reports["semantic_mapping"] = ev.write("qa/semantic_mapping.json", ev.audit_report("semantic_mapping", **override))
            self.ev = ev
            code, result = self.check(ev.manifest("mapping_verified"))
            self.assertEqual((code, result["justified_proof_level"]), (1, "structurally_verified"), override)

    def test_semantic_gate_bound_to_other_mapping_hash_fails(self):
        data = self.ev.manifest("mapping_verified")
        self.gate(data, "semantic_mapping")["mapping_sha256"] = FAKE
        code, result = self.check(data)
        self.assertEqual((code, result["justified_proof_level"]), (1, "structurally_verified"))

    def test_route_b_without_encoding_contract_is_not_mapping_verified(self):
        data = self.ev.manifest("mapping_verified")
        data["encoding"] = {"mapping_source": "contract/vn128.json"}
        code, result = self.check(data)
        self.assertEqual((code, result["justified_proof_level"]), (1, "inventory_only"))

    def test_missing_screenshot_blocks_runtime(self):
        (self.ev.root / "proof/pause.png").unlink()
        code, result = self.check(self.ev.manifest())
        self.assertEqual((code, result["justified_proof_level"]), (1, "archive_verified"))

    def test_screenshot_hash_mismatch_blocks_runtime(self):
        (self.ev.root / "proof/pause.png").write_bytes(b"other image")
        code, result = self.check(self.ev.manifest())
        self.assertEqual((code, result["justified_proof_level"]), (1, "archive_verified"))

    def test_screenshot_without_path_blocks_runtime(self):
        data = self.ev.manifest()
        del self.font(data)["runtime"]["screenshots"][0]["path"]
        code, result = self.check(data)
        self.assertEqual((code, result["justified_proof_level"]), (1, "archive_verified"))

    def test_missing_readback_blocks_archive(self):
        (self.ev.root / "readback/Menu.font").unlink()
        code, result = self.check(self.ev.manifest("archive_verified"))
        self.assertEqual((code, result["justified_proof_level"]), (1, "mapping_verified"))

    def test_readback_file_differs_from_output_blocks_archive(self):
        (self.ev.root / "readback/Menu.font").write_bytes(self.ev.original)
        code, result = self.check(self.ev.manifest("archive_verified"))
        self.assertEqual((code, result["justified_proof_level"]), (1, "mapping_verified"))
        data = self.ev.manifest("archive_verified")
        self.font(data)["archive"]["readback_sha256"] = sha(self.ev.original)
        code, result = self.check(data)
        self.assertEqual((code, result["justified_proof_level"]), (1, "mapping_verified"))
        self.assertTrue(any("live container differ" in e for e in result["errors"]))

    def test_container_metadata_hash_is_verified_when_path_given(self):
        data = self.ev.manifest()
        self.font(data)["archive"].update({"container_path": "readback/Menu.font", "container_sha256_after": FAKE})
        code, result = self.check(data)
        self.assertEqual(code, 1)
        self.assertTrue(any("archive container (metadata)" in e for e in result["errors"]))


AUDIT = SCRIPT.parent / "custom_encoding_audit.py"


class EndToEndBindingTests(Base):
    """Run the real custom_encoding_audit.py, feed its report to the proof checker."""

    def audit_into_manifest(self, inventory: dict) -> tuple[int, dict, dict]:
        root = self.ev.root
        (root / "inventory.json").write_text(json.dumps(inventory, ensure_ascii=False), encoding="utf-8")
        proc = subprocess.run([sys.executable, str(AUDIT), "--mapping", str(root / "contract/vn128.json"),
                               "--inventory", str(root / "inventory.json"), "--font-file", str(root / "build/Menu.font"),
                               "--evidence-root", str(root), "--output", str(root / "qa/semantic_mapping.json")],
                              capture_output=True)
        report = json.loads(proc.stdout.decode("utf-8"))
        self.ev.reports["semantic_mapping"] = sha((root / "qa/semantic_mapping.json").read_bytes())
        return proc.returncode, report, self.ev.manifest()

    def inventory(self, **adapter) -> dict:
        return {"schema": "fonttv/font-inventory/v1", "font": "Menu.font", "sha256": self.ev.out, "lookup": "hash",
                "adapter": {"name": "forger", "version": "1", "inventory_method": "typed by hand", "supported": True,
                            "capabilities": ["records", "glyph_identity", "ink", "metrics"], **adapter},
                "records": [{"id": 178, "glyph_identity": "đ", "identity_source": ["build_manifest"],
                             "ink_pixels": 344, "x_advance": 32}]}

    def test_hermes_repro_forged_inventory_never_reaches_mapping_or_runtime(self):
        code, report, manifest = self.audit_into_manifest(self.inventory())
        self.assertEqual((code, report["verdict"], report["proof_level"]), (1, "FAIL", "inventory_only"))
        code, result = self.check(manifest)
        self.assertEqual((code, result["justified_proof_level"]), (1, "structurally_verified"))
        self.assertTrue(result["errors"])

    def test_forged_inventory_with_copied_input_hash_but_no_evidence_is_rejected(self):
        code, report, manifest = self.audit_into_manifest(self.inventory(input_sha256=self.ev.out))
        self.assertEqual((code, report["verdict"], report["proof_level"]), (4, "INCOMPLETE", "inventory_only"))
        code, result = self.check(manifest)
        self.assertEqual((code, result["justified_proof_level"]), (1, "structurally_verified"))

    def test_hermes_repro_forged_font_inventory_and_real_evidence_never_mapping_verified(self):
        data = json.dumps({"schema": "fonttv/glyph-evidence/v1", "type": "build_manifest",
                           "font_sha256": self.ev.out, "slots": {"178": "đ"}}).encode()
        manifest_sha = self.ev.write("build/glyph-manifest.json", data)
        inventory = self.inventory(input_sha256=self.ev.out)
        inventory["evidence"] = [{"id": "bm", "type": "build_manifest", "path": "build/glyph-manifest.json", "sha256": manifest_sha}]
        inventory["records"][0]["identity_evidence"] = ["bm"]
        code, report, manifest = self.audit_into_manifest(inventory)
        self.assertEqual((code, report["verdict"], report["proof_level"], report["records_rederived"]),
                         (4, "INCOMPLETE", "inventory_only", False))
        code, result = self.check(manifest)
        self.assertEqual((code, result["justified_proof_level"]), (1, "inventory_only"))
        self.assertTrue(result["errors"])

    def test_adapter_executed_report_on_real_ftvf_output_is_accepted(self):
        from ftvf_fixture import FTVF_ADAPTER, REMAPPED, VN_SLOTS, build, file_sha, write_evidence
        self.ev = Evidence(self.tmp / "ftvf", output=build(REMAPPED))
        root = self.ev.root
        evidence = write_evidence(root / "build/glyph-manifest.json", self.ev.output, VN_SLOTS)
        proc = subprocess.run([sys.executable, str(AUDIT), "--mapping", str(root / "contract/vn128.json"),
                               "--adapter-script", str(FTVF_ADAPTER), "--adapter-sha256", file_sha(FTVF_ADAPTER),
                               "--font-file", str(root / "build/Menu.font"), "--identity-evidence", f"build_manifest={evidence}",
                               "--output", str(root / "qa/semantic_mapping.json")], capture_output=True)
        report = json.loads(proc.stdout.decode("utf-8"))
        self.assertEqual((proc.returncode, report["proof_level"], report["inventory_origin"]),
                         (0, "mapping_verified", "adapter_executed"), report.get("errors"))
        real = (root / "qa/semantic_mapping.json").read_bytes()
        for gate in GATES:
            self.ev.reports[gate] = self.ev.write(f"qa/{gate}.json", real)
        manifest = self.ev.manifest()
        manifest["encoding"]["adapter_path"] = str(FTVF_ADAPTER)
        manifest["encoding"]["adapter_sha256"] = file_sha(FTVF_ADAPTER)
        manifest["encoding"]["identity_evidence"][0]["sha256"] = file_sha(evidence)
        code, result = self.check(manifest)
        self.assertEqual((code, result["justified_proof_level"], result["semantic_reexecution"], result["adapter_reexecuted"]),
                         (0, "release_verified", True, True), result)
        self.assertTrue(result["report_file_rehashed"])
        self.assertEqual(result["reexecution"]["exit_code"], 0)
        manifest["encoding"]["adapter_sha256"] = FAKE
        code, result = self.check(manifest)
        self.assertEqual((code, result["justified_proof_level"]), (1, "inventory_only"))

    def test_v052_report_without_execution_binding_is_capped(self):
        report = json.loads(self.ev.audit_report("semantic_mapping"))
        for key in ("inventory_origin", "records_rederived", "adapter_execution"):
            report.pop(key)
        self.ev.reports["semantic_mapping"] = self.ev.write("qa/semantic_mapping.json", json.dumps(report).encode())
        code, result = self.check(self.ev.manifest("mapping_verified"))
        self.assertEqual((code, result["justified_proof_level"]), (1, "structurally_verified"))
        self.assertTrue(any("not re-derived" in e or "digest differs" in e for e in result["errors"]))

    def test_external_origin_report_is_capped_even_if_it_claims_pass(self):
        report = json.loads(self.ev.audit_report("semantic_mapping"))
        report.update(inventory_origin="external", records_rederived=False)
        self.ev.reports["semantic_mapping"] = self.ev.write("qa/semantic_mapping.json", json.dumps(report).encode())
        code, result = self.check(self.ev.manifest("mapping_verified"))
        self.assertEqual((code, result["justified_proof_level"]), (1, "structurally_verified"))

    def test_execution_record_missing_fields_is_rejected(self):
        for field, value in (("exit_code", 1), ("input_unchanged", False), ("script_sha256", None), ("invocation_id", "")):
            report = json.loads(self.ev.audit_report("semantic_mapping"))
            report["adapter_execution"][field] = value
            self.ev.reports["semantic_mapping"] = self.ev.write("qa/semantic_mapping.json", json.dumps(report).encode())
            code, result = self.check(self.ev.manifest("mapping_verified"))
            self.assertEqual((code, result["justified_proof_level"]), (1, "structurally_verified"), field)

    def test_pre_binding_report_format_is_rejected(self):
        legacy = {"schema": "fonttv/custom-encoding-audit/v1", "verdict": "PASS", "proof_level": "mapping_verified",
                  "inputs": {"mapping_sha256": self.ev.mapping}, "inventory": {"font_sha256": self.ev.out}}
        self.ev.reports["semantic_mapping"] = self.ev.write("qa/semantic_mapping.json", json.dumps(legacy).encode())
        code, result = self.check(self.ev.manifest("mapping_verified"))
        self.assertEqual((code, result["justified_proof_level"]), (1, "structurally_verified"))
        self.assertTrue(any("did not hash the output font itself" in e or "digest differs" in e for e in result["errors"]))


class DeclaredConsistencyTests(Base):
    def test_without_verify_files_claims_above_inventory_fail(self):
        code, result = self.check(self.ev.manifest(), verify=False)
        self.assertEqual((code, result["evidence_mode"], result["rehashed_artifacts"]), (1, "declared_only", 0))
        self.assertEqual((result["justified_proof_level"], result["declared_consistent_level"]),
                         ("inventory_only", "release_verified"))
        self.assertTrue(any("capped at inventory_only" in w for w in result["warnings"]))
        code, result = self.check(self.ev.manifest("inventory_only"), verify=False)
        self.assertEqual(code, 0)

    def test_hermes_repro_without_verify_files_is_not_runtime_verified(self):
        data = self.ev.manifest()
        for g in self.font(data)["gates"]:
            g["report"] = f"missing-{g['gate']}.json"
        code, result = self.check(data, verify=False)
        self.assertEqual((code, result["justified_proof_level"]), (1, "inventory_only"))

    def test_pass_status_without_report_does_not_count(self):
        data = self.ev.manifest("structurally_verified")
        del self.gate(data, "coverage")["report"]
        code, result = self.check(data)
        self.assertEqual((code, result["justified_proof_level"]), (1, "inventory_only"))
        code, result = self.check(data, verify=False)
        self.assertEqual(result["declared_consistent_level"], "inventory_only")

    def test_metrics_waiver_needs_approver_and_scope(self):
        data = self.ev.manifest("structurally_verified")
        self.gate(data, "metrics").update({"status": "WAIVED", "reason": "tight cell", "approver_type": "human"})
        code, result = self.check(data)
        self.assertEqual((code, result["justified_proof_level"]), (1, "inventory_only"))
        self.gate(data, "metrics").update({"approved_by": "reviewer A", "scope": "x_advance, pause menu"})
        code, result = self.check(data)
        self.assertEqual(code, 0, result)
        self.assertNotEqual(result["justified_proof_level"], "inventory_only")
        self.assertTrue(any("WAIVED by reviewer A" in w for w in result["warnings"]))

    def test_structural_validator_cannot_be_waived(self):
        data = self.ev.manifest("structurally_verified")
        self.gate(data, "structural_validator").update({"status": "WAIVED", "reason": "r", "approved_by": "a",
                                                       "approver_type": "human", "scope": "s"})
        code, result = self.check(data)
        self.assertEqual((code, result["justified_proof_level"]), (1, "inventory_only"))

    def test_v7_style_preserved_original_without_semantic_proof_fails(self):
        data = self.ev.manifest("structurally_verified")
        font = self.font(data)
        font.update({"change": "unchanged", "output_sha256": font["input_sha256"]})
        self.gate(data, "semantic_mapping")["status"] = "NOT_RUN"
        code, result = self.check(data, verify=False)
        self.assertEqual(code, 1)
        self.assertTrue(any("record presence is not mapping correctness" in e for e in result["errors"]))

    def test_ai_only_review_caps_at_archive_verified(self):
        data = self.ev.manifest()
        self.font(data)["runtime"]["reviewer_type"] = "ai"
        code, result = self.check(data)
        self.assertEqual((code, result["justified_proof_level"], result["overclaim"]), (1, "archive_verified", True))

    def test_runtime_on_other_build_does_not_count(self):
        data = self.ev.manifest()
        self.font(data)["runtime"]["build_id"] = "build-0"
        code, result = self.check(data)
        self.assertEqual((code, result["justified_proof_level"]), (1, "archive_verified"))

    def test_not_run_validator_is_not_pass(self):
        data = self.ev.manifest("inventory_only")
        self.gate(data, "structural_validator")["status"] = "NOT_RUN"
        code, result = self.check(data)
        self.assertEqual((code, result["justified_proof_level"]), (0, "inventory_only"))

    def test_approved_requires_release_verified(self):
        data = self.ev.manifest() | {"status": "APPROVED"}
        data["release"]["rollback"] = {"status": "PASS"}
        code, result = self.check(data)
        self.assertEqual((code, result["justified_proof_level"]), (1, "runtime_verified"))

    def test_template_parses_and_claims_nothing(self):
        data = json.loads(TEMPLATE.read_text(encoding="utf-8"))
        code, result = self.check(data, verify=False)
        self.assertNotEqual(result["verdict"], "INPUT_ERROR", result)
        self.assertIsNone(result["claimed_proof_level"])


class SemanticReexecutionTests(Base):
    """mapping_verified on route B/C comes from rerunning the audit, not from report fields."""

    def test_handwritten_execution_fields_without_adapter_path_are_not_mapping_verified(self):
        data = self.ev.manifest("runtime_verified")
        data["encoding"].pop("adapter_path")
        data["encoding"].pop("adapter_sha256")
        code, result = self.check(data)
        self.assertEqual((code, result["justified_proof_level"], result["adapter_reexecuted_for_all_encoded_fonts"]),
                         (1, "inventory_only", False))

    def test_adapter_hash_mismatch_fails(self):
        data = self.ev.manifest("mapping_verified")
        data["encoding"]["adapter_sha256"] = FAKE
        code, result = self.check(data)
        self.assertEqual((code, result["justified_proof_level"]), (1, "inventory_only"))
        self.assertTrue(any("hashes to" in e for e in result["errors"]))

    def test_unsupported_adapter_does_not_reach_mapping_verified(self):
        from ftvf_fixture import TELLTALE_ADAPTER, file_sha
        data = self.ev.manifest("mapping_verified")
        data["encoding"]["adapter_path"] = str(TELLTALE_ADAPTER)
        data["encoding"]["adapter_sha256"] = file_sha(TELLTALE_ADAPTER)
        code, result = self.check(data)
        self.assertEqual((code, result["justified_proof_level"]), (1, "inventory_only"))
        self.assertTrue(result["semantic_reexecution"])
        self.assertNotEqual(result["reexecution"]["exit_code"], 0)

    def test_stale_report_disagrees_with_rerun(self):
        data = self.ev.manifest("mapping_verified")
        report = json.loads((self.ev.root / "qa/semantic_mapping.json").read_text(encoding="utf-8"))
        report["entries"][0]["mapping_correct"] = "FAIL"
        self.ev.reports["semantic_mapping"] = self.ev.write("qa/semantic_mapping.json", json.dumps(report).encode())
        data = self.ev.manifest("mapping_verified")
        code, result = self.check(data)
        self.assertEqual((code, result["justified_proof_level"]), (1, "structurally_verified"))
        self.assertTrue(result["semantic_reexecution"])
        self.assertTrue(any("semantic digest differs" in e for e in result["errors"]))

    def test_rerun_nonzero_exit_fails(self):
        script = self.ev.root / "bad_adapter.py"
        script.write_text("import sys\nsys.exit(1)\n", encoding="utf-8")
        data = self.ev.manifest("mapping_verified")
        data["encoding"]["adapter_path"] = "bad_adapter.py"
        data["encoding"]["adapter_sha256"] = sha(script.read_bytes())
        code, result = self.check(data)
        self.assertEqual(code, 1)
        self.assertLess(
            ["inventory_only", "structurally_verified", "mapping_verified"].index(result["justified_proof_level"]),
            2)
        self.assertTrue(result["adapter_reexecuted"])
        self.assertNotEqual(result["reexecution"]["exit_code"], 0)

    def test_generated_inventory_missing_or_wrong_or_different(self):
        from ftvf_fixture import FTVF_ADAPTER, file_sha
        saved = self.ev.root / "qa/generated.json"
        proc = subprocess.run([sys.executable, str(AUDIT), "--mapping", str(self.ev.root / "contract/vn128.json"),
                               "--adapter-script", str(FTVF_ADAPTER), "--adapter-sha256", file_sha(FTVF_ADAPTER),
                               "--font-file", str(self.ev.root / "build/Menu.font"),
                               "--identity-evidence", f"build_manifest={self.ev.root / self.ev.evidence}",
                               "--save-generated-inventory", str(saved)], capture_output=True)
        self.assertEqual(proc.returncode, 0, proc.stdout.decode()[:500])
        data = self.ev.manifest("mapping_verified")
        data["fonts"][0]["semantic_audit"] = {"generated_inventory_path": "qa/missing.json", "generated_inventory_sha256": FAKE}
        code, result = self.check(data)
        self.assertNotEqual(result["justified_proof_level"], "mapping_verified")

        data["fonts"][0]["semantic_audit"] = {"generated_inventory_path": "qa/generated.json", "generated_inventory_sha256": FAKE}
        code, result = self.check(data)
        self.assertEqual(code, 1)
        self.assertTrue(any("hashes to" in e for e in result["errors"]))

        body = json.loads(saved.read_text(encoding="utf-8"))
        body["records"][0]["ink_pixels"] = 1
        saved.write_text(json.dumps(body), encoding="utf-8")
        data["fonts"][0]["semantic_audit"]["generated_inventory_sha256"] = sha(saved.read_bytes())
        code, result = self.check(data)
        self.assertEqual((code, result["semantic_reexecution"]), (1, True))
        self.assertTrue(any("canonical form differs" in b for b in result["per_font"][0]["blockers"]))
        self.assertNotEqual(result["justified_proof_level"], "mapping_verified")

    def test_forged_semantic_report_with_real_files_stops_at_structural(self):
        forged = json.loads(self.ev.audit_report("semantic_mapping"))
        forged["inputs"]["font_sha256"] = self.ev.out
        forged["inputs"]["mapping_sha256"] = self.ev.mapping
        forged["inventory"]["declared_font_sha256"] = self.ev.out
        self.ev.reports["semantic_mapping"] = self.ev.write("qa/semantic_mapping.json", json.dumps(forged).encode())
        code, result = self.check(self.ev.manifest("runtime_verified"))
        self.assertEqual((code, result["justified_proof_level"]), (1, "structurally_verified"))
        self.assertTrue(any("digest differs" in e for e in result["errors"]))
        data = self.ev.manifest("runtime_verified")
        data["encoding"].pop("adapter_path", None)
        data["encoding"].pop("adapter_sha256", None)
        code, result = self.check(data)
        self.assertEqual((code, result["justified_proof_level"]), (1, "inventory_only"))

    def test_report_without_rerun_inputs_is_capped(self):
        code, result = self.check(self.ev.manifest("mapping_verified") | {"encoding": {
            "mapping_source": "contract/vn128.json", "mapping_sha256": self.ev.mapping}})
        self.assertEqual((code, result["justified_proof_level"], result["semantic_reexecution"]),
                         (1, "inventory_only", False))

    def test_real_records_without_identity_are_structural_only(self):
        from ftvf_fixture import build
        bare = build([{"id": 178, "uv": (0.1, 0.1, 0.4, 0.5), "x_advance": 32, "ink_pixels": 100}], native="")
        self.ev.write("build/Menu.font", bare)
        proc = subprocess.run([sys.executable, str(AUDIT), "--mapping", str(self.ev.root / "contract/vn128.json"),
                               "--adapter-script", str(self.ev.adapter), "--adapter-sha256", self.ev.adapter_sha,
                               "--font-file", str(self.ev.root / "build/Menu.font"),
                               "--output", str(self.ev.root / "qa/semantic_mapping.json")], capture_output=True)
        self.assertEqual(proc.returncode, 4, proc.stdout.decode()[:400])
        report = json.loads(proc.stdout.decode("utf-8"))
        self.assertEqual(report["structural_result"]["status"], "PASS")
        self.assertEqual(report["semantic_result"]["status"], "INCOMPLETE")
        self.ev.reports["semantic_mapping"] = sha((self.ev.root / "qa/semantic_mapping.json").read_bytes())
        data = self.ev.manifest("mapping_verified")
        data["fonts"][0]["output_sha256"] = sha(bare)
        data["fonts"][0]["archive"]["readback_sha256"] = sha(bare)
        self.ev.write("readback/Menu.font", bare)
        note = self.ev.write("qa/note-structural.json", b'{"schema":"fonttv/note/v1"}\n')
        for gate in data["fonts"][0]["gates"]:
            gate["font_sha256"] = sha(bare)
            if gate["gate"] != "semantic_mapping":
                gate["report"] = "qa/note-structural.json"
                gate["report_sha256"] = note
        data["encoding"]["identity_evidence"] = []
        code, result = self.check(data)
        self.assertEqual((code, result["justified_proof_level"]), (1, "structurally_verified"))
        self.assertEqual(result["per_font"][0]["reexecution"]["semantic_status"], "INCOMPLETE")

    def test_empty_ink_and_bad_metrics_are_not_structural(self):
        from ftvf_fixture import build
        empty = build([{"id": 178, "uv": (0.2, 0.2, 0.2, 0.4), "x_advance": 32, "ink_pixels": 0}])
        self.ev.write("build/Menu.font", empty)
        self.ev.write("readback/Menu.font", empty)
        data = self.ev.manifest("structurally_verified")
        data["fonts"][0]["output_sha256"] = sha(empty)
        data["fonts"][0]["archive"]["readback_sha256"] = sha(empty)
        data["encoding"]["identity_evidence"] = []
        code, result = self.check(data)
        self.assertEqual((code, result["justified_proof_level"]), (1, "inventory_only"))

    def test_roundtrip_or_contract_tamper_changes_digest(self):
        report = json.loads((self.ev.root / "qa/semantic_mapping.json").read_text(encoding="utf-8"))
        report["roundtrip"] = {"status": "FAIL"}
        self.ev.reports["semantic_mapping"] = self.ev.write("qa/semantic_mapping.json", json.dumps(report).encode())
        code, result = self.check(self.ev.manifest("mapping_verified"))
        self.assertEqual(code, 1)
        self.assertTrue(any("digest differs" in e for e in result["errors"]))
        report = json.loads((self.ev.root / "qa/semantic_mapping.json").read_text(encoding="utf-8"))
        report["encoding_contract"]["normalization"] = "NFD"
        report.pop("roundtrip", None)
        self.ev.reports["semantic_mapping"] = self.ev.write("qa/semantic_mapping.json", json.dumps(report).encode())
        code, result = self.check(self.ev.manifest("mapping_verified"))
        self.assertEqual(code, 1)
        self.assertTrue(any("digest differs" in e for e in result["errors"]))

    def test_two_fonts_one_without_adapter_caps_the_project(self):
        data = self.ev.manifest("runtime_verified")
        second = json.loads(json.dumps(data["fonts"][0]))
        second["name"] = "Other.font"
        second["adapter_path"] = None
        second["adapter_sha256"] = None
        data["fonts"].append(second)
        code, result = self.check(data)
        self.assertEqual((code, result["justified_proof_level"]), (1, "inventory_only"))
        self.assertEqual([row["adapter_reexecuted"] for row in result["per_font"]], [True, False])
        self.assertFalse(result["adapter_reexecuted_for_all_encoded_fonts"])
        self.assertFalse(result["semantic_reexecution_for_all_encoded_fonts"])

    def test_two_fonts_keep_separate_receipts(self):
        from ftvf_fixture import build
        other = build([{"id": 178, "uv": (0.1, 0.1, 0.3, 0.4), "x_advance": 20, "ink_pixels": 80}])
        self.ev.write("build/Other.font", other)
        self.ev.write("readback/Other.font", other)
        data = self.ev.manifest("structurally_verified")
        data["encoding"]["identity_evidence"] = []
        second = json.loads(json.dumps(data["fonts"][0]))
        second.update(name="Other.font", output_path="build/Other.font", output_sha256=sha(other))
        second["archive"]["readback_path"] = "readback/Other.font"
        second["archive"]["readback_sha256"] = sha(other)
        note = self.ev.write("qa/note.json", b'{"schema":"fonttv/note/v1"}\n')
        for gate in second["gates"]:
            gate["font_sha256"] = sha(other)
            if gate["gate"] != "semantic_mapping":
                gate["report"] = "qa/note.json"
                gate["report_sha256"] = note
        data["fonts"].append(second)
        code, result = self.check(data)
        self.assertEqual(code, 0, result.get("errors"))
        self.assertEqual(len(result["reexecutions"]), 2)
        self.assertNotEqual(result["reexecutions"][0]["font_sha256"], result["reexecutions"][1]["font_sha256"])
        self.assertTrue(result["adapter_reexecuted_for_all_encoded_fonts"])
        self.assertEqual(result["per_font"][0]["reexecution"]["font_sha256"], self.ev.out)


if __name__ == "__main__":
    unittest.main()
