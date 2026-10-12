from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import sys
from pathlib import Path
from typing import Any

CONTRACT = "AGY-VIETHOA-HANDOFF/2.5-TWO-PHASE-DRAFT12-PREVIEW-FINAL0-GUARDED"
AUDIT_SCHEMA = "agy-phase2-provenance-audit/v1"
FULL_SCHEDULE_SCHEMA = "agy-phase2-schedule/v2"
RECHECK_SCHEDULE_SCHEMA = "agy-phase2-recheck-schedule/v1"


def canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def collapse_idempotent_response_pairs(
    events: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], int]:
    """Collapse only byte-identical authorize/readback retries before one commit."""
    collapsed: list[dict[str, Any]] = []
    seen: set[tuple[object, ...]] = set()
    duplicate_count = 0
    index = 0
    while index < len(events):
        event = events[index]
        if event.get("action") == "authorize_direct_response" and index + 1 < len(events):
            readback = events[index + 1]
            if (
                readback.get("action") == "direct_response_readback"
                and readback.get("batch_id") == event.get("batch_id")
                and readback.get("payload_sha256") == event.get("payload_sha256")
            ):
                key = (
                    event.get("authorization_sha256"), event.get("conversation_id"),
                    event.get("batch_id"), event.get("prompt_sha256"),
                    event.get("payload_sha256"), event.get("native_lf_sha256"),
                    readback.get("disk_sha256"), readback.get("normalization"),
                )
                if key in seen:
                    duplicate_count += 1
                    index += 2
                    continue
                seen.add(key)
        collapsed.append(event)
        if event.get("action") == "allow_controller_command" and event.get("command_name") == "commit":
            seen.clear()
        index += 1
    return collapsed, duplicate_count


