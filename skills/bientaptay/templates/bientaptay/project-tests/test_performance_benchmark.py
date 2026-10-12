from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "tests" / "BienTapTay.Benchmarks" / "BienTapTay.Benchmarks.csproj"


class PerformanceBenchmarkTests(unittest.TestCase):
    def test_benchmark_reports_real_paths_without_mutating_csv(self) -> None:
        with tempfile.TemporaryDirectory(prefix="bientaptay-benchmark-") as raw:
            root = Path(raw)
            data = root / "data"
            data.mkdir()
            main = root / "main.csv"
            ui = root / "ui.csv"
            glossary = data / "glossary.csv"
            pronouns = data / "pronouns.csv"
            self._write_csv(
                main,
                ["key", "speaker", "source", "translation_vi", "status", "notes", "group"],
                [
                    ["a", "Ema", "同じ", "Một", "reviewed", "", "scene"],
                    ["b", "Ema", "同じ", "Hai", "reviewed", "", "scene"],
                ],
            )
            self._write_csv(
                ui,
                ["key", "source", "translation_vi", "status", "notes", "group"],
                [["ui::1", "設定", "Cài đặt", "reviewed", "", "Options"]],
            )
            self._write_csv(
                glossary,
                ["term", "translation", "type", "context", "status"],
                [["設定", "Cài đặt", "ui", "", "locked"]],
            )
            self._write_csv(
                pronouns,
                ["speaker", "self_reference", "address_form", "notes", "status", "evidence_keys"],
                [["Ema", "tôi", "cậu", "fixture", "reviewed", "a"]],
            )
            project = root / "project.json"
            project.write_text(
                json.dumps(
                    {
                        "schemaVersion": 1,
                        "projectName": "Benchmark fixture",
                        "canonicalPath": "main.csv",
                        "keyColumn": "key",
                        "sourceFields": [{"column": "source", "label": "Nguồn"}],
                        "targetColumn": "translation_vi",
                        "speakerColumn": "speaker",
                        "groupColumn": "group",
                        "statusColumn": "status",
                        "notesColumn": "notes",
                        "statuses": ["pending", "translated", "reviewed", "needs_context"],
                        "translationFiles": [
                            {"id": "main", "label": "Main", "path": "main.csv"},
                            {
                                "id": "ui",
                                "label": "UI",
                                "path": "ui.csv",
                                "speakerColumn": "",
                            },
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
            output = root / "performance.json"
            csv_paths = [main, ui, glossary, pronouns]
            before = {path: self._sha256(path) for path in csv_paths}

            result = subprocess.run(
                [
                    "dotnet",
                    "run",
                    "--project",
                    str(PROJECT),
                    "--configuration",
                    "Release",
                    "--",
                    str(project),
                    str(output),
                    "2",
                ],
                text=True,
                capture_output=True,
            )
            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            report = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual("bientaptay-performance/v1", report["schema"])
            self.assertEqual(3, report["row_count"])
            self.assertEqual(1, report["warning_count"])
            self.assertEqual(2, report["iterations"])
            self.assertEqual(
                {"startup_load", "view_model_build", "current_filter", "project_search", "consistency_qa"},
                set(report["metrics_ms"]),
            )
            self.assertEqual(1, len(report["metrics_ms"]["startup_load"]["samples"]))
            for name, metric in report["metrics_ms"].items():
                self.assertGreaterEqual(metric["median"], 0, name)
                self.assertGreaterEqual(metric["max"], metric["median"], name)
            self.assertEqual(before, {path: self._sha256(path) for path in csv_paths})
            self.assertFalse((root / "performance.json.writing").exists())

    @staticmethod
    def _write_csv(path: Path, headers: list[str], rows: list[list[str]]) -> None:
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.writer(handle, lineterminator="\r\n")
            writer.writerow(headers)
            writer.writerows(rows)

    @staticmethod
    def _sha256(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()


if __name__ == "__main__":
    unittest.main()
