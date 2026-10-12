from __future__ import annotations

import argparse
import csv
import ctypes
import hashlib
import json
import os
import re
import sys
from ctypes import wintypes
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class ReleaseError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def assembly_file_version(app_version: str) -> str:
    text = (app_version or "").strip()
    if not text:
        raise ReleaseError("app version is empty")
    core = text.split("-", 1)[0]
    if not re.fullmatch(r"\d+(?:\.\d+){0,3}", core):
        raise ReleaseError(f"app version is not a numeric version: {app_version}")
    parts = core.split(".")
    if any(int(part) > 65535 for part in parts):
        raise ReleaseError(f"app version part exceeds 65535: {app_version}")
    while len(parts) < 4:
        parts.append("0")
    return ".".join(parts)


def read_exe_version_strings(path: Path) -> tuple[str, str]:
    if os.name != "nt":
        raise ReleaseError("executable version readback requires Windows")
    version = ctypes.WinDLL("version")
    get_size = version.GetFileVersionInfoSizeW
    get_size.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(wintypes.DWORD)]
    get_size.restype = wintypes.DWORD
    get_info = version.GetFileVersionInfoW
    get_info.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID]
    get_info.restype = wintypes.BOOL
    query = version.VerQueryValueW
    query.argtypes = [wintypes.LPVOID, wintypes.LPCWSTR, ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(wintypes.UINT)]
    query.restype = wintypes.BOOL

    handle = wintypes.DWORD(0)
    size = get_size(str(path), ctypes.byref(handle))
    if size == 0:
        raise ReleaseError(f"executable has no version resource: {path}")
    buffer = ctypes.create_string_buffer(size)
    if not get_info(str(path), 0, size, buffer):
        raise ReleaseError(f"cannot read version resource: {path}")

    class LanguageAndCodePage(ctypes.Structure):
        _fields_ = [("wLanguage", wintypes.WORD), ("wCodePage", wintypes.WORD)]

    pointer = ctypes.c_void_p()
    length = wintypes.UINT(0)
    if not query(buffer, r"\VarFileInfo\Translation", ctypes.byref(pointer), ctypes.byref(length)):
        raise ReleaseError(f"executable version translation is missing: {path}")
    if pointer.value is None or length.value < ctypes.sizeof(LanguageAndCodePage):
        raise ReleaseError(f"executable version translation is empty: {path}")
    translation = LanguageAndCodePage.from_address(pointer.value)
    prefix = f"\\StringFileInfo\\{translation.wLanguage:04x}{translation.wCodePage:04x}\\"

    def read_string(name: str) -> str:
        value_pointer = ctypes.c_void_p()
        value_length = wintypes.UINT(0)
        if not query(buffer, prefix + name, ctypes.byref(value_pointer), ctypes.byref(value_length)):
            raise ReleaseError(f"executable missing {name} version string: {path}")
        if value_pointer.value is None:
            raise ReleaseError(f"executable {name} version string is empty: {path}")
        chars = max(int(value_length.value) - 1, 0)
        return ctypes.wstring_at(value_pointer, chars).rstrip("\x00")

    file_version = read_string("FileVersion")
    product_version = read_string("ProductVersion")
    if not file_version or not product_version:
        raise ReleaseError(f"executable version strings are empty: {path}")
    return file_version, product_version


def assert_executable_metadata(path: Path, app_version: str) -> tuple[str, str]:
    expected_file = assembly_file_version(app_version)
    expected_product = app_version.strip()
    file_version, product_version = read_exe_version_strings(path)
    if file_version != expected_file:
        raise ReleaseError(f"FileVersion mismatch: expected {expected_file}, got {file_version}")
    if product_version != expected_product:
        raise ReleaseError(f"ProductVersion mismatch: expected {expected_product}, got {product_version}")
    if "+" in product_version:
        raise ReleaseError(f"ProductVersion contains a source-revision suffix: {product_version}")
    return file_version, product_version


def resolve(base: Path, raw: object) -> Path:
    text = str(raw or "").strip()
    if not text:
        raise ReleaseError("project.json contains an empty path")
    path = Path(text)
    return (path if path.is_absolute() else base / path).resolve()


