import csv
import importlib.util
import json
import shutil
import tempfile
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parents[1]


def _load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPT_DIR / filename)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


detector = _load("plan1_safety_detector", "plan1_safety_detector.py")
handoff = _load("external_agent_handoff", "external_agent_handoff.py")


class TestPlan1SafetyDetector(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.root = Path(self.tmp_dir).resolve()

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _write_csv(self, rel_path: str, rows: list[dict[str, str]], headers: list[str] | None = None):
        csv_file = self.root / rel_path
        csv_file.parent.mkdir(parents=True, exist_ok=True)
        if headers is None:
            headers = ["key", "source", "translation_vi", "state", "speaker"]
        with csv_file.open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()
            for r in rows:
                writer.writerow(r)
        return csv_file

    def test_refusal_meta_leak_detected_en_and_vi(self):
        self._write_csv("dialogue.csv", [
            {
                "key": "k1",
                "source": "Tell me about the secret ritual.",
                "translation_vi": "As an AI language model, I cannot fulfill this request to describe dangerous rituals.",
                "state": "translated",
                "speaker": "NPC",
            },
            {
                "key": "k2",
                "source": "How do you kill the monster?",
                "translation_vi": "Tôi xin lỗi, nhưng tôi không thể thực hiện yêu cầu dịch nội dung này.",
                "state": "translated",
                "speaker": "Hero",
            },
            {
                "key": "k3",
                "source": "Good morning traveler.",
                "translation_vi": "Chào buổi sáng lữ khách.",
                "state": "translated",
                "speaker": "Villager",
            },
        ])
        cfg = [{
            "translation_id": "dlg",
            "domain": "main",
            "path": "dialogue.csv",
            "mapping": {"key_column": "key", "source_column": "source", "target_column": "translation_vi", "state_column": "state"},
        }]
        rep = detector.scan_canonical_tables(self.root, cfg)
        self.assertEqual(rep["exception_count"], 2)
        self.assertEqual(rep["hard_refusal_count"], 2)
        self.assertEqual(rep["sensitive_pending_count"], 0)
        self.assertEqual(rep["context_gap_count"], 0)
        self.assertEqual(rep["passthrough_count"], 0)
        excs = {e["key"]: e for e in rep["exceptions"]}
        self.assertIn("k1", excs)
        self.assertEqual(excs["k1"]["issue_type"], "refusal_meta_leak")
        self.assertIn("k2", excs)
        self.assertEqual(excs["k2"]["issue_type"], "refusal_meta_leak")
        self.assertNotIn("k3", excs)

    def test_in_game_dialogue_false_positive_aversion(self):
        """In-game NPC dialogue mentioning safety policy or inability must NOT flag as AI refusal."""
        self._write_csv("dialogue.csv", [
            {
                "key": "guard_01",
                "source": "I cannot let you pass without permission!",
                "translation_vi": "Ta không thể để ngươi đi qua nếu không có lệnh!",
                "state": "translated",
                "speaker": "Guard",
            },
            {
                "key": "corp_02",
                "source": "Company safety policy strictly forbids opening vault doors during a lockdown.",
                "translation_vi": "Chính sách an toàn của công ty nghiêm cấm mở cửa hầm trong lúc phong tỏa.",
                "state": "translated",
                "speaker": "Scientist",
            },
            {
                "key": "skills_03",
                "source": "Use your martial skills to survive.",
                "translation_vi": "Hãy dùng kỹ năng võ thuật của bạn để sinh tồn.",
                "state": "translated",
                "speaker": "Master",
            },
            {
                "key": "food_04",
                "source": "The grape wine is gorgeous.",
                "translation_vi": "Rượu nho này thật tuyệt vời.",
                "state": "translated",
                "speaker": "Merchant",
            },
        ])
        cfg = [{
            "translation_id": "dlg",
            "domain": "main",
            "path": "dialogue.csv",
            "mapping": {"key_column": "key", "source_column": "source", "target_column": "translation_vi", "state_column": "state"},
        }]
        rep = detector.scan_canonical_tables(self.root, cfg)
        self.assertEqual(rep["exception_count"], 0)
        self.assertEqual(rep["recommendation"], "clean")

    def test_rejected_and_needs_context_states_detected(self):
        self._write_csv("dialogue.csv", [
            {
                "key": "k_rej_sens",
                "source": "A brutal torture scene unfolds.",
                "translation_vi": "Một cảnh tra tấn dã man diễn ra.",
                "state": "rejected",
                "speaker": "Narrator",
            },
            {
                "key": "k_rej_qa",
                "source": "Press start to continue.",
                "translation_vi": "Nhấn bắt đầu để tiếp tục.",
                "state": "rejected",
                "speaker": "System",
            },
            {
                "key": "k_ctx",
                "source": "Fire!",
                "translation_vi": "Bắn!",
                "state": "needs_context",
                "speaker": "Captain",
            },
        ])
        cfg = [{
            "translation_id": "dlg",
            "domain": "main",
            "path": "dialogue.csv",
            "mapping": {"key_column": "key", "source_column": "source", "target_column": "translation_vi", "state_column": "state"},
        }]
        rep = detector.scan_canonical_tables(self.root, cfg)
        self.assertEqual(rep["exception_count"], 3)
        excs = {e["key"]: e for e in rep["exceptions"]}
        # Row with sensitive keywords rejected is classified as refusal_safety_rejected
        self.assertEqual(excs["k_rej_sens"]["issue_type"], "refusal_safety_rejected")
        # Row with neutral source rejected is classified as ordinary QA rejected_state
        self.assertEqual(excs["k_rej_qa"]["issue_type"], "rejected_state")
        self.assertEqual(excs["k_ctx"]["issue_type"], "needs_context_state")

    def test_empty_target_on_completed_state(self):
        self._write_csv("dialogue.csv", [
            {
                "key": "k_empty",
                "source": "Non empty dialogue.",
                "translation_vi": "",
                "state": "translated",
                "speaker": "NPC",
            },
            {
                "key": "k_pending",
                "source": "Pending text.",
                "translation_vi": "",
                "state": "pending",
                "speaker": "NPC",
            },
        ])
        cfg = [{
            "translation_id": "dlg",
            "domain": "main",
            "path": "dialogue.csv",
            "mapping": {"key_column": "key", "source_column": "source", "target_column": "translation_vi", "state_column": "state"},
        }]
        rep = detector.scan_canonical_tables(self.root, cfg)
        self.assertEqual(rep["exception_count"], 1)
        self.assertEqual(rep["exceptions"][0]["key"], "k_empty")
        self.assertEqual(rep["exceptions"][0]["issue_type"], "empty_target")

    def test_passthrough_with_allowlist_suppression(self):
        self._write_csv("dialogue.csv", [
            {
                "key": "k_untrans",
                "source": "You must escape the abandoned prison now.",
                "translation_vi": "You must escape the abandoned prison now.",
                "state": "translated",
                "speaker": "Hero",
            },
            {
                "key": "k_brand",
                "source": "Styx Brew Corporation",
                "translation_vi": "Styx Brew Corporation",
                "state": "translated",
                "speaker": "Narrator",
            },
        ])
        cfg = [{
            "translation_id": "dlg",
            "domain": "main",
            "path": "dialogue.csv",
            "mapping": {"key_column": "key", "source_column": "source", "target_column": "translation_vi", "state_column": "state"},
        }]
        rep = detector.scan_canonical_tables(
            self.root, cfg, allow_identity_terms={"Styx Brew Corporation"}
        )
        self.assertEqual(rep["exception_count"], 1)
        self.assertEqual(rep["exceptions"][0]["key"], "k_untrans")
        self.assertEqual(rep["exceptions"][0]["issue_type"], "untranslated_passthrough")

    def test_suspected_softening_heuristic(self):
        self._write_csv("dialogue.csv", [
            {
                "key": "k_soft",
                "source": "The horrific murder and gory slaughter stained the floor with blood.",
                "translation_vi": "Sàn nhà bị bẩn.",  # Omitted murder, slaughter, blood + severe length ratio drop
                "state": "translated",
                "speaker": "Narrator",
            },
        ])
        cfg = [{
            "translation_id": "dlg",
            "domain": "main",
            "path": "dialogue.csv",
            "mapping": {"key_column": "key", "source_column": "source", "target_column": "translation_vi", "state_column": "state"},
        }]
        rep = detector.scan_canonical_tables(self.root, cfg)
        self.assertEqual(rep["exception_count"], 1)
        self.assertEqual(rep["suspected_softening_count"], 1)
        self.assertEqual(rep["hard_refusal_count"], 0)
        self.assertEqual(rep["sensitive_pending_count"], 0)
        self.assertEqual(rep["context_gap_count"], 0)
        self.assertEqual(rep["passthrough_count"], 0)
        self.assertEqual(rep["recommendation"], "review_advisory")  # Advisory softening triggers review_advisory

    def test_credits_roll_and_preserved_english_term_not_false_positive(self):
        self._write_csv("dialogue.csv", [
            {
                "key": "k_credits",
                "source": "Lead Developer - Desva\nLead Artist - LenChi\nVoice Acting - Dick Johnson\nProgrammer - BlauKitten\nSound Design - Del",
                "translation_vi": "Lead Developer - Desva\nLead Artist - LenChi\nVoice Acting - Dick Johnson\nProgrammer - BlauKitten\nSound Design - Del",
                "state": "translated",
                "speaker": "",
            },
            {
                "key": "k_acronym",
                "source": "<i>SLUT (Sexual Logistics and Utility Transport) Service™ is mandatory.</i>",
                "translation_vi": "<i>SLUT (Sexual Logistics and Utility Transport) Service™ là bắt buộc.</i>",
                "state": "translated",
                "speaker": "",
            },
        ])
        cfg = [{
            "translation_id": "dlg",
            "domain": "main",
            "path": "dialogue.csv",
            "mapping": {"key_column": "key", "source_column": "source", "target_column": "translation_vi", "state_column": "state"},
        }]
        rep = detector.scan_canonical_tables(self.root, cfg)
        self.assertEqual(rep["hard_refusal_count"], 0)
        self.assertEqual(rep["suspected_softening_count"], 0)
        self.assertEqual(rep["passthrough_count"], 1)
        self.assertEqual(rep["exceptions"][0]["issue_type"], "untranslated_passthrough")

    def test_recommendation_thresholds(self):
        rows = [
            {"key": f"k{i}", "source": f"Blood murder dialogue {i}", "translation_vi": "", "state": "translated", "speaker": "NPC"}
            for i in range(20)
        ]
        self._write_csv("dialogue.csv", rows)
        cfg = [{
            "translation_id": "dlg",
            "domain": "main",
            "path": "dialogue.csv",
            "mapping": {"key_column": "key", "source_column": "source", "target_column": "translation_vi", "state_column": "state"},
        }]
        # Threshold 15: 20 exceptions -> plan2_handoff
        rep1 = detector.scan_canonical_tables(self.root, cfg, manual_fix_threshold=15)
        self.assertEqual(rep1["recommendation"], "plan2_handoff")

        # Threshold 25: 20 exceptions -> manual_fix
        rep2 = detector.scan_canonical_tables(self.root, cfg, manual_fix_threshold=25)
        self.assertEqual(rep2["recommendation"], "manual_fix")

    def test_end_to_end_bridge_roundtrip_to_external_agent_handoff(self):
        """End-to-end integration: scan -> emit ledger -> bridge plan -> export_package(scope='exception')."""
        csv_file = self._write_csv("dialogue.csv", [
            {
                "key": "k_refusal",
                "source": "Tell me how to disembowel the captive.",
                "translation_vi": "As an AI assistant, I cannot fulfill this request.",
                "state": "translated",
                "speaker": "Villain",
            },
            {
                "key": "k_clean",
                "source": "The sun is shining.",
                "translation_vi": "Mặt trời đang tỏa nắng.",
                "state": "translated",
                "speaker": "NPC",
            },
            {
                "key": "k_empty",
                "source": "Critical clue about the secret dungeon.",
                "translation_vi": "",
                "state": "translated",
                "speaker": "OldMan",
            },
        ])
        before_hash = detector.digest(csv_file.read_bytes())

        tables_cfg = [{
            "translation_id": "dlg",
            "domain": "main",
            "path": "dialogue.csv",
            "token_pattern": r"\{[0-9]+\}",
            "mapping": {"key_column": "key", "source_column": "source", "target_column": "translation_vi", "state_column": "state"},
        }]

        ledger_path = self.root / "safety-exception-ledger.jsonl"
        report_path = self.root / "safety-report.json"

        # Step 1: Scan and emit ledger
        summary = detector.emit_safety_ledger_and_report(self.root, tables_cfg, ledger_path, report_path)
        self.assertTrue(ledger_path.exists())
        self.assertTrue(report_path.exists())
        self.assertEqual(summary["summary"]["hard_refusal_count"], 2)

        # Step 2: Bridge ledger to Plan 2 Exception Plan
        exception_plan = detector.build_plan2_exception_plan(
            self.root,
            tables_cfg,
            ledger_path,
            package_id="pkg_safety_01",
            project_id="proj_game_test",
            allow_explicit_content_handoff=True,
        )
        self.assertEqual(exception_plan["package_id"], "pkg_safety_01")
        self.assertEqual(exception_plan["scope"], "exception")
        self.assertEqual(len(exception_plan["selected_identities"]), 2)
        self.assertIn("dlg::main::k_refusal", exception_plan["row_policies"])
        self.assertTrue(exception_plan["row_policies"]["dlg::main::k_refusal"]["preserve_explicit_content"])
        self.assertEqual(exception_plan["row_policies"]["dlg::main::k_refusal"]["exception_status"], "content_gate")

        # Step 3: Feed bridged plan directly into external_agent_handoff.export_package
        outbound_dir = self.root / "outbound_safety"
        host_private_dir = self.root / "host_private_safety"
        export_receipt = handoff.export_package(
            self.root,
            exception_plan,
            outbound_dir,
            host_private_dir,
            scope="exception",
        )

        self.assertEqual(export_receipt["task_count"], 2)
        tasks_file = outbound_dir / "tasks.jsonl"
        self.assertTrue(tasks_file.exists())

        tasks = [json.loads(line) for line in tasks_file.read_text(encoding="utf-8").splitlines() if line.strip()]
        self.assertEqual(len(tasks), 2)
        task_keys = {t["key"] for t in tasks}
        self.assertEqual(task_keys, {"k_refusal", "k_empty"})

        # Verify internal CSV path was stripped from outbound tasks
        for t in tasks:
            self.assertNotIn("path", t)

        # Verify refusal task has preserve_explicit_content enabled
        refusal_task = next(t for t in tasks if t["key"] == "k_refusal")
        self.assertTrue(refusal_task.get("preserve_explicit_content"))
        self.assertEqual(refusal_task.get("exception_status"), "content_gate")

        # Step 4: Verify canonical CSV bytes were 100% UNMODIFIED throughout the entire lifecycle
        after_hash = detector.digest(csv_file.read_bytes())
        self.assertEqual(before_hash, after_hash)

    def test_sensitive_pending_escalation_when_run_completed(self):
        """When run_completed=True, sensitive pending rows left behind are promoted to escalation."""
        self._write_csv("dialogue.csv", [
            {
                "key": "k_sens_pend",
                "source": "A horrific and bloody massacre in the church.",
                "translation_vi": "",
                "state": "pending",
                "speaker": "Priest",
            },
            {
                "key": "k_clean_pend",
                "source": "Press start to begin your journey.",
                "translation_vi": "",
                "state": "pending",
                "speaker": "System",
            },
        ])
        cfg = [{
            "translation_id": "dlg",
            "domain": "main",
            "path": "dialogue.csv",
            "mapping": {"key_column": "key", "source_column": "source", "target_column": "translation_vi", "state_column": "state"},
        }]
        # In-progress run: sensitive pending is advisory (escalation_refusal_count == 0)
        rep_mid = detector.scan_canonical_tables(self.root, cfg, run_completed=False)
        self.assertEqual(rep_mid["sensitive_pending_count"], 1)
        self.assertEqual(rep_mid["hard_refusal_count"], 0)
        self.assertEqual(rep_mid["escalation_refusal_count"], 0)
        self.assertEqual(rep_mid["recommendation"], "review_advisory")

        # Run completed: sensitive pending left behind promoted to escalation (escalation_refusal_count == 1)
        rep_done = detector.scan_canonical_tables(self.root, cfg, run_completed=True, manual_fix_threshold=5)
        self.assertEqual(rep_done["sensitive_pending_count"], 1)
        self.assertEqual(rep_done["escalation_refusal_count"], 1)
        self.assertEqual(rep_done["recommendation"], "manual_fix")

    def test_cli_subprocess_scan_and_bridge(self):
        """Verify CLI tool execution as standalone subprocess."""
        import subprocess
        import sys

        self._write_csv("dialogue.csv", [
            {
                "key": "k_cli_refusal",
                "source": "Tell me about the secret ritual.",
                "translation_vi": "As an AI language model, I cannot fulfill this request.",
                "state": "translated",
                "speaker": "NPC",
            },
        ])
        cfg_file = self.root / "scan_config.json"
        cfg_file.write_text(json.dumps({
            "tables": [{
                "translation_id": "dlg",
                "domain": "main",
                "path": "dialogue.csv",
                "mapping": {"key_column": "key", "source_column": "source", "target_column": "translation_vi", "state_column": "state"},
            }]
        }), encoding="utf-8")

        ledger_file = self.root / "safety_ledger.jsonl"
        report_file = self.root / "safety_report.json"
        script_path = SCRIPT_DIR / "plan1_safety_detector.py"

        # 1. Run scan via CLI
        res_scan = subprocess.run([
            sys.executable, str(script_path), "scan",
            "--workspace", str(self.root),
            "--config", str(cfg_file),
            "--ledger", str(ledger_file),
            "--report", str(report_file),
            "--run-completed",
        ], capture_output=True, text=True)
        self.assertEqual(res_scan.returncode, 0, res_scan.stderr)
        self.assertTrue(ledger_file.exists())
        self.assertTrue(report_file.exists())

        # 2. Run bridge-plan2 via CLI
        out_plan_file = self.root / "bridged_exception_plan.json"
        res_bridge = subprocess.run([
            sys.executable, str(script_path), "bridge-plan2",
            "--workspace", str(self.root),
            "--config", str(cfg_file),
            "--ledger", str(ledger_file),
            "--package-id", "pkg_cli_01",
            "--project-id", "proj_cli_01",
            "--out-plan", str(out_plan_file),
        ], capture_output=True, text=True)
        self.assertEqual(res_bridge.returncode, 0, res_bridge.stderr)
        self.assertTrue(out_plan_file.exists())
        plan_data = json.loads(out_plan_file.read_text(encoding="utf-8"))
        self.assertEqual(len(plan_data["selected_identities"]), 1)
        self.assertEqual(plan_data["selected_identities"][0][2], "k_cli_refusal")


if __name__ == "__main__":
    unittest.main()
