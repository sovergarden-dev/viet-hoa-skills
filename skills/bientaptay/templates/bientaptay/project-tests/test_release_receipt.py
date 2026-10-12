from __future__ import annotations

import csv
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "release_receipt.py"
_VERSIONED_EXE_BYTES: dict[str, bytes] = {}


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_RECEIPT = _load_module("bientaptay_release_receipt", SCRIPT)
_PUBLISH_TESTS = _load_module("bientaptay_test_publish_script", Path(__file__).resolve().parent / "test_publish_script.py")

_HEX64_A = "a" * 64
_HEX64_B = "b" * 64
_HEX64_C = "c" * 64
_RECORD = (
    '{"id":"'
    + _HEX64_A
    + '","translationId":"scripts","kind":"GlossaryDrift","key":"scene::001","relatedKeys":["scene::001"],"contentFingerprint":"'
    + _HEX64_B
    + '","status":"needs_fix","note":"a","updatedAtUtc":"2026-09-02T00:00:00Z"}'
)
CORE_MALFORMED_QA_DECISIONS: list[tuple[str, bytes]] = [
    ("null-schema", b'{"schema":null,"decisions":[]}'),
    ("null-decisions", b'{"schema":"bientaptay-qa-decisions/v1","decisions":null}'),
    (
        "null-record-fields",
        (
            '{"schema":"bientaptay-qa-decisions/v1","decisions":[{"id":null,"translationId":"scripts","kind":"GlossaryDrift","key":null,"relatedKeys":[],"contentFingerprint":null,"status":null,"note":"","updatedAtUtc":"2026-09-02T00:00:00Z"}]}'
        ).encode("utf-8"),
    ),
    ("non-object-root", b"[1,2,3]"),
    ("null-decision-element", b'{"schema":"bientaptay-qa-decisions/v1","decisions":[null]}'),
    (
        "duplicate-id-case-insensitive",
        (
            '{"schema":"bientaptay-qa-decisions/v1","decisions":['
            + _RECORD
            + ',{"id":"'
            + ("A" * 64)
            + '","translationId":"scripts","kind":"GlossaryDrift","key":"scene::002","relatedKeys":["scene::002"],"contentFingerprint":"'
            + _HEX64_C
            + '","status":"needs_fix","note":"b","updatedAtUtc":"2026-09-02T00:00:00Z"}]}'
        ).encode("utf-8"),
    ),
    (
        "duplicate-id-exact",
        (
            '{"schema":"bientaptay-qa-decisions/v1","decisions":['
            + _RECORD
            + ',{"id":"'
            + _HEX64_A
            + '","translationId":"scripts","kind":"GlossaryDrift","key":"scene::002","relatedKeys":["scene::002"],"contentFingerprint":"'
            + _HEX64_C
            + '","status":"needs_fix","note":"b","updatedAtUtc":"2026-09-02T00:00:00Z"}]}'
        ).encode("utf-8"),
    ),
    (
        "kind-null",
        (
            '{"schema":"bientaptay-qa-decisions/v1","decisions":[{"id":"'
            + _HEX64_A
            + '","translationId":"scripts","kind":null,"key":"scene::001","relatedKeys":["scene::001"],"contentFingerprint":"'
            + _HEX64_B
            + '","status":"needs_fix","note":"a","updatedAtUtc":"2026-09-02T00:00:00Z"}]}'
        ).encode("utf-8"),
    ),
    (
        "kind-invalid",
        (
            '{"schema":"bientaptay-qa-decisions/v1","decisions":[{"id":"'
            + _HEX64_A
            + '","translationId":"scripts","kind":"NotAKind","key":"scene::001","relatedKeys":["scene::001"],"contentFingerprint":"'
            + _HEX64_B
            + '","status":"needs_fix","note":"a","updatedAtUtc":"2026-09-02T00:00:00Z"}]}'
        ).encode("utf-8"),
    ),
    (
        "related-keys-null",
        (
            '{"schema":"bientaptay-qa-decisions/v1","decisions":[{"id":"'
            + _HEX64_A
            + '","translationId":"scripts","kind":"GlossaryDrift","key":"scene::001","relatedKeys":null,"contentFingerprint":"'
            + _HEX64_B
            + '","status":"needs_fix","note":"a","updatedAtUtc":"2026-09-02T00:00:00Z"}]}'
        ).encode("utf-8"),
    ),
    (
        "related-keys-contains-null",
        (
            '{"schema":"bientaptay-qa-decisions/v1","decisions":[{"id":"'
            + _HEX64_A
            + '","translationId":"scripts","kind":"GlossaryDrift","key":"scene::001","relatedKeys":[null],"contentFingerprint":"'
            + _HEX64_B
            + '","status":"needs_fix","note":"a","updatedAtUtc":"2026-09-02T00:00:00Z"}]}'
        ).encode("utf-8"),
    ),
    (
        "related-keys-blank",
        (
            '{"schema":"bientaptay-qa-decisions/v1","decisions":[{"id":"'
            + _HEX64_A
            + '","translationId":"scripts","kind":"GlossaryDrift","key":"scene::001","relatedKeys":[" "],"contentFingerprint":"'
            + _HEX64_B
            + '","status":"needs_fix","note":"a","updatedAtUtc":"2026-09-02T00:00:00Z"}]}'
        ).encode("utf-8"),
    ),
    (
        "status-null",
        (
            '{"schema":"bientaptay-qa-decisions/v1","decisions":[{"id":"'
            + _HEX64_A
            + '","translationId":"scripts","kind":"GlossaryDrift","key":"scene::001","relatedKeys":["scene::001"],"contentFingerprint":"'
            + _HEX64_B
            + '","status":null,"note":"a","updatedAtUtc":"2026-09-02T00:00:00Z"}]}'
        ).encode("utf-8"),
    ),
    (
        "status-unreviewed",
        (
            '{"schema":"bientaptay-qa-decisions/v1","decisions":[{"id":"'
            + _HEX64_A
            + '","translationId":"scripts","kind":"GlossaryDrift","key":"scene::001","relatedKeys":["scene::001"],"contentFingerprint":"'
            + _HEX64_B
            + '","status":"unreviewed","note":"a","updatedAtUtc":"2026-09-02T00:00:00Z"}]}'
        ).encode("utf-8"),
    ),
    (
        "status-accepted",
        (
            '{"schema":"bientaptay-qa-decisions/v1","decisions":[{"id":"'
            + _HEX64_A
            + '","translationId":"scripts","kind":"GlossaryDrift","key":"scene::001","relatedKeys":["scene::001"],"contentFingerprint":"'
            + _HEX64_B
            + '","status":"accepted","note":"a","updatedAtUtc":"2026-09-02T00:00:00Z"}]}'
        ).encode("utf-8"),
    ),
    (
        "note-null",
        (
            '{"schema":"bientaptay-qa-decisions/v1","decisions":[{"id":"'
            + _HEX64_A
            + '","translationId":"scripts","kind":"GlossaryDrift","key":"scene::001","relatedKeys":["scene::001"],"contentFingerprint":"'
            + _HEX64_B
            + '","status":"needs_fix","note":null,"updatedAtUtc":"2026-09-02T00:00:00Z"}]}'
        ).encode("utf-8"),
    ),
    (
        "updated-at-missing",
        (
            '{"schema":"bientaptay-qa-decisions/v1","decisions":[{"id":"'
            + _HEX64_A
            + '","translationId":"scripts","kind":"GlossaryDrift","key":"scene::001","relatedKeys":["scene::001"],"contentFingerprint":"'
            + _HEX64_B
            + '","status":"needs_fix","note":"a"}]}'
        ).encode("utf-8"),
    ),
    (
        "updated-at-default",
        (
            '{"schema":"bientaptay-qa-decisions/v1","decisions":[{"id":"'
            + _HEX64_A
            + '","translationId":"scripts","kind":"GlossaryDrift","key":"scene::001","relatedKeys":["scene::001"],"contentFingerprint":"'
            + _HEX64_B
            + '","status":"needs_fix","note":"a","updatedAtUtc":"0001-01-01T00:00:00+00:00"}]}'
        ).encode("utf-8"),
    ),
    (
        "updated-at-space",
        (
            '{"schema":"bientaptay-qa-decisions/v1","decisions":[{"id":"'
            + _HEX64_A
            + '","translationId":"scripts","kind":"GlossaryDrift","key":"scene::001","relatedKeys":["scene::001"],"contentFingerprint":"'
            + _HEX64_B
            + '","status":"needs_fix","note":"a","updatedAtUtc":"2026-09-02 00:00:00"}]}'
        ).encode("utf-8"),
    ),
    (
        "updated-at-offset-15",
        (
            '{"schema":"bientaptay-qa-decisions/v1","decisions":[{"id":"'
            + _HEX64_A
            + '","translationId":"scripts","kind":"GlossaryDrift","key":"scene::001","relatedKeys":["scene::001"],"contentFingerprint":"'
            + _HEX64_B
            + '","status":"needs_fix","note":"a","updatedAtUtc":"2026-09-02T00:00:00+15:00"}]}'
        ).encode("utf-8"),
    ),
    (
        "id-non-hex",
        (
            '{"schema":"bientaptay-qa-decisions/v1","decisions":[{"id":"'
            + ("g" * 64)
            + '","translationId":"scripts","kind":"GlossaryDrift","key":"scene::001","relatedKeys":["scene::001"],"contentFingerprint":"'
            + _HEX64_B
            + '","status":"needs_fix","note":"a","updatedAtUtc":"2026-09-02T00:00:00Z"}]}'
        ).encode("utf-8"),
    ),
    (
        "fingerprint-non-hex",
        (
            '{"schema":"bientaptay-qa-decisions/v1","decisions":[{"id":"'
            + _HEX64_A
            + '","translationId":"scripts","kind":"GlossaryDrift","key":"scene::001","relatedKeys":["scene::001"],"contentFingerprint":"'
            + ("z" * 64)
            + '","status":"needs_fix","note":"a","updatedAtUtc":"2026-09-02T00:00:00Z"}]}'
        ).encode("utf-8"),
    ),
    ("corrupt-json", b"{not-json"),
    ("unsupported-schema", b'{"schema":"other/v0","decisions":[]}'),
]