def correlate_epoch(
    events: list[dict[str, Any]], commits: list[dict[str, Any]], authorization_sha256: str,
    expected_conversation_id: str | None = None,
) -> dict[str, Any]:
    events, idempotent_duplicate_response_count = collapse_idempotent_response_pairs(events)
    if not events or events[0].get("action") != "arm":
        raise ValueError("semantic epoch must begin with one arm event")
    if sum(event.get("action") == "arm" for event in events) != 1:
        raise ValueError("semantic epoch arm count invalid")
    allowed_actions = {
        "arm", "reset", "allow_controller_command", "allow_prompt_read",
        "authorize_direct_response", "direct_response_readback",
    }
    unknown_actions = {event.get("action") for event in events} - allowed_actions
    if unknown_actions:
        raise ValueError(f"unsupported semantic event action: {sorted(unknown_actions)!r}")
    if any(event.get("authorization_sha256") != authorization_sha256 for event in events):
        raise ValueError("semantic epoch authorization hash mismatch")
    semantic_events = [
        event for event in events
        if event.get("action") not in {"arm", "reset"}
    ]
    conversation_ids = {event.get("conversation_id") for event in semantic_events}
    if None in conversation_ids or len(conversation_ids) != 1:
        raise ValueError("semantic epoch conversation binding invalid")
    conversation_id = next(iter(conversation_ids))
    if expected_conversation_id is not None and conversation_id != expected_conversation_id:
        raise ValueError("semantic epoch conversation changed across guard epochs")

    authorized = [event for event in events if event.get("action") == "authorize_direct_response"]
    readbacks = [event for event in events if event.get("action") == "direct_response_readback"]
    commit_commands = [
        event for event in events
        if event.get("action") == "allow_controller_command" and event.get("command_name") == "commit"
    ]
    finalize_commands = [
        event for event in events
        if event.get("action") == "allow_controller_command" and event.get("command_name") == "finalize"
    ]
    if len(authorized) != len(commits):
        raise ValueError("semantic response authorization count differs from commit count")
    if len(readbacks) != len(commits):
        raise ValueError("semantic response readback count differs from commit count")
    if len(commit_commands) != len(commits):
        raise ValueError("extra or missing controller commit count")
    if len(finalize_commands) != 1:
        raise ValueError("controller finalize count invalid")

    cursor = 0
    used_authorized: set[int] = set()
    used_readbacks: set[int] = set()
    used_commits: set[int] = set()

    def locate(predicate, start: int, label: str) -> int:
        for index in range(start, len(events)):
            if predicate(events[index]):
                return index
        raise ValueError(f"semantic epoch missing {label}")

    for commit in commits:
        batch_id = commit.get("batch_id")
        prompt_sha256 = commit.get("prompt_sha256")
        response_sha256 = commit.get("response_sha256")
        next_index = locate(
            lambda event: event.get("action") == "allow_controller_command" and event.get("command_name") == "next",
            cursor, f"next command for {batch_id}",
        )
        prompt_index = locate(
            lambda event: event.get("action") == "allow_prompt_read" and event.get("prompt_sha256") == prompt_sha256,
            next_index + 1, f"prompt read for {batch_id}",
        )
        authorize_index = locate(
            lambda event: (
                event.get("action") == "authorize_direct_response"
                and event.get("batch_id") == batch_id
                and event.get("prompt_sha256") == prompt_sha256
            ),
            prompt_index + 1, f"native response authorization for {batch_id}",
        )
        authorized_event = events[authorize_index]
        payload_sha256 = authorized_event.get("payload_sha256")
        readback_index = locate(
            lambda event: (
                event.get("action") == "direct_response_readback"
                and event.get("batch_id") == batch_id
                and event.get("payload_sha256") == payload_sha256
                and event.get("disk_sha256") == response_sha256
            ),
            authorize_index + 1, f"native response readback for {batch_id}",
        )
        normalization = events[readback_index].get("normalization")
        if normalization == "exact":
            if payload_sha256 != response_sha256:
                raise ValueError(f"exact semantic readback hash mismatch: {batch_id}")
        elif normalization == "append_lf":
            if authorized_event.get("native_lf_sha256") != response_sha256:
                raise ValueError(f"native LF semantic readback hash mismatch: {batch_id}")
        else:
            raise ValueError(f"semantic readback normalization invalid: {batch_id}")
        commit_index = locate(
            lambda event: event.get("action") == "allow_controller_command" and event.get("command_name") == "commit",
            readback_index + 1, f"controller commit for {batch_id}",
        )
        used_authorized.add(authorize_index)
        used_readbacks.add(readback_index)
        used_commits.add(commit_index)
        cursor = commit_index + 1

    if len(used_authorized) != len(authorized) or len(used_readbacks) != len(readbacks) or len(used_commits) != len(commit_commands):
        raise ValueError("extra unbound semantic response or commit event")
    if not any(
        index >= cursor and event.get("action") == "allow_controller_command" and event.get("command_name") == "finalize"
        for index, event in enumerate(events)
    ):
        raise ValueError("controller finalize did not follow all packet commits")
    return {
        "authorization_sha256": authorization_sha256,
        "conversation_id": conversation_id,
        "committed_packets": len(commits),
        "native_response_count": len(authorized),
        "idempotent_duplicate_response_count": idempotent_duplicate_response_count,
    }


