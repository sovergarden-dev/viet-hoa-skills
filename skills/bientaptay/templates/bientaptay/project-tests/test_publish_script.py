from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from release_receipt import read_exe_version_strings
APP_PROJECT = ROOT / "src" / "BienTapTay.App" / "BienTapTay.App.csproj"
PUBLISH_PY = ROOT / "release_publish.py"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_PUBLISH = _load("bientaptay_release_publish", PUBLISH_PY)


def read_exe_versions(path: Path) -> tuple[str, str]:
    return read_exe_version_strings(path)


def isolated_publish(app_version: str, output: Path) -> subprocess.CompletedProcess[str]:
    output.mkdir(parents=True, exist_ok=True)
    command = [
        "dotnet",
        "publish",
        str(APP_PROJECT),
        "-c",
        "Release",
        "-r",
        "win-x64",
        "--self-contained",
        "false",
        "-p:PublishSingleFile=true",
        "-p:DebugType=None",
        "-p:DebugSymbols=false",
        *_PUBLISH.version_msbuild_properties(app_version),
        "-o",
        str(output),
    ]
    return subprocess.run(
        command,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
        cwd=APP_PROJECT.parent,
    )


_VERSIONED_EXE_BYTES: dict[str, bytes] = {}
LEFTOVERS = (
    "app.previous",
    ".install-receipt.previous.json",
    "app.staging",
    ".install-receipt.candidate.json",
    ".bientaptay.writer.lock",
)


def versioned_exe_bytes(app_version: str) -> bytes:
    cached = _VERSIONED_EXE_BYTES.get(app_version)
    if cached is not None:
        return cached
    with tempfile.TemporaryDirectory(prefix="bientaptay-versioned-exe-") as temp:
        output = Path(temp) / "out"
        result = isolated_publish(app_version, output)
        if result.returncode != 0:
            raise AssertionError(result.stdout + result.stderr)
        cached = (output / "BienTapTay.exe").read_bytes()
    _VERSIONED_EXE_BYTES[app_version] = cached
    return cached