QA_TIMESTAMP_PARITY_CASES: list[tuple[str, str, bool]] = [
    ("z", "2026-09-02T00:00:00Z", True),
    ("offset-zero", "2026-09-02T00:00:00+00:00", True),
    ("fractional-z", "2026-09-02T00:00:00.1234567Z", True),
    ("offset-plus-14", "2026-06-15T12:00:00+14:00", True),
    ("set-produced", "2026-09-02T08:30:00.0000000Z", True),
    ("date-only", "2026-09-02", False),
    ("no-offset", "2026-09-02T00:00:00", False),
    ("space-separator", "2026-09-02 00:00:00", False),
    ("offset-plus-14-01", "2026-09-02T00:00:00+14:01", False),
    ("offset-plus-15", "2026-09-02T00:00:00+15:00", False),
    ("utc-overflow-max", "9999-12-31T23:59:59-14:00", False),
    ("utc-underflow-min", "0001-01-01T00:00:00+14:00", False),
    ("dotnet-default-z", "0001-01-01T00:00:00Z", False),
]


def sidecar_with_timestamp(stamp: str) -> bytes:
    return (
        '{"schema":"bientaptay-qa-decisions/v1","decisions":[{"id":"'
        + _HEX64_A
        + '","translationId":"scripts","kind":"GlossaryDrift","key":"scene::001","relatedKeys":["scene::001"],"contentFingerprint":"'
        + _HEX64_B
        + '","status":"needs_fix","note":"a","updatedAtUtc":"'
        + stamp
        + '"}]}'
    ).encode("utf-8")