def read_csv(path: Path) -> tuple[list[str], int]:
    if not path.is_file():
        raise ReleaseError(f"missing CSV: {path}")
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        headers = list(reader.fieldnames or [])
        count = sum(1 for _ in reader)
    if not headers:
        raise ReleaseError(f"CSV has no header: {path}")
    return headers, count


def load_project(project_path: Path) -> dict[str, Any]:
    try:
        project = json.loads(project_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReleaseError(f"invalid project config {project_path}: {exc}") from exc
    if not isinstance(project, dict):
        raise ReleaseError("project.json root must be an object")
    return project


def inventory(project_path: Path) -> dict[str, Any]:
    project_path = project_path.resolve()
    project = load_project(project_path)
    base = project_path.parent
    translations = project.get("translationFiles") or [
        {
            "id": "canonical",
            "label": "Bản dịch",
            "path": project.get("canonicalPath"),
        }
    ]
    references = project.get("references") or []
    result: dict[str, Any] = {"translation_files": [], "reference_files": []}
    for kind, entries in (("translation_files", translations), ("reference_files", references)):
        if not isinstance(entries, list):
            raise ReleaseError(f"{kind} must be an array")
        seen: set[str] = set()
        for entry in entries:
            if not isinstance(entry, dict):
                raise ReleaseError(f"{kind} entry must be an object")
            file_id = str(entry.get("id") or "").strip()
            if not file_id or file_id.casefold() in seen:
                raise ReleaseError(f"{kind} contains an empty or duplicate id")
            seen.add(file_id.casefold())
            path = resolve(base, entry.get("path"))
            headers, row_count = read_csv(path)
            result[kind].append(
                {
                    "id": file_id,
                    "label": str(entry.get("label") or file_id),
                    "path": str(path),
                    "sha256": sha256(path),
                    "row_count": row_count,
                    "headers": headers,
                }
            )
    if not result["translation_files"]:
        raise ReleaseError("project has no translation files")
    result["project"] = project
    result["project_path"] = str(project_path)
    result["qa_decisions"] = inspect_qa_decisions(qa_decisions_path(project_path))
    return result


def comparable(files: list[dict[str, Any]]) -> list[tuple[str, str, str, int]]:
    return [
        (
            str(item["id"]),
            os.path.normcase(str(Path(item["path"]).resolve())),
            str(item["sha256"]),
            int(item["row_count"]),
        )
        for item in files
    ]


def assert_unchanged(baseline: dict[str, Any], current: dict[str, Any]) -> None:
    for kind in ("translation_files", "reference_files"):
        if comparable(list(baseline.get(kind) or [])) != comparable(list(current.get(kind) or [])):
            raise ReleaseError(f"{kind} changed after baseline")
    if "qa_decisions" not in baseline:
        raise ReleaseError("release baseline missing qa_decisions")
    assert_qa_decisions_unchanged(
        baseline["qa_decisions"],
        current["qa_decisions"],
        "baseline",
        qa_decisions_path(Path(str(current["project_path"]))),
    )


def qa_decisions_path(project_path: Path) -> Path:
    return project_path.resolve().parent / "qa-decisions.json"


# Lockstep with BienTapTay.Core.QaDecisionStore.Open: existing malformed sidecar is fail-closed.
QA_DECISION_SCHEMA = "bientaptay-qa-decisions/v1"
QA_DECISION_KINDS = frozenset({"DuplicateSource", "GlossaryDrift", "PronounDeviation"})
QA_DECISION_STATUSES = ("needs_fix", "accepted_difference", "resolved")


_SHA256_HEX = re.compile(r"^[0-9A-Fa-f]{64}$")
_SHA256_HEX_LOWER = re.compile(r"^[0-9a-f]{64}$")
_DOTNET_DTO = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,7})?(?:Z|[+-]\d{2}:\d{2})$"
)


def comparable_qa_decisions(meta: dict[str, Any]) -> tuple[Any, ...]:
    by_status = meta["by_status"]
    return (
        meta["present"],
        os.path.normcase(str(Path(str(meta["path"])).resolve())),
        meta["sha256"],
        meta["decision_count"],
        by_status["needs_fix"],
        by_status["accepted_difference"],
        by_status["resolved"],
    )


