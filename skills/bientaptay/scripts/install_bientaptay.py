#!/usr/bin/env python3
# Materializes the readable WPF source and tests into one workspace.
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

TEMPLATE_ROOT = Path(__file__).resolve().parents[1] / "templates" / "bientaptay"
APP_VERSION = "0.7.0"


def die(message: str) -> "NoReturn":
    raise SystemExit(message)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def translation_inventory(config_path: Path, workspace: Path) -> list[dict[str, object]]:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    raw_tables = config.get("translationFiles") or [
        {"id": "canonical", "label": "Bản dịch", "path": config.get("canonicalPath")}
    ]
    inventory: list[dict[str, object]] = []
    seen: set[str] = set()
    seen_paths: set[str] = set()
    for raw in raw_tables:
        table_id = str(raw.get("id") or "").strip()
        relative = str(raw.get("path") or "").strip()
        if not table_id or not relative or table_id.casefold() in seen:
            die("translationFiles có id/path trống hoặc id trùng.")
        seen.add(table_id.casefold())
        path = Path(relative)
        if not path.is_absolute():
            path = config_path.parent / path
        path = path.resolve()
        if not path.is_relative_to(workspace) or not path.is_file():
            die(f"Bảng dịch nằm ngoài workspace hoặc không tồn tại: {path}")
        identity = os.path.normcase(str(path))
        if identity in seen_paths:
            die(f"translationFiles trỏ trùng CSV: {path}")
        seen_paths.add(identity)
        with path.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            table_headers = list(reader.fieldnames or [])
            if len(set(table_headers)) != len(table_headers) or any(not name.strip() for name in table_headers):
                die(f"Header CSV trùng hoặc trống: {path}")
            row_count = 0
            for row in reader:
                if None in row or any(value is None for value in row.values()):
                    die(f"Dòng CSV thiếu/thừa cột tại dòng {reader.line_num}: {path}")
                row_count += 1
        if not table_headers or row_count == 0:
            die(f"Bảng dịch trống hoặc thiếu header: {path}")
        inventory.append({
            "id": table_id,
            "label": str(raw.get("label") or table_id),
            "path": str(path),
            "sha256": sha256(path),
            "row_count": row_count,
        })
    return inventory


def pick(headers: list[str], explicit: str | None, candidates: list[str], label: str, required: bool = True) -> str | None:
    if explicit:
        if explicit not in headers:
            die(f"Cột {label} không tồn tại: {explicit}")
        return explicit
    found = [item for item in candidates if item in headers]
    if len(found) == 1:
        return found[0]
    if not found and not required:
        return None
    if not found:
        die(f"Không tìm thấy cột {label}. Hãy truyền tham số rõ ràng.")
    die(f"Có nhiều cột có thể là {label}: {found}. Hãy truyền tham số rõ ràng.")


def source_label(column: str) -> str:
    labels = {
        "source_ja": "Nguồn (Nhật)",
        "source_en": "Nguồn/đối chiếu (Anh)",
        "source_zh_hans": "Đối chiếu (Trung giản thể)",
        "source_zh_hant": "Đối chiếu (Trung phồn thể)",
        "reference": "Đối chiếu",
        "source": "Nguồn",
    }
    return labels.get(column, column)


def run(command: list[str], *, cwd: Path, env: dict[str, str] | None = None) -> None:
    result = subprocess.run(command, cwd=cwd, env=env, text=True)
    if result.returncode:
        die(f"Lệnh thất bại ({result.returncode}): {' '.join(command)}")


def validate_receipt_flags(receipt: dict) -> None:
    for field in ('canonical_unchanged', 'translation_files_unchanged', 'reference_files_unchanged'):
        if receipt.get(field) is not True:
            raise ValueError(f'Release receipt requires JSON true: {field}')


def validate_receipt_count(receipt: dict, inventory: list[dict]) -> None:
    count = receipt.get('text_row_count')
    expected = sum(item['row_count'] for item in inventory)
    if type(count) is not int or count != expected:
        raise ValueError('Release receipt text_row_count does not match CSV inventory')


def rollback_install(transaction, restore, owned_state, extra=()) -> None:
    failures = []
    try:
        transaction.rollback()
    except BaseException as error:
        failures.append(error)
    try:
        restore(owned_state)
    except BaseException as error:
        failures.append(error)
    for step in extra:
        try:
            step()
        except BaseException as error:
            failures.append(error)
    if failures:
        raise BaseExceptionGroup('Installer recovery incomplete; retain backups', failures)


