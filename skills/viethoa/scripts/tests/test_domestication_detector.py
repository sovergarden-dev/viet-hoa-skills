import csv
import json
import shutil
import subprocess
import sys
import tempfile
import unicodedata
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

    def test_expanded_western_brands_detected(self):
        items = [
            {"key": "k_bd", "source": "Welcome to Blackdog HQ", "target": "Chào mừng đến trụ sở Chó Đen"},
            {"key": "k_tg", "source": "Contract with Titan Group", "target": "Hợp đồng với Tập đoàn khổng lồ"},
            {"key": "k_sb", "source": "Meet at Styx Brew", "target": "Gặp nhau ở quán Bia sông Styx"},
            {"key": "k_nc", "source": "Arriving at Night City", "target": "Đang đến thành phố đêm"},
        ]
        violations = detector.scan_pairs(items)
        detected_rules = {v["rule_id"] for v in violations}
        self.assertIn("blackdog_brand", detected_rules)
        self.assertIn("titan_group_brand", detected_rules)
        self.assertIn("styx_brew_brand", detected_rules)
        self.assertIn("night_city_proper_noun", detected_rules)

    def test_expanded_romaji_names_detected(self):
        items = [
            {"key": "k_sz", "source": "Suzume is waiting", "target": "Chim sẻ đang chờ"},
            {"key": "k_yk", "source": "Letter from Yukari", "target": "Bức thư từ duyên phận"},
            {"key": "k_kz", "source": "Kazuha strikes again", "target": "Nhất diệp lại ra tay"},
            {"key": "k_sj", "source": "Shinji get in the robot", "target": "Chân nhị hãy vào robot"},
            {"key": "k_ht", "source": "Hotaru shines bright", "target": "Đom đóm tỏa sáng rực rỡ"},
        ]
        violations = detector.scan_pairs(items)
        detected_rules = {v["rule_id"] for v in violations}
        self.assertIn("romaji_suzume", detected_rules)
        self.assertIn("romaji_yukari", detected_rules)
        self.assertIn("romaji_kazuha", detected_rules)
        self.assertIn("romaji_shinji", detected_rules)
        self.assertIn("romaji_hotaru", detected_rules)

    def test_expanded_adult_euphemisms_detected(self):
        items = [
            {"key": "k_cp", "source": "Fresh creampie", "target": "Bánh kem tươi ngon"},
            {"key": "k_sl", "source": "She is a whore", "target": "Cô ấy là gái bán hoa"},
            {"key": "k_cm", "source": "I am cumming", "target": "Tôi đang ra mồ hôi"},
            {"key": "k_dd", "source": "Found a dildo", "target": "Tìm thấy máy mát xa"},
        ]
        violations = detector.scan_pairs(items)
        detected_rules = {v["rule_id"] for v in violations}
        self.assertIn("creampie_softening", detected_rules)
        self.assertIn("slut_whore_bureaucratic", detected_rules)
        self.assertIn("cum_ejaculation_softening", detected_rules)
        self.assertIn("dildo_flattening", detected_rules)

    def test_rich_text_placeholders_and_fullwidth_compat(self):
        """Test vectors for C28: rich text tags, placeholders, printf format, and full-width Unicode."""
        test_items = [
            # Rich text / TextMeshPro tags
            {"key": "tag_01", "source": "<color=red>Blackdog</color> is here", "target": "<color=#fff>Chó Đen</color> đã tới"},
            # Placeholders
            {"key": "plc_01", "source": "Hello {player}, Suzume is waiting", "target": "Chào bạn, chim sẻ đang chờ"},
            # Printf format specifiers
            {"key": "prf_01", "source": "Item %s from Titan Group", "target": "Vật phẩm %s từ Tập đoàn khổng lồ"},
            # Full-width Unicode characters (e.g. Japanese IME input)
            {"key": "fw_01", "source": "Ｂｌａｃｋｄｏｇ HQ", "target": "chó đen"},
            # Comparison operators in text should NOT cause issues or false positives
            {"key": "op_01", "source": "If HP < 50 and ATK > 20, use Styx Brew", "target": "Nếu HP < 50 và ATK > 20, dùng bia sông styx"},
        ]
        violations = detector.scan_pairs(test_items)
        detected_rules = {v["rule_id"] for v in violations}
        self.assertIn("blackdog_brand", detected_rules)
        self.assertIn("romaji_suzume", detected_rules)
        self.assertIn("titan_group_brand", detected_rules)
        self.assertIn("styx_brew_brand", detected_rules)
        self.assertEqual(len(violations), 5)

    def test_negative_controls_zero_false_positives(self):
        negative_corpus = [
            # Group 1: General vocabulary containing substrings
            {"key": "neg_01", "source": "A black dog barked outside", "target": "Một con chó đen sủa ngoài sân"},
            {"key": "neg_02", "source": "Titan armor is heavy", "target": "Bộ giáp Titan rất nặng"},
            {"key": "neg_03", "source": "We drank cold beer", "target": "Chúng tôi uống bia lạnh"},
            {"key": "neg_04", "source": "The city skyline was glowing at night", "target": "Đường chân trời thành phố lung linh trong đêm"},
            {"key": "neg_05", "source": "The sparrow flew away", "target": "Con chim sẻ bay đi"},
            {"key": "neg_06", "source": "Fate brought us together", "target": "Duyên phận đã đưa chúng ta đến với nhau"},
            {"key": "neg_07", "source": "A single leaf fell", "target": "Một chiếc lá rơi xuống đất"},
            {"key": "neg_08", "source": "Fireflies glowing in summer", "target": "Đom đóm lập lòe trong đêm hè"},
            {"key": "neg_09", "source": "Strawberry cream pie dessert", "target": "Món tráng miệng bánh kem dâu tây"},
            {"key": "neg_10", "source": "Sweating after training", "target": "Đang toát mồ hôi sau giờ tập luyện"},
            {"key": "neg_11", "source": "Electric neck massager", "target": "Máy mát xa cổ bằng điện"},
            {"key": "neg_12", "source": "Weather forecast for tomorrow", "target": "Dự báo thời tiết ngày mai có mưa"},
            {"key": "neg_13", "source": "Wearing a long wool overcoat", "target": "Mặc một chiếc áo choàng len dài"},
            # Group 2: Valid source-faithful preservations
            {"key": "neg_14", "source": "Welcome to Blackdog HQ", "target": "Chào mừng đến tổng bộ Blackdog"},
            {"key": "neg_15", "source": "Contract with Titan Group", "target": "Hợp đồng với Titan Group"},
            {"key": "neg_16", "source": "Suzume arrived early", "target": "Suzume đã đến từ sớm"},
            {"key": "neg_17", "source": "Yukari greeted everyone", "target": "Yukari cúi đầu chào mọi người"},
            {"key": "neg_18", "source": "Kazuha drew his blade", "target": "Kazuha rút thanh bảo kiếm"},
            {"key": "neg_19", "source": "Shinji took a deep breath", "target": "Shinji hít một hơi thật sâu"},
            {"key": "neg_20", "source": "Hotaru smiled gently", "target": "Hotaru khẽ mỉm cười dịu dàng"},
            {"key": "neg_21", "source": "A bottle of Styx Brew", "target": "Một chai Styx Brew ướp lạnh"},
            {"key": "neg_22", "source": "Living in Night City", "target": "Cuộc sống tại Night City đầy rẫy hiểm nguy"},
            {"key": "neg_23", "source": "Fired a Silver Bullet round", "target": "Bắn ra một phát Silver Bullet"},
            {"key": "neg_24", "source": "HORNY stat increased", "target": "Chỉ số DÂM DỤC đã tăng lên"},
            {"key": "neg_25", "source": "Pervert behavior detected", "target": "Phát hiện hành vi biến thái"},
            # Group 3: NFD decomposed and Unicode normalization variants
            {"key": "neg_26_nfd", "source": unicodedata.normalize("NFD", "A black dog"), "target": unicodedata.normalize("NFD", "Một con chó đen")},
            {"key": "neg_27_nfd", "source": unicodedata.normalize("NFD", "Hotaru is kind"), "target": unicodedata.normalize("NFD", "Hotaru rất tốt bụng")},
            {"key": "neg_28", "source": "The dog was very black", "target": "Con chó này đen tuyền"},
            {"key": "neg_29", "source": "Group of titans formed", "target": "Một nhóm titan đã tập hợp"},
            {"key": "neg_30", "source": "Brewing tea by the river", "target": "Pha trà bên bờ sông"},
            # Group 4: Rich text tags and placeholders in non-violating lines
            {"key": "neg_31", "source": "<color=blue>Dog</color> running", "target": "<color=blue>Chó</color> đang chạy"},
            {"key": "neg_32", "source": "Level {level} reached", "target": "Đạt cấp độ {level}"},
            {"key": "neg_33", "source": "Player %s won", "target": "Người chơi %s đã chiến thắng"},
            {"key": "neg_34", "source": "City lights at midnight", "target": "Ánh đèn đô thị lúc nửa đêm"},
            {"key": "neg_35", "source": "Small pie with cream", "target": "Chiếc bánh nướng nhỏ có kem"},
            {"key": "neg_36", "source": "A massager tool in bag", "target": "Một chiếc máy mát xa trong túi"},
            {"key": "neg_37", "source": "Cold sweat on forehead", "target": "Mồ hôi lạnh toát ra trên trán"},
            {"key": "neg_38", "source": "Rainy weather today", "target": "Thời tiết hôm nay nhiều mưa"},
            {"key": "neg_39", "source": "Classic trench style coat", "target": "Áo khoác phong cách cổ điển"},
            {"key": "neg_40", "source": "Bullet made of silver alloy", "target": "Viên đạn đúc bằng hợp kim bạc"},
            # Group 5: Modern gaming terms and compound phrases
            {"key": "neg_41", "source": "Cyber security system", "target": "Hệ thống an ninh mạng"},
            {"key": "neg_42", "source": "Night patrol duty", "target": "Ca tuần tra ban đêm"},
            {"key": "neg_43", "source": "Sparrow on the roof", "target": "Chim sẻ đậu trên mái nhà"},
            {"key": "neg_44", "source": "The brew has fermented", "target": "Mẻ ủ đã lên men"},
            {"key": "neg_45", "source": "Titanium ore deposit", "target": "Mỏ quặng titan"},
            {"key": "neg_46", "source": "Black hound companion", "target": "Chú chó săn màu đen đi cùng"},
            {"key": "neg_47", "source": "City night festival", "target": "Lễ hội đêm của thành phố"},
            {"key": "neg_48", "source": "Silver coin found", "target": "Tìm thấy một đồng xu bạc"},
            {"key": "neg_49", "source": "Brewing herbal remedy", "target": "Đang nấu thuốc thảo mộc"},
            {"key": "neg_50", "source": "Group strategy session", "target": "Buổi họp chiến thuật của nhóm"},
            {"key": "neg_51", "source": "Weather is clear", "target": "Thời tiết quang đãng"},
            {"key": "neg_52", "source": "Dino footprint fossil", "target": "Hóa thạch dấu chân khủng long cổ đại"},
        ]
        violations = detector.scan_pairs(negative_corpus)
        self.assertEqual(len(violations), 0, f"False positives detected: {violations}")

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
