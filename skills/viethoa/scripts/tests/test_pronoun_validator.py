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


if __name__ == "__main__":
    unittest.main()
