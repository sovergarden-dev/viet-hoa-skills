import re
import unittest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
FONTV_DIR = ROOT_DIR / "skills" / "fonttv"
VIETHOA_DIR = ROOT_DIR / "skills" / "viethoa"


class TestRouterGolden(unittest.TestCase):
    """End-to-end golden verification tests for fonttv and viethoa routers (C19 & C23)."""

    def test_fonttv_skill_size_budget_and_directives(self):
        skill_file = FONTV_DIR / "SKILL.md"
        self.assertTrue(skill_file.exists(), "fonttv/SKILL.md must exist")

        text = skill_file.read_text(encoding="utf-8")
        lf_bytes = len(text.replace("\r\n", "\n").encode("utf-8"))
        self.assertLessEqual(
            lf_bytes,
            10240,
            f"fonttv/SKILL.md is {lf_bytes:,} bytes LF, exceeds 10KB cap (C19)",
        )

        # Mandatory reading directives check
        self.assertIn(
            "references/tool-inventory-and-verdicts.md",
            text,
            "Must link tool-inventory-and-verdicts.md",
        )
        self.assertIn(
            "references/workflow-and-route-lifecycle.md",
            text,
            "Must link workflow-and-route-lifecycle.md",
        )
        self.assertIn(
            "references/unity-tmp-fallback-and-weight-policy.md",
            text,
            "Must link unity-tmp-fallback-and-weight-policy.md",
        )

    def test_fonttv_all_reference_links_resolve_on_disk(self):
        skill_file = FONTV_DIR / "SKILL.md"
        text = skill_file.read_text(encoding="utf-8")
        ref_links = re.findall(r"references/([a-zA-Z0-9_\-]+\.md)", text)
        self.assertGreaterEqual(len(ref_links), 15, "Expected at least 15 reference links")

        missing = []
        for l in sorted(set(ref_links)):
            target = FONTV_DIR / "references" / l
            if not target.exists() or target.stat().st_size == 0:
                missing.append(l)

        self.assertEqual(len(missing), 0, f"Missing or empty reference files: {missing}")

    def test_tool_inventory_and_verdicts_spec_completeness(self):
        tiv_file = FONTV_DIR / "references" / "tool-inventory-and-verdicts.md"
        self.assertTrue(tiv_file.exists(), "tool-inventory-and-verdicts.md must exist")

        content = tiv_file.read_text(encoding="utf-8")
        # Must retain full 7-script audit capability inventory
        self.assertIn("scripts/fonttv_audit.py", content)
        self.assertIn("scripts/shaping_audit.py", content)
        self.assertIn("scripts/custom_encoding_audit.py", content)
        self.assertIn("scripts/proof_level_check.py", content)
        self.assertIn("scripts/tmpro_audit.py", content)

        # Must retain exit code specifications 0..4
        for code in ["0", "1", "2", "3", "4"]:
            self.assertIn(code, content)

        # Must retain semantic reexecution and fixture isolation contracts
        self.assertIn("semantic_reexecution", content)
        self.assertIn("tempfile.TemporaryDirectory()", content)

    def test_viethoa_skill_budget_and_corpus_pointers(self):
        skill_file = VIETHOA_DIR / "SKILL.md"
        self.assertTrue(skill_file.exists(), "viethoa/SKILL.md must exist")

        text = skill_file.read_text(encoding="utf-8")
        lf_bytes = len(text.replace("\r\n", "\n").encode("utf-8"))
        self.assertLessEqual(
            lf_bytes,
            15360,
            f"viethoa/SKILL.md is {lf_bytes:,} bytes LF, exceeds 15KB cap",
        )

        self.assertIn("references/anti-domestication-corpus.md", text)
        self.assertIn("templates/proper-noun-ledger.csv", text)

        corpus_file = VIETHOA_DIR / "references" / "anti-domestication-corpus.md"
        ledger_file = VIETHOA_DIR / "templates" / "proper-noun-ledger.csv"
        self.assertTrue(corpus_file.exists(), "anti-domestication-corpus.md must exist")
        self.assertTrue(ledger_file.exists(), "proper-noun-ledger.csv must exist")


if __name__ == "__main__":
    unittest.main()
