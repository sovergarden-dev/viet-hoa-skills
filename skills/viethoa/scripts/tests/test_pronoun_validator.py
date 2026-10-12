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

    def test_redteam_r5_trap_corpus_30_dirty_50_clean(self) -> None:
        """Verify expanded corpus with >=30 dirty and >=50 clean cases covering trap homographs."""
        matrix = {
            "$schema": "viethoa/pronoun-matrix/v1",
            "project": "ExpandedTrapHarness",
            "version": "1.0.0",
            "characters": {
                "Father": {"gender": "male", "age_group": "adult", "role": "father"},
                "Mother": {"gender": "female", "age_group": "adult", "role": "mother"},
                "ElderBrother": {"gender": "male", "age_group": "young_adult", "role": "elder_brother"},
                "ElderSister": {"gender": "female", "age_group": "young_adult", "role": "elder_sister"},
                "Child": {"gender": "choice", "age_group": "child", "role": "child"},
                "YoungerSibling": {"gender": "unknown", "age_group": "child", "role": "younger_sibling"},
                "Grandparent": {"gender": "unknown", "age_group": "elder", "role": "grandparent"},
                "Master": {"gender": "male", "age_group": "elder", "role": "teacher"},
                "Disciple": {"gender": "male", "age_group": "young_adult", "role": "student"},
                "UnknownEntity": {"gender": "unknown", "age_group": "unknown", "role": "npc"},
            },
            "matrices": [
                {"speaker": "Father", "listener": "Child", "stage": "all", "self_pronouns": ["ba", "bố", "cha"], "call_pronouns": ["con"]},
                {"speaker": "Mother", "listener": "Child", "stage": "all", "self_pronouns": ["mẹ", "u", "má"], "call_pronouns": ["con"]},
                {"speaker": "Child", "listener": "Father", "stage": "all", "self_pronouns": ["con"], "call_pronouns": ["ba", "bố", "cha"]},
                {"speaker": "Child", "listener": "Mother", "stage": "all", "self_pronouns": ["con"], "call_pronouns": ["mẹ", "u", "má"]},
                {"speaker": "ElderBrother", "listener": "YoungerSibling", "stage": "all", "self_pronouns": ["anh"], "call_pronouns": ["em", "các em"]},
                {"speaker": "YoungerSibling", "listener": "ElderBrother", "stage": "all", "self_pronouns": ["em"], "call_pronouns": ["anh"]},
                {"speaker": "Master", "listener": "Disciple", "stage": "all", "self_pronouns": ["ta", "thầy"], "call_pronouns": ["con", "ngươi"]},
                {"speaker": "Disciple", "listener": "Master", "stage": "all", "self_pronouns": ["con", "đệ tử"], "call_pronouns": ["sư phụ", "thầy"]},
                {"speaker": "Grandparent", "listener": "Child", "stage": "all", "self_pronouns": ["ông", "bà"], "call_pronouns": ["cháu", "con"]},
                {"speaker": "Child", "listener": "Grandparent", "stage": "all", "self_pronouns": ["cháu", "con"], "call_pronouns": ["ông", "bà"]},
            ],
            "special_rules": {
                "forbidden_gendered_pronouns_for_unknown": ["anh", "chị", "ông", "bà"],
                "allowed_neutral_pronouns_for_unknown": ["bạn", "người", "cậu"],
                "group_call_pronouns": ["các con", "các em", "mọi người"],
            },
        }

        # 32 Dirty Synthetic Cases (Must be 100% caught)
        dirty_cases = [
            # 1-5: Mother falsely using self 'em' / call 'anh'
            {"key": "d01", "speaker": "Mother", "listener": "Child", "source": "s", "target": "Em đã bảo con bao nhiêu lần rồi hả?"},
            {"key": "d02", "speaker": "Mother", "listener": "Child", "source": "s", "target": "Dạo này em bận rộn nhiều việc quá."},
            {"key": "d03", "speaker": "Mother", "listener": "Child", "source": "s", "target": "Anh hãy nghe lời mẹ dặn đi nào."},
            {"key": "d04", "speaker": "Mother", "listener": "Child", "source": "s", "target": "Em nghĩ anh nên đi chợ mua đồ giùm em."},
            {"key": "d05", "speaker": "Mother", "listener": "Child", "source": "s", "target": "Này cậu, dừng lại đó ngay lập tức!"},
            # 6-10: Father falsely using self 'em' / 'anh' / call 'em'
            {"key": "d06", "speaker": "Father", "listener": "Child", "source": "s", "target": "Em không biết phải giải thích sao với con nữa."},
            {"key": "d07", "speaker": "Father", "listener": "Child", "source": "s", "target": "Anh sẽ dẫn con đi công viên chơi nhé."},
            {"key": "d08", "speaker": "Father", "listener": "Child", "source": "s", "target": "Em mau vào bàn ăn cơm đi."},
            {"key": "d09", "speaker": "Father", "listener": "Child", "source": "s", "target": "Mày dám cãi lời tao à thằng nhãi?"},
            {"key": "d10", "speaker": "Father", "listener": "Child", "source": "s", "target": "Bạn có thể đưa cho tôi mượn cây bút không?"},
            # 11-15: Child calling Father/Mother as 'anh' / 'em' / 'cậu'
            {"key": "d11", "speaker": "Child", "listener": "Father", "source": "s", "target": "Anh ơi, hôm nay con được điểm mười nè."},
            {"key": "d12", "speaker": "Child", "listener": "Father", "source": "s", "target": "Cậu đi làm về có mệt lắm không?"},
            {"key": "d13", "speaker": "Child", "listener": "Mother", "source": "s", "target": "Em ơi, trưa nay nhà mình ăn món gì vậy?"},
            {"key": "d14", "speaker": "Child", "listener": "Mother", "source": "s", "target": "Bạn mua cho con cuốn truyện này được không?"},
            {"key": "d15", "speaker": "Child", "listener": "Father", "source": "s", "target": "Tôi không thích ăn món rau này đâu."},
            # 16-20: ElderBrother calling YoungerSibling as 'cậu' / 'anh' / 'mày' / self 'em'
            {"key": "d16", "speaker": "ElderBrother", "listener": "YoungerSibling", "source": "s", "target": "Cậu nhớ bảo vệ đồ chơi cẩn thận đấy."},
            {"key": "d17", "speaker": "ElderBrother", "listener": "YoungerSibling", "source": "s", "target": "Mày chào anh, mày đi đâu đấy?"},
            {"key": "d18", "speaker": "ElderBrother", "listener": "YoungerSibling", "source": "s", "target": "Tôi sẽ dẫn cậu đi dạo phố bây giờ."},
            {"key": "d19", "speaker": "ElderBrother", "listener": "YoungerSibling", "source": "s", "target": "Mày liệu hồn mà dọn dẹp phòng ốc đi."},
            {"key": "d20", "speaker": "ElderBrother", "listener": "YoungerSibling", "source": "s", "target": "Bác có muốn ăn thêm chút cháo không?"},
            # 21-25: Master & Disciple relationship drift
            {"key": "d21", "speaker": "Master", "listener": "Disciple", "source": "s", "target": "Em chào đệ tử, em vừa luyện công xong."},
            {"key": "d22", "speaker": "Master", "listener": "Disciple", "source": "s", "target": "Đệ tử hãy làm việc cho ta, bạn ơi."},
            {"key": "d23", "speaker": "Disciple", "listener": "Master", "source": "s", "target": "Tôi chào sư phụ, tôi muốn học tiếp chiêu mới."},
            {"key": "d24", "speaker": "Disciple", "listener": "Master", "source": "s", "target": "Ông hãy truyền dạy kiếm pháp thượng thừa cho tôi."},
            {"key": "d25", "speaker": "Disciple", "listener": "Master", "source": "s", "target": "Mày nghĩ chiêu thức này có thể đả thương được tao sao?"},
            # 26-30: Grandparent & Child drift + UnknownEntity violations
            {"key": "d26", "speaker": "Grandparent", "listener": "Child", "source": "s", "target": "Em chào con, em vừa đi thăm bạn về."},
            {"key": "d27", "speaker": "Grandparent", "listener": "Child", "source": "s", "target": "Anh lại đây ông cho viên kẹo ngọt này."},
            {"key": "d28", "speaker": "Child", "listener": "Grandparent", "source": "s", "target": "Bà ơi, em vừa nhổ cỏ trong vườn xong rồi."},
            {"key": "d29", "speaker": "Child", "listener": "UnknownEntity", "source": "s", "target": "Này bà, người có cần con chỉ đường không?"},
            {"key": "d30", "speaker": "Child", "listener": "UnknownEntity", "source": "s", "target": "Này anh, hãy dừng bước tại cổng thành ngay!"},
            # 31-32: Mixed traps containing numbers & drift
            {"key": "d31", "speaker": "Mother", "listener": "Child", "source": "s", "target": "Em mua được ba quả cam về cho anh ăn rồi này."},
            {"key": "d32", "speaker": "Child", "listener": "Father", "source": "s", "target": "Anh ơi, hôm nay con nhìn thấy ba con cá ngoài sông."},
        ]
        self.assertEqual(len(dirty_cases), 32)
        res_d = pv.scan_dialogue_rows(dirty_cases, matrix)
        self.assertEqual(res_d["drift_count"], 32, f"Expected 32 caught, got {res_d['drift_count']}")

        # 52 Clean Golden Cases (Must be 0 False Positives)
        clean_cases = [
            # Traps 1-10: Noun Classifier 'con' (con mèo, con đường, con số, con dao...)
            {"key": "c01", "speaker": "Mother", "listener": "Child", "source": "s", "target": "Mẹ thấy con mèo đang nằm ngủ trên con đường kia."},
            {"key": "c02", "speaker": "Father", "listener": "Child", "source": "s", "target": "Ba dặn con cẩn thận với con dao bén này nhé."},
            {"key": "c03", "speaker": "Child", "listener": "Father", "source": "s", "target": "Con vừa tính xong những con số phức tạp này rồi ba."},
            {"key": "c04", "speaker": "Mother", "listener": "Child", "source": "s", "target": "Mẹ đứng ngắm con sông quê hương êm đềm trôi."},
            {"key": "c05", "speaker": "Father", "listener": "Child", "source": "s", "target": "Ba nhìn thấy con thuyền đánh cá trở về bến."},
            {"key": "c06", "speaker": "Child", "listener": "Mother", "source": "s", "target": "Mẹ ơi con mắt của con hơi bị mỏi một chút."},
            {"key": "c07", "speaker": "ElderBrother", "listener": "YoungerSibling", "source": "s", "target": "Anh dẫn em qua con suối nhỏ mát lành này."},
            {"key": "c08", "speaker": "Mother", "listener": "Child", "source": "s", "target": "Trái tim mẹ luôn hướng về con tim bé bỏng của con."},
            {"key": "c09", "speaker": "Father", "listener": "Child", "source": "s", "target": "Con người cần phải giữ gìn lòng nhân hậu con à."},
            {"key": "c10", "speaker": "Child", "listener": "Father", "source": "s", "target": "Ba có thích con thỏ trắng mà con mới nuôi không?"},
            # Traps 11-20: Numeral 'ba' (ba người, ba mươi, ba đứa, ba quả...) & Kinship rank (anh ba, chú ba)
            {"key": "c11", "speaker": "Mother", "listener": "Child", "source": "s", "target": "Mẹ vừa gặp ba người bạn cũ ngoài chợ về."},
            {"key": "c12", "speaker": "Child", "listener": "Father", "source": "s", "target": "Con đã chờ ba mươi phút rồi mà ba chưa tới."},
            {"key": "c13", "speaker": "Father", "listener": "Child", "source": "s", "target": "Ba mua cho con ba quả táo chín mọng này."},
            {"key": "c14", "speaker": "Child", "listener": "Mother", "source": "s", "target": "Hôm nay lớp con có ba đứa bạn đạt điểm tuyệt đối mẹ ơi."},
            {"key": "c15", "speaker": "ElderBrother", "listener": "YoungerSibling", "source": "s", "target": "Anh em mình cùng ăn hết ba cái bánh ngọt này nhé."},
            {"key": "c16", "speaker": "Mother", "listener": "Child", "source": "s", "target": "Cả nhà mình đi nghỉ dưỡng trong ba ngày tới con nhé."},
            {"key": "c17", "speaker": "Father", "listener": "Child", "source": "s", "target": "Ba tích góp tiền bạc suốt ba năm ròng rã vì con."},
            {"key": "c18", "speaker": "Child", "listener": "Father", "source": "s", "target": "Con chào chú ba khi đi ngang qua ngõ nhà chú."},
            {"key": "c19", "speaker": "Mother", "listener": "Child", "source": "s", "target": "Bác ba vừa gửi tặng gia đình ta giỏ trái cây tươi."},
            {"key": "c20", "speaker": "ElderBrother", "listener": "YoungerSibling", "source": "s", "target": "Anh ba vừa dặn anh em mình phải giúp đỡ lẫn nhau."},
            # Traps 21-28: Single letter 'u' (u uất, u ám, khối u, u xơ...) vs Maternal 'u ơi'
            {"key": "c21", "speaker": "Child", "listener": "Mother", "source": "s", "target": "Con nhìn thấy đám mây đen u ám phía chân trời."},
            {"key": "c22", "speaker": "Mother", "listener": "Child", "source": "s", "target": "Con đừng để tâm hồn mình chìm trong nỗi u uất."},
            {"key": "c23", "speaker": "Father", "listener": "Child", "source": "s", "target": "Bác sĩ đã phẫu thuật cắt bỏ khối u lành tính rồi con."},
            {"key": "c24", "speaker": "Child", "listener": "Father", "source": "s", "target": "Căn phòng tối tăm u mê này làm con thấy sợ quá ba."},
            {"key": "c25", "speaker": "ElderBrother", "listener": "YoungerSibling", "source": "s", "target": "Anh khuyên em không nên mang tâm trạng u sầu mãi thế."},
            {"key": "c26", "speaker": "Child", "listener": "Mother", "source": "s", "target": "U ơi, con vừa đi học về đến nhà đây ạ."},
            {"key": "c27", "speaker": "Child", "listener": "Mother", "source": "s", "target": "Con lạy u, u tha thứ lỗi lầm lần này cho con."},
            {"key": "c28", "speaker": "Mother", "listener": "Child", "source": "s", "target": "U thương con nhiều lắm, đứa con bé bỏng của u."},
            # Traps 29-36: Perception verb 'thấy' vs 'thầy'
            {"key": "c29", "speaker": "Disciple", "listener": "Master", "source": "s", "target": "Con nhìn thấy thầy đang tịnh tâm tọa thiền dưới gốc tùng."},
            {"key": "c30", "speaker": "Master", "listener": "Disciple", "source": "s", "target": "Ta cảm thấy tâm hồn con đã thanh thản hơn trước."},
            {"key": "c31", "speaker": "Disciple", "listener": "Master", "source": "s", "target": "Con nhận thấy lời dạy của sư phụ vô cùng uyên thâm."},
            {"key": "c32", "speaker": "Child", "listener": "Mother", "source": "s", "target": "Mẹ ơi con thấy con mèo đang trèo lên mái nhà."},
            {"key": "c33", "speaker": "Father", "listener": "Child", "source": "s", "target": "Ba trông thấy con chăm chỉ học tập ba mừng lắm."},
            {"key": "c34", "speaker": "Disciple", "listener": "Master", "source": "s", "target": "Thưa thầy, con xin ghi lòng tạc dạ những lời thầy truyền."},
            {"key": "c35", "speaker": "Child", "listener": "Father", "source": "s", "target": "Con thấy mình chưa thật sự chuẩn bị kỹ cho kỳ thi ba à."},
            {"key": "c36", "speaker": "Mother", "listener": "Child", "source": "s", "target": "Mẹ thấy con lớn khôn từng ngày mẹ an tâm rồi."},
            # Traps 37-44: 3rd-person mentions 'cháu nó', 'cháu ấy', 'anh ấy', 'em ấy'
            {"key": "c37", "speaker": "Grandparent", "listener": "Child", "source": "s", "target": "Cháu nó đang ngủ say trong nôi, ông bà đừng làm ồn nhé."},
            {"key": "c38", "speaker": "Mother", "listener": "Child", "source": "s", "target": "Con để cho cháu nó nghỉ ngơi một chút đi con."},
            {"key": "c39", "speaker": "ElderBrother", "listener": "YoungerSibling", "source": "s", "target": "Anh dặn em cẩn thận với em ấy khi chơi ngoài sân."},
            {"key": "c40", "speaker": "YoungerSibling", "listener": "ElderBrother", "source": "s", "target": "Em nghe theo lời anh dặn và không làm phiền anh ấy nữa."},
            {"key": "c41", "speaker": "Mother", "listener": "Child", "source": "s", "target": "Bác ba dặn mẹ chăm sóc cháu nó thật chu đáo."},
            {"key": "c42", "speaker": "Father", "listener": "Child", "source": "s", "target": "Ba vừa chở cháu nó sang nhà cô giáo học vẽ rồi."},
            {"key": "c43", "speaker": "Child", "listener": "Mother", "source": "s", "target": "Mẹ ơi chị ấy vừa sang gửi quà biếu mẹ này."},
            {"key": "c44", "speaker": "ElderBrother", "listener": "YoungerSibling", "source": "s", "target": "Anh thấy cô ấy vừa đi ngang qua cổng trường em à."},
            # Traps 45-52: Compounds & plural modifiers (một mình, tự mình, các em, các con)
            {"key": "c45", "speaker": "Child", "listener": "Mother", "source": "s", "target": "Mẹ có chắc là con ra ngoài đó một mình sẽ an toàn không?"},
            {"key": "c46", "speaker": "Child", "listener": "Father", "source": "s", "target": "Con tự mình hoàn thành bài tập vẽ tranh này ba ơi."},
            {"key": "c47", "speaker": "Mother", "listener": "Child", "source": "s", "target": "Mẹ muốn các con dắt theo các em trong chuyến dạo chơi này."},
            {"key": "c48", "speaker": "Father", "listener": "Child", "source": "s", "target": "Ba tin các con sẽ biết bảo ban các em học hành nghiêm chỉnh."},
            {"key": "c49", "speaker": "Mother", "listener": "Child", "source": "s", "target": "Nào các con, hãy đi theo anh trai và nghe lời anh dặn nhé!"},
            {"key": "c50", "speaker": "Disciple", "listener": "Master", "source": "s", "target": "Con xin nhận lấy bài học này cho riêng mình thưa sư phụ."},
            {"key": "c51", "speaker": "ElderBrother", "listener": "YoungerSibling", "source": "s", "target": "Này, cẩn thận với em ấy chứ! Các em làm vỡ đồ bây giờ."},
            {"key": "c52", "speaker": "Child", "listener": "Father", "source": "s", "target": "Ba ơi, con thấy chính mình cần phải nỗ lực rèn luyện nhiều hơn."},
        ]
        self.assertEqual(len(clean_cases), 52)
        res_c = pv.scan_dialogue_rows(clean_cases, matrix)
        self.assertEqual(res_c["drift_count"], 0, f"Expected 0 False Positives, got {res_c['drift_count']}: {res_c['violations']}")

    def test_c28_unicode_byte_exact_preservation(self) -> None:
        """Verify C28 invariant: evidence, target, source are byte-identical NFC regardless of NFD input."""
        import unicodedata
        matrix = {
            "characters": {
                "Mother": {"gender": "female", "role": "mother"},
                "Child": {"gender": "choice", "role": "child"},
            },
            "matrices": [
                {"speaker": "Mother", "listener": "Child", "stage": "all", "self_pronouns": ["mẹ"], "call_pronouns": ["con"]},
            ],
            "special_rules": {},
        }

        # Create decomposed NFD strings intentionally
        # 'mẹ' decomposed: 'm' + 'e' + U+0323
        # 'đang' with decomposed characters
        raw_dirty_target = unicodedata.normalize("NFD", "Dạo này em đang thèm quả mọng lắm.")
        raw_source = unicodedata.normalize("NFD", "I crave berries lately.")

        # Verify input is truly decomposed and different in raw bytes from NFC
        self.assertNotEqual(raw_dirty_target.encode("utf-8"), unicodedata.normalize("NFC", raw_dirty_target).encode("utf-8"))

        rows = [{
            "key": "c28_test",
            "speaker": "Mother",
            "listener": "Child",
            "source": raw_source,
            "target": raw_dirty_target,
        }]

        res = pv.scan_dialogue_rows(rows, matrix)
        self.assertEqual(res["drift_count"], 1)
        v = res["violations"][0]

        # Target and source in violations MUST strictly adhere to NFC byte representation
        expected_target_nfc = unicodedata.normalize("NFC", raw_dirty_target)
        expected_source_nfc = unicodedata.normalize("NFC", raw_source)

        self.assertEqual(v["target"].encode("utf-8"), expected_target_nfc.encode("utf-8"))
        self.assertEqual(v["source"].encode("utf-8"), expected_source_nfc.encode("utf-8"))
        # Verify unauthorized pronouns in violation payload are strictly NFC
        for p in v.get("unauthorized_self", []):
            self.assertTrue(unicodedata.is_normalized("NFC", p))
        for p in v.get("unauthorized_call", []):
            self.assertTrue(unicodedata.is_normalized("NFC", p))


if __name__ == "__main__":
    unittest.main()