def versioned_exe_bytes(app_version: str) -> bytes:
    cached = _VERSIONED_EXE_BYTES.get(app_version)
    if cached is not None:
        return cached
    with tempfile.TemporaryDirectory(prefix="bientaptay-versioned-exe-") as temp:
        output = Path(temp) / "out"
        result = _PUBLISH_TESTS.isolated_publish(app_version, output)
        if result.returncode != 0:
            raise AssertionError(result.stdout + result.stderr)
        cached = (output / "BienTapTay.exe").read_bytes()
    _VERSIONED_EXE_BYTES[app_version] = cached
    return cached


class ReleaseReceiptTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="bientaptay-release-")
        self.root = Path(self.temp.name)
        self.project = self.root / "bientaptay" / "project.json"
        self.project.parent.mkdir(parents=True)
        project_tests = self.project.parent / "project-tests"
        project_tests.mkdir()
        (project_tests / "test_publish_script.py").write_text("# gate\n", encoding="utf-8")
        (project_tests / "test_performance_benchmark.py").write_text("# gate\n", encoding="utf-8")
        (self.root / "workbook").mkdir()
        (self.project.parent / "data").mkdir()
        self._write_csv(
            self.root / "workbook" / "main.csv",
            ["key", "source", "translation_vi", "status"],
            [["a", "A", "Dòng 1\nDòng 2", "reviewed"], ["b", "B", "B", "reviewed"]],
        )
        self._write_csv(
            self.root / "workbook" / "ui.csv",
            ["key", "source", "translation_vi", "status"],
            [["ui::1", "Options", "Cài đặt", "reviewed"]],
        )
        self._write_csv(
            self.project.parent / "data" / "glossary.csv",
            ["term", "translation", "status"],
            [["A", "A", "locked"]],
        )
        self._write_csv(
            self.project.parent / "data" / "pronouns.csv",
            ["speaker", "self_reference", "address_form", "notes", "status", "evidence_keys"],
            [["Ema", "tôi", "cậu", "ghi chú", "reviewed", "a"]],
        )
        self.project.write_text(
            json.dumps(
                {
                    "schemaVersion": 1,
                    "projectName": "Test",
                    "canonicalPath": "../workbook/main.csv",
                    "keyColumn": "key",
                    "sourceFields": [{"column": "source", "label": "Nguồn"}],
                    "targetColumn": "translation_vi",
                    "statusColumn": "status",
                    "translationFiles": [
                        {"id": "main", "label": "Main", "path": "../workbook/main.csv"},
                        {"id": "ui", "label": "UI", "path": "../workbook/ui.csv"},
                    ],
                    "references": [
                        {"id": "glossary", "label": "Glossary", "path": "data/glossary.csv", "keyColumn": "term"},
                        {"id": "pronouns", "label": "Pronouns", "path": "data/pronouns.csv", "keyColumn": "speaker"},
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        self.executable = self.root / "staging" / "BienTapTay.exe"
        self.executable.parent.mkdir()
        self.executable.write_bytes(b"release-binary")
        self.live_executable = self.root / "bientaptay" / "app" / "BienTapTay.exe"
        self.existing = self.root / "bientaptay" / "install-receipt.json"
        self.existing.write_text(json.dumps({"features": ["kept-feature"], "consistency_qa": {"warnings_total": 7}}), encoding="utf-8")
        self.baseline = self.root / "baseline.json"
        self.output = self.root / "receipt.tmp"

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_prepare_records_every_file_and_preserves_release_metadata(self) -> None:
        self.executable.write_bytes(versioned_exe_bytes("0.5.1"))
        self._run("snapshot", "--project", self.project, "--output", self.baseline)
        self._run(
            "prepare",
            "--project",
            self.project,
            "--baseline",
            self.baseline,
            "--executable",
            self.executable,
            "--published-executable",
            self.live_executable,
            "--existing-receipt",
            self.existing,
            "--output",
            self.output,
            "--app-version",
            "0.5.1",
        )

        receipt = json.loads(self.output.read_text(encoding="utf-8"))
        self.assertEqual("bientaptay-install/v3", receipt["schema"])
        self.assertEqual("0.5.1", receipt["app_version"])
        self.assertEqual("0.5.1.0", receipt["executable_file_version"])
        self.assertEqual("0.5.1", receipt["executable_product_version"])
        self.assertEqual(3, receipt["text_row_count"])
        self.assertEqual([2, 1], [item["row_count"] for item in receipt["translation_files"]])
        self.assertEqual([1, 1], [item["row_count"] for item in receipt["reference_files"]])
        self.assertTrue(receipt["translation_files_unchanged"])
        self.assertTrue(receipt["reference_files_unchanged"])
        self.assertIn("test_publish_script.py", receipt["tests"])
        self.assertIn("BienTapTay.Benchmarks", receipt["tests"])
        self.assertIn("test_performance_benchmark.py", receipt["tests"])
        self.assertEqual("kept-feature", receipt["features"][0])
        for feature in (
            "full_corpus_save_gate",
            "reference_validators",
            "shared_writer_lock",
            "transactional_release_pipeline",
            "qa_triage_sidecar",
            "qa_related_context_packet",
            "semantic_high_contrast_per_monitor_v2",
            "performance_baseline",
            "culture_stable_fast_search",
            "qa_report_export",
            "qa_clipboard_retry",
            "local_diagnostics_redaction",
        ):
            self.assertIn(feature, receipt["features"])
        self.assertEqual(7, receipt["consistency_qa"]["warnings_total"])
        qa = receipt["qa_decisions"]
        expected_sidecar = (self.project.parent / "qa-decisions.json").resolve()
        self.assertFalse(qa["present"])
        self.assertEqual(str(expected_sidecar), qa["path"])
        self.assertIsNone(qa["sha256"])
        self.assertEqual(0, qa["decision_count"])
        self.assertEqual({"needs_fix": 0, "accepted_difference": 0, "resolved": 0}, qa["by_status"])
        dumped = json.dumps(receipt)
        self.assertNotIn("qa-report", dumped)
        self.assertFalse(expected_sidecar.exists())

        self.live_executable.parent.mkdir(parents=True)
        self.live_executable.write_bytes(self.executable.read_bytes())
        self.output.replace(self.existing)
        self._run(
            "verify",
            "--project",
            self.project,
            "--baseline",
            self.baseline,
            "--executable",
            self.live_executable,
            "--receipt",
            self.existing,
            "--app-version",
            "0.5.1",
        )

    def test_prepare_refuses_drift_without_overwriting_output(self) -> None:
        self._run("snapshot", "--project", self.project, "--output", self.baseline)
        with (self.root / "workbook" / "main.csv").open("a", encoding="utf-8", newline="") as handle:
            handle.write("c,C,C,reviewed\r\n")
        self.output.write_text("keep", encoding="utf-8")

        result = self._run(
            "prepare",
            "--project",
            self.project,
            "--baseline",
            self.baseline,
            "--executable",
            self.executable,
            "--published-executable",
            self.live_executable,
            "--existing-receipt",
            self.existing,
            "--output",
            self.output,
            "--app-version",
            "0.5.1",
            check=False,
        )

        self.assertNotEqual(0, result.returncode)
        self.assertIn("changed after baseline", result.stderr)
        self.assertEqual("keep", self.output.read_text(encoding="utf-8"))

    def test_prepare_rejects_exe_without_matching_version_metadata(self) -> None:
        self._run("snapshot", "--project", self.project, "--output", self.baseline)
        result = self._run(
            "prepare",
            "--project",
            self.project,
            "--baseline",
            self.baseline,
            "--executable",
            self.executable,
            "--published-executable",
            self.live_executable,
            "--existing-receipt",
            self.existing,
            "--output",
            self.output,
            "--app-version",
            "0.6.1",
            check=False,
        )
        self.assertNotEqual(0, result.returncode)
        self.assertRegex(result.stderr, r"FileVersion|ProductVersion|version resource")

    def test_assembly_file_version_pads_semantic_input_without_hardcoding_061(self) -> None:
        self.assertEqual("0.6.1.0", _RECEIPT.assembly_file_version("0.6.1"))
        self.assertEqual("1.2.3.0", _RECEIPT.assembly_file_version("1.2.3"))
        self.assertEqual("1.2.3.4", _RECEIPT.assembly_file_version("1.2.3.4"))

    def test_verify_rejects_when_published_exe_metadata_no_longer_matches(self) -> None:
        self.executable.write_bytes(versioned_exe_bytes("0.6.1"))
        self._run("snapshot", "--project", self.project, "--output", self.baseline)
        self._run(
            "prepare",
            "--project",
            self.project,
            "--baseline",
            self.baseline,
            "--executable",
            self.executable,
            "--published-executable",
            self.live_executable,
            "--existing-receipt",
            self.existing,
            "--output",
            self.output,
            "--app-version",
            "0.6.1",
        )
        self.live_executable.parent.mkdir(parents=True)
        self.live_executable.write_bytes(self.executable.read_bytes())
        self.output.replace(self.existing)
        self.live_executable.write_bytes(b"not-a-versioned-exe")
        result = self._run(
            "verify",
            "--project",
            self.project,
            "--baseline",
            self.baseline,
            "--executable",
            self.live_executable,
            "--receipt",
            self.existing,
            "--app-version",
            "0.6.1",
            check=False,
        )
        self.assertNotEqual(0, result.returncode)
        self.assertRegex(result.stderr, r"FileVersion|ProductVersion|version resource")

    def test_valid_qa_decisions_receipt_metadata_and_verify(self) -> None:
        sidecar = self.project.parent / "qa-decisions.json"
        payload = _PUBLISH_TESTS.valid_qa_decisions_bytes()
        sidecar.write_bytes(payload)
        self.executable.write_bytes(versioned_exe_bytes("0.5.1"))
        self._run("snapshot", "--project", self.project, "--output", self.baseline)
        self._run(
            "prepare",
            "--project",
            self.project,
            "--baseline",
            self.baseline,
            "--executable",
            self.executable,
            "--published-executable",
            self.live_executable,
            "--existing-receipt",
            self.existing,
            "--output",
            self.output,
            "--app-version",
            "0.5.1",
        )
        receipt = json.loads(self.output.read_text(encoding="utf-8"))
        qa = receipt["qa_decisions"]
        self.assertTrue(qa["present"])
        self.assertEqual(str(sidecar.resolve()), qa["path"])
        self.assertEqual(_RECEIPT.sha256(sidecar), qa["sha256"])
        self.assertEqual(4, qa["decision_count"])
        self.assertEqual({"needs_fix": 2, "accepted_difference": 1, "resolved": 1}, qa["by_status"])
        self.assertEqual(payload, sidecar.read_bytes())
        self.assertNotIn("qa-report", json.dumps(receipt))
        self.live_executable.parent.mkdir(parents=True)
        self.live_executable.write_bytes(self.executable.read_bytes())
        self.output.replace(self.existing)
        self._run(
            "verify",
            "--project",
            self.project,
            "--baseline",
            self.baseline,
            "--executable",
            self.live_executable,
            "--receipt",
            self.existing,
            "--app-version",
            "0.5.1",
        )
        self.assertEqual(payload, sidecar.read_bytes())

    def test_malformed_qa_decisions_shapes_fail_closed_like_core(self) -> None:
        sidecar = self.project.parent / "qa-decisions.json"
        for name, payload in CORE_MALFORMED_QA_DECISIONS:
            with self.subTest(name=name):
                sidecar.write_bytes(payload)
                with self.assertRaises(_RECEIPT.ReleaseError):
                    _RECEIPT.inspect_qa_decisions(sidecar)
                self.assertEqual(payload, sidecar.read_bytes())
        payload = dict(CORE_MALFORMED_QA_DECISIONS)["corrupt-json"]
        sidecar.write_bytes(payload)
        result = self._run("snapshot", "--project", self.project, "--output", self.baseline, check=False)
        self.assertNotEqual(0, result.returncode, result.stderr)
        self.assertIn("qa-decisions", result.stderr)
        self.assertEqual(payload, sidecar.read_bytes())
        self.assertFalse(self.baseline.exists())

    def test_unreadable_directory_sidecar_fails_without_creating_file(self) -> None:
        sidecar = self.project.parent / "qa-decisions.json"
        sidecar.mkdir()
        with self.assertRaises(_RECEIPT.ReleaseError):
            _RECEIPT.inspect_qa_decisions(sidecar)
        self.assertTrue(sidecar.is_dir())
        result = self._run("snapshot", "--project", self.project, "--output", self.baseline, check=False)
        self.assertNotEqual(0, result.returncode)
        self.assertTrue(sidecar.is_dir())
        self.assertEqual([], list(sidecar.iterdir()))

    def test_sidecar_changed_after_snapshot_blocks_prepare(self) -> None:
        sidecar = self.project.parent / "qa-decisions.json"
        sidecar.write_bytes(_PUBLISH_TESTS.valid_qa_decisions_bytes())
        self.executable.write_bytes(versioned_exe_bytes("0.5.1"))
        self._run("snapshot", "--project", self.project, "--output", self.baseline)
        sidecar.write_bytes(sidecar.read_bytes() + b"\n")
        self.output.write_text("keep", encoding="utf-8")
        result = self._run(
            "prepare",
            "--project",
            self.project,
            "--baseline",
            self.baseline,
            "--executable",
            self.executable,
            "--published-executable",
            self.live_executable,
            "--existing-receipt",
            self.existing,
            "--output",
            self.output,
            "--app-version",
            "0.5.1",
            check=False,
        )
        self.assertNotEqual(0, result.returncode)
        self.assertRegex(result.stderr, r"qa_decisions|qa-decisions")
        self.assertEqual("keep", self.output.read_text(encoding="utf-8"))

    def test_verify_rejects_altered_sidecar_hash_count_status_and_file(self) -> None:
        sidecar = self.project.parent / "qa-decisions.json"
        payload = _PUBLISH_TESTS.valid_qa_decisions_bytes()
        sidecar.write_bytes(payload)
        self.executable.write_bytes(versioned_exe_bytes("0.5.1"))
        self._run("snapshot", "--project", self.project, "--output", self.baseline)
        self._run(
            "prepare",
            "--project",
            self.project,
            "--baseline",
            self.baseline,
            "--executable",
            self.executable,
            "--published-executable",
            self.live_executable,
            "--existing-receipt",
            self.existing,
            "--output",
            self.output,
            "--app-version",
            "0.5.1",
        )
        self.live_executable.parent.mkdir(parents=True)
        self.live_executable.write_bytes(self.executable.read_bytes())
        self.output.replace(self.existing)

        def verify(check: bool = False):
            return self._run(
                "verify",
                "--project",
                self.project,
                "--baseline",
                self.baseline,
                "--executable",
                self.live_executable,
                "--receipt",
                self.existing,
                "--app-version",
                "0.5.1",
                check=check,
            )

        original = json.loads(self.existing.read_text(encoding="utf-8"))
        for field, value in (
            ("sha256", "0" * 64),
            ("decision_count", 99),
        ):
            tampered = json.loads(json.dumps(original))
            tampered["qa_decisions"][field] = value
            self.existing.write_text(json.dumps(tampered, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            result = verify()
            self.assertNotEqual(0, result.returncode, field)
            self.assertRegex(result.stderr, r"qa_decisions|qa-decisions")
        tampered = json.loads(json.dumps(original))
        tampered["qa_decisions"]["by_status"]["needs_fix"] = 99
        self.existing.write_text(json.dumps(tampered, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        result = verify()
        self.assertNotEqual(0, result.returncode)
        self.existing.write_text(json.dumps(original, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        sidecar.write_bytes(payload + b"\n")
        result = verify()
        self.assertNotEqual(0, result.returncode)
        sidecar.write_bytes(payload)
        self.assertEqual(payload, sidecar.read_bytes())

    def test_empty_note_sidecar_is_valid_like_core(self) -> None:
        sidecar = self.project.parent / "qa-decisions.json"
        payload = (
            '{"schema":"bientaptay-qa-decisions/v1","decisions":[{"id":"'
            + ("a" * 64)
            + '","translationId":"scripts","kind":"GlossaryDrift","key":"scene::001","relatedKeys":["scene::001"],"contentFingerprint":"'
            + ("b" * 64)
            + '","status":"needs_fix","note":"","updatedAtUtc":"2026-09-02T00:00:00Z"}]}'
        ).encode("utf-8")
        sidecar.write_bytes(payload)
        meta = _RECEIPT.inspect_qa_decisions(sidecar)
        self.assertTrue(meta["present"])
        self.assertEqual(1, meta["decision_count"])
        self.assertEqual(1, meta["by_status"]["needs_fix"])
        self.assertEqual(payload, sidecar.read_bytes())

    def test_diagnostics_directory_is_ignored_by_snapshot_prepare_and_verify(self) -> None:
        diagnostics = self.project.parent / "diagnostics"
        diagnostics.mkdir()
        malformed = [
            ("app.log", b'{"utc":"not-a-timestamp","operation":\x00 broken jsonl\n'),
            ("app.log.1", b"\xff\xfe not utf-8 at all\n"),
            ("app.log.2", b""),
        ]
        for name, payload in malformed:
            (diagnostics / name).write_bytes(payload)

        self.executable.write_bytes(versioned_exe_bytes("0.5.1"))
        self._run("snapshot", "--project", self.project, "--output", self.baseline)
        baseline = json.loads(self.baseline.read_text(encoding="utf-8"))
        self._assert_no_diagnostics_path(baseline)

        self._run(
            "prepare",
            "--project",
            self.project,
            "--baseline",
            self.baseline,
            "--executable",
            self.executable,
            "--published-executable",
            self.live_executable,
            "--existing-receipt",
            self.existing,
            "--output",
            self.output,
            "--app-version",
            "0.5.1",
        )
        receipt = json.loads(self.output.read_text(encoding="utf-8"))
        self._assert_no_diagnostics_path(receipt)
        self.assertIn("local_diagnostics_redaction", receipt["features"])
        for entry in receipt["translation_files"] + receipt["reference_files"]:
            self.assertNotIn("diagnostics", Path(entry["path"]).parts)
        self.assertNotIn("diagnostics", Path(receipt["qa_decisions"]["path"]).parts)

        self.live_executable.parent.mkdir(parents=True)
        self.live_executable.write_bytes(self.executable.read_bytes())
        self.output.replace(self.existing)
        _RECEIPT.verify(self.project, self.baseline, self.live_executable, self.existing, "0.5.1")

        (diagnostics / "app.log").write_bytes(b"{still broken\n")
        (diagnostics / "app.log.3").write_bytes(b"rotated beyond retention\n")
        _RECEIPT.verify(self.project, self.baseline, self.live_executable, self.existing, "0.5.1")
        for name, payload in malformed:
            if name != "app.log":
                self.assertEqual(payload, (diagnostics / name).read_bytes())

    def test_qa_decision_timestamp_parity_matches_core(self) -> None:
        sidecar = self.project.parent / "qa-decisions.json"
        for name, stamp, valid in QA_TIMESTAMP_PARITY_CASES:
            payload = sidecar_with_timestamp(stamp)
            sidecar.write_bytes(payload)
            with self.subTest(name=name):
                if valid:
                    meta = _RECEIPT.inspect_qa_decisions(sidecar)
                    self.assertTrue(meta["present"], name)
                    _RECEIPT.parse_qa_decisions_bytes(payload)
                else:
                    with self.assertRaises(_RECEIPT.ReleaseError):
                        _RECEIPT.parse_qa_decisions_bytes(payload)
                    with self.assertRaises(_RECEIPT.ReleaseError):
                        _RECEIPT.inspect_qa_decisions(sidecar)
                self.assertEqual(payload, sidecar.read_bytes(), name)

    def test_unrepresentable_timestamps_raise_release_error_not_overflow(self) -> None:
        sidecar = self.project.parent / "qa-decisions.json"
        for name in ("utc-overflow-max", "utc-underflow-min"):
            stamp = next(item[1] for item in QA_TIMESTAMP_PARITY_CASES if item[0] == name)
            payload = sidecar_with_timestamp(stamp)
            sidecar.write_bytes(payload)
            with self.subTest(name=name):
                with self.assertRaises(_RECEIPT.ReleaseError) as raised_parse:
                    _RECEIPT.parse_qa_decisions_bytes(payload)
                self.assertNotIsInstance(raised_parse.exception, OverflowError)
                with self.assertRaises(_RECEIPT.ReleaseError):
                    _RECEIPT.inspect_qa_decisions(sidecar)
                self.assertEqual(payload, sidecar.read_bytes())
                if self.baseline.exists():
                    self.baseline.unlink()
                result = self._run("snapshot", "--project", self.project, "--output", self.baseline, check=False)
                self.assertNotEqual(0, result.returncode, result.stderr)
                combined = result.stdout + result.stderr
                self.assertNotIn("Traceback", combined)
                self.assertNotIn("OverflowError", combined)
                self.assertIn("qa-decisions", result.stderr)
                self.assertEqual(payload, sidecar.read_bytes())
                self.assertFalse(self.baseline.exists())

    def test_app_utc_offset_and_z_sidecars_remain_valid(self) -> None:
        sidecar = self.project.parent / "qa-decisions.json"
        for label, stamp in (
            ("z", "2026-09-02T00:00:00Z"),
            ("offset", "2026-09-02T00:00:00+00:00"),
        ):
            payload = (
                '{"schema":"bientaptay-qa-decisions/v1","decisions":[{"id":"'
                + _HEX64_A
                + '","translationId":"scripts","kind":"GlossaryDrift","key":"scene::001","relatedKeys":["scene::001"],"contentFingerprint":"'
                + _HEX64_B
                + '","status":"needs_fix","note":"a","updatedAtUtc":"'
                + stamp
                + '"}]}'
            ).encode("utf-8")
            sidecar.write_bytes(payload)
            meta = _RECEIPT.inspect_qa_decisions(sidecar)
            self.assertTrue(meta["present"], label)
            self.assertEqual(payload, sidecar.read_bytes(), label)

    def test_qa_decisions_metadata_validator_is_strict(self) -> None:
        expected = (self.project.parent / "qa-decisions.json").resolve()
        valid = {
            "present": False,
            "path": str(expected),
            "sha256": None,
            "decision_count": 0,
            "by_status": {"needs_fix": 0, "accepted_difference": 0, "resolved": 0},
        }
        _RECEIPT.validate_qa_decisions_metadata(valid, expected)
        present_valid = {
            "present": True,
            "path": str(expected),
            "sha256": "a" * 64,
            "decision_count": 1,
            "by_status": {"needs_fix": 1, "accepted_difference": 0, "resolved": 0},
        }
        _RECEIPT.validate_qa_decisions_metadata(present_valid, expected)
        with self.assertRaises(_RECEIPT.ReleaseError):
            _RECEIPT.assert_qa_decisions_unchanged({"path": str(expected)}, valid, "receipt")
        cases: list[tuple[str, dict[str, object]]] = [
            ("missing-present", {key: value for key, value in valid.items() if key != "present"}),
            ("missing-sha256", {key: value for key, value in valid.items() if key != "sha256"}),
            ("missing-decision-count", {key: value for key, value in valid.items() if key != "decision_count"}),
            ("missing-by-status", {key: value for key, value in valid.items() if key != "by_status"}),
            ("missing-one-status", {**valid, "by_status": {"needs_fix": 0, "accepted_difference": 0}}),
            ("numeric-present", {**valid, "present": 0}),
            ("string-count", {**valid, "decision_count": "0"}),
            ("float-count", {**valid, "decision_count": 0.0}),
            ("bool-count", {**valid, "decision_count": False}),
            ("relative-path", {**valid, "path": "qa-decisions.json"}),
            ("present-null-hash", {**present_valid, "sha256": None}),
            ("present-non-hex-hash", {**present_valid, "sha256": "g" * 64}),
            ("present-wrong-length-hash", {**present_valid, "sha256": "a" * 63}),
            ("present-uppercase-hash", {**present_valid, "sha256": "A" * 64}),
            ("negative-count", {**valid, "decision_count": -1}),
            ("negative-status", {**valid, "by_status": {"needs_fix": -1, "accepted_difference": 0, "resolved": 0}}),
            ("sum-mismatch", {**present_valid, "decision_count": 2}),
            ("absent-nonzero-count", {**valid, "decision_count": 1, "by_status": {"needs_fix": 1, "accepted_difference": 0, "resolved": 0}}),
            ("absent-non-null-hash", {**valid, "sha256": "a" * 64}),
            ("extra-unreviewed", {**valid, "by_status": {"needs_fix": 0, "accepted_difference": 0, "resolved": 0, "unreviewed": 99}}),
            ("unknown-status-key", {**valid, "by_status": {"needs_fix": 0, "accepted_difference": 0, "resolved": 0, "other": 0}}),
            ("case-changed-status", {**valid, "by_status": {"Needs_Fix": 0, "accepted_difference": 0, "resolved": 0}}),
        ]
        for name, meta in cases:
            with self.subTest(name=name):
                with self.assertRaises(_RECEIPT.ReleaseError):
                    _RECEIPT.validate_qa_decisions_metadata(meta, expected)

    def test_verify_rejects_malformed_qa_decisions_metadata_fields(self) -> None:
        self.executable.write_bytes(versioned_exe_bytes("0.5.1"))
        self._run("snapshot", "--project", self.project, "--output", self.baseline)
        self._run(
            "prepare",
            "--project",
            self.project,
            "--baseline",
            self.baseline,
            "--executable",
            self.executable,
            "--published-executable",
            self.live_executable,
            "--existing-receipt",
            self.existing,
            "--output",
            self.output,
            "--app-version",
            "0.5.1",
        )
        self.live_executable.parent.mkdir(parents=True)
        self.live_executable.write_bytes(self.executable.read_bytes())
        self.output.replace(self.existing)
        original = json.loads(self.existing.read_text(encoding="utf-8"))

        def mutate_and_verify(name: str, mutator) -> None:
            tampered = json.loads(json.dumps(original))
            mutator(tampered["qa_decisions"])
            self.existing.write_text(json.dumps(tampered, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            with self.subTest(name=name):
                with self.assertRaises(_RECEIPT.ReleaseError):
                    _RECEIPT.verify(
                        self.project,
                        self.baseline,
                        self.live_executable,
                        self.existing,
                        "0.5.1",
                    )

        mutate_and_verify("missing-present", lambda qa: qa.pop("present"))
        mutate_and_verify("missing-sha256", lambda qa: qa.pop("sha256"))
        mutate_and_verify("numeric-present", lambda qa: qa.__setitem__("present", 0))
        mutate_and_verify("string-count", lambda qa: qa.__setitem__("decision_count", "0"))
        mutate_and_verify("relative-path", lambda qa: qa.__setitem__("path", "qa-decisions.json"))
        mutate_and_verify("extra-unreviewed", lambda qa: qa["by_status"].__setitem__("unreviewed", 99))
        mutate_and_verify("unknown-status-key", lambda qa: qa["by_status"].__setitem__("other", 0))
        mutate_and_verify(
            "case-changed-status",
            lambda qa: qa.__setitem__("by_status", {"Needs_Fix": 0, "accepted_difference": 0, "resolved": 0}),
        )
        self.existing.write_text(json.dumps(original, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def _assert_no_diagnostics_path(self, document: object) -> None:
        def walk(value: object) -> None:
            if isinstance(value, dict):
                self.assertNotIn("diagnostics", value)
                for item in value.values():
                    walk(item)
                return
            if isinstance(value, list):
                for item in value:
                    walk(item)
                return
            if isinstance(value, str):
                self.assertNotIn("diagnostics", Path(value).parts, value)

        walk(document)

    def _run(self, *args: object, check: bool = True) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(
            [sys.executable, str(SCRIPT), *(str(arg) for arg in args)],
            text=True,
            capture_output=True,
        )
        if check and result.returncode:
            self.fail(f"release_receipt.py failed: {result.stderr or result.stdout}")
        return result

    @staticmethod
    def _write_csv(path: Path, headers: list[str], rows: list[list[str]]) -> None:
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.writer(handle, lineterminator="\r\n")
            writer.writerow(headers)
            writer.writerows(rows)


if __name__ == "__main__":
    unittest.main()