def verify_install_result(canonical, before, translations_before, config_path, workspace, app_root, executable):
    after = sha256(canonical)
    translations_after = translation_inventory(config_path, workspace)
    before_state = [(item["id"], item["path"], item["sha256"], item["row_count"]) for item in translations_before]
    after_state = [(item["id"], item["path"], item["sha256"], item["row_count"]) for item in translations_after]
    if before != after or before_state != after_state:
        die("LỖI: cài app đã làm đổi một CSV authoritative.")
    receipt_path = app_root / "install-receipt.json"
    try:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        die(f"Không đọc được release receipt: {exc}")
    if receipt.get("schema") != "bientaptay-install/v3" or receipt.get("app_version") != APP_VERSION:
        die("Release receipt sai schema hoặc app version.")
    try:
        validate_receipt_flags(receipt)
        validate_receipt_count(receipt, translations_after)
    except ValueError as exc:
        die(str(exc))
    if Path(str(receipt.get("executable") or "")).resolve() != executable.resolve():
        die("Release receipt trỏ sai executable.")
    if receipt.get("executable_sha256") != sha256(executable):
        die("Release receipt có executable hash sai.")
    return receipt, translations_after


def verify_preflight_inputs(expected: dict[Path, str | None]) -> None:
    for path, digest in expected.items():
        try:
            actual = sha256(path) if path.is_file() else None
            valid_type = not path.is_symlink() and (not path.exists() or path.is_file())
        except OSError as error:
            die(f'Cannot recheck preflight input: {path}: {error}')
        if not valid_type or actual != digest:
            die(f'Preflight input changed before installation: {path}')