def assert_qa_decisions_unchanged(left: object, right: object, label: str, expected_path: Path | None = None) -> None:
    if expected_path is None:
        if not isinstance(right, dict) or not isinstance(right.get("path"), str) or not Path(str(right["path"])).is_absolute():
            raise ReleaseError("qa_decisions path is required for comparison")
        expected_path = Path(str(right["path"]))
    validate_qa_decisions_metadata(left, expected_path)
    validate_qa_decisions_metadata(right, expected_path)
    if comparable_qa_decisions(left) != comparable_qa_decisions(right):  # type: ignore[arg-type]
        raise ReleaseError(f"qa_decisions changed after {label}")


def validate_qa_decisions_metadata(meta: object, expected_path: Path) -> None:
    try:
        _validate_qa_decisions_metadata(meta, expected_path)
    except ReleaseError:
        raise
    except (TypeError, ValueError, AttributeError) as exc:
        raise ReleaseError("qa_decisions metadata is invalid") from exc


def _is_json_bool(value: object) -> bool:
    return type(value) is bool


def _is_json_int(value: object) -> bool:
    return type(value) is int


def _validate_qa_decisions_metadata(meta: object, expected_path: Path) -> None:
    if not isinstance(meta, dict):
        raise ReleaseError("qa_decisions metadata must be an object")
    expected = expected_path.resolve()
    if "present" not in meta:
        raise ReleaseError("qa_decisions missing present")
    if not _is_json_bool(meta["present"]):
        raise ReleaseError("qa_decisions present must be a JSON boolean")
    present = meta["present"]
    if "path" not in meta:
        raise ReleaseError("qa_decisions missing path")
    path = meta["path"]
    if not isinstance(path, str) or path == "":
        raise ReleaseError("qa_decisions path must be a string")
    if not Path(path).is_absolute():
        raise ReleaseError("qa_decisions path must be absolute")
    if os.path.normcase(str(Path(path).resolve())) != os.path.normcase(str(expected)):
        raise ReleaseError("qa_decisions path mismatch")
    if "sha256" not in meta:
        raise ReleaseError("qa_decisions missing sha256")
    digest = meta["sha256"]
    if "decision_count" not in meta:
        raise ReleaseError("qa_decisions missing decision_count")
    if not _is_json_int(meta["decision_count"]):
        raise ReleaseError("qa_decisions decision_count must be a JSON integer")
    count = meta["decision_count"]
    if count < 0:
        raise ReleaseError("qa_decisions decision_count is negative")
    if "by_status" not in meta:
        raise ReleaseError("qa_decisions missing by_status")
    by_status = meta["by_status"]
    if not isinstance(by_status, dict):
        raise ReleaseError("qa_decisions by_status must be an object")
    if set(by_status.keys()) != set(QA_DECISION_STATUSES):
        raise ReleaseError("qa_decisions by_status keys must be exactly needs_fix, accepted_difference, resolved")
    statuses: dict[str, int] = {}
    for name in QA_DECISION_STATUSES:
        value = by_status[name]
        if not _is_json_int(value):
            raise ReleaseError(f"qa_decisions by_status.{name} must be a JSON integer")
        if value < 0:
            raise ReleaseError(f"qa_decisions by_status.{name} is negative")
        statuses[name] = value
    if sum(statuses.values()) != count:
        raise ReleaseError("qa_decisions by_status does not sum to decision_count")
    if present:
        if not isinstance(digest, str) or _SHA256_HEX_LOWER.fullmatch(digest) is None:
            raise ReleaseError("qa_decisions sha256 must be 64 lowercase hex when present")
    else:
        if digest is not None:
            raise ReleaseError("qa_decisions sha256 must be null when absent")
        if count != 0:
            raise ReleaseError("qa_decisions decision_count must be 0 when absent")
        if any(value != 0 for value in statuses.values()):
            raise ReleaseError("qa_decisions by_status must be zero when absent")


