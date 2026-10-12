from __future__ import annotations

import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

# Bootstrap sys.path to import modules from parent directory
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pronoun_validator as pv


class TestPronounValidator(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.matrix_data = {
            "characters": {
                "Protagonist": {"gender": "choice", "age_group": "young_adult", "role": "hero"},
                "Mentor": {"gender": "male", "age_group": "elder", "role": "teacher"},
                "Rival": {"gender": "female", "age_group": "young_adult", "role": "competitor"},
                "UnknownEntity": {"gender": "unknown", "age_group": "adult", "role": "npc"},
            },
            "matrices": [
                {
                    "speaker": "Protagonist",
                    "listener": "Mentor",
                    "stage": "all",
                    "self_pronouns": ["con", "tôi"],
                    "call_pronouns": ["thầy", "sư phụ", "người"],
                    "emotion_exceptions": {
                        "rebellious": {
                            "self_pronouns": ["tôi"],
                            "call_pronouns": ["ông"]
                        }
                    },
                    "confidence": "high",
                },
                {
                    "speaker": "Protagonist",
                    "listener": "Rival",
                    "stage": "early",
                    "self_pronouns": ["tôi"],
                    "call_pronouns": ["cô", "cậu"],
                    "emotion_exceptions": {
                        "hostile": {
                            "self_pronouns": ["tao"],
                            "call_pronouns": ["mày"]
                        }
                    },
                    "confidence": "high",
                },
                {
                    "speaker": "Protagonist",
                    "listener": "Rival",
                    "stage": "late",
                    "self_pronouns": ["mình", "tôi"],
                    "call_pronouns": ["cậu", "bạn"],
                    "emotion_exceptions": {},
                    "confidence": "medium",
                },
                {
                    "speaker": "*",
                    "listener": "Mentor",
                    "stage": "all",
                    "self_pronouns": ["tôi"],
                    "call_pronouns": ["đại sư", "thầy", "tiền bối"],
                },
            ],
            "special_rules": {
                "forbidden_gendered_pronouns_for_unknown": ["cô", "nàng", "chị", "bà", "anh", "chú", "ông"],
                "allowed_neutral_pronouns_for_unknown": ["người đó", "họ", "kẻ đó", "đối phương", "người"],
                "group_call_pronouns": ["các bạn", "mọi người", "các ngươi", "chúng mày"]
            }
        }

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_clean_dialogue_passes(self) -> None:
        rows = [
            {
                "key": "d1",
                "speaker": "Protagonist",
                "listener": "Mentor",
                "source": "I respect you, master.",
                "target": "Con luôn kính trọng thầy.",
            }
        ]
        res = pv.scan_dialogue_rows(rows, self.matrix_data)
        self.assertEqual(res["drift_count"], 0)
        self.assertEqual(res["scanned_dialogue_count"], 1)

    def test_unauthorized_pronoun_drift_flagged(self) -> None:
        rows = [
            {
                "key": "d2",
                "speaker": "Protagonist",
                "listener": "Mentor",
                "source": "Hey you, listen to me!",
                "target": "Mày nghe tao nói đây!",  # Completely unauthorized for Mentor
            }
        ]
        res = pv.scan_dialogue_rows(rows, self.matrix_data)
        self.assertEqual(res["drift_count"], 1)
        v = res["violations"][0]
        self.assertEqual(v["issue_type"], "pronoun_drift")
        self.assertIn("mày", v["unauthorized_call"])
        self.assertIn("tao", v["unauthorized_self"])

    def test_stage_progression_differentiation(self) -> None:
        # Protagonist -> Rival in early stage allows "cô/cậu", late stage allows "bạn/cậu"
        # Using "mình" in early stage should flag drift
        rows = [
            {
                "key": "d_early",
                "speaker": "Protagonist",
                "listener": "Rival",
                "stage": "early",
                "source": "I will defeat you.",
                "target": "Mình sẽ đánh bại cậu.",  # "mình" only allowed in late stage
            },
            {
                "key": "d_late",
                "speaker": "Protagonist",
                "listener": "Rival",
                "stage": "late",
                "source": "I will defeat you.",
                "target": "Mình sẽ giúp đỡ bạn.",  # Valid in late stage
            }
        ]
        res = pv.scan_dialogue_rows(rows, self.matrix_data)
        self.assertEqual(res["drift_count"], 1)
        self.assertEqual(res["violations"][0]["key"], "d_early")

    def test_emotion_exception_unlocks_alternate_pronouns(self) -> None:
        rows = [
            {
                "key": "d_hostile",
                "speaker": "Protagonist",
                "listener": "Rival",
                "stage": "early",
                "emotion": "hostile",
                "source": "I hate you!",
                "target": "Tao ghét mày!",  # Allowed under hostile emotion exception
            }
        ]
        res = pv.scan_dialogue_rows(rows, self.matrix_data)
        self.assertEqual(res["drift_count"], 0)

    def test_third_person_and_reflexive_and_honorific_not_flagged(self) -> None:
        rows = [
            {
                "key": "d_3rd",
                "speaker": "Protagonist",
                "listener": "Mentor",
                "source": "He told me that it was over.",
                # "hắn" (3rd person) and "nó" (3rd person) should not be flagged as call pronouns to Mentor
                "target": "Hắn nói với con rằng nó đã kết thúc rồi.",
            },
            {
                "key": "d_honorific",
                "speaker": "Protagonist",
                "listener": "Mentor",
                "source": "Yes, madam.",
                "target": "Dạ vâng, thưa bà.",
            },
            {
                "key": "d_reflexive",
                "speaker": "Protagonist",
                "listener": "Mentor",
                "source": "They are looking at me.",
                "target": "Bọn họ đang nhìn chằm chằm mình.",
            },
        ]
        res = pv.scan_dialogue_rows(rows, self.matrix_data)
        self.assertEqual(res["drift_count"], 0)

    def test_unknown_gender_guardrail(self) -> None:
        rows = [
            {
                "key": "d_unk",
                "speaker": "Protagonist",
                "listener": "UnknownEntity",
                "source": "Look at her over there.",
                "target": "Hãy nhìn cô ấy ở đằng kia kìa.",  # "cô" is forbidden for unknown gender
            }
        ]
        res = pv.scan_dialogue_rows(rows, self.matrix_data)
        self.assertEqual(res["drift_count"], 1)
        v = res["violations"][0]
        self.assertEqual(v["issue_type"], "gendered_pronoun_on_unknown")

    def test_compound_false_positive_suppression(self) -> None:
        rows = [
            {
                "key": "d_compound",
                "speaker": "Protagonist",
                "listener": "Mentor",
                "source": "The road ahead is lonely, my heroic brother.",
                # "con đường", "cô đơn", "anh hùng", "chú ý" should not trigger pronoun drift
                "target": "Con đường phía trước thật cô đơn, người anh hùng hãy chú ý.",
            },
            {
                "key": "d_compound_field",
                "speaker": "Protagonist",
                "listener": "Mentor",
                "source": "Fill in for my missing bunny.",
                # "cô thỏ", "cho riêng mình" should not trigger pronoun drift
                "target": "Thế chỗ cô thỏ đang thiếu của tôi đi, nhận đồ cho riêng mình.",
            },
        ]
        res = pv.scan_dialogue_rows(rows, self.matrix_data)
        self.assertEqual(res["drift_count"], 0)

    def test_conversational_listener_inference(self) -> None:
        # Context block with 2 speakers taking turns where listener is omitted in the raw table
        rows = [
            {
                "key": "c1",
                "context_id": "scene_forest_01",
                "speaker": "Protagonist",
                "source": "Greetings master.",
                "target": "Con kính chào thầy.",
            },
            {
                "key": "c2",
                "context_id": "scene_forest_01",
                "speaker": "Mentor",
                "source": "You came, disciple.",
                "target": "Ta chờ con đã lâu.",
            }
        ]
        res = pv.scan_dialogue_rows(rows, self.matrix_data, infer_listeners=True)
        self.assertEqual(res["drift_count"], 0)
        self.assertEqual(res["scanned_dialogue_count"], 2)

    def test_wildcard_precedence_tier(self) -> None:
        # Anyone (*) speaking to Mentor uses wildcard rule tier
        rows = [
            {
                "key": "d_wildcard",
                "speaker": "StrangerNPC",
                "listener": "Mentor",
                "source": "Master, help me.",
                "target": "Tôi xin tiền bối giúp đỡ.",
            }
        ]
        res = pv.scan_dialogue_rows(rows, self.matrix_data)
        self.assertEqual(res["drift_count"], 0)

    def test_scan_canonical_csv_read_only(self) -> None:
        csv_file = self.root / "dialogue.csv"
        matrix_file = self.root / "matrix.json"

        matrix_file.write_text(json.dumps(self.matrix_data, ensure_ascii=False), encoding="utf-8")
        rows = [
            {"key": "r1", "speaker": "Protagonist", "listener": "Mentor", "source": "Master", "translation_vi": "Con chào thầy.", "context_id": "s1", "notes": ""},
            {"key": "r2", "speaker": "Protagonist", "listener": "Mentor", "source": "Hey you", "translation_vi": "Mày đó hả?", "context_id": "s1", "notes": ""},
        ]
        with csv_file.open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["key", "speaker", "listener", "source", "translation_vi", "context_id", "notes"])
            writer.writeheader()
            writer.writerows(rows)

        orig_bytes = csv_file.read_bytes()
        res = pv.scan_canonical_csv(csv_file, matrix_file)
        self.assertEqual(res["scanned_dialogue_count"], 2)
        self.assertEqual(res["drift_count"], 1)
        self.assertEqual(res["canonical_modified"], False)
        # Verify canonical file was byte-identical after scan
        self.assertEqual(csv_file.read_bytes(), orig_bytes)

    def test_directional_kinship_and_false_positive_guardrails(self) -> None:
        """Verify directional kinship validation with 100% recall on synthetic errors and 0 FP on clean phrasing."""
        kinship_matrix = {
            "$schema": "viethoa/pronoun-matrix/v1",
            "project": "KinshipHarness",
            "version": "1.0.0",
            "characters": {
                "MotherEntity": {"gender": "female", "age_group": "adult", "role": "mother"},
                "ChildEntity": {"gender": "choice", "age_group": "child", "role": "protagonist"},
                "ElderBrotherEntity": {"gender": "male", "age_group": "young_adult", "role": "elder_brother"},
                "YoungerSiblingEntity": {"gender": "unknown", "age_group": "child", "role": "younger_sibling"},
                "UnknownEntity": {"gender": "unknown", "age_group": "unknown", "role": "npc"},
            },
            "matrices": [
                {
                    "speaker": "MotherEntity",
                    "listener": "ChildEntity",
                    "stage": "all",
                    "self_pronouns": ["mẹ"],
                    "call_pronouns": ["con", "các con"],
                    "emotion_exceptions": {},
                },
                {
                    "speaker": "ChildEntity",
                    "listener": "MotherEntity",
                    "stage": "all",
                    "self_pronouns": ["con"],
                    "call_pronouns": ["mẹ"],
                    "emotion_exceptions": {},
                },
                {
                    "speaker": "ElderBrotherEntity",
                    "listener": "YoungerSiblingEntity",
                    "stage": "all",
                    "self_pronouns": ["anh"],
                    "call_pronouns": ["em", "các em"],
                    "emotion_exceptions": {},
                },
            ],
            "special_rules": {
                "forbidden_gendered_pronouns_for_unknown": ["anh", "chị", "ông", "bà"],
                "allowed_neutral_pronouns_for_unknown": ["bạn", "người", "cậu"],
                "group_call_pronouns": ["các con", "các em", "mọi người"],
            },
        }

        # 1. Synthetic Dirty Injections (Must be caught with 100% Recall)
        dirty_rows = [
            {
                "key": "d40",
                "speaker": "MotherEntity",
                "listener": "ChildEntity",
                "source": "Maybe take your siblings with you...",
                "target": "Và có lẽ em nên dắt theo các em trong chuyến phiêu lưu nhỏ này.",
            },
            {
                "key": "d42",
                "speaker": "MotherEntity",
                "listener": "ChildEntity",
                "source": "Follow your brother, he will protect you.",
                "target": "Nào các con, hãy đi theo anh trai và nghe lời anh dặn, anh sẽ bảo vệ các con.",
            },
            {
                "key": "d53",
                "speaker": "MotherEntity",
                "listener": "ChildEntity",
                "source": "If you see berries, grab some for me.",
                "target": "Em chỉ đang nghĩ, lỡ anh có thấy mấy quả mọng trên đĩa, anh có thể lấy thêm vài quả về cho em không?",
            },
            {
                "key": "d54",
                "speaker": "MotherEntity",
                "listener": "ChildEntity",
                "source": "I crave berries lately.",
                "target": "Dạo này em đang ghiền quả mọng lắm.",
            },
            {
                "key": "d55",
                "speaker": "ElderBrotherEntity",
                "listener": "YoungerSiblingEntity",
                "source": "Be careful! You could break the egg.",
                "target": "Này, cẩn thận với em ấy chứ! Cậu có thể làm vỡ vỏ trứng của em ấy đấy.",
            },
        ]
        res_dirty = pv.scan_dialogue_rows(dirty_rows, kinship_matrix)
        self.assertEqual(res_dirty["drift_count"], 5)
        violations_map = {v["key"]: v for v in res_dirty["violations"]}

        # d40: mother falsely uses self 'em'
        self.assertIn("em", violations_map["d40"]["unauthorized_self"])
        # d42: mother falsely uses 'anh'
        self.assertTrue(
            "anh" in violations_map["d42"]["unauthorized_self"]
            or "anh" in violations_map["d42"]["unauthorized_call"]
        )
        # d53: mother falsely uses self 'em' and call 'anh'
        self.assertIn("em", violations_map["d53"]["unauthorized_self"])
        self.assertIn("anh", violations_map["d53"]["unauthorized_call"])
        # d54: mother falsely uses self 'em'
        self.assertIn("em", violations_map["d54"]["unauthorized_self"])
        # d55: elder brother calls sibling 'cậu'
        self.assertIn("cậu", violations_map["d55"]["unauthorized_call"])

        # 2. Golden Clean Rows (Must produce 0 False Positives)
        clean_rows = [
            {
                "key": "c40",
                "speaker": "MotherEntity",
                "listener": "ChildEntity",
                "source": "Maybe take your siblings with you...",
                "target": "Ôi! Và có lẽ con nên dắt theo các em trong chuyến phiêu lưu nhỏ này.",
            },
            {
                "key": "c42",
                "speaker": "MotherEntity",
                "listener": "ChildEntity",
                "source": "Follow your brother and listen to him.",
                "target": "Nào các con, hãy đi theo anh trai và nghe lời anh dặn nhé!",
            },
            {
                "key": "c49",
                "speaker": "ChildEntity",
                "listener": "MotherEntity",
                "source": "Will it be safe for me to go out alone?",
                "target": "Mẹ có chắc là con ra ngoài đó một mình sẽ an toàn không?",
            },
            {
                "key": "c50",
                "speaker": "ChildEntity",
                "listener": "MotherEntity",
                "source": "I don't feel ready.",
                "target": "Con thấy mình chưa thật sự sẵn sàng cho chuyện đó đâu.",
            },
            {
                "key": "c53",
                "speaker": "MotherEntity",
                "listener": "ChildEntity",
                "source": "If you see berries, grab some for mother.",
                "target": "Mẹ chỉ đang nghĩ, ngộ nhỡ con thấy mấy quả mọng... con có thể lấy thêm vài quả về cho mẹ được không?",
            },
            {
                "key": "c54",
                "speaker": "MotherEntity",
                "listener": "ChildEntity",
                "source": "Mother craves berries.",
                "target": "Dạo này mẹ thèm quả mọng quá chừng.",
            },
            {
                "key": "c55",
                "speaker": "ElderBrotherEntity",
                "listener": "YoungerSiblingEntity",
                "source": "Be careful with him! You kids might break the egg.",
                "target": "Này, cẩn thận với em ấy chứ! Các em làm vỡ vỏ trứng của nó bây giờ.",
            },
        ]
        res_clean = pv.scan_dialogue_rows(clean_rows, kinship_matrix)
        self.assertEqual(res_clean["drift_count"], 0)
        self.assertEqual(len(res_clean["violations"]), 0)


if __name__ == "__main__":
    unittest.main()
