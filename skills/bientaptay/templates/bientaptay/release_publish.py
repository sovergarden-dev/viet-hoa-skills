from __future__ import annotations

import argparse
import ctypes
import os
import shutil
import subprocess
import sys
import tempfile
from ctypes import wintypes
from pathlib import Path

from release_receipt import ReleaseError, assembly_file_version, assert_executable_metadata, snapshot, prepare, verify
from writer_lock import WriterLock, WriterLockBusy


SCRIPT_ROOT = Path(__file__).resolve().parent


class PublishError(RuntimeError):
    pass


TEST_MODE_ENV = "BIENTAPTAY_PUBLISH_TEST_MODE"


def authorize_test_overrides(publish_root: Path | None, inject: str) -> None:
    if publish_root is None and not inject:
        return
    if os.environ.get(TEST_MODE_ENV) != "1":
        raise PublishError(
            f"{TEST_MODE_ENV}=1 is required before --publish-root or --inject-publish-failure"
        )
    if publish_root is not None and publish_root.resolve() == SCRIPT_ROOT.resolve():
        raise PublishError("test publish root must not be the live BienTapTay root")


def version_msbuild_properties(app_version: str) -> list[str]:
    file_version = assembly_file_version(app_version)
    informational = app_version.strip()
    return [
        f"-p:Version={informational}",
        f"-p:AssemblyVersion={file_version}",
        f"-p:FileVersion={file_version}",
        f"-p:InformationalVersion={informational}",
        "-p:IncludeSourceRevisionInInformationalVersion=false",
    ]


def run_checked(step: str, command: list[str], cwd: Path) -> None:
    result = subprocess.run(command, cwd=cwd, text=True, encoding="utf-8", errors="replace", capture_output=False)
    if result.returncode != 0:
        raise PublishError(f"{step} failed with exit code {result.returncode}")


TH32CS_SNAPPROCESS = 0x00000002
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
ERROR_NO_MORE_FILES = 18
MAX_PATH = 260


class PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("cntUsage", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD),
        ("th32DefaultHeapID", ctypes.c_size_t),
        ("th32ModuleID", wintypes.DWORD),
        ("cntThreads", wintypes.DWORD),
        ("th32ParentProcessID", wintypes.DWORD),
        ("pcPriClassBase", wintypes.LONG),
        ("dwFlags", wintypes.DWORD),
        ("szExeFile", wintypes.WCHAR * MAX_PATH),
    ]


def query_bientaptay_executable_paths(
    *,
    process32_first=None,
    process32_next=None,
    get_last_error=None,
    set_last_error=None,
) -> list[str | None]:
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    kernel32.CreateToolhelp32Snapshot.restype = ctypes.c_void_p
    kernel32.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
    kernel32.Process32FirstW.restype = wintypes.BOOL
    kernel32.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
    kernel32.Process32NextW.restype = wintypes.BOOL
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.QueryFullProcessImageNameW.argtypes = [
        wintypes.HANDLE,
        wintypes.DWORD,
        wintypes.LPWSTR,
        ctypes.POINTER(wintypes.DWORD),
    ]
    kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL

    first = process32_first or kernel32.Process32FirstW
    next_process = process32_next or kernel32.Process32NextW
    read_error = get_last_error or ctypes.get_last_error
    clear_error = set_last_error or ctypes.set_last_error

    snapshot = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if snapshot in (None, 0, ctypes.c_void_p(-1).value):
        raise PublishError("cannot snapshot running processes")
    paths: list[str | None] = []
    try:
        entry = PROCESSENTRY32W()
        entry.dwSize = ctypes.sizeof(PROCESSENTRY32W)
        clear_error(0)
        if not first(snapshot, ctypes.byref(entry)):
            raise PublishError(f"Process32FirstW failed: {read_error()}")
        while True:
            if entry.szExeFile.lower() == "bientaptay.exe":
                handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, entry.th32ProcessID)
                if not handle:
                    paths.append(None)
                else:
                    try:
                        length = wintypes.DWORD(32768)
                        buffer = ctypes.create_unicode_buffer(length.value)
                        if kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(length)):
                            paths.append(buffer.value or None)
                        else:
                            paths.append(None)
                    finally:
                        kernel32.CloseHandle(handle)
            clear_error(0)
            if next_process(snapshot, ctypes.byref(entry)):
                continue
            error = read_error()
            if error == ERROR_NO_MORE_FILES:
                break
            raise PublishError(f"Process32NextW failed: {error}")
    finally:
        kernel32.CloseHandle(snapshot)
    return paths


def assert_app_closed(executable: Path, query_paths=query_bientaptay_executable_paths) -> None:
    if not executable.is_file():
        return
    target = os.path.normcase(str(executable.resolve()))
    try:
        paths = list(query_paths())
    except Exception as exc:
        raise PublishError(f"Cannot verify whether BienTapTay.exe is running: {exc}") from exc
    for raw in paths:
        if not raw:
            raise PublishError("Cannot verify whether BienTapTay.exe is running: a matching process path is unavailable.")
        try:
            candidate = os.path.normcase(str(Path(raw).resolve()))
        except OSError as exc:
            raise PublishError(f"Cannot verify whether BienTapTay.exe is running: {exc}") from exc
        if candidate == target:
            raise PublishError("BienTapTay.exe is running from the release directory. Close it before publishing.")