def _is_valid_dotnet_datetime_offset(value: object) -> bool:
    if not isinstance(value, str) or not value:
        return False
    if _DOTNET_DTO.fullmatch(value) is None:
        return False
    offset = value[value.rfind("Z") :] if value.endswith("Z") else value[-6:]
    if offset != "Z":
        hours = int(offset[1:3])
        minutes = int(offset[4:6])
        if hours > 14 or (hours == 14 and minutes != 0):
            return False
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, OverflowError):
        return False
    if parsed.tzinfo is None:
        return False
    try:
        utc_naive = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    except OverflowError:
        return False
    return utc_naive != datetime(1, 1, 1)


def parse_qa_decisions_bytes(raw: bytes) -> list[dict[str, Any]]:
    try:
        document = json.loads(raw.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ReleaseError("qa-decisions.json is malformed or unreadable") from exc
    if not isinstance(document, dict):
        raise ReleaseError("qa-decisions.json is malformed or unreadable")
    schema = document["schema"] if "schema" in document else ""
    if schema is None or schema != QA_DECISION_SCHEMA:
        raise ReleaseError("qa-decisions.json is malformed or unreadable")
    if "decisions" in document and document["decisions"] is None:
        raise ReleaseError("qa-decisions.json is malformed or unreadable")
    decisions = document["decisions"] if "decisions" in document else []
    if not isinstance(decisions, list):
        raise ReleaseError("qa-decisions.json is malformed or unreadable")
    parsed: list[dict[str, Any]] = []
    for item in decisions:
        if not isinstance(item, dict):
            raise ReleaseError("qa-decisions.json is malformed or unreadable")
        decision_id = item["id"] if "id" in item else ""
        translation_id = item["translationId"] if "translationId" in item else ""
        kind = item["kind"] if "kind" in item else ""
        key = item["key"] if "key" in item else ""
        if "relatedKeys" in item and item["relatedKeys"] is None:
            raise ReleaseError("qa-decisions.json is malformed or unreadable")
        related = item["relatedKeys"] if "relatedKeys" in item else []
        fingerprint = item["contentFingerprint"] if "contentFingerprint" in item else ""
        status = item["status"] if "status" in item else ""
        if "note" in item and item["note"] is None:
            raise ReleaseError("qa-decisions.json is malformed or unreadable")
        note = item["note"] if "note" in item else ""
        if "updatedAtUtc" not in item or not _is_valid_dotnet_datetime_offset(item["updatedAtUtc"]):
            raise ReleaseError("qa-decisions.json is malformed or unreadable")
        if (
            not isinstance(decision_id, str)
            or _SHA256_HEX.fullmatch(decision_id) is None
            or not isinstance(translation_id, str)
            or len(translation_id) == 0
            or not isinstance(kind, str)
            or kind not in QA_DECISION_KINDS
            or not isinstance(key, str)
            or len(key) == 0
            or not isinstance(related, list)
            or any(not isinstance(entry, str) or not entry.strip() for entry in related)
            or not isinstance(fingerprint, str)
            or _SHA256_HEX.fullmatch(fingerprint) is None
            or status not in QA_DECISION_STATUSES
            or not isinstance(note, str)
        ):
            raise ReleaseError("qa-decisions.json is malformed or unreadable")
        parsed.append({"id": decision_id, "status": status})
    ids = [item["id"] for item in parsed]
    if len({item.casefold() for item in ids}) != len(ids):
        raise ReleaseError("qa-decisions.json is malformed or unreadable")
    return parsed


def inspect_qa_decisions(path: Path) -> dict[str, Any]:
    path = path.resolve()
    absent = {
        "present": False,
        "path": str(path),
        "sha256": None,
        "decision_count": 0,
        "by_status": {status: 0 for status in QA_DECISION_STATUSES},
    }
    if path.is_dir():
        raise ReleaseError(f"qa-decisions.json is malformed or unreadable: {path}")
    if not path.is_file():
        return absent
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise ReleaseError(f"qa-decisions.json is malformed or unreadable: {path}") from exc
    try:
        records = parse_qa_decisions_bytes(raw)
    except (ReleaseError, json.JSONDecodeError, UnicodeDecodeError, TypeError, ValueError) as exc:
        raise ReleaseError(f"qa-decisions.json is malformed or unreadable: {path}") from exc
    by_status = {status: 0 for status in QA_DECISION_STATUSES}
    for item in records:
        by_status[str(item["status"])] += 1
    return {
        "present": True,
        "path": str(path),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "decision_count": len(records),
        "by_status": by_status,
    }


def atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".writing")
    try:
        temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        json.loads(temp.read_text(encoding="utf-8"))
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def snapshot(project_path: Path, output: Path) -> None:
    current = inventory(project_path)
    value = {
        "schema": "bientaptay-release-baseline/v1",
        "project": current["project_path"],
        "translation_files": current["translation_files"],
        "reference_files": current["reference_files"],
        "qa_decisions": current["qa_decisions"],
    }
    atomic_json(output, value)
    print(json.dumps({"result": "snapshot", "files": len(value["translation_files"]) + len(value["reference_files"])}, ensure_ascii=False))


