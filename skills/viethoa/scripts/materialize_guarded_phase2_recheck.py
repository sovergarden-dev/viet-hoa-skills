from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import os
import secrets
import subprocess
import sys
from pathlib import Path
from typing import Any

CONTRACT = "AGY-VIETHOA-HANDOFF/2.5-TWO-PHASE-DRAFT12-PREVIEW-FINAL0-GUARDED"
FULL_SCHEMA = "agy-phase2-full-pass-snapshot/v1"
RECHECK_SCHEMA = "agy-phase2-recheck-schedule/v1"
PHASE = "phase2_main_only_final"


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        with temporary.open("wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()
    if path.read_bytes() != data:
        raise RuntimeError(f"atomic readback mismatch: {path}")


def json_bytes(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, indent=2).encode("utf-8") + b"\n"


def read_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError(f"{label} unreadable: {path}") from error
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object")
    return value


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        rows = [dict(row) for row in csv.DictReader(stream)]
    if not rows or any(None in row for row in rows):
        raise ValueError("full-pass snapshot CSV malformed or empty")
    return rows


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import pinned module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def truth(value: object) -> bool:
    return str(value).strip().casefold() in {"1", "true", "yes", "y", "high"}


def runtime_flagged_ids(rows: list[dict[str, str]]) -> list[str]:
    return [row["handoff_id"] for row in rows if truth(row.get("runtime_flagged"))]


def explicit_high_risk_ids(rows: list[dict[str, str]]) -> list[str]:
    fields = ("high_risk", "semantic_high_risk", "language_high_risk")
    return [row["handoff_id"] for row in rows if any(truth(row.get(field)) for field in fields)]


def read_optional_ids(path: Path | None, label: str) -> list[str]:
    if path is None:
        return []
    value: object = json.loads(path.read_text(encoding="utf-8-sig"))
    if isinstance(value, dict):
        value = value.get("handoff_ids")
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ValueError(f"{label} must be a JSON string array or object with handoff_ids")
    if len(value) != len(set(value)):
        raise ValueError(f"{label} contains duplicate IDs")
    return list(value)


def stable_union(rows: list[dict[str, str]], *groups: list[str]) -> list[str]:
    valid = {row["handoff_id"] for row in rows}
    selected = set().union(*map(set, groups))
    if not selected <= valid:
        raise ValueError("runtime/high-risk IDs are outside the full-pass snapshot")
    return [row["handoff_id"] for row in rows if row["handoff_id"] in selected]


def ensure_work_root(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    if not path.is_dir():
        raise ValueError("receiver work root is not a directory")


def recheck_commands(
    python: Path, controller: Path, authorization: Path, package_root: Path,
) -> list[dict[str, str]]:
    executable = str(python.resolve())
    if any(character.isspace() for character in executable):
        raise ValueError("PowerShell receiver Python path must not contain whitespace")
    if any(character in executable for character in '"\'`;&|<>(){}'):
        raise ValueError("PowerShell receiver Python path contains unsafe characters")
    prefix = f'{executable} -X utf8 -B "{controller.resolve()}" --authorization "{authorization.resolve()}"'
    return [
        {"name": name, "cwd": str(package_root.resolve()), "command_line": f"{prefix} {name}"}
        for name in ("next", "commit", "status", "finalize")
    ]


def resolve_descriptor(package_root: Path, descriptor: object, label: str) -> Path:
    if not isinstance(descriptor, dict):
        raise ValueError(f"{label} descriptor missing")
    relative = descriptor.get("path")
    expected = descriptor.get("sha256")
    if not isinstance(relative, str) or not isinstance(expected, str):
        raise ValueError(f"{label} descriptor malformed")
    path = (package_root / relative).resolve()
    try:
        path.relative_to(package_root)
    except ValueError as error:
        raise ValueError(f"{label} escapes package root") from error
    if not path.is_file() or sha256(path) != expected:
        raise ValueError(f"{label} file/hash mismatch")
    return path


def verify(
    *, stage: Path, package_root: Path, work_root: Path, full_snapshot: Path,
    full_decisions: Path, full_receipt: Path,
) -> dict[str, Any]:
    stage = stage.resolve()
    package_root = package_root.resolve()
    manifest = read_json(package_root / "project-manifest.json", "manifest")
    package_id = manifest.get("package_id")
    run_id = manifest.get("run_id")
    if manifest.get("receiver_control_baseline") != CONTRACT:
        raise ValueError("recheck helper requires the current v2.5 receiver baseline")
    if manifest.get("phase") != PHASE or not isinstance(package_id, str) or not isinstance(run_id, str):
        raise ValueError("package is not a guarded Phase-2 package")
    paths = {
        "parent": stage / "full-pass-parent.csv",
        "schedule": stage / "recheck-schedule.json",
        "overlay": stage / "recheck-challenge-overlay.json",
        "authorization": stage / "semantic-authorization.json",
        "commands": stage / "allowed-commands.json",
        "receipt": stage / "recheck-materialization-receipt.json",
    }
    if any(not path.is_file() for path in paths.values()):
        raise ValueError("recheck stage is incomplete")
    if paths["parent"].read_bytes() != full_snapshot.read_bytes():
        raise ValueError("recheck parent differs byte-for-byte from full-pass snapshot")

    snapshot_receipt = read_json(full_receipt, "full-pass receipt")
    if (
        snapshot_receipt.get("schema") != FULL_SCHEMA
        or snapshot_receipt.get("package_id") != package_id
        or snapshot_receipt.get("run_id") != run_id
        or snapshot_receipt.get("snapshot_sha256") != sha256(full_snapshot)
    ):
        raise ValueError("full-pass receipt/snapshot binding mismatch")
    rows = read_rows(full_snapshot)
    decisions = read_json(full_decisions, "full-pass decision index").get("decisions")
    ids = [row["handoff_id"] for row in rows]
    if not isinstance(decisions, list) or [item.get("handoff_id") for item in decisions if isinstance(item, dict)] != ids:
        raise ValueError("full-pass decision order differs from snapshot")
    if any(item.get("action") not in {"accepted", "rewritten"} for item in decisions):
        raise ValueError("full-pass decision index contains unresolved/invalid action")

    schedule = read_json(paths["schedule"], "recheck schedule")
    overlay = read_json(paths["overlay"], "recheck overlay")
    if schedule.get("schema") != RECHECK_SCHEMA or schedule.get("package_id") != package_id or schedule.get("run_id") != run_id:
        raise ValueError("recheck schedule identity mismatch")
    parent = schedule.get("parent_full_pass")
    if parent != {"path": str(paths["parent"]), "sha256": sha256(paths["parent"]), "row_count": len(rows)}:
        raise ValueError("recheck parent descriptor mismatch")
    selection = schedule.get("selection")
    if not isinstance(selection, dict):
        raise ValueError("recheck selection missing")
    actions = {item["handoff_id"]: item["action"] for item in decisions}
    rewritten = [handoff_id for handoff_id in ids if actions[handoff_id] == "rewritten"]
    for name, required in (
        ("rewritten_handoff_ids", rewritten),
        ("runtime_handoff_ids", selection.get("runtime_handoff_ids")),
        ("high_risk_handoff_ids", selection.get("high_risk_handoff_ids")),
    ):
        if selection.get(name) != required:
            raise ValueError(f"recheck {name} binding mismatch")
    selected = selection.get("selected_handoff_ids")
    expected_union = set(rewritten) | set(selection.get("runtime_handoff_ids", [])) | set(selection.get("high_risk_handoff_ids", [])) | set(selection.get("accepted_sample_handoff_ids", []))
    if not isinstance(selected, list) or set(selected) != expected_union or len(selected) != len(expected_union):
        raise ValueError("recheck selected union mismatch")
    if selection.get("selected_handoff_ids_sha256") != sha256_bytes(canonical(selected)):
        raise ValueError("recheck selected hash mismatch")

    challenge_tool = resolve_descriptor(package_root, manifest.get("tools", {}).get("challenge_materializer"), "challenge materializer")
    materializer = load_module("guarded_recheck_challenge_verify", challenge_tool)
    row_map, packets = materializer.validate_inputs(
        schedule, rows, package_id, run_id, sha256(package_root / "project-manifest.json"),
        bytes.fromhex(overlay["generation"]["seed_hex"]),
    )
    expected_overlay = materializer.build_overlay(
        schedule, rows, package_id, run_id, sha256(package_root / "project-manifest.json"),
        bytes.fromhex(overlay["generation"]["seed_hex"]),
    )
    if canonical(expected_overlay) != canonical(overlay):
        raise ValueError("recheck challenge overlay differs from deterministic materialization")

    controller_path = resolve_descriptor(package_root, manifest.get("tools", {}).get("controller"), "controller")
    controller = load_module("guarded_recheck_controller_verify", controller_path)
    context = controller.load_context(paths["authorization"])
    if context.get("schedule_schema") != RECHECK_SCHEMA or len(context.get("rows", [])) != len(rows):
        raise ValueError("controller cannot load recheck authorization")
    receipt = read_json(paths["receipt"], "recheck receipt")
    if receipt.get("authorization_sha256") != sha256(paths["authorization"]):
        raise ValueError("recheck authorization receipt mismatch")
    return {
        "status": "verified_recheck_materialization",
        "package_id": package_id,
        "run_id": run_id,
        "selected_rows": len(selected),
        "packets": len(packets),
        "challenge_count": sum(len(items) for items in overlay["packets"].values()),
        "authorization_sha256": sha256(paths["authorization"]),
        "schedule_sha256": sha256(paths["schedule"]),
        "overlay_sha256": sha256(paths["overlay"]),
        "parent_snapshot_sha256": sha256(paths["parent"]),
        "row_count": len(row_map),
    }


def materialize(args: argparse.Namespace) -> dict[str, Any]:
    package_root = args.package_root.resolve()
    work_root = args.work_root.resolve()
    stage = args.stage.resolve()
    full_snapshot = args.full_snapshot.resolve()
    full_decisions = args.full_decisions.resolve()
    full_receipt = (args.full_receipt or full_snapshot.with_suffix(".json")).resolve()
    full_authorization = args.full_authorization.resolve()
    semantic_guard = args.semantic_guard.resolve()
    receiver_python = args.python.resolve()
    required = (package_root / "project-manifest.json", full_snapshot, full_decisions, full_receipt, full_authorization, semantic_guard, receiver_python)
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise ValueError("required recheck input is missing: " + ", ".join(missing))
    ensure_work_root(work_root)
    if stage.exists() and any(stage.iterdir()):
        raise ValueError("recheck stage must be new or empty")

    manifest = read_json(package_root / "project-manifest.json", "manifest")
    package_id = manifest.get("package_id")
    run_id = manifest.get("run_id")
    if manifest.get("receiver_control_baseline") != CONTRACT:
        raise ValueError("recheck helper requires the current v2.5 receiver baseline")
    if manifest.get("phase") != PHASE or not isinstance(package_id, str) or not isinstance(run_id, str):
        raise ValueError("package is not a guarded Phase-2 package")
    full_auth = read_json(full_authorization, "full authorization")
    if full_auth.get("package_id") != package_id or full_auth.get("run_id") != run_id or full_auth.get("phase") != PHASE:
        raise ValueError("full authorization identity mismatch")
    receipt = read_json(full_receipt, "full-pass receipt")
    if receipt.get("schema") != FULL_SCHEMA or receipt.get("snapshot_sha256") != sha256(full_snapshot):
        raise ValueError("full-pass receipt/snapshot mismatch")
    rows = read_rows(full_snapshot)
    decisions = read_json(full_decisions, "full-pass decision index").get("decisions")
    if not isinstance(decisions, list) or [item.get("handoff_id") for item in decisions if isinstance(item, dict)] != [row["handoff_id"] for row in rows]:
        raise ValueError("full-pass decisions do not match snapshot order")

    stage.mkdir(parents=True, exist_ok=not stage.exists())
    parent = stage / "full-pass-parent.csv"
    atomic_write(parent, full_snapshot.read_bytes())
    runtime_ids = stable_union(rows, runtime_flagged_ids(rows), read_optional_ids(args.runtime_ids_json, "runtime IDs"))
    high_risk_ids = stable_union(rows, explicit_high_risk_ids(rows), read_optional_ids(args.high_risk_ids_json, "high-risk IDs"))
    seed = bytes.fromhex(args.seed_hex) if args.seed_hex else secrets.token_bytes(32)
    if len(seed) != 32:
        raise ValueError("recheck seed must be exactly 32 bytes")

    tools = manifest.get("tools", {})
    challenge_path = resolve_descriptor(package_root, tools.get("challenge_materializer"), "challenge materializer")
    authorization_path_tool = resolve_descriptor(package_root, tools.get("semantic_authorization_materializer"), "authorization materializer")
    controller_path = resolve_descriptor(package_root, tools.get("controller"), "controller")
    challenge = load_module("guarded_recheck_challenge", challenge_path)
    authorization_tool = load_module("guarded_recheck_authorization", authorization_path_tool)
    schedule = challenge.build_recheck_schedule(
        rows, decisions, runtime_ids=runtime_ids, high_risk_ids=high_risk_ids,
        package_id=package_id, run_id=run_id, parent_full_pass_path=parent,
        seed=seed, packet_size=args.packet_size,
    )
    schedule_path = stage / "recheck-schedule.json"
    atomic_write(schedule_path, json_bytes(schedule))
    manifest_hash = sha256(package_root / "project-manifest.json")
    overlay = challenge.build_overlay(schedule, rows, package_id, run_id, manifest_hash, seed)
    overlay_path = stage / "recheck-challenge-overlay.json"
    atomic_write(overlay_path, json_bytes(overlay))

    authorization_path = stage / "semantic-authorization.json"
    commands_path = stage / "allowed-commands.json"
    commands = recheck_commands(receiver_python, controller_path, authorization_path, package_root)
    atomic_write(commands_path, json_bytes(commands))
    authorization = authorization_tool.build_authorization(
        package_root=package_root, work_root=work_root,
        manifest_path=package_root / "project-manifest.json", controller_path=controller_path,
        schedule_path=schedule_path, challenge_overlay_path=overlay_path,
        current_prompt_path=work_root / "current/prompt.json",
        current_response_path=work_root / "current/response.json",
        allowed_run_commands=commands,
    )
    auth_receipt = authorization_tool.materialize_authorization(authorization_path, authorization, semantic_guard)
    probe = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", commands[2]["command_line"]],
        cwd=package_root, text=True, capture_output=True, check=False,
    )
    if probe.returncode:
        raise RuntimeError(f"PowerShell receiver probe failed ({probe.returncode}): {(probe.stderr or probe.stdout).strip()}")
    try:
        probe_result = json.loads(probe.stdout)
    except json.JSONDecodeError as error:
        raise RuntimeError("PowerShell receiver probe did not return JSON") from error
    materialization_receipt = {
        "schema": "agy-guarded-phase2-recheck-materialization/v1",
        "package_id": package_id,
        "run_id": run_id,
        "contract": manifest.get("receiver_control_baseline"),
        "full_authorization_sha256": sha256(full_authorization),
        "full_snapshot_sha256": sha256(full_snapshot),
        "full_decision_index_sha256": sha256(full_decisions),
        "recheck_seed_sha256": sha256_bytes(seed),
        "runtime_handoff_ids": runtime_ids,
        "high_risk_handoff_ids": high_risk_ids,
        "identity_rows_are_not_implicitly_high_risk": True,
        "receiver_shell": "powershell",
        "shell_probe": True,
        "probe_result": probe_result,
        **auth_receipt,
    }
    receipt_path = stage / "recheck-materialization-receipt.json"
    atomic_write(receipt_path, json_bytes(materialization_receipt))
    return verify(
        stage=stage, package_root=package_root, work_root=work_root,
        full_snapshot=full_snapshot, full_decisions=full_decisions, full_receipt=full_receipt,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Materialize a generic host-private guarded Phase-2 fresh recheck.")
    parser.add_argument("--package-root", type=Path, required=True)
    parser.add_argument("--work-root", type=Path, required=True)
    parser.add_argument("--stage", type=Path, required=True)
    parser.add_argument("--full-snapshot", type=Path, required=True)
    parser.add_argument("--full-decisions", type=Path, required=True)
    parser.add_argument("--full-receipt", type=Path)
    parser.add_argument("--full-authorization", type=Path, required=True)
    parser.add_argument("--semantic-guard", type=Path, required=True)
    parser.add_argument("--python", type=Path, required=True)
    parser.add_argument("--packet-size", type=int, default=45)
    parser.add_argument("--runtime-ids-json", type=Path)
    parser.add_argument("--high-risk-ids-json", type=Path)
    parser.add_argument("--seed-hex")
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.verify:
            result = verify(
                stage=args.stage.resolve(), package_root=args.package_root.resolve(),
                work_root=args.work_root.resolve(), full_snapshot=args.full_snapshot.resolve(),
                full_decisions=args.full_decisions.resolve(),
                full_receipt=(args.full_receipt or args.full_snapshot.with_suffix(".json")).resolve(),
            )
        else:
            result = materialize(args)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0
    except (OSError, UnicodeError, ValueError, RuntimeError, KeyError, json.JSONDecodeError) as error:
        print(f"FAIL: {type(error).__name__}: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
