from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import sys
from pathlib import Path
from typing import Any

AUTH_SCHEMA = "agy-semantic-origin-authorization/v3"
CONTRACT = "AGY-VIETHOA-HANDOFF/2.5-TWO-PHASE-DRAFT12-PREVIEW-FINAL0-GUARDED"
PHASE1 = "phase1_parallel_draft"
PHASE2 = "phase2_main_only_final"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def bound_file(path: Path, label: str, *, within: Path | None = None, outside: tuple[Path, ...] = ()) -> Path:
    path = path.resolve()
    if not path.is_file():
        raise ValueError(f"{label} file missing")
    if within is not None and not is_within(path, within):
        raise ValueError(f"{label} outside required root")
    if any(is_within(path, root) for root in outside):
        raise ValueError(f"{label} must remain host-private outside package/work roots")
    return path


def read_object(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as error:
        raise ValueError(f"{label} JSON invalid") from error
    if not isinstance(value, dict):
        raise ValueError(f"{label} JSON object required")
    return value


def build_authorization(
    *, package_root: Path, work_root: Path, manifest_path: Path,
    controller_path: Path, schedule_path: Path,
    challenge_overlay_path: Path | None, current_prompt_path: Path,
    current_response_path: Path, allowed_run_commands: list[dict[str, str]],
) -> dict[str, Any]:
    package_root = package_root.resolve()
    work_root = work_root.resolve()
    if not package_root.is_dir() or not work_root.is_dir():
        raise ValueError("package/work root missing")
    manifest_path = bound_file(manifest_path, "manifest", within=package_root)
    controller_path = bound_file(controller_path, "controller", within=package_root)
    schedule_path = bound_file(schedule_path, "schedule")
    current_prompt_path = current_prompt_path.resolve()
    current_response_path = current_response_path.resolve()
    if not is_within(current_prompt_path, work_root) or not is_within(current_response_path, work_root):
        raise ValueError("current prompt/response outside work root")
    schedule = read_object(schedule_path, "schedule")
    phase = schedule.get("phase")
    package_id = schedule.get("package_id")
    run_id = schedule.get("run_id")
    if phase not in {PHASE1, PHASE2} or not isinstance(package_id, str) or not isinstance(run_id, str):
        raise ValueError("schedule phase/package/run invalid")
    schedule_schema = schedule.get("schema")
    if phase == PHASE1 or schedule_schema == "agy-phase2-schedule/v2":
        if not is_within(schedule_path, package_root):
            raise ValueError("full-review/Phase-1 schedule must remain package-pinned")
    elif schedule_schema == "agy-phase2-recheck-schedule/v1":
        if is_within(schedule_path, package_root) or is_within(schedule_path, work_root):
            raise ValueError("fresh-recheck schedule must remain host-private outside package/work roots")
    else:
        raise ValueError("schedule schema invalid")
    manifest_sha256 = digest(manifest_path)
    manifest = read_object(manifest_path, "manifest")
    if manifest.get("package_id") != package_id or manifest.get("run_id") != run_id:
        raise ValueError("schedule/manifest identity mismatch")
    if phase == PHASE2:
        if challenge_overlay_path is None:
            raise ValueError("Phase-2 challenge overlay missing")
        overlay_path = bound_file(
            challenge_overlay_path, "challenge overlay", outside=(package_root, work_root),
        )
        overlay = read_object(overlay_path, "challenge overlay")
        if (
            overlay.get("schema") != "agy-phase2-challenge-overlay/v1"
            or overlay.get("package_id") != package_id
            or overlay.get("run_id") != run_id
            or overlay.get("manifest_sha256") != manifest_sha256
        ):
            raise ValueError("challenge overlay identity mismatch")
        packets = overlay.get("packets")
        schedule_packets = schedule.get("packets")
        if not isinstance(packets, dict) or not packets:
            raise ValueError("challenge overlay packets missing")
        if not isinstance(schedule_packets, list) or not schedule_packets:
            raise ValueError("Phase-2 schedule packets missing")
        slots_by_packet: dict[str, int] = {}
        for packet in schedule_packets:
            if not isinstance(packet, dict):
                raise ValueError("Phase-2 schedule packet invalid")
            packet_id = packet.get("packet_id")
            slots = packet.get("challenge_slots")
            if not isinstance(packet_id, str) or packet_id in slots_by_packet or not isinstance(slots, int) or isinstance(slots, bool) or slots < 1:
                raise ValueError("Phase-2 challenge slot declaration invalid")
            slots_by_packet[packet_id] = slots
        if set(packets) != set(slots_by_packet):
            raise ValueError("challenge slot packet coverage mismatch")
        challenge_map: dict[str, dict[str, str]] = {}
        for packet_id, entries in packets.items():
            if not isinstance(packet_id, str) or not isinstance(entries, list) or len(entries) != slots_by_packet[packet_id]:
                raise ValueError("challenge slot count mismatch")
            expected: dict[str, str] = {}
            for item in entries:
                if not isinstance(item, dict):
                    raise ValueError("challenge overlay row invalid")
                handoff_id = item.get("handoff_id")
                target_hash = item.get("expected_target_sha256")
                prompt_row = item.get("prompt_row")
                if not isinstance(handoff_id, str) or not isinstance(target_hash, str) or handoff_id in expected:
                    raise ValueError("challenge overlay expectation invalid")
                if not isinstance(prompt_row, dict) or prompt_row.get("handoff_id") != handoff_id:
                    raise ValueError("challenge prompt row identity invalid")
                source = prompt_row.get("source")
                current = prompt_row.get("current_translation_vi")
                if (
                    item.get("expected_target_derivation") != "prompt_source_keep_identity"
                    or prompt_row.get("translation_policy") != "keep_identity"
                    or not isinstance(source, str)
                    or not isinstance(current, str)
                    or current == source
                    or target_hash != hashlib.sha256(source.encode("utf-8")).hexdigest()
                ):
                    raise ValueError("challenge target is not prompt-derivable")
                if not source.strip():
                    raise ValueError("challenge source is whitespace-only")
                expected[handoff_id] = target_hash
            challenge_map[packet_id] = expected
        challenge_descriptor: dict[str, str] | None = {
            "path": str(overlay_path), "sha256": digest(overlay_path),
        }
        response_schema = "agy-explicit-review/v2"
    else:
        if challenge_overlay_path is not None:
            raise ValueError("Phase-1 cannot bind a challenge overlay")
        challenge_map = {}
        challenge_descriptor = None
        response_schema = "agy-phase1-draft/v2"
    authorization = {
        "schema": AUTH_SCHEMA,
        "contract": CONTRACT,
        "phase": phase,
        "package_id": package_id,
        "run_id": run_id,
        "manifest_sha256": manifest_sha256,
        "package_root": str(package_root),
        "work_root": str(work_root),
        "controller": {"path": str(controller_path), "sha256": digest(controller_path)},
        "schedule": {"path": str(schedule_path), "sha256": digest(schedule_path)},
        "challenge_overlay": challenge_descriptor,
        "current_prompt_path": str(current_prompt_path),
        "current_response_path": str(current_response_path),
        "response_schema": response_schema,
        "allowed_run_commands": [dict(item) for item in allowed_run_commands],
        "challenge_ids_by_batch": challenge_map,
    }
    return authorization


def load_guard(path: Path):
    path = bound_file(path, "semantic guard")
    spec = importlib.util.spec_from_file_location("semantic_authorization_guard_validator", path)
    if spec is None or spec.loader is None:
        raise ValueError("semantic guard import unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if getattr(module, "AUTH_SCHEMA", None) != AUTH_SCHEMA or getattr(module, "CONTRACT", None) != CONTRACT:
        raise ValueError("semantic guard schema/contract mismatch")
    return module


def materialize_authorization(output: Path, authorization: dict[str, Any], guard_path: Path) -> dict[str, Any]:
    package_root = Path(authorization["package_root"]).resolve()
    work_root = Path(authorization["work_root"]).resolve()
    output = output.resolve()
    if is_within(output, package_root) or is_within(output, work_root):
        raise ValueError("authorization must remain host-private outside package/work roots")
    guard = load_guard(guard_path)
    if guard.validate_authorization(authorization) != authorization:
        raise RuntimeError("semantic guard authorization normalization changed bytes")
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(authorization, ensure_ascii=False, indent=2).encode("utf-8") + b"\n"
    temporary = output.with_name(f".{output.name}.{os.getpid()}.tmp")
    try:
        with temporary.open("wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, output)
    finally:
        if temporary.exists():
            temporary.unlink()
    readback = output.read_bytes()
    parsed = json.loads(readback.decode("utf-8"))
    if readback != payload or parsed != authorization or guard.validate_authorization(parsed) != parsed:
        raise RuntimeError("semantic authorization atomic readback/guard validation mismatch")
    challenge_count = sum(len(items) for items in authorization["challenge_ids_by_batch"].values())
    return {
        "schema": "agy-semantic-origin-authorization-materialization-receipt/v1",
        "authorization_path": str(output),
        "authorization_sha256": hashlib.sha256(readback).hexdigest(),
        "package_id": authorization["package_id"],
        "run_id": authorization["run_id"],
        "phase": authorization["phase"],
        "challenge_count": challenge_count,
        "prompt_derivable_challenge_count": challenge_count,
        "guard_sha256": digest(guard_path),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Materialize host-only semantic authorization v3.")
    parser.add_argument("--package-root", type=Path, required=True)
    parser.add_argument("--work-root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--controller", type=Path, required=True)
    parser.add_argument("--schedule", type=Path, required=True)
    parser.add_argument("--challenge-overlay", type=Path)
    parser.add_argument("--current-prompt", type=Path, required=True)
    parser.add_argument("--current-response", type=Path, required=True)
    parser.add_argument("--commands-json", type=Path, required=True)
    parser.add_argument("--guard", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    commands = json.loads(args.commands_json.read_text(encoding="utf-8-sig"))
    if not isinstance(commands, list):
        raise ValueError("allowed commands JSON list required")
    authorization = build_authorization(
        package_root=args.package_root, work_root=args.work_root,
        manifest_path=args.manifest, controller_path=args.controller,
        schedule_path=args.schedule, challenge_overlay_path=args.challenge_overlay,
        current_prompt_path=args.current_prompt, current_response_path=args.current_response,
        allowed_run_commands=commands,
    )
    print(json.dumps(materialize_authorization(args.output, authorization, args.guard), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, RuntimeError, KeyError, json.JSONDecodeError) as error:
        print(f"FAIL: {type(error).__name__}: {error}", file=sys.stderr)
        raise SystemExit(1)