def load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReleaseError(f"invalid {label} {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ReleaseError(f"{label} root must be an object")
    return value


def receipt_inventory(files: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "id": item["id"],
            "label": item["label"],
            "path": item["path"],
            "sha256": item["sha256"],
            "row_count": item["row_count"],
        }
        for item in files
    ]


def completed_gates(project_path: Path) -> list[str]:
    root = project_path.resolve().parent
    workspace = root.parent
    gates = ["BienTapTay.Tests", "BienTapTay.AppSmoke", "BienTapTay.Benchmarks", "consistency_corpus_audit"]
    optional = [
        (workspace / "tools" / "validate_workbook.py", "validate_workbook.py"),
        (root / "project-tests" / "test_pronoun_data.py", "test_pronoun_data.py"),
        (root / "project-tests" / "test_release_receipt.py", "test_release_receipt.py"),
        (root / "project-tests" / "test_writer_lock.py", "test_writer_lock.py"),
        (root / "project-tests" / "test_publish_script.py", "test_publish_script.py"),
        (root / "project-tests" / "test_performance_benchmark.py", "test_performance_benchmark.py"),
        (root / "project-tests" / "test_project_migration.py", "test_project_migration.py"),
    ]
    return gates + [name for path, name in optional if path.is_file()]


def prepare(
    project_path: Path,
    baseline_path: Path,
    executable: Path,
    published_executable: Path,
    existing_receipt: Path | None,
    output: Path,
    app_version: str,
) -> None:
    baseline = load_json(baseline_path, "release baseline")
    current = inventory(project_path)
    assert_unchanged(baseline, current)
    executable = executable.resolve()
    if not executable.is_file() or executable.stat().st_size == 0:
        raise ReleaseError(f"missing published executable: {executable}")
    file_version, product_version = assert_executable_metadata(executable, app_version)
    existing: dict[str, Any] = {}
    if existing_receipt is not None and existing_receipt.is_file():
        existing = load_json(existing_receipt, "existing receipt")

    translations = list(current["translation_files"])
    references = list(current["reference_files"])
    primary = translations[0]
    before_primary = list(baseline["translation_files"])[0]
    project = current["project"]
    receipt: dict[str, Any] = {
        "schema": "bientaptay-install/v3",
        "installed_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "app_version": app_version,
        "workspace": str(project_path.resolve().parent.parent),
        "project_config": str(project_path.resolve()),
        "canonical": primary["path"],
        "canonical_sha256_before": before_primary["sha256"],
        "canonical_sha256_after": primary["sha256"],
        "canonical_unchanged": before_primary["sha256"] == primary["sha256"],
        "translation_files_unchanged": True,
        "reference_files_unchanged": True,
        "translation_files": receipt_inventory(translations),
        "text_row_count": sum(int(item["row_count"]) for item in translations),
        "reference_files": receipt_inventory(references),
        "row_count": primary["row_count"],
        "headers": primary["headers"],
        "source_columns": [str(item.get("column") or "") for item in project.get("sourceFields") or []],
        "target_column": str(project.get("targetColumn") or "translation_vi"),
        "executable": str(published_executable.resolve()),
        "executable_sha256": sha256(executable),
        "executable_file_version": file_version,
        "executable_product_version": product_version,
        "release_pipeline": {
            "mode": "fail_closed_transaction",
            "canonical_and_references_unchanged": True,
            "receipt_readback_required": True,
        },
        "tests": completed_gates(project_path),
        "qa_decisions": current["qa_decisions"],
    }
    features = [str(item) for item in existing.get("features") or []]
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
        if feature not in features:
            features.append(feature)
    receipt["features"] = features
    if "consistency_qa" in existing:
        receipt["consistency_qa"] = existing["consistency_qa"]
    if not receipt["canonical_unchanged"]:
        raise ReleaseError("canonical changed after baseline")
    atomic_json(output, receipt)
    print(json.dumps({"result": "prepared", "text_rows": receipt["text_row_count"], "executable_sha256": receipt["executable_sha256"]}, ensure_ascii=False))


