import csv
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parents[1]
SCRIPT_PATH = SCRIPT_DIR / "domestication_detector.py"

import importlib.util

spec = importlib.util.spec_from_file_location("dom_detector", SCRIPT_PATH)
detector = importlib.util.module_from_spec(spec)
spec.loader.exec_module(detector)


class TestDomesticationDetector(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.root = Path(self.tmp_dir).resolve()

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_horny_euphemism_detected(self):
        items = [
            {"key": "stat_horny", "source": "HORNY", "target": "HƯNG PHẤN"},
            {"key": "stat_clean", "source": "HORNY", "target": "DÂM DỤC"},
        ]
        violations = detector.scan_pairs(items)
        self.assertEqual(len(violations), 1)
        self.assertEqual(violations[0]["rule_id"], "horny_euphemism")
        self.assertEqual(violations[0]["category"], "banned_euphemism")

    def test_perversion_bureaucratic_detected(self):
        items = [
            {"key": "item_perv", "source": "Small Perversion Brew", "target": "Thuốc Đồi Trụy Nhỏ"},
            {"key": "item_clean", "source": "Small Perversion Brew", "target": "Thuốc Biến Thái Nhỏ"},
        ]
        violations = detector.scan_pairs(items)
        self.assertEqual(len(violations), 1)
        self.assertEqual(violations[0]["rule_id"], "perversion_bureaucratic")
        self.assertEqual(violations[0]["category"], "bureaucratic_softening")

    def test_trenchcoat_archaic_loanword_detected(self):
        items = [
            {"key": "outfit_trench", "source": "Un/ZIP Trenchcoat", "target": "Áo Măng Tô Khóa Kéo"},
            {"key": "outfit_clean", "source": "Un/ZIP Trenchcoat", "target": "Áo Choàng Un/ZIP"},
        ]
        violations = detector.scan_pairs(items)
        self.assertEqual(len(violations), 1)
        self.assertEqual(violations[0]["rule_id"], "trenchcoat_archaic_loanword")
        self.assertEqual(violations[0]["category"], "archaic_loanword")

    def test_weatherbear_brand_flattening_detected(self):
        items = [
            {"key": "app_wb", "source": "WEATHERBEAR", "target": "DỰ BÁO THỜI TIẾT"},
            {"key": "app_clean", "source": "WEATHERBEAR", "target": "WeatherBear (Dự Báo)"},
        ]
        violations = detector.scan_pairs(items)
        self.assertEqual(len(violations), 1)
        self.assertEqual(violations[0]["rule_id"], "weatherbear_brand_flattening")
        self.assertEqual(violations[0]["category"], "brand_flattening")

    def test_scan_canonical_csv_clean_and_dirty(self):
        csv_file = self.root / "dialogue.csv"
        with csv_file.open("w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f)
            w.writerow(["key", "source", "translation_vi", "state"])
            w.writerow(["k1", "HORNY", "HƯNG PHẤN", "translated"])
            w.writerow(["k2", "Hello", "Xin chào", "translated"])

        res = detector.scan_canonical_csv(csv_file)
        self.assertEqual(res["violation_count"], 1)
        self.assertFalse(res["canonical_modified"])

    def test_scan_json_dict(self):
        json_file = self.root / "dict.json"
        json_file.write_text(json.dumps({
            "HORNY": "HƯNG PHẤN",
            "Trenchcoat (Black)": "Áo Măng Tô (Đen)",
            "Safe Key": "An Toàn",
        }, ensure_ascii=False), encoding="utf-8")

        res = detector.scan_localization_dict_json(json_file)
        self.assertEqual(res["violation_count"], 2)
        self.assertFalse(res["canonical_modified"])

    def test_custom_rules_loading(self):
        rules_file = self.root / "custom_rules.json"
        rules_file.write_text(json.dumps([
            {
                "rule_id": "custom_curse",
                "category": "euphemism",
                "source_pattern": r"\bfuck\b",
                "target_pattern": r"\bchết tiệt\b",
                "rationale": "fuck should be translated as mẹ kiếp / đụ má, not softened to chết tiệt",
            }
        ]), encoding="utf-8")

        rules = detector.load_rules(rules_file)
        self.assertEqual(len(rules), 1)

        items = [{"key": "1", "source": "Fuck off!", "target": "Chết tiệt cút đi!"}]
        violations = detector.scan_pairs(items, rules=rules)
        self.assertEqual(len(violations), 1)
        self.assertEqual(violations[0]["rule_id"], "custom_curse")

    def test_cli_subprocess_execution(self):
        json_file = self.root / "cli_dict.json"
        json_file.write_text(json.dumps({
            "WEATHERBEAR": "DỰ BÁO THỜI TIẾT",
            "OK": "Được",
        }), encoding="utf-8")

        report_file = self.root / "report.json"
        cmd = [
            sys.executable, str(SCRIPT_PATH),
            "--file", str(json_file),
            "--format", "json",
            "--out-report", str(report_file),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(proc.returncode, 1)  # 1 because violations > 0
        self.assertTrue(report_file.exists())
        data = json.loads(report_file.read_text(encoding="utf-8"))
        self.assertEqual(data["violation_count"], 1)


if __name__ == "__main__":
    unittest.main()