def select_semantic_epochs(
    events: list[dict[str, Any]], full_authorization_path: Path,
    recheck_authorization_path: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Select full/final epochs while proving intermediate retries were prestart-only."""
    full_path = str(full_authorization_path.resolve())
    recheck_path = str(recheck_authorization_path.resolve())
    arm_indices = [index for index, event in enumerate(events) if event.get("action") == "arm"]
    full_indices = [index for index in arm_indices if events[index].get("authorization_path") == full_path]
    recheck_indices = [index for index in arm_indices if events[index].get("authorization_path") == recheck_path]
    if len(full_indices) != 1 or len(recheck_indices) != 1 or full_indices[0] >= recheck_indices[0]:
        raise ValueError("semantic full/final recheck arm selection invalid")
    full_index = full_indices[0]
    recheck_index = recheck_indices[0]
    scoped_arms = [index for index in arm_indices if full_index <= index <= recheck_index]
    if scoped_arms[0] != full_index or scoped_arms[-1] != recheck_index:
        raise ValueError("semantic arm scope invalid")

    rejected: list[dict[str, Any]] = []
    epochs: list[list[dict[str, Any]]] = []
    for offset, start in enumerate(scoped_arms[:-1]):
        stop = scoped_arms[offset + 1]
        epoch = events[start:stop]
        if not epoch or epoch[-1].get("action") != "reset" or sum(item.get("action") == "reset" for item in epoch) != 1:
            raise ValueError("semantic superseded epoch must end in one reset")
        epochs.append(epoch)
        if start == full_index:
            continue
        if any(item.get("action") in {"authorize_direct_response", "direct_response_readback"} for item in epoch):
            raise ValueError("semantic prestart retry contains semantic write")
        commands = [
            item.get("command_name") for item in epoch
            if item.get("action") == "allow_controller_command"
        ]
        if any(command != "status" for command in commands):
            raise ValueError("semantic prestart retry contains non-status controller command")
        allowed = {"arm", "reset", "allow_prompt_read", "allow_controller_command"}
        unknown = {item.get("action") for item in epoch} - allowed
        if unknown:
            raise ValueError(f"semantic prestart retry event invalid: {sorted(unknown)!r}")
        rejected.append({
            "authorization_path": epoch[0].get("authorization_path"),
            "authorization_sha256": epoch[0].get("authorization_sha256"),
            "event_count": len(epoch),
            "controller_commands": commands,
            "semantic_response_count": 0,
        })

    recheck_epoch = events[recheck_index:]
    if any(item.get("action") in {"arm", "reset"} for item in recheck_epoch[1:]):
        raise ValueError("semantic final recheck epoch was superseded or reset")
    return epochs[0], recheck_epoch, rejected


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ValueError(f"cannot load pinned audit dependency: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read_json(path: Path, label: str, *, canonical_required: bool = True) -> tuple[dict[str, Any], bytes]:
    raw = path.read_bytes()
    value = json.loads(raw.decode("utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object")
    if canonical_required and canonical(value) != raw:
        raise ValueError(f"{label} bytes are not canonical")
    return value, raw


def atomic_json(path: Path, value: dict[str, Any]) -> None:
    payload = canonical(value)
    path = path.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        with temporary.open("wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()
    if path.read_bytes() != payload:
        raise RuntimeError("provenance audit atomic readback mismatch")


def audit_stage(controller: Any, authorization_path: Path) -> dict[str, Any]:
    context = controller.load_context(authorization_path)
    paths = controller.controller_paths(context)
    state = controller.load_state(context, paths)
    commits = controller.verify_commits(context, paths, state)
    if not state["finalized"] or state["active_packet_id"] is not None:
        raise ValueError("controller stage is not finalized")
    is_recheck = context["schedule_schema"] == RECHECK_SCHEDULE_SCHEMA
    snapshot_name = "fresh-recheck-final-snapshot" if is_recheck else "full-pass-snapshot"
    snapshot_path = paths["snapshots"] / f"{snapshot_name}.csv"
    receipt_path = paths["snapshots"] / f"{snapshot_name}.json"
    receipt, receipt_raw = read_json(receipt_path, "snapshot receipt")
    if digest(receipt_raw) != state["snapshot_receipt_sha256"]:
        raise ValueError("snapshot receipt/state hash mismatch")
    snapshot_raw = snapshot_path.read_bytes()
    if digest(snapshot_raw) != state["snapshot_sha256"] or receipt.get("snapshot_sha256") != digest(snapshot_raw):
        raise ValueError("snapshot bytes/hash mismatch")
    if Path(receipt.get("snapshot_csv", "")).resolve() != snapshot_path.resolve():
        raise ValueError("snapshot receipt path mismatch")
    output_rows = context["materializer"].read_rows(snapshot_path)
    input_ids = [row["handoff_id"] for row in context["rows"]]
    if [row.get("handoff_id") for row in output_rows] != input_ids:
        raise ValueError("snapshot full-row order/coverage mismatch")

    required_ids = context["schedule"]["selection"]["selected_handoff_ids"] if is_recheck else input_ids
    real_decisions: dict[str, dict[str, Any]] = {}
    expected_challenge_count = 0
    challenge_ids: set[str] = set()
    for commit in commits:
        for decision in commit["real_decisions"]:
            handoff_id = decision["handoff_id"]
            if handoff_id in real_decisions:
                raise ValueError(f"duplicate real decision in commit chain: {handoff_id}")
            real_decisions[handoff_id] = decision
        expected_targets = context["authorization"]["challenge_ids_by_batch"].get(commit["batch_id"], {})
        receipts = {item["handoff_id"]: item for item in commit["challenge_receipts"]}
        if set(receipts) != set(expected_targets):
            raise ValueError(f"challenge receipt coverage mismatch: {commit['batch_id']}")
        for handoff_id, expected_target in expected_targets.items():
            item = receipts[handoff_id]
            if item["expected_target_sha256"] != expected_target or item["response_target_sha256"] != expected_target:
                raise ValueError(f"challenge correction proof mismatch: {handoff_id}")
        challenge_ids.update(expected_targets)
        expected_challenge_count += len(expected_targets)
    if set(real_decisions) != set(required_ids) or len(real_decisions) != len(required_ids):
        raise ValueError("stage real-decision coverage mismatch")
    if challenge_ids & set(input_ids):
        raise ValueError("challenge identity leaked into release corpus")

    decision_index_path = Path(receipt.get("decision_index", "")).resolve()
    if not decision_index_path.is_file() or digest(decision_index_path.read_bytes()) != receipt.get("decision_index_sha256"):
        raise ValueError("decision index hash/path mismatch")
    decision_index, _index_raw = read_json(decision_index_path, "decision index")
    expected_index_decisions = [real_decisions[handoff_id] for handoff_id in required_ids]
    if decision_index.get("decisions") != expected_index_decisions:
        raise ValueError("decision index differs from packet commit chain")
    if challenge_ids & {item["handoff_id"] for item in decision_index["decisions"]}:
        raise ValueError("challenge identity leaked into decision index")

    expected_rows: list[dict[str, Any]] = []
    for row in context["rows"]:
        expected = dict(row)
        decision = real_decisions.get(row["handoff_id"])
        if decision is not None and decision["action"] == "rewritten":
            expected["current_translation_vi"] = decision["translation_vi"]
        expected_rows.append(expected)
    if output_rows != expected_rows:
        raise ValueError("snapshot targets differ from exact real decisions")
    action_counts = {"accepted": 0, "rewritten": 0, "needs_context": 0}
    for decision in real_decisions.values():
        action_counts[decision["action"]] += 1
    if receipt.get("action_counts") != action_counts or receipt.get("unresolved_count") != 0:
        raise ValueError("snapshot action counts/unresolved proof mismatch")
    if receipt.get("commit_count") != len(commits) or receipt.get("commit_head_sha256") != state["commit_head_sha256"]:
        raise ValueError("snapshot commit-chain binding mismatch")
    return {
        "authorization_path": str(authorization_path.resolve()),
        "authorization_sha256": context["authorization_sha256"],
        "schedule_schema": context["schedule_schema"],
        "schedule_sha256": context["schedule_sha256"],
        "overlay_sha256": context["overlay_sha256"],
        "snapshot_path": str(snapshot_path.resolve()),
        "snapshot_sha256": digest(snapshot_raw),
        "snapshot_receipt_sha256": digest(receipt_raw),
        "decision_index_sha256": receipt["decision_index_sha256"],
        "row_count": len(output_rows),
        "selected_row_count": len(required_ids),
        "challenge_count": expected_challenge_count,
        "commit_count": len(commits),
        "commit_head_sha256": state["commit_head_sha256"],
        "commits": commits,
        "output_rows": output_rows,
        "context": context,
    }


def audit_run(
    *, package_root: Path, full_authorization_path: Path, recheck_authorization_path: Path,
    events_path: Path, guard_state_path: Path, output_path: Path | None = None,
) -> dict[str, Any]:
    package_root = package_root.resolve()
    full_authorization_path = full_authorization_path.resolve()
    recheck_authorization_path = recheck_authorization_path.resolve()
    events_path = events_path.resolve()
    guard_state_path = guard_state_path.resolve()
    validator = load_module(package_root / "tools/validate_two_phase_handoff_package.py", "agy_audit_package_validator")
    package_report = validator.validate_package(package_root)
    guard = load_module(package_root / "tools/semantic_response_guard.py", "agy_audit_guard")
    controller = load_module(package_root / "tools/controller.py", "agy_audit_controller")
    full = audit_stage(controller, full_authorization_path)
    recheck = audit_stage(controller, recheck_authorization_path)
    if full["schedule_schema"] != FULL_SCHEDULE_SCHEMA or recheck["schedule_schema"] != RECHECK_SCHEDULE_SCHEMA:
        raise ValueError("full/recheck stage schedule order invalid")
    full_context = full.pop("context")
    recheck_context = recheck.pop("context")
    full_rows = full.pop("output_rows")
    recheck_rows = recheck.pop("output_rows")
    for key in ("package_id", "run_id", "manifest_sha256"):
        if full_context["authorization"][key] != recheck_context["authorization"][key]:
            raise ValueError(f"full/recheck authorization identity mismatch: {key}")
    parent = recheck_context["schedule"].get("parent_full_pass")
    if not isinstance(parent, dict) or parent.get("sha256") != full["snapshot_sha256"]:
        raise ValueError("fresh recheck parent does not bind full-pass snapshot")
    parent_path = Path(parent["path"]).resolve()
    if digest(parent_path.read_bytes()) != full["snapshot_sha256"] or recheck_context["materializer"].read_rows(parent_path) != full_rows:
        raise ValueError("promoted full-pass parent bytes differ from audited snapshot")
    if [row["handoff_id"] for row in recheck_rows] != [row["handoff_id"] for row in full_rows]:
        raise ValueError("fresh recheck final corpus order differs from full-pass parent")

    events = guard.verify_events(events_path)
    full_epoch, recheck_epoch, prestart_rejected_epochs = select_semantic_epochs(
        events, full_authorization_path, recheck_authorization_path,
    )
    for retry in prestart_rejected_epochs:
        retry_path = Path(retry["authorization_path"]).resolve()
        retry_context = controller.load_context(retry_path)
        retry_paths = controller.controller_paths(retry_context)
        if retry_context["schedule_schema"] != RECHECK_SCHEDULE_SCHEMA:
            raise ValueError("semantic prestart retry is not a fresh-recheck authorization")
        if retry_paths["state"].exists() or any(retry_paths["commits"].glob("*.json")):
            raise ValueError("semantic prestart retry created controller state or commits")
    full_epoch_report = correlate_epoch(full_epoch, full["commits"], full["authorization_sha256"])
    recheck_epoch_report = correlate_epoch(
        recheck_epoch, recheck["commits"], recheck["authorization_sha256"],
        expected_conversation_id=full_epoch_report["conversation_id"],
    )
    guard_state = guard.load_state(guard_state_path)
    guard.verify_event_head(events_path, guard_state)
    if guard_state.get("authorization_sha256") != recheck["authorization_sha256"] or guard_state.get("main_conversation_id") != recheck_epoch_report["conversation_id"]:
        raise ValueError("effective guard state does not match audited recheck epoch")

    full.pop("commits")
    recheck.pop("commits")
    report = {
        "schema": AUDIT_SCHEMA,
        "contract": CONTRACT,
        "status": "guarded_phase2_provenance_clean",
        "package_id": full_context["authorization"]["package_id"],
        "run_id": full_context["authorization"]["run_id"],
        "manifest_sha256": full_context["authorization"]["manifest_sha256"],
        "package_validation_status": package_report["status"],
        "event_count": len(events),
        "event_head_sha256": events[-1]["entry_sha256"],
        "conversation_id": full_epoch_report["conversation_id"],
        "prestart_rejected_epochs": prestart_rejected_epochs,
        "full_review": full,
        "fresh_recheck": recheck,
        "final_snapshot_sha256": recheck["snapshot_sha256"],
        "final_row_count": recheck["row_count"],
    }
    if output_path is not None:
        atomic_json(output_path, report)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit guarded Phase-2 semantic provenance.")
    parser.add_argument("--package-root", type=Path, required=True)
    parser.add_argument("--full-authorization", type=Path, required=True)
    parser.add_argument("--recheck-authorization", type=Path, required=True)
    parser.add_argument("--events", type=Path, required=True)
    parser.add_argument("--guard-state", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    report = audit_run(
        package_root=args.package_root,
        full_authorization_path=args.full_authorization,
        recheck_authorization_path=args.recheck_authorization,
        events_path=args.events,
        guard_state_path=args.guard_state,
        output_path=args.output,
    )
    print(json.dumps({
        "status": report["status"],
        "final_snapshot_sha256": report["final_snapshot_sha256"],
        "final_row_count": report["final_row_count"],
    }, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, UnicodeError, ValueError, RuntimeError, json.JSONDecodeError) as error:
        print(f"FAIL: {type(error).__name__}: {error}", file=sys.stderr)
        raise SystemExit(1)