def verify(project_path: Path, baseline_path: Path, executable: Path, receipt_path: Path, app_version: str) -> None:
    baseline = load_json(baseline_path, "release baseline")
    current = inventory(project_path)
    assert_unchanged(baseline, current)
    receipt = load_json(receipt_path, "install receipt")
    executable = executable.resolve()
    if receipt.get("schema") != "bientaptay-install/v3":
        raise ReleaseError("receipt schema mismatch")
    if receipt.get("app_version") != app_version:
        raise ReleaseError("receipt app_version mismatch")
    file_version, product_version = assert_executable_metadata(executable, app_version)
    if receipt.get("executable_file_version") != file_version:
        raise ReleaseError("receipt executable_file_version mismatch")
    if receipt.get("executable_product_version") != product_version:
        raise ReleaseError("receipt executable_product_version mismatch")
    if receipt.get("executable") != str(executable):
        raise ReleaseError("receipt executable path mismatch")
    if not executable.is_file() or receipt.get("executable_sha256") != sha256(executable):
        raise ReleaseError("receipt executable hash mismatch")
    if comparable(list(receipt.get("translation_files") or [])) != comparable(list(current["translation_files"])):
        raise ReleaseError("receipt translation inventory mismatch")
    if comparable(list(receipt.get("reference_files") or [])) != comparable(list(current["reference_files"])):
        raise ReleaseError("receipt reference inventory mismatch")
    if not receipt.get("canonical_unchanged") or not receipt.get("translation_files_unchanged") or not receipt.get("reference_files_unchanged"):
        raise ReleaseError("receipt unchanged guards are false")
    if "qa_decisions" not in receipt:
        raise ReleaseError("receipt missing qa_decisions")
    assert_qa_decisions_unchanged(
        receipt["qa_decisions"],
        current["qa_decisions"],
        "receipt",
        qa_decisions_path(project_path),
    )
    print(json.dumps({"result": "verified", "text_rows": receipt.get("text_row_count"), "executable_sha256": receipt["executable_sha256"]}, ensure_ascii=False))


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Build and verify a fail-closed bientaptay release receipt.")
    commands = root.add_subparsers(dest="command", required=True)
    snapshot_parser = commands.add_parser("snapshot")
    snapshot_parser.add_argument("--project", type=Path, required=True)
    snapshot_parser.add_argument("--output", type=Path, required=True)

    prepare_parser = commands.add_parser("prepare")
    prepare_parser.add_argument("--project", type=Path, required=True)
    prepare_parser.add_argument("--baseline", type=Path, required=True)
    prepare_parser.add_argument("--executable", type=Path, required=True)
    prepare_parser.add_argument("--published-executable", type=Path, required=True)
    prepare_parser.add_argument("--existing-receipt", type=Path)
    prepare_parser.add_argument("--output", type=Path, required=True)
    prepare_parser.add_argument("--app-version", required=True)

    verify_parser = commands.add_parser("verify")
    verify_parser.add_argument("--project", type=Path, required=True)
    verify_parser.add_argument("--baseline", type=Path, required=True)
    verify_parser.add_argument("--executable", type=Path, required=True)
    verify_parser.add_argument("--receipt", type=Path, required=True)
    verify_parser.add_argument("--app-version", required=True)
    return root


def main() -> int:
    args = parser().parse_args()
    try:
        if args.command == "snapshot":
            snapshot(args.project, args.output)
        elif args.command == "prepare":
            prepare(
                args.project,
                args.baseline,
                args.executable,
                args.published_executable,
                args.existing_receipt,
                args.output,
                args.app_version,
            )
        else:
            verify(args.project, args.baseline, args.executable, args.receipt, args.app_version)
        return 0
    except ReleaseError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