def remove_build_artifacts(script_root: Path) -> None:
    for build_root in (script_root / "src", script_root / "tests"):
        if not build_root.is_dir():
            continue
        for project_dir in build_root.iterdir():
            if not project_dir.is_dir():
                continue
            for leftover in ("bin", "obj"):
                path = project_dir / leftover
                if path.exists():
                    shutil.rmtree(path, ignore_errors=True)
    cache = script_root / "project-tests"
    if cache.is_dir():
        for item in cache.glob("__pycache__"):
            shutil.rmtree(item, ignore_errors=True)


def replace_file(source: Path, destination: Path, backup: Path | None) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if backup is not None and destination.is_file():
        backup.write_bytes(destination.read_bytes())
    os.replace(source, destination)


def inject_failure(checkpoint: str, inject: str) -> None:
    if inject and inject == checkpoint:
        raise PublishError(f"Injected publish failure: {checkpoint}")


def publish_to_staging(project: Path, staging: Path, configuration: str, app_version: str) -> Path:
    staging.mkdir(parents=True, exist_ok=True)
    command = [
        "dotnet",
        "publish",
        str(project),
        "-c",
        configuration,
        "-r",
        "win-x64",
        "--self-contained",
        "false",
        "-p:PublishSingleFile=true",
        "-p:DebugType=None",
        "-p:DebugSymbols=false",
        *version_msbuild_properties(app_version),
        "-o",
        str(staging),
    ]
    run_checked("dotnet publish", command, cwd=project.parent)
    staged = staging / "BienTapTay.exe"
    if not staged.is_file() or staged.stat().st_size == 0:
        raise PublishError("Publish did not create a non-empty BienTapTay.exe")
    return staged


def run_quality_gates(script_root: Path, workspace: Path, root: Path, project_config: Path, configuration: str) -> None:
    old_project = os.environ.get("BIENTAPTAY_PROJECT_CONFIG")
    old_consistency = os.environ.get("BIENTAPTAY_CONSISTENCY_CONFIG")
    os.environ["BIENTAPTAY_PROJECT_CONFIG"] = str(project_config)
    os.environ["BIENTAPTAY_CONSISTENCY_CONFIG"] = str(project_config)
    try:
        print("Step 2/7 - Run core, corpus and reference validation")
        run_checked(
            "core tests",
            ["dotnet", "run", "--project", str(script_root / "tests" / "BienTapTay.Tests" / "BienTapTay.Tests.csproj")],
            cwd=script_root,
        )
        optional = [
            (workspace / "tools" / "validate_workbook.py", "validate_workbook.py", workspace),
            (root / "project-tests" / "test_pronoun_data.py", "test_pronoun_data.py", root),
            (root / "project-tests" / "test_release_receipt.py", "test_release_receipt.py", root),
            (root / "project-tests" / "test_writer_lock.py", "test_writer_lock.py", root),
            (root / "project-tests" / "test_publish_script.py", "test_publish_script.py", root),
            (root / "project-tests" / "test_performance_benchmark.py", "test_performance_benchmark.py", root),
        ]
        for path, name, command_cwd in optional:
            if path.is_file():
                run_checked(name, [sys.executable, str(path)], cwd=command_cwd)
        run_checked(
            "full-corpus performance benchmark",
            [
                "dotnet",
                "run",
                "--project",
                str(script_root / "tests" / "BienTapTay.Benchmarks" / "BienTapTay.Benchmarks.csproj"),
                "-c",
                configuration,
                "--",
                str(project_config),
                str(script_root / "performance-baseline.json"),
                "7",
            ],
            cwd=script_root,
        )
        print("Step 3/7 - Run WPF smoke")
        run_checked(
            "WPF smoke",
            ["dotnet", "run", "--project", str(script_root / "tests" / "BienTapTay.AppSmoke" / "BienTapTay.AppSmoke.csproj")],
            cwd=script_root,
        )
    finally:
        if old_project is None:
            os.environ.pop("BIENTAPTAY_PROJECT_CONFIG", None)
        else:
            os.environ["BIENTAPTAY_PROJECT_CONFIG"] = old_project
        if old_consistency is None:
            os.environ.pop("BIENTAPTAY_CONSISTENCY_CONFIG", None)
        else:
            os.environ["BIENTAPTAY_CONSISTENCY_CONFIG"] = old_consistency


