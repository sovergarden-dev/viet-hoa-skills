"""Test suite for Generic External Agent Translation Handoff (viethoa/external-agent-handoff/v1)."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "external_agent_handoff.py"
import importlib.util

spec = importlib.util.spec_from_file_location("handoff", SCRIPT)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class HandoffExportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
        self.csv_path = self.root / "dialogue.csv"
        self.csv_path.write_text(
            "key,speaker,source,target,state,notes\n"
            "k1,Hero,Hello {0} {0},,pending,\n"
            "k2,Hero,Goodbye,Tạm biệt,translated,done\n"
            "k3,Villain,Refuse me,,needs_context,needs review\n",
            encoding="utf-8",
        )
        self.plan = {
            "package_id": "pkg_01",
            "project_id": "test_game",
            "tables": [
                {
                    "translation_id": "dlg",
                    "domain": "main",
                    "path": "dialogue.csv",
                    "mapping": {
                        "key_column": "key",
                        "source_column": "source",
                        "target_column": "target",
                        "state_column": "state",
                        "notes_column": "notes",
                        "speaker_column": "speaker",
                    },
                    "token_pattern": r"\{[0-9]+\}",
                }
            ],
        }

    def tearDown(self):
        self.tmp.cleanup()

    def test_export_preserves_verbatim_keys_and_token_counts(self):
        # Add a key with whitespace to verify verbatim key preservation
        self.csv_path.write_text(
            "key,speaker,source,target,state,notes\n"
            "k1,Hero,Hello {0} {0},,pending,\n"
            "k2,Hero,Goodbye,Tạm biệt,translated,done\n"
            "k3,Villain,Refuse me,,needs_context,needs review\n"
            " k_space ,Hero,Whitespace key,,pending,\n",
            encoding="utf-8",
        )
        out_dir = self.root / "outbound"
        host_dir = self.root / "host_private"
        res = m.export_package(self.root, self.plan, out_dir, host_dir, scope="full")
        self.assertEqual(res["task_count"], 3)  # k1, k3, ' k_space '
        tasks_file = out_dir / "tasks.jsonl"
        tasks = [json.loads(line) for line in tasks_file.read_text(encoding="utf-8").splitlines() if line.strip()]
        self.assertEqual(len(tasks), 3)
        k1_task = next(t for t in tasks if t["key"] == "k1")
        # Token {0} appears twice in source, list must contain both occurrences to track count
        self.assertEqual(k1_task["protected_tokens"], ["{0}", "{0}"])
        k_space_task = next(t for t in tasks if t["key"] == " k_space ")
        self.assertEqual(k_space_task["key"], " k_space ")

    def test_export_rejects_overlapping_or_escaping_directories(self):
        out_dir = self.root / "outbound"
        nested_host = out_dir / "host_private"
        with self.assertRaises(ValueError):
            m.export_package(self.root, self.plan, out_dir, nested_host)
        with self.assertRaises(ValueError):
            m.export_package(self.root, self.plan, self.root.parent / "outbound", self.root / "host_private")

    def test_exception_scope_filters_by_flagged_state_or_explicit_keys(self):
        out_dir = self.root / "outbound"
        host_dir = self.root / "host_private"
        # Case A: In exception scope without explicit keys, only needs_context/rejected are exported
        res = m.export_package(self.root, self.plan, out_dir, host_dir, scope="exception")
        self.assertEqual(res["task_count"], 1)  # only k3 (needs_context)
        tasks = [json.loads(line) for line in (out_dir / "tasks.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
        self.assertEqual(tasks[0]["key"], "k3")

        # Case B: In exception scope with explicit selected_identities
        out_dir_sel = self.root / "outbound_sel"
        host_dir_sel = self.root / "host_private_sel"
        sel_plan = dict(self.plan)
        sel_plan["package_id"] = "pkg_sel"
        sel_plan["selected_identities"] = [["dlg", "main", "k1"]]
        res_sel = m.export_package(self.root, sel_plan, out_dir_sel, host_dir_sel, scope="exception")
        self.assertEqual(res_sel["task_count"], 1)
        tasks_sel = [json.loads(line) for line in (out_dir_sel / "tasks.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
        self.assertEqual(tasks_sel[0]["key"], "k1")

        # Case C: Rejects missing selected identity
        bad_plan_missing = dict(self.plan)
        bad_plan_missing["selected_identities"] = [["dlg", "main", "nonexistent_key"]]
        with self.assertRaises(ValueError):
            m.export_package(self.root, bad_plan_missing, self.root / "out_bad", self.root / "host_bad", scope="exception")

        # Case D: Rejects duplicate selected identity in plan
        bad_plan_dup = dict(self.plan)
        bad_plan_dup["selected_identities"] = [["dlg", "main", "k1"], ["dlg", "main", "k1"]]
        with self.assertRaises(ValueError):
            m.export_package(self.root, bad_plan_dup, self.root / "out_bad2", self.root / "host_bad2", scope="exception")


class HandoffValidationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
        self.csv_path = self.root / "dialogue.csv"
        self.csv_path.write_text(
            "key,speaker,source,target,state,notes\n"
            "k1,Hero,Hello {0} {0},,pending,\n"
            "k2,Hero,Refuse me,,needs_context,needs review\n",
            encoding="utf-8",
        )
        self.plan = {
            "package_id": "pkg_01",
            "project_id": "test_game",
            "tables": [
                {
                    "translation_id": "dlg",
                    "domain": "main",
                    "path": "dialogue.csv",
                    "mapping": {
                        "key_column": "key",
                        "source_column": "source",
                        "target_column": "target",
                        "state_column": "state",
                    },
                    "token_pattern": r"\{[0-9]+\}",
                }
            ],
        }
        self.out_dir = self.root / "outbound"
        self.host_dir = self.root / "host_private"
        m.export_package(self.root, self.plan, self.out_dir, self.host_dir, scope="full")
        self.host_mf = self.host_dir / "host-manifest.json"

    def tearDown(self):
        self.tmp.cleanup()

    def test_valid_return_stream_passes(self):
        res_file = self.root / "results.jsonl"
        res_file.write_text(
            json.dumps({
                "package_id": "pkg_01",
                "translation_id": "dlg",
                "domain": "main",
                "key": "k1",
                "source_sha256": m.digest("Hello {0} {0}"),
                "candidate_target": "Xin chào {0} {0}",
                "candidate_status": "completed",
                "notes": "ok",
            }) + "\n" +
            json.dumps({
                "package_id": "pkg_01",
                "translation_id": "dlg",
                "domain": "main",
                "key": "k2",
                "source_sha256": m.digest("Refuse me"),
                "candidate_target": "",
                "candidate_status": "refused",
                "notes": "Provider safety filter triggered on sensitive dialogue",
            }) + "\n",
            encoding="utf-8",
        )
        rep = m.validate_return(self.root, self.host_mf, res_file)
        self.assertTrue(rep["valid"], rep.get("errors"))
        self.assertEqual(rep["completed"], 1)
        self.assertEqual(rep["refused"], 1)

    def test_token_multiplicity_and_extraneous_tokens_rejected(self):
        # Case A: Missing token multiplicity ({0} appears twice in source, only once in target)
        res_file_missing = self.root / "results_missing.jsonl"
        res_file_missing.write_text(
            json.dumps({
                "package_id": "pkg_01",
                "translation_id": "dlg",
                "domain": "main",
                "key": "k1",
                "source_sha256": m.digest("Hello {0} {0}"),
                "candidate_target": "Xin chào {0}",
                "candidate_status": "completed",
            }) + "\n" +
            json.dumps({
                "package_id": "pkg_01",
                "translation_id": "dlg",
                "domain": "main",
                "key": "k2",
                "source_sha256": m.digest("Refuse me"),
                "candidate_target": "",
                "candidate_status": "refused",
                "notes": "refused",
            }) + "\n",
            encoding="utf-8",
        )
        rep_missing = m.validate_return(self.root, self.host_mf, res_file_missing)
        self.assertFalse(rep_missing["valid"])
        self.assertTrue(any("token" in err.lower() for err in rep_missing["errors"]))

        # Case B: Extraneous token ({1} invented in target, not present in source)
        res_file_extra = self.root / "results_extra.jsonl"
        res_file_extra.write_text(
            json.dumps({
                "package_id": "pkg_01",
                "translation_id": "dlg",
                "domain": "main",
                "key": "k1",
                "source_sha256": m.digest("Hello {0} {0}"),
                "candidate_target": "Xin chào {0} {0} {1}",
                "candidate_status": "completed",
            }) + "\n" +
            json.dumps({
                "package_id": "pkg_01",
                "translation_id": "dlg",
                "domain": "main",
                "key": "k2",
                "source_sha256": m.digest("Refuse me"),
                "candidate_target": "",
                "candidate_status": "refused",
                "notes": "refused",
            }) + "\n",
            encoding="utf-8",
        )
        rep_extra = m.validate_return(self.root, self.host_mf, res_file_extra)
        self.assertFalse(rep_extra["valid"])
        self.assertTrue(any("token" in err.lower() for err in rep_extra["errors"]))

    def test_stale_source_on_disk_rejected(self):
        # Canonical CSV source is modified on disk after export
        self.csv_path.write_text(
            "key,speaker,source,target,state,notes\n"
            "k1,Hero,Hello modified {0} {0},,pending,\n"
            "k2,Hero,Refuse me,,needs_context,needs review\n",
            encoding="utf-8",
        )
        res_file = self.root / "results.jsonl"
        res_file.write_text(
            json.dumps({
                "package_id": "pkg_01",
                "translation_id": "dlg",
                "domain": "main",
                "key": "k1",
                "source_sha256": m.digest("Hello {0} {0}"),
                "candidate_target": "Xin chào {0} {0}",
                "candidate_status": "completed",
            }) + "\n" +
            json.dumps({
                "package_id": "pkg_01",
                "translation_id": "dlg",
                "domain": "main",
                "key": "k2",
                "source_sha256": m.digest("Refuse me"),
                "candidate_target": "",
                "candidate_status": "refused",
                "notes": "refused",
            }) + "\n",
            encoding="utf-8",
        )
        rep = m.validate_return(self.root, self.host_mf, res_file)
        self.assertFalse(rep["valid"])
        self.assertTrue(any("stale" in err.lower() or "disk" in err.lower() for err in rep["errors"]))

    def test_stale_target_and_state_drift_rejected(self):
        # Case A: Concurrent modification of target on disk
        self.csv_path.write_text(
            "key,speaker,source,target,state,notes\n"
            "k1,Hero,Hello {0} {0},drifted target,pending,\n"
            "k2,Hero,Refuse me,,needs_context,needs review\n",
            encoding="utf-8",
        )
        res_file = self.root / "results_target_drift.jsonl"
        res_file.write_text(
            json.dumps({
                "package_id": "pkg_01",
                "translation_id": "dlg",
                "domain": "main",
                "key": "k1",
                "source_sha256": m.digest("Hello {0} {0}"),
                "candidate_target": "Xin chào {0} {0}",
                "candidate_status": "completed",
            }) + "\n" +
            json.dumps({
                "package_id": "pkg_01",
                "translation_id": "dlg",
                "domain": "main",
                "key": "k2",
                "source_sha256": m.digest("Refuse me"),
                "candidate_target": "",
                "candidate_status": "refused",
                "notes": "refused",
            }) + "\n",
            encoding="utf-8",
        )
        rep = m.validate_return(self.root, self.host_mf, res_file)
        self.assertFalse(rep["valid"])
        self.assertTrue(any("target" in err.lower() and "disk" in err.lower() for err in rep["errors"]))

        # Case B: Concurrent modification of state on disk
        self.csv_path.write_text(
            "key,speaker,source,target,state,notes\n"
            "k1,Hero,Hello {0} {0},,translated,\n"
            "k2,Hero,Refuse me,,needs_context,needs review\n",
            encoding="utf-8",
        )
        rep2 = m.validate_return(self.root, self.host_mf, res_file)
        self.assertFalse(rep2["valid"])
        self.assertTrue(any("state" in err.lower() and "disk" in err.lower() for err in rep2["errors"]))

    def test_refused_candidate_with_text_or_empty_notes_rejected(self):
        # Case A: Candidate marked refused but includes non-empty target text
        res_file_text = self.root / "results_bad_refused_text.jsonl"
        res_file_text.write_text(
            json.dumps({
                "package_id": "pkg_01",
                "translation_id": "dlg",
                "domain": "main",
                "key": "k1",
                "source_sha256": m.digest("Hello {0} {0}"),
                "candidate_target": "Xin chào {0} {0}",
                "candidate_status": "completed",
            }) + "\n" +
            json.dumps({
                "package_id": "pkg_01",
                "translation_id": "dlg",
                "domain": "main",
                "key": "k2",
                "source_sha256": m.digest("Refuse me"),
                "candidate_target": "Unexpected text",
                "candidate_status": "refused",
                "notes": "filtered",
            }) + "\n",
            encoding="utf-8",
        )
        rep = m.validate_return(self.root, self.host_mf, res_file_text)
        self.assertFalse(rep["valid"])
        self.assertTrue(any("refused" in err.lower() and "target" in err.lower() for err in rep["errors"]))

        # Case B: Candidate marked refused but has empty/blank notes
        res_file_notes = self.root / "results_bad_refused_notes.jsonl"
        res_file_notes.write_text(
            json.dumps({
                "package_id": "pkg_01",
                "translation_id": "dlg",
                "domain": "main",
                "key": "k1",
                "source_sha256": m.digest("Hello {0} {0}"),
                "candidate_target": "Xin chào {0} {0}",
                "candidate_status": "completed",
            }) + "\n" +
            json.dumps({
                "package_id": "pkg_01",
                "translation_id": "dlg",
                "domain": "main",
                "key": "k2",
                "source_sha256": m.digest("Refuse me"),
                "candidate_target": "",
                "candidate_status": "refused",
                "notes": "   ",
            }) + "\n",
            encoding="utf-8",
        )
        rep_n = m.validate_return(self.root, self.host_mf, res_file_notes)
        self.assertFalse(rep_n["valid"])
        self.assertTrue(any("refused" in err.lower() and "notes" in err.lower() for err in rep_n["errors"]))

        # Case C: Candidate marked refused with candidate_target omitted entirely (valid)
        res_file_omitted = self.root / "results_refused_omitted.jsonl"
        res_file_omitted.write_text(
            json.dumps({
                "package_id": "pkg_01",
                "translation_id": "dlg",
                "domain": "main",
                "key": "k1",
                "source_sha256": m.digest("Hello {0} {0}"),
                "candidate_target": "Xin chào {0} {0}",
                "candidate_status": "completed",
            }) + "\n" +
            json.dumps({
                "package_id": "pkg_01",
                "translation_id": "dlg",
                "domain": "main",
                "key": "k2",
                "source_sha256": m.digest("Refuse me"),
                "candidate_status": "refused",
                "notes": "filtered cleanly",
            }) + "\n",
            encoding="utf-8",
        )
        rep_omitted = m.validate_return(self.root, self.host_mf, res_file_omitted)
        self.assertTrue(rep_omitted["valid"], rep_omitted.get("errors"))
        self.assertEqual(rep_omitted["refused"], 1)

        # Case D: Candidate marked refused with whitespace-only target is rejected
        res_file_ws = self.root / "results_bad_refused_ws.jsonl"
        res_file_ws.write_text(
            json.dumps({
                "package_id": "pkg_01",
                "translation_id": "dlg",
                "domain": "main",
                "key": "k1",
                "source_sha256": m.digest("Hello {0} {0}"),
                "candidate_target": "Xin chào {0} {0}",
                "candidate_status": "completed",
            }) + "\n" +
            json.dumps({
                "package_id": "pkg_01",
                "translation_id": "dlg",
                "domain": "main",
                "key": "k2",
                "source_sha256": m.digest("Refuse me"),
                "candidate_target": "   ",
                "candidate_status": "refused",
                "notes": "filtered",
            }) + "\n",
            encoding="utf-8",
        )
        rep_ws = m.validate_return(self.root, self.host_mf, res_file_ws)
        self.assertFalse(rep_ws["valid"])
        self.assertTrue(any("refused" in err.lower() and "target" in err.lower() for err in rep_ws["errors"]))

    def test_whitespace_identity_accepted(self):
        # Setup workspace with whitespace source text
        ws_dir = self.root / "ws_ws"
        ws_dir.mkdir()
        csv_file = ws_dir / "space.csv"
        csv_file.write_text(
            "key,source,target,state\n"
            "s1,   ,,pending\n",
            encoding="utf-8",
        )
        p = {
            "package_id": "pkg_ws",
            "project_id": "ws_game",
            "tables": [{
                "translation_id": "sp",
                "domain": "ui",
                "path": "space.csv",
                "mapping": {"key_column": "key", "source_column": "source", "target_column": "target", "state_column": "state"},
                "token_pattern": r"\{[0-9]+\}",
            }],
        }
        out = ws_dir / "out"
        host = ws_dir / "host"
        m.export_package(ws_dir, p, out, host, scope="full")
        res = ws_dir / "res.jsonl"
        res.write_text(
            json.dumps({
                "package_id": "pkg_ws",
                "translation_id": "sp",
                "domain": "ui",
                "key": "s1",
                "source_sha256": m.digest("   "),
                "candidate_target": "   ",
                "candidate_status": "completed",
            }) + "\n",
            encoding="utf-8",
        )
        rep = m.validate_return(ws_dir, host / "host-manifest.json", res)
        self.assertTrue(rep["valid"], rep.get("errors"))
        self.assertEqual(rep["completed"], 1)
        self.assertTrue(rep["translation_complete"])

    def test_marker_corrupted_or_mismatched_rejected(self):
        marker = self.host_dir / ".export-complete"
        res_file = self.root / "res_dummy.jsonl"
        res_file.write_text("", encoding="utf-8")
        original_marker_text = marker.read_text(encoding="utf-8")
        base_marker = json.loads(original_marker_text)

        # Subtest 1: Corrupted JSON
        marker.write_text("corrupted json {", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "corrupted .export-complete"):
            m.validate_return(self.root, self.host_mf, res_file)

        # Subtest 2: Missing marker
        marker.unlink()
        with self.assertRaisesRegex(ValueError, "missing .export-complete"):
            m.validate_return(self.root, self.host_mf, res_file)

        # Subtest 3: Host manifest byte modification without updating marker
        original_manifest_bytes = self.host_mf.read_bytes()
        marker.write_text(original_marker_text, encoding="utf-8")
        tampered_manifest = dict(json.loads(original_manifest_bytes.decode("utf-8")))
        tampered_manifest["tampered"] = True
        self.host_mf.write_text(json.dumps(tampered_manifest, indent=2) + "\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "host_manifest_sha256 mismatch"):
            m.validate_return(self.root, self.host_mf, res_file)

        # Restore valid manifest bytes byte-for-byte for remaining subtests
        self.host_mf.write_bytes(original_manifest_bytes)

        # Subtest 4: Package ID mismatch
        bad_pkg_marker = dict(base_marker)
        bad_pkg_marker["package_id"] = "wrong_pkg"
        marker.write_text(json.dumps(bad_pkg_marker), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "package_id mismatch"):
            m.validate_return(self.root, self.host_mf, res_file)

        # Subtest 5: Tasks hash mismatch
        bad_tasks_marker = dict(base_marker)
        bad_tasks_marker["tasks_sha256"] = "wrong_hash"
        marker.write_text(json.dumps(bad_tasks_marker), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "tasks_sha256 mismatch"):
            m.validate_return(self.root, self.host_mf, res_file)

    def test_duplicate_candidate_stream_identity_rejected(self):
        # Candidate stream contains duplicate entry for k1
        res_file = self.root / "results_dup.jsonl"
        res_file.write_text(
            json.dumps({
                "package_id": "pkg_01",
                "translation_id": "dlg",
                "domain": "main",
                "key": "k1",
                "source_sha256": m.digest("Hello {0} {0}"),
                "candidate_target": "Xin chào {0} {0}",
                "candidate_status": "completed",
            }) + "\n" +
            json.dumps({
                "package_id": "pkg_01",
                "translation_id": "dlg",
                "domain": "main",
                "key": "k1",
                "source_sha256": m.digest("Hello {0} {0}"),
                "candidate_target": "Chào {0} {0}",
                "candidate_status": "completed",
            }) + "\n",
            encoding="utf-8",
        )
        rep = m.validate_return(self.root, self.host_mf, res_file)
        self.assertFalse(rep["valid"])
        self.assertTrue(any("duplicate" in err.lower() for err in rep["errors"]))

    def test_translation_complete_flag_semantics(self):
        # Case A: One task completed, one refused -> valid=True but translation_complete=False
        res_file_refused = self.root / "res_ref.jsonl"
        res_file_refused.write_text(
            json.dumps({
                "package_id": "pkg_01",
                "translation_id": "dlg",
                "domain": "main",
                "key": "k1",
                "source_sha256": m.digest("Hello {0} {0}"),
                "candidate_target": "Xin chào {0} {0}",
                "candidate_status": "completed",
            }) + "\n" +
            json.dumps({
                "package_id": "pkg_01",
                "translation_id": "dlg",
                "domain": "main",
                "key": "k2",
                "source_sha256": m.digest("Refuse me"),
                "candidate_target": "",
                "candidate_status": "refused",
                "notes": "Violence/mature dialogue safety filter triggered",
            }) + "\n",
            encoding="utf-8",
        )
        rep_ref = m.validate_return(self.root, self.host_mf, res_file_refused)
        self.assertTrue(rep_ref["valid"])
        self.assertFalse(rep_ref["translation_complete"])
        self.assertEqual(rep_ref["completed"], 1)
        self.assertEqual(rep_ref["refused"], 1)

        # Case B: All tasks completed -> valid=True and translation_complete=True
        res_file_all = self.root / "res_all.jsonl"
        res_file_all.write_text(
            json.dumps({
                "package_id": "pkg_01",
                "translation_id": "dlg",
                "domain": "main",
                "key": "k1",
                "source_sha256": m.digest("Hello {0} {0}"),
                "candidate_target": "Xin chào {0} {0}",
                "candidate_status": "completed",
            }) + "\n" +
            json.dumps({
                "package_id": "pkg_01",
                "translation_id": "dlg",
                "domain": "main",
                "key": "k2",
                "source_sha256": m.digest("Refuse me"),
                "candidate_target": "Từ chối tôi",
                "candidate_status": "completed",
            }) + "\n",
            encoding="utf-8",
        )
        rep_all = m.validate_return(self.root, self.host_mf, res_file_all)
        self.assertTrue(rep_all["valid"])
        self.assertTrue(rep_all["translation_complete"])
        self.assertEqual(rep_all["completed"], 2)

    def test_canonical_csv_bytes_preserved_exactly_across_lifecycle(self):
        # Record canonical CSV bytes before any export or validate
        fresh_ws = self.root / "fresh_lifecycle"
        fresh_ws.mkdir()
        fresh_csv = fresh_ws / "fresh.csv"
        fresh_csv.write_text("key,source,target,state\nf1,Hello,,pending\n", encoding="utf-8")
        hash_before = m.digest(fresh_csv.read_bytes())

        plan = {
            "package_id": "pkg_fresh",
            "project_id": "fresh_game",
            "tables": [{
                "translation_id": "fr",
                "domain": "ui",
                "path": "fresh.csv",
                "mapping": {"key_column": "key", "source_column": "source", "target_column": "target", "state_column": "state"},
                "token_pattern": r"\{[0-9]+\}",
            }],
        }
        out = fresh_ws / "out"
        host = fresh_ws / "host"
        m.export_package(fresh_ws, plan, out, host, scope="full")
        self.assertEqual(m.digest(fresh_csv.read_bytes()), hash_before)

        res = fresh_ws / "res.jsonl"
        res.write_text(
            json.dumps({
                "package_id": "pkg_fresh",
                "translation_id": "fr",
                "domain": "ui",
                "key": "f1",
                "source_sha256": m.digest("Hello"),
                "candidate_target": "Xin chào",
                "candidate_status": "completed",
            }) + "\n",
            encoding="utf-8",
        )
        rep = m.validate_return(fresh_ws, host / "host-manifest.json", res)
        self.assertTrue(rep["valid"])
        self.assertFalse(rep["canonical_modified"])
        self.assertEqual(m.digest(fresh_csv.read_bytes()), hash_before)


class HandoffExceptionBundleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
        self.csv_path = self.root / "dialogue.csv"
        self.csv_path.write_text(
            "key,speaker,source,target,state,notes\n"
            "t1,Hero,Normal line,,pending,\n"
            "t2,Villain,Extremely violent 18+ blood scene {0},,pending,\n"
            "t3,NPC,Ambiguous riddle,,pending,\n"
            "t4,Ghost,Unheard whispers,,pending,\n",
            encoding="utf-8",
        )
        self.canonical_hash = m.digest(self.csv_path.read_bytes())
        self.plan = {
            "package_id": "pkg_bundle_01",
            "project_id": "game_horror",
            "tables": [{
                "translation_id": "dlg",
                "domain": "story",
                "path": "dialogue.csv",
                "mapping": {
                    "key_column": "key",
                    "source_column": "source",
                    "target_column": "target",
                    "state_column": "state",
                    "speaker_column": "speaker",
                },
                "token_pattern": r"\{[0-9]+\}",
            }],
        }
        self.out_dir = self.root / "outbound"
        self.host_dir = self.root / "host_private"
        m.export_package(self.root, self.plan, self.out_dir, self.host_dir, scope="full")
        self.host_mf = self.host_dir / "host-manifest.json"

    def tearDown(self):
        self.tmp.cleanup()

    def test_bundle_aggregates_content_gate_refusal_needs_context_and_missing(self):
        # Setup results with 1 completed, 1 content_gate refusal, 1 needs_context, and t4 omitted (missing)
        res_file = self.root / "results.jsonl"
        res_file.write_text(
            json.dumps({
                "package_id": "pkg_bundle_01",
                "translation_id": "dlg",
                "domain": "story",
                "key": "t1",
                "source_sha256": m.digest("Normal line"),
                "candidate_target": "Dòng thoại bình thường",
                "candidate_status": "completed",
            }) + "\n" +
            json.dumps({
                "package_id": "pkg_bundle_01",
                "translation_id": "dlg",
                "domain": "story",
                "key": "t2",
                "source_sha256": m.digest("Extremely violent 18+ blood scene {0}"),
                "candidate_target": "",
                "candidate_status": "refused",
                "notes": "Provider safety refused: extreme 18+ violence and blood",
            }) + "\n" +
            json.dumps({
                "package_id": "pkg_bundle_01",
                "translation_id": "dlg",
                "domain": "story",
                "key": "t3",
                "source_sha256": m.digest("Ambiguous riddle"),
                "candidate_target": "",
                "candidate_status": "needs_context",
                "notes": "Need to know if NPC is speaking in past or future tense",
            }) + "\n",
            encoding="utf-8",
        )

        bundle_path = self.root / "exceptions" / "exception-packet.jsonl"
        summary = m.build_exception_bundle(self.root, self.host_mf, res_file, bundle_path)

        # Assert summary counts and statuses
        self.assertTrue(summary["integrity_valid"])
        self.assertEqual(summary["exception_count"], 3)  # t2, t3, t4
        self.assertEqual(summary["content_gate_count"], 1)  # t2 matched 18+/blood/violence
        self.assertEqual(summary["refused_count"], 0)
        self.assertEqual(summary["needs_context_count"], 1)  # t3
        self.assertEqual(summary["missing_count"], 1)  # t4 missing
        self.assertTrue(summary["re_dispatch_eligible"])
        self.assertEqual(len(summary["selected_identities"]), 3)

        # Assert exception rows contents
        lines = [json.loads(line) for line in bundle_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        self.assertEqual(len(lines), 3)

        t2_row = next(r for r in lines if r["key"] == "t2")
        self.assertEqual(t2_row["exception_status"], "content_gate")
        self.assertTrue(t2_row["preserve_explicit_content"])
        self.assertEqual(t2_row["notes_provenance"], "external_untrusted")
        self.assertEqual(t2_row["protected_tokens"], ["{0}"])
        self.assertEqual(t2_row["source"], "Extremely violent 18+ blood scene {0}")

        t3_row = next(r for r in lines if r["key"] == "t3")
        self.assertEqual(t3_row["exception_status"], "needs_context")
        self.assertFalse(t3_row["preserve_explicit_content"])
        self.assertIn("tense", t3_row["prior_refusal_reason"])

        t4_row = next(r for r in lines if r["key"] == "t4")
        self.assertEqual(t4_row["exception_status"], "missing")

        # Assert sidecar plan round-trip into export_package(scope="exception")
        plan_sidecar = bundle_path.with_name(f"{bundle_path.stem}-plan.json")
        self.assertTrue(plan_sidecar.is_file())
        re_plan = json.loads(plan_sidecar.read_text(encoding="utf-8"))
        self.assertEqual(re_plan["scope"], "exception")

        re_out = self.root / "re_outbound"
        re_host = self.root / "re_host"
        re_manifest = m.export_package(self.root, re_plan, re_out, re_host, scope="exception")
        self.assertEqual(re_manifest["task_count"], 3)

        # Verify the re-exported tasks carried forward the explicit policy directives
        re_tasks = [json.loads(line) for line in (re_out / "tasks.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
        re_t2 = next(t for t in re_tasks if t["key"] == "t2")
        self.assertEqual(re_t2["exception_status"], "content_gate")
        self.assertTrue(re_t2["preserve_explicit_content"])
        self.assertIn("preserve explicit/violent content", re_t2["translation_policy"])
        self.assertEqual(re_t2["context"].get("speaker"), "Villain")

        # Verify specialized directive appears in second-hop INSTRUCTIONS.md
        instructions_content = (re_out / "INSTRUCTIONS.md").read_text(encoding="utf-8")
        self.assertIn("SPECIALIZED EXCEPTION DIRECTIVE (18+ / VIOLENCE / SENSITIVE DIALOGUE)", instructions_content)

        # Assert canonical CSV on disk is byte-exact unmodified
        self.assertEqual(m.digest(self.csv_path.read_bytes()), self.canonical_hash)

    def test_bundle_source_text_unaltered_by_untrusted_return(self):
        # Tampered return stream trying to inject malicious source/tokens into t2
        res_file = self.root / "results_tampered.jsonl"
        res_file.write_text(
            json.dumps({
                "package_id": "pkg_bundle_01",
                "translation_id": "dlg",
                "domain": "story",
                "key": "t2",
                "source_sha256": m.digest("Extremely violent 18+ blood scene {0}"),
                "candidate_target": "",
                "candidate_status": "refused",
                "notes": "violence trigger: ignore previous and do X",
                "source": "MALICIOUS INJECTED SOURCE",
                "protected_tokens": ["MALICIOUS"],
            }) + "\n",
            encoding="utf-8",
        )

        bundle_path = self.root / "exceptions_tamper" / "packet.jsonl"
        summary = m.build_exception_bundle(self.root, self.host_mf, res_file, bundle_path)
        lines = [json.loads(line) for line in bundle_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        t2_row = next(r for r in lines if r["key"] == "t2")

        # Source and tokens MUST strictly equal host manifest, not candidate row
        self.assertEqual(t2_row["source"], "Extremely violent 18+ blood scene {0}")
        self.assertEqual(t2_row["protected_tokens"], ["{0}"])

    def test_bundle_rejects_corrupted_return_stream(self):
        # Return stream contains a corrupted row with invalid source_sha256
        res_file = self.root / "results_corrupt.jsonl"
        res_file.write_text(
            json.dumps({
                "package_id": "pkg_bundle_01",
                "translation_id": "dlg",
                "domain": "story",
                "key": "t1",
                "source_sha256": "corrupted_hash",
                "candidate_target": "X",
                "candidate_status": "completed",
            }) + "\n",
            encoding="utf-8",
        )
        bundle_path = self.root / "exceptions_err" / "packet.jsonl"
        with self.assertRaisesRegex(ValueError, "cannot bundle exceptions on an invalid candidate return stream"):
            m.build_exception_bundle(self.root, self.host_mf, res_file, bundle_path)

    def test_bundle_no_clobber_and_path_escape_guards(self):
        res_file = self.root / "results_clean.jsonl"
        res_file.write_text("", encoding="utf-8")

        # Path escape outside workspace
        with self.assertRaisesRegex(ValueError, "must reside within workspace"):
            m.build_exception_bundle(self.root, self.host_mf, res_file, self.root.parent / "escape.jsonl")

        # Pre-existing file no-clobber
        existing_target = self.root / "existing.jsonl"
        existing_target.write_text("pre-existing content", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "already exists"):
            m.build_exception_bundle(self.root, self.host_mf, res_file, existing_target)

        # Pre-existing manifest sidecar no-clobber
        manifest_sidecar = self.root / "sidecar-manifest.json"
        manifest_sidecar.write_text("{}", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "bundle manifest sidecar already exists"):
            m.build_exception_bundle(self.root, self.host_mf, res_file, self.root / "sidecar.jsonl")

    def test_bundle_host_authority_content_gate_without_keywords(self):
        # Canonical row has state == 'rejected' (host-marked). Even if agent's notes lack keywords,
        # host authority marks it as content_gate
        ws = self.root / "ws_host_auth"
        ws.mkdir()
        csv_file = ws / "dlg.csv"
        csv_file.write_text(
            "key,source,target,state\n"
            "k_rej,Sensitive host-flagged dialogue,,rejected\n",
            encoding="utf-8",
        )
        p = {
            "package_id": "pkg_auth",
            "project_id": "game_auth",
            "tables": [{
                "translation_id": "d",
                "domain": "main",
                "path": "dlg.csv",
                "mapping": {"key_column": "key", "source_column": "source", "target_column": "target", "state_column": "state"},
                "token_pattern": r"\{[0-9]+\}",
            }],
        }
        out_d = ws / "out"
        host_d = ws / "host"
        m.export_package(ws, p, out_d, host_d, scope="exception")

        res_f = ws / "res.jsonl"
        res_f.write_text(
            json.dumps({
                "package_id": "pkg_auth",
                "translation_id": "d",
                "domain": "main",
                "key": "k_rej",
                "source_sha256": m.digest("Sensitive host-flagged dialogue"),
                "candidate_target": "",
                "candidate_status": "refused",
                "notes": "generic upstream policy refusal without magic words",
            }) + "\n",
            encoding="utf-8",
        )

        bundle_f = ws / "bundle.jsonl"
        summary = m.build_exception_bundle(ws, host_d / "host-manifest.json", res_f, bundle_f)
        self.assertEqual(summary["content_gate_count"], 1)
        self.assertEqual(summary["refused_count"], 0)

        lines = [json.loads(line) for line in bundle_f.read_text(encoding="utf-8").splitlines() if line.strip()]
        self.assertEqual(lines[0]["exception_status"], "content_gate")
        self.assertTrue(lines[0]["preserve_explicit_content"])

    def test_cli_smoke_subprocesses(self):
        # Exercises CLI actions export -> validate -> bundle-exceptions via subprocess
        ws = self.root / "ws_cli"
        ws.mkdir()
        csv_file = ws / "c.csv"
        csv_file.write_text("key,source,target,state\nc1,Hello {0},,pending\n", encoding="utf-8")
        plan_file = ws / "plan.json"
        plan_file.write_text(
            json.dumps({
                "package_id": "pkg_cli",
                "project_id": "proj_cli",
                "tables": [{
                    "translation_id": "c",
                    "domain": "d",
                    "path": "c.csv",
                    "mapping": {"key_column": "key", "source_column": "source", "target_column": "target", "state_column": "state"},
                    "token_pattern": r"\{[0-9]+\}",
                }],
            }),
            encoding="utf-8",
        )
        out_d = ws / "out"
        host_d = ws / "host"

        # Action: export
        cmd_export = [
            sys.executable, str(SCRIPT), "export",
            "--workspace", str(ws),
            "--plan", str(plan_file),
            "--outbound", str(out_d),
            "--host-private", str(host_d),
        ]
        res_exp = subprocess.run(cmd_export, capture_output=True, text=True, timeout=30)
        self.assertEqual(res_exp.returncode, 0, res_exp.stderr)
        exp_json = json.loads(res_exp.stdout)
        self.assertEqual(exp_json["result"], "exported")

        # Action: validate (success)
        res_file = ws / "results.jsonl"
        res_file.write_text(
            json.dumps({
                "package_id": "pkg_cli",
                "translation_id": "c",
                "domain": "d",
                "key": "c1",
                "source_sha256": m.digest("Hello {0}"),
                "candidate_target": "Xin chào {0}",
                "candidate_status": "completed",
            }) + "\n",
            encoding="utf-8",
        )
        cmd_val = [
            sys.executable, str(SCRIPT), "validate",
            "--workspace", str(ws),
            "--host-manifest", str(host_d / "host-manifest.json"),
            "--results", str(res_file),
        ]
        res_val = subprocess.run(cmd_val, capture_output=True, text=True, timeout=30)
        self.assertEqual(res_val.returncode, 0, res_val.stderr)

        # Action: bundle-exceptions
        bundle_file = ws / "bundle.jsonl"
        cmd_bundle = [
            sys.executable, str(SCRIPT), "bundle-exceptions",
            "--workspace", str(ws),
            "--host-manifest", str(host_d / "host-manifest.json"),
            "--results", str(res_file),
            "--out", str(bundle_file),
        ]
        res_bun = subprocess.run(cmd_bundle, capture_output=True, text=True, timeout=30)
        self.assertEqual(res_bun.returncode, 0, res_bun.stderr)
        bun_json = json.loads(res_bun.stdout)
        self.assertEqual(bun_json["result"], "bundled")
        self.assertEqual(bun_json["summary"]["exception_count"], 0)

    def test_plan_scope_and_selected_identities_guards(self):
        ws = self.root / "ws_guards"
        ws.mkdir()
        (ws / "g.csv").write_text("key,source,target,state\ng1,Hi,,pending\n", encoding="utf-8")
        base_plan = {
            "package_id": "pkg_g",
            "project_id": "proj_g",
            "tables": [{
                "translation_id": "g",
                "domain": "d",
                "path": "g.csv",
                "mapping": {"key_column": "key", "source_column": "source", "target_column": "target", "state_column": "state"},
                "token_pattern": r"\{[0-9]+\}",
            }],
        }

        # Guard 1: Plan declares scope='exception', but invocation requested scope='full'
        plan_mismatch = dict(base_plan, scope="exception")
        with self.assertRaisesRegex(ValueError, "plan scope mismatch"):
            m.export_package(ws, plan_mismatch, ws / "out1", ws / "host1", scope="full")

        # Guard 2: Plan supplies selected_identities when scope='full'
        plan_bad_sel = dict(base_plan, selected_identities=[["g", "d", "g1"]])
        with self.assertRaisesRegex(ValueError, "selected_identities is only supported for scope='exception'"):
            m.export_package(ws, plan_bad_sel, ws / "out2", ws / "host2", scope="full")

        # Guard 3: Standard full-scope export INSTRUCTIONS.md does NOT contain specialized exception directive
        out_std = ws / "out_std"
        host_std = ws / "host_std"
        m.export_package(ws, base_plan, out_std, host_std, scope="full")
        std_instr = (out_std / "INSTRUCTIONS.md").read_text(encoding="utf-8")
        self.assertNotIn("SPECIALIZED EXCEPTION DIRECTIVE", std_instr)


if __name__ == "__main__":
    unittest.main()