def valid_qa_decisions_bytes() -> bytes:
    def record(decision_id: str, fingerprint: str, status: str, key: str) -> dict[str, object]:
        return {
            "id": decision_id,
            "translationId": "scripts",
            "kind": "GlossaryDrift",
            "key": key,
            "relatedKeys": [key],
            "contentFingerprint": fingerprint,
            "status": status,
            "note": "a",
            "updatedAtUtc": "2026-09-02T00:00:00Z",
        }

    document = {
        "schema": "bientaptay-qa-decisions/v1",
        "decisions": [
            record("a" * 64, "b" * 64, "needs_fix", "scene::001"),
            record("c" * 64, "d" * 64, "accepted_difference", "scene::002"),
            record("e" * 64, "0" * 64, "resolved", "scene::003"),
            record("f" * 64, "1" * 64, "needs_fix", "scene::004"),
        ],
    }
    return json.dumps(document, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def write_csv(path: Path, headers: list[str], rows: list[list[str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\r\n")
        writer.writerow(headers)
        writer.writerows(rows)


def make_publish_fixture(temp: Path, app_version: str) -> tuple[Path, bytes, bytes]:
    root = temp / "bientaptay"
    workbook = temp / "workbook"
    data = root / "data"
    tests = root / "project-tests"
    app = root / "app"
    staging = root / "app.staging"
    for path in (root, workbook, data, tests, app, staging):
        path.mkdir(parents=True, exist_ok=True)
    (tests / "test_publish_script.py").write_text("# gate\n", encoding="utf-8")
    (tests / "test_performance_benchmark.py").write_text("# gate\n", encoding="utf-8")
    write_csv(
        workbook / "main.csv",
        ["key", "source", "translation_vi", "status"],
        [["a", "A", "Dòng 1\nDòng 2", "reviewed"], ["b", "B", "B", "reviewed"]],
    )
    write_csv(
        workbook / "ui.csv",
        ["key", "source", "translation_vi", "status"],
        [["ui::1", "Options", "Cài đặt", "reviewed"]],
    )
    write_csv(data / "glossary.csv", ["term", "translation", "status"], [["A", "A", "locked"]])
    write_csv(
        data / "pronouns.csv",
        ["speaker", "self_reference", "address_form", "notes", "status", "evidence_keys"],
        [["Ema", "tôi", "cậu", "ghi chú", "reviewed", "a"]],
    )
    (root / "project.json").write_text(
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
    old_app = b"previous-published-app"
    (app / "BienTapTay.exe").write_bytes(old_app)
    old_receipt = (
        json.dumps({"schema": "bientaptay-install/v3", "app_version": "0.5.0", "features": ["kept-feature"]}, ensure_ascii=False) + "\n"
    ).encode("utf-8")
    (root / "install-receipt.json").write_bytes(old_receipt)
    (root / "qa-decisions.json").write_bytes(valid_qa_decisions_bytes())
    new_app = versioned_exe_bytes(app_version)
    (staging / "BienTapTay.exe").write_bytes(new_app)
    return root, old_app, old_receipt


def run_publish_fixture(
    root: Path,
    app_version: str,
    inject: str = "",
    *,
    cwd: Path | None = None,
    extra_env: dict[str, str] | None = None,
    include_test_mode: bool = False,
) -> subprocess.CompletedProcess[str]:
    command = [
        sys.executable,
        str(PUBLISH_PY),
        "--app-version",
        app_version,
        "--publish-root",
        str(root),
    ]
    if inject:
        command.extend(["--inject-publish-failure", inject])
    env = os.environ.copy()
    if extra_env:
        env.update(extra_env)
    if include_test_mode:
        env["BIENTAPTAY_PUBLISH_TEST_MODE"] = "1"
    elif "BIENTAPTAY_PUBLISH_TEST_MODE" in env:
        env.pop("BIENTAPTAY_PUBLISH_TEST_MODE", None)
    return subprocess.run(
        command,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
        cwd=cwd,
        env=env,
    )


class PublishScriptTests(unittest.TestCase):
    def tearDown(self) -> None:
        for build_root in (ROOT / "src", ROOT / "tests"):
            if not build_root.is_dir():
                continue
            for project_dir in build_root.iterdir():
                if not project_dir.is_dir():
                    continue
                for leftover in ("bin", "obj"):
                    path = project_dir / leftover
                    if path.exists():
                        shutil.rmtree(path, ignore_errors=True)

    def test_isolated_publish_stamps_appversion_file_and_product_metadata(self) -> None:
        with tempfile.TemporaryDirectory(prefix="bientaptay-version-stamp-") as temp:
            output = Path(temp) / "out"
            result = isolated_publish("0.6.1", output)
            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            exe = output / "BienTapTay.exe"
            self.assertTrue(exe.is_file())
            file_version, product_version = read_exe_versions(exe)
            self.assertEqual("0.6.1.0", file_version)
            self.assertEqual("0.6.1", product_version)
            self.assertNotIn("+", product_version)

    def test_release_pipeline_source_stays_local_and_unencoded(self) -> None:
        source = PUBLISH_PY.read_text(encoding="utf-8")
        self.assertIn("--app-version", source)
        self.assertIn('default="0.7.0"', source)
        self.assertIn('app_version: str = "0.7.0"', source)
        self.assertIn("BienTapTay.Benchmarks", source)
        self.assertIn("test_performance_benchmark.py", source)
        self.assertIn("performance-baseline.json", source)
        lowered = source.casefold()
        for banned in (
            "downloadstring",
            "frombase64string",
            "encodedcommand",
            "invoke-expression",
            "iex(",
            "powershell.exe",
            "get-ciminstance",
        ):
            self.assertNotIn(banned, lowered)
        self.assertFalse((ROOT / "publish.ps1.txt").exists())

    def test_app_process_query_or_path_failure_stops_publication(self) -> None:
        exe = Path(tempfile.mkdtemp(prefix="bientaptay-process-guard-")) / "BienTapTay.exe"
        exe.write_bytes(b"probe")
        try:
            def query_boom():
                raise RuntimeError("forced CIM failure")

            with self.assertRaises(Exception) as boom:
                _PUBLISH.assert_app_closed(exe, query_paths=query_boom)
            self.assertIn("Cannot verify whether BienTapTay.exe is running", str(boom.exception))

            def query_blank():
                return [None]

            with self.assertRaises(Exception) as blank:
                _PUBLISH.assert_app_closed(exe, query_paths=query_blank)
            self.assertIn("Cannot verify whether BienTapTay.exe is running", str(blank.exception))
        finally:
            shutil.rmtree(exe.parent, ignore_errors=True)

    def test_process32_first_failure_is_fail_closed(self) -> None:
        def first(*_args):
            return 0

        def next_fn(*_args):
            return 0

        with self.assertRaises(_PUBLISH.PublishError) as raised:
            _PUBLISH.query_bientaptay_executable_paths(
                process32_first=first,
                process32_next=next_fn,
                get_last_error=lambda: 87,
                set_last_error=lambda _code: None,
            )
        self.assertIn("Process32FirstW", str(raised.exception))

    def test_process32_next_non_terminal_error_is_fail_closed(self) -> None:
        def first(*_args):
            return 1

        def next_fn(*_args):
            return 0

        with self.assertRaises(_PUBLISH.PublishError) as raised:
            _PUBLISH.query_bientaptay_executable_paths(
                process32_first=first,
                process32_next=next_fn,
                get_last_error=lambda: 5,
                set_last_error=lambda _code: None,
            )
        self.assertIn("Process32NextW", str(raised.exception))

    def test_process32_next_no_more_files_stops_enumeration(self) -> None:
        paths = _PUBLISH.query_bientaptay_executable_paths(
            process32_first=lambda *_args: 1,
            process32_next=lambda *_args: 0,
            get_last_error=lambda: 18,
            set_last_error=lambda _code: None,
        )
        self.assertEqual([], paths)

    def test_busy_writer_lock_leaves_transaction_sentinels_byte_exact(self) -> None:
        lock_tool = ROOT / "writer_lock.py"
        with tempfile.TemporaryDirectory(prefix="bientaptay-lock-order-") as temp:
            root, old_app, old_receipt = make_publish_fixture(Path(temp), "0.6.1")
            candidate = root / ".install-receipt.candidate.json"
            backup = root / ".install-receipt.previous.json"
            staging_exe = root / "app.staging" / "BienTapTay.exe"
            sentinels = {
                candidate: b"SENTINEL-CANDIDATE-BYTES",
                backup: b"SENTINEL-BACKUP-BYTES",
                staging_exe: b"SENTINEL-STAGING-BYTES",
            }
            for path, payload in sentinels.items():
                path.write_bytes(payload)
            holder = subprocess.Popen(
                [sys.executable, str(lock_tool), "hold", "--project", str(root / "project.json"), "--seconds", "30"],
                text=True,
                encoding="utf-8",
                errors="replace",
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            try:
                ready = holder.stdout.readline() if holder.stdout is not None else ""
                self.assertTrue(ready.startswith("LOCKED "), ready)
                result = run_publish_fixture(root, "0.6.1", include_test_mode=True)
                self.assertNotEqual(0, result.returncode, result.stdout + result.stderr)
                for path, payload in sentinels.items():
                    self.assertTrue(path.exists(), f"missing {path.name}\n{result.stdout}{result.stderr}")
                    self.assertEqual(payload, path.read_bytes(), path.name + "\n" + result.stdout + result.stderr)
                self.assertEqual(old_app, (root / "app" / "BienTapTay.exe").read_bytes())
                self.assertEqual(old_receipt, (root / "install-receipt.json").read_bytes())
                self.assertIn("LOCK-REFUSED", result.stdout + result.stderr)
            finally:
                holder.terminate()
                holder.communicate(timeout=10)

    def _assert_fixture_untouched(self, root: Path, old_app: bytes, old_receipt: bytes, sentinels: dict[Path, bytes], result: subprocess.CompletedProcess[str]) -> None:
        output = result.stdout + result.stderr
        self.assertNotEqual(0, result.returncode, output)
        for path, payload in sentinels.items():
            self.assertTrue(path.exists(), f"missing {path.name}\n{output}")
            self.assertEqual(payload, path.read_bytes(), path.name + "\n" + output)
        self.assertEqual(old_app, (root / "app" / "BienTapTay.exe").read_bytes())
        self.assertEqual(old_receipt, (root / "install-receipt.json").read_bytes())

    def _fixture_with_sentinels(self, temp: str) -> tuple[Path, bytes, bytes, dict[Path, bytes]]:
        root, old_app, old_receipt = make_publish_fixture(Path(temp), "0.6.1")
        sentinels = {
            root / ".install-receipt.candidate.json": b"SENTINEL-CANDIDATE-BYTES",
            root / ".install-receipt.previous.json": b"SENTINEL-BACKUP-BYTES",
            root / "app.staging" / "BienTapTay.exe": b"SENTINEL-STAGING-BYTES",
        }
        for path, payload in sentinels.items():
            path.write_bytes(payload)
        return root, old_app, old_receipt, sentinels

    def test_publish_root_rejected_without_test_mode(self) -> None:
        with tempfile.TemporaryDirectory(prefix="bientaptay-no-test-mode-root-") as temp:
            root, old_app, old_receipt, sentinels = self._fixture_with_sentinels(temp)
            result = run_publish_fixture(root, "0.6.1", include_test_mode=False)
            self._assert_fixture_untouched(root, old_app, old_receipt, sentinels, result)
            self.assertIn("BIENTAPTAY_PUBLISH_TEST_MODE", result.stdout + result.stderr)

    def test_inject_publish_failure_rejected_without_test_mode(self) -> None:
        with tempfile.TemporaryDirectory(prefix="bientaptay-no-test-mode-inject-") as temp:
            root, old_app, old_receipt, sentinels = self._fixture_with_sentinels(temp)
            result = run_publish_fixture(root, "0.6.1", inject="after-app-promotion", include_test_mode=False)
            self._assert_fixture_untouched(root, old_app, old_receipt, sentinels, result)
            self.assertIn("BIENTAPTAY_PUBLISH_TEST_MODE", result.stdout + result.stderr)

    def test_test_mode_rejects_live_publish_root(self) -> None:
        live_receipt = ROOT / "install-receipt.json"
        live_app = ROOT / "app" / "BienTapTay.exe"
        before_receipt = live_receipt.read_bytes() if live_receipt.is_file() else b""
        before_app = live_app.read_bytes() if live_app.is_file() else b""
        env = os.environ.copy()
        env["BIENTAPTAY_PUBLISH_TEST_MODE"] = "1"
        result = subprocess.run(
            [
                sys.executable,
                str(PUBLISH_PY),
                "--publish-root",
                str(ROOT),
                "--inject-publish-failure",
                "during-verify",
            ],
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            check=False,
            env=env,
        )
        self.assertNotEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn("live BienTapTay root", result.stdout + result.stderr)
        if live_receipt.is_file():
            self.assertEqual(before_receipt, live_receipt.read_bytes())
        if live_app.is_file():
            self.assertEqual(before_app, live_app.read_bytes())

    def test_test_only_switches_are_hidden_from_help_and_launch_cmd(self) -> None:
        result = subprocess.run(
            [sys.executable, str(PUBLISH_PY), "-h"],
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            check=False,
        )
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        help_text = (result.stdout + result.stderr).casefold()
        self.assertNotIn("publish-root", help_text)
        self.assertNotIn("inject-publish-failure", help_text)
        launch = (ROOT / "Launch-Publish.cmd").read_text(encoding="utf-8")
        self.assertNotIn("publish-root", launch.casefold())
        self.assertNotIn("inject-publish-failure", launch.casefold())
        self.assertNotIn("BIENTAPTAY_PUBLISH_TEST_MODE", launch)

    def test_injected_failures_roll_back_app_and_receipt_byte_exact(self) -> None:
        for checkpoint in ("after-app-promotion", "after-receipt-promotion", "during-verify"):
            with self.subTest(checkpoint=checkpoint), tempfile.TemporaryDirectory(prefix="bientaptay-rollback-") as temp:
                root, old_app, old_receipt = make_publish_fixture(Path(temp), "0.6.1")
                result = run_publish_fixture(root, "0.6.1", inject=checkpoint, include_test_mode=True)
                self.assertNotEqual(0, result.returncode, result.stdout + result.stderr)
                self.assertIn("Injected publish failure: " + checkpoint, result.stdout + result.stderr)
                self.assertEqual(old_app, (root / "app" / "BienTapTay.exe").read_bytes())
                self.assertEqual(old_receipt, (root / "install-receipt.json").read_bytes())
                self.assertEqual(valid_qa_decisions_bytes(), (root / "qa-decisions.json").read_bytes())
                for leftover in LEFTOVERS:
                    self.assertFalse((root / leftover).exists(), leftover + "\n" + result.stdout + result.stderr)

    def test_publish_transaction_succeeds_without_failure_injection(self) -> None:
        with tempfile.TemporaryDirectory(prefix="bientaptay-promote-") as temp:
            root, old_app, old_receipt = make_publish_fixture(Path(temp), "0.6.1")
            sidecar_before = (root / "qa-decisions.json").read_bytes()
            new_app = (root / "app.staging" / "BienTapTay.exe").read_bytes()
            result = run_publish_fixture(root, "0.6.1", include_test_mode=True)
            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            self.assertEqual(new_app, (root / "app" / "BienTapTay.exe").read_bytes())
            self.assertNotEqual(old_app, (root / "app" / "BienTapTay.exe").read_bytes())
            self.assertNotEqual(old_receipt, (root / "install-receipt.json").read_bytes())
            self.assertEqual(sidecar_before, (root / "qa-decisions.json").read_bytes())
            receipt = json.loads((root / "install-receipt.json").read_text(encoding="utf-8"))
            self.assertEqual("0.6.1", receipt["app_version"])
            self.assertEqual("0.6.1.0", receipt["executable_file_version"])
            self.assertEqual("0.6.1", receipt["executable_product_version"])
            qa = receipt["qa_decisions"]
            self.assertTrue(qa["present"])
            self.assertEqual(str((root / "qa-decisions.json").resolve()), qa["path"])
            self.assertEqual(hashlib.sha256(sidecar_before).hexdigest(), qa["sha256"])
            self.assertEqual(4, qa["decision_count"])
            self.assertEqual({"needs_fix": 2, "accepted_difference": 1, "resolved": 1}, qa["by_status"])
            self.assertNotIn("qa-report", json.dumps(receipt))
            for leftover in LEFTOVERS:
                self.assertFalse((root / leftover).exists(), leftover)

    def test_publish_from_unrelated_cwd_keeps_behavior_and_launch_exit_code(self) -> None:
        with tempfile.TemporaryDirectory(prefix="bientaptay-unrelated-cwd-") as temp:
            base = Path(temp)
            unrelated = base / "elsewhere"
            unrelated.mkdir()
            root, old_app, old_receipt = make_publish_fixture(base / "fixture", "0.6.1")
            new_app = (root / "app.staging" / "BienTapTay.exe").read_bytes()
            result = run_publish_fixture(root, "0.6.1", include_test_mode=True, cwd=unrelated)
            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            self.assertEqual(new_app, (root / "app" / "BienTapTay.exe").read_bytes())
            self.assertNotEqual(old_app, (root / "app" / "BienTapTay.exe").read_bytes())
            self.assertNotEqual(old_receipt, (root / "install-receipt.json").read_bytes())

            inject_root, inject_app, inject_receipt = make_publish_fixture(base / "inject", "0.6.1")
            env = os.environ.copy()
            env["BIENTAPTAY_PUBLISH_TEST_MODE"] = "1"
            launched = subprocess.run(
                [
                    "cmd.exe",
                    "/d",
                    "/c",
                    "call",
                    str((ROOT / "Launch-Publish.cmd").resolve()),
                    "--app-version",
                    "0.6.1",
                    "--publish-root",
                    str(inject_root.resolve()),
                    "--inject-publish-failure",
                    "during-verify",
                ],
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                check=False,
                cwd=unrelated,
                env=env,
            )
            self.assertEqual(1, launched.returncode, launched.stdout + launched.stderr)
            self.assertIn("Injected publish failure: during-verify", launched.stdout + launched.stderr)
            self.assertEqual(inject_app, (inject_root / "app" / "BienTapTay.exe").read_bytes())
            self.assertEqual(inject_receipt, (inject_root / "install-receipt.json").read_bytes())
            self.assertEqual(valid_qa_decisions_bytes(), (inject_root / "qa-decisions.json").read_bytes())

    def test_malformed_qa_decisions_blocks_before_staging_and_keeps_sidecar_bytes(self) -> None:
        with tempfile.TemporaryDirectory(prefix="bientaptay-malformed-qa-") as temp:
            root, old_app, old_receipt = make_publish_fixture(Path(temp), "0.6.1")
            sidecar = root / "qa-decisions.json"
            payload = b"{not-json"
            sidecar.write_bytes(payload)
            result = run_publish_fixture(root, "0.6.1", include_test_mode=True)
            self.assertNotEqual(0, result.returncode, result.stdout + result.stderr)
            self.assertNotIn("Step 4/7", result.stdout)
            self.assertEqual(old_app, (root / "app" / "BienTapTay.exe").read_bytes())
            self.assertEqual(old_receipt, (root / "install-receipt.json").read_bytes())
            self.assertEqual(payload, sidecar.read_bytes())
            self.assertNotEqual(ROOT.resolve(), root.resolve())

    def test_publish_succeeds_when_qa_decisions_absent_and_does_not_create_sidecar(self) -> None:
        with tempfile.TemporaryDirectory(prefix="bientaptay-absent-qa-") as temp:
            root, old_app, old_receipt = make_publish_fixture(Path(temp), "0.6.1")
            sidecar = root / "qa-decisions.json"
            sidecar.unlink()
            result = run_publish_fixture(root, "0.6.1", include_test_mode=True)
            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            self.assertFalse(sidecar.exists())
            receipt = json.loads((root / "install-receipt.json").read_text(encoding="utf-8"))
            qa = receipt["qa_decisions"]
            self.assertFalse(qa["present"])
            self.assertIsNone(qa["sha256"])
            self.assertEqual(0, qa["decision_count"])
            self.assertEqual({"needs_fix": 0, "accepted_difference": 0, "resolved": 0}, qa["by_status"])
            self.assertNotEqual(old_app, (root / "app" / "BienTapTay.exe").read_bytes())
            self.assertNotEqual(old_receipt, (root / "install-receipt.json").read_bytes())

    def test_sidecar_changed_after_snapshot_blocks_prepare(self) -> None:
        with tempfile.TemporaryDirectory(prefix="bientaptay-qa-drift-") as temp:
            root, old_app, old_receipt = make_publish_fixture(Path(temp), "0.6.1")
            from release_receipt import prepare, snapshot

            baseline = Path(temp) / "baseline.json"
            candidate = root / ".install-receipt.candidate.json"
            snapshot(root / "project.json", baseline)
            sidecar = root / "qa-decisions.json"
            before = sidecar.read_bytes()
            sidecar.write_bytes(before + b"\n")
            with self.assertRaises(Exception) as raised:
                prepare(
                    root / "project.json",
                    baseline,
                    root / "app.staging" / "BienTapTay.exe",
                    root / "app" / "BienTapTay.exe",
                    root / "install-receipt.json",
                    candidate,
                    "0.6.1",
                )
            self.assertIn("qa_decisions", str(raised.exception).casefold())
            self.assertEqual(old_app, (root / "app" / "BienTapTay.exe").read_bytes())
            self.assertEqual(old_receipt, (root / "install-receipt.json").read_bytes())
            self.assertFalse(candidate.exists())


if __name__ == "__main__":
    unittest.main()