def publish_release(
    app_version: str = "0.7.0",
    configuration: str = "Release",
    inject_publish_failure: str = "",
    publish_root: Path | None = None,
) -> None:
    authorize_test_overrides(publish_root, inject_publish_failure)
    script_root = SCRIPT_ROOT
    fixture_mode = publish_root is not None
    root = publish_root.resolve() if publish_root is not None else script_root
    workspace = root.parent
    project_config = root / "project.json"
    project = script_root / "src" / "BienTapTay.App" / "BienTapTay.App.csproj"
    receipt = root / "install-receipt.json"
    receipt_candidate = root / ".install-receipt.candidate.json"
    receipt_backup = root / ".install-receipt.previous.json"
    output = root / "app"
    staging = root / "app.staging"
    previous = root / "app.previous"
    live_executable = output / "BienTapTay.exe"

    run_temp = Path(tempfile.mkdtemp(prefix="bientaptay-release-"))
    baseline = run_temp / "baseline.json"
    try:
        assert_app_closed(live_executable)
        with WriterLock(project_config):
            had_receipt = receipt.is_file()
            live_moved = False
            new_promoted = False
            receipt_promoted = False
            if previous.exists():
                raise PublishError(f"Recovery directory exists: {previous}. Resolve it before publishing.")
            for leftover in (receipt_candidate, receipt_backup):
                if leftover.is_dir():
                    shutil.rmtree(leftover, ignore_errors=True)
                elif leftover.is_file():
                    leftover.unlink(missing_ok=True)
            if not fixture_mode and staging.exists():
                shutil.rmtree(staging, ignore_errors=True)
            try:
                print("Step 1/7 - Snapshot authoritative CSV files")
                snapshot(project_config, baseline)

                if not fixture_mode:
                    run_quality_gates(script_root, workspace, root, project_config, configuration)

                print("Step 4/7 - Publish to staging")
                staged_executable = staging / "BienTapTay.exe"
                if fixture_mode:
                    if not staged_executable.is_file() or staged_executable.stat().st_size == 0:
                        raise PublishError(f"Fixture staging executable is missing: {staged_executable}")
                else:
                    staged_executable = publish_to_staging(project, staging, configuration, app_version)
                assert_executable_metadata(staged_executable, app_version)

                print("Step 5/7 - Clean generated files and run migration guard")
                if not fixture_mode:
                    remove_build_artifacts(script_root)
                    migration = root / "project-tests" / "test_project_migration.py"
                    if migration.is_file():
                        run_checked("test_project_migration.py", [sys.executable, str(migration)], cwd=root)
                    if (workspace / ".git").exists():
                        run_checked("git diff --check", ["git", "diff", "--check", "--", str(root)], cwd=workspace)
                prepare(
                    project_config,
                    baseline,
                    staged_executable,
                    live_executable,
                    receipt if had_receipt else None,
                    receipt_candidate,
                    app_version,
                )

                print("Step 6/7 - Promote app and receipt transactionally")
                if output.exists():
                    output.rename(previous)
                    live_moved = True
                staging.rename(output)
                new_promoted = True
                inject_failure("after-app-promotion", inject_publish_failure)
                if had_receipt:
                    replace_file(receipt_candidate, receipt, receipt_backup)
                else:
                    os.replace(receipt_candidate, receipt)
                receipt_promoted = True
                inject_failure("after-receipt-promotion", inject_publish_failure)

                print("Step 7/7 - Read back exact release")
                inject_failure("during-verify", inject_publish_failure)
                verify(project_config, baseline, live_executable, receipt, app_version)
                if previous.exists():
                    shutil.rmtree(previous, ignore_errors=True)
                receipt_backup.unlink(missing_ok=True)
                print(f"Published: {output}")
            except Exception:
                if receipt_promoted:
                    if receipt_backup.is_file():
                        replace_file(receipt_backup, receipt, None)
                    elif not had_receipt and receipt.is_file():
                        receipt.unlink(missing_ok=True)
                if new_promoted and output.exists():
                    shutil.rmtree(output, ignore_errors=True)
                if live_moved and previous.exists():
                    previous.rename(output)
                receipt_backup.unlink(missing_ok=True)
                raise
            finally:
                if not fixture_mode:
                    remove_build_artifacts(script_root)
                if staging.exists():
                    shutil.rmtree(staging, ignore_errors=True)
                receipt_candidate.unlink(missing_ok=True)
    finally:
        shutil.rmtree(run_temp, ignore_errors=True)


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Fail-closed BienTapTay release publisher.")
    root.add_argument("--configuration", default="Release")
    root.add_argument("--app-version", default="0.7.0")
    root.add_argument("--inject-publish-failure", default="", help=argparse.SUPPRESS)
    root.add_argument("--publish-root", type=Path, default=None, help=argparse.SUPPRESS)
    return root


def main() -> int:
    args = parser().parse_args()
    try:
        publish_release(
            app_version=args.app_version,
            configuration=args.configuration,
            inject_publish_failure=args.inject_publish_failure,
            publish_root=args.publish_root,
        )
        return 0
    except WriterLockBusy as exc:
        print(f"LOCK-REFUSED {exc}", file=sys.stderr)
        return 1
    except (PublishError, ReleaseError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