def main() -> None:
    parser = argparse.ArgumentParser(description="Cài bientaptay vào workspace Việt hóa dùng CSV canonical.")
    parser.add_argument("--handoff", required=True, help="Verified canonical-editor-handoff/v1 manifest")
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--canonical", required=True, help="Đường dẫn CSV, tương đối với workspace hoặc tuyệt đối.")
    parser.add_argument("--project-name", required=True)
    parser.add_argument("--source-column", action="append", default=[], help="Lặp lại theo thứ tự: nguồn chuẩn trước, đối chiếu sau.")
    parser.add_argument("--key-column")
    parser.add_argument("--target-column")
    parser.add_argument("--status-column")
    parser.add_argument("--notes-column")
    parser.add_argument("--speaker-column")
    parser.add_argument("--group-column")
    parser.add_argument("--protected-tokens-column")
    parser.add_argument("--update", action="store_true", help="Cập nhật source/app hiện có; giữ data và config nếu không --reconfigure.")
    parser.add_argument("--reconfigure", action="store_true")
    args = parser.parse_args()

    if platform.system() != "Windows":
        die("bientaptay hiện dùng WPF và chỉ hỗ trợ Windows.")
    workspace = Path(args.workspace).expanduser().resolve()
    import runpy
    _val_candidates = (
        Path(__file__).resolve().parents[3] / "gaming/viethoa/scripts/validate_canonical_editor_handoff.py",
        Path(__file__).resolve().parents[2] / "viethoa/scripts/validate_canonical_editor_handoff.py",
    )
    validator = next((c for c in _val_candidates if c.is_file()), _val_candidates[0])
    if not validator.is_file():
        die("Missing viethoa handoff validator; install the companion skill.")
    validator_module = runpy.run_path(str(validator))
    if validator_module.get("SCHEMA") != "viethoa/canonical-editor-handoff/v1" or "validate" not in validator_module:
        die("Incompatible viethoa handoff validator; require canonical-editor-handoff/v1.")
    contract = validator_module["validate"](Path(args.handoff), workspace)
    if contract.get("schema") != "viethoa/canonical-editor-handoff/v1":
        die("Unsupported handoff schema; this installer accepts v1 only.")
    # ponytail: installer currently materializes one table; multi-table upgrade requires a separate mapped-config contract.
    if len(contract["files"]) != 1:
        die("Multi-table installation is not supported by this handoff integration.")
    mapping = contract["canonical_identity"]
    for flag, field in [("key_column", "key_column"), ("target_column", "target_column"), ("status_column", "state_column"), ("protected_tokens_column", "protected_tokens_column")]:
        value = mapping.get(field)
        if getattr(args, flag) is not None and getattr(args, flag) != value:
            die("CLI mapping conflicts with handoff.")
        setattr(args, flag, value)
    if args.source_column and args.source_column[0] != mapping["source_column"]:
        die("Authoritative source conflicts with handoff.")
    args.source_column = args.source_column or [mapping["source_column"]]
    existing = workspace / "bientaptay/project.json"
    existing_digest = sha256(existing) if existing.is_file() else None
    if existing.exists() and args.update:
        config = json.loads(existing.read_text(encoding="utf-8"))
        if config.get("translationFiles"):
            die("Multi-table update requires per-table handoff support; existing config remains untouched.")
        for field, expected in [("keyColumn", mapping["key_column"]), ("targetColumn", mapping["target_column"]), ("statusColumn", mapping["state_column"])]:
            if not args.reconfigure and config.get(field) != expected:
                die("Existing config conflicts with handoff; explicit reconfiguration required.")
        if not args.reconfigure and (not config.get("sourceFields") or config["sourceFields"][0].get("column") != mapping["source_column"]):
            die("Existing authoritative source conflicts with handoff.")
        if (existing.parent / config["canonicalPath"]).resolve() != (workspace / contract["files"][0]["path"]).resolve():
            die("Existing canonical path conflicts with handoff.")
    canonical = Path(args.canonical).expanduser()
    if not canonical.is_absolute():
        canonical = workspace / canonical
    canonical = canonical.resolve()
    if not canonical.is_relative_to(workspace):
        die("Canonical phải nằm trong workspace.")
    if not canonical.is_file():
        die(f"Không tìm thấy canonical: {canonical}")

    if canonical != (workspace / contract["files"][0]["path"]).resolve():
        die("Canonical path conflicts with handoff.")
    before = sha256(canonical)
    if before != contract["files"][0]["sha256"]:
        die("Canonical changed after handoff validation.")
    handoff_sha256 = sha256(Path(args.handoff).resolve())
    if Path(args.handoff).resolve().is_relative_to(workspace):
        pass
    else:
        die("Handoff must be inside workspace.")
    with canonical.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        headers = list(reader.fieldnames or [])
        rows = list(reader)
    if not headers or not rows:
        die("Canonical phải có header và ít nhất một dòng.")

    key = pick(headers, args.key_column, ["key", "id", "Key"], "key")
    target = pick(headers, args.target_column, ["translation_vi", "target_vi", "vi", "target"], "bản dịch Việt")
    status = pick(headers, args.status_column, ["status", "state"], "trạng thái")
    notes = pick(headers, args.notes_column, ["review_note", "notes", "note"], "ghi chú", required=False)
    speaker = pick(headers, args.speaker_column, ["speaker", "character", "actor"], "người nói", required=False)
    group = pick(headers, args.group_column, ["asset", "domain", "scene", "file"], "nhóm", required=False)
    protected = pick(headers, args.protected_tokens_column, ["protected_tokens", "tokens"], "protected tokens", required=False)

    sources = list(args.source_column)
    if sources:
        missing = [item for item in sources if item not in headers]
        if missing:
            die(f"Cột nguồn không tồn tại: {missing}")
    else:
        priority = ["source", "source_ja", "source_en", "source_zh_hans", "source_zh_hant", "reference"]
        sources = [item for item in priority if item in headers and item != target]
        sources += [item for item in headers if item.startswith("source_") and item not in sources and item != target]
        if not sources:
            die("Không nhận diện được cột nguồn. Dùng --source-column và đặt nguồn chuẩn trước.")

    current_statuses = {row.get(status or "", "").strip() for row in rows}
    current_statuses.discard("")
    preferred = ["pending", "translated", "reviewed", "needs_context", "needs-context", "rejected"]
    statuses = [item for item in preferred if item in current_statuses or item in {"pending", "translated", "reviewed", "needs_context", "rejected"}]
    statuses += sorted(current_statuses - set(statuses))

    app_root = workspace / "bientaptay"
    if (app_root / "src").exists() and not args.update:
        die("bientaptay đã tồn tại. Dùng --update để cập nhật có chủ ý.")
    if not TEMPLATE_ROOT.is_dir():
        die(f"Thiếu template bientaptay: {TEMPLATE_ROOT}")
    import runpy
    inventory = runpy.run_path(str(Path(__file__).with_name("template_inventory.py")))
    swapper = runpy.run_path(str(Path(__file__).with_name("template_swap.py")))
    installer_lock = swapper["InstallerLock"](workspace)
    try:
        installer_lock.__enter__()
    except swapper["SwapError"] as exc:
        die(f"Installer khác đang chạy trên workspace này: {exc}")
    import atexit
    atexit.register(installer_lock.__exit__, None, None, None)
    verify_preflight_inputs({canonical: before, Path(args.handoff).resolve(): handoff_sha256,
                             existing: existing_digest})
    owned_state = swapper["snapshot_files"]([
        app_root / "project.json", app_root / "data" / "glossary.csv", app_root / "data" / "pronouns.csv",
        app_root / "install-receipt.json", app_root / "performance-baseline.json",
    ])
    try:
        app_backup = swapper["DirBackup"](app_root / "app")
    except swapper["SwapError"] as exc:
        die(f"Không backup được app hiện tại: {exc}")
    try:
        transaction = swapper["begin_swap"](app_root, TEMPLATE_ROOT, inventory["template_files"](TEMPLATE_ROOT))
    except swapper["SwapError"] as exc:
        app_backup.discard()
        die(f"Cập nhật template thất bại, bản cũ đã được khôi phục: {exc}")

    try:
        data_dir = app_root / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        glossary = data_dir / "glossary.csv"
        pronouns = data_dir / "pronouns.csv"
        if not glossary.exists():
            glossary.write_text("term,translation,type,context,status\n", encoding="utf-8-sig", newline="")
        if not pronouns.exists():
            pronouns.write_text("speaker,addressee,relationship,self_reference,address_form,notes,status,evidence_keys\n", encoding="utf-8-sig", newline="")

        config_path = app_root / "project.json"
        if not config_path.exists() or args.reconfigure or not args.update:
            config = {
                "schemaVersion": 1,
                "handoffSchema": contract["schema"],
                "handoffSha256": handoff_sha256,
                "canonicalSha256": contract["files"][0]["sha256"],
                "keySetSha256": contract["files"][0]["key_set_sha256"],
                "projectName": args.project_name,
                "canonicalPath": os.path.relpath(canonical, app_root).replace("\\", "/"),
                "keyColumn": key,
                "sourceFields": [{"column": item, "label": source_label(item)} for item in sources],
                "targetColumn": target,
                "speakerColumn": speaker,
                "groupColumn": group,
                "statusColumn": status,
                "notesColumn": notes,
                "protectedTokensColumn": protected,
                "statuses": statuses,
                "tokenPattern": r"<[^>]+>|\|#[^|]+\||\{[^{}]+\}|%\d*\$?[A-Za-z]|\\[nrt]",
                "references": [
                    {"id": "glossary", "label": "Thuật ngữ", "path": "data/glossary.csv", "keyColumn": "term"},
                    {"id": "pronouns", "label": "Xưng hô", "path": "data/pronouns.csv", "keyColumn": "speaker"},
                ],
            }
            config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        readme = app_root / "README.md"
        if not readme.exists():
            readme.write_text(
                "# bientaptay\n\nỨng dụng biên tập trực tiếp một hoặc nhiều CSV authoritative; không tạo XLSX hoặc database bóng.\n\n"
                "Chạy `Launch-BienTapTay.cmd`. `Ctrl+S` lưu, `Ctrl+F` tìm, `F5` nạp lại.\n"
                "Mọi save dùng stale SHA-256 guard, temp sibling, atomic replace, readback và checkpoint `.bientaptay.bak`.\n",
                encoding="utf-8", newline="")

        translations_before = translation_inventory(config_path, workspace)

        version = subprocess.run(["dotnet", "--version"], text=True, capture_output=True)
        if version.returncode or not version.stdout.strip().startswith("8."):
            die("Cần .NET 8 SDK để build bientaptay.")
        run([
            sys.executable, str(app_root / "release_publish.py"),
            "--app-version", APP_VERSION,
        ], cwd=workspace)
        live = app_root / "app"
        executable = live / "BienTapTay.exe"
        if not executable.is_file() or executable.stat().st_size == 0:
            die("Release pipeline không tạo BienTapTay.exe.")
        receipt, translations_after = verify_install_result(
            canonical, before, translations_before, config_path, workspace, app_root, executable)
    except BaseException:
        rollback_install(transaction, swapper["restore_files"], owned_state, extra=(app_backup.restore,))
        print("Cài/cập nhật thất bại; source, config, receipt, baseline và app đã khôi phục.", file=sys.stderr)
        raise
    transaction.commit()
    app_backup.discard()

    for base in (app_root / "src", app_root / "tests"):
        for generated in list(base.rglob("bin")) + list(base.rglob("obj")):
            shutil.rmtree(generated, ignore_errors=True)
    for cache in (app_root / "tests").rglob("__pycache__"):
        shutil.rmtree(cache, ignore_errors=True)
    print(json.dumps({
        "result": "installed",
        "text_rows": receipt["text_row_count"],
        "translation_files": len(translations_after),
        "canonical_unchanged": True,
        "app": str(live / "BienTapTay.exe"),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
