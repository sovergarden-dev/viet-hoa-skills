from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any

ACTIONS = ("verify", "init", "wave", "select", "commit", "status", "finalize")


def read_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"{label} unreadable: {path}") from error
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    return value


def atomic_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = text.encode("utf-8")
    temporary = path.with_name(path.name + ".tmp-recovery-diagnostic")
    with temporary.open("wb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)
    if path.read_bytes() != raw:
        raise RuntimeError(f"atomic readback mismatch: {path}")


def exact_reservation(
    path: Path, package_id: str, run_id: str, lease_ids: list[str],
) -> list[int]:
    if not path.is_file():
        return []
    sequences: list[int] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if (
            event.get("action") == "reserve"
            and event.get("package_id") == package_id
            and event.get("run_id") == run_id
            and event.get("lease_ids") == lease_ids
        ):
            sequence = event.get("sequence")
            if isinstance(sequence, int):
                sequences.append(sequence)
    return sequences


def diagnose(
    package_root: Path,
    work_root: Path,
    commands_path: Path,
    subagent_events_path: Path,
) -> dict[str, Any]:
    package_root = Path(package_root).resolve()
    work_root = Path(work_root).resolve()
    manifest = read_json(package_root / "project-manifest.json", "manifest")
    state = read_json(work_root / "controller/state.json", "controller state")
    prompt_path = work_root / "current/prompt.json"
    prompt = read_json(prompt_path, "current prompt")
    commands_value = json.loads(Path(commands_path).read_text(encoding="utf-8-sig"))
    if not isinstance(commands_value, list):
        raise ValueError("allowed commands must be an array")
    commands = {
        item.get("name"): item
        for item in commands_value
        if isinstance(item, dict) and set(item) == {"name", "command_line", "cwd"}
    }
    if set(commands) != set(ACTIONS):
        raise ValueError("allowed command set mismatch")
    package_id = manifest.get("package_id")
    run_id = manifest.get("run_id")
    if not isinstance(package_id, str) or not isinstance(run_id, str):
        raise ValueError("manifest package/run missing")
    statuses = state.get("lease_status")
    if not isinstance(statuses, dict):
        raise ValueError("controller lease status missing")
    counts = {
        name: sum(value == name for value in statuses.values())
        for name in ("pending", "staged", "committed")
    }
    schema = prompt.get("schema")
    lease_ids: list[str] = []
    reservation_sequences: list[int] = []
    if state.get("finalized") is True:
        classification = "complete"
        action = "No recovery required. Return the finalized artifact for deterministic acceptance."
    elif schema == "agy-semantic-wave/v1":
        raw_ids = prompt.get("lease_ids")
        if not isinstance(raw_ids, list) or not raw_ids or not all(isinstance(item, str) for item in raw_ids):
            raise ValueError("wave lease IDs invalid")
        lease_ids = raw_ids
        reservation_sequences = exact_reservation(
            Path(subagent_events_path), package_id, run_id, lease_ids,
        )
        if reservation_sequences:
            classification = "recoverable_run_select"
            action = "Run exact SELECT before any response write; then write and commit each selected lease separately."
        else:
            classification = "recoverable_invoke_full_wave"
            action = "Read only the current wave wrapper and issue one invoke_subagent call containing every staged lease before SELECT."
    elif schema == "agy-semantic-prompt/v1":
        batch_id = prompt.get("batch_id")
        if not isinstance(batch_id, str):
            raise ValueError("single prompt batch ID invalid")
        lease_ids = [batch_id]
        classification = "recoverable_submit_selected_raw"
        action = "Submit one byte-exact valid native child result for the selected lease, then run exact COMMIT."
    else:
        raise ValueError(f"unsupported current prompt schema: {schema}")
    tool_args = {
        name: json.dumps(
            {"CommandLine": commands[name]["command_line"], "Cwd": commands[name]["cwd"]},
            ensure_ascii=False, separators=(",", ":"),
        )
        for name in ("select", "commit", "status", "wave")
    }
    continuation = (
        "CONTINUE THE SAME GUARDED CONVERSATION. DO NOT MODIFY OR CLEAR THE HOOK.\n\n"
        f"Classification: {classification}\n"
        f"Package/run: {package_id} / {run_id}\n"
        f"Committed/staged/pending: {counts['committed']}/{counts['staged']}/{counts['pending']}\n"
        f"Current schema: {schema}\n"
        f"Lease IDs: {', '.join(lease_ids) if lease_ids else 'none'}\n"
        f"Recovery: {action}\n\n"
        "Call `run_command` with the exact JSON args below. Copy both fields byte-for-byte; "
        "never use the project CWD or wrap either value in extra quotes.\n"
        f"SELECT_ARGS: {tool_args['select']}\n"
        f"COMMIT_ARGS: {tool_args['commit']}\n"
        f"STATUS_ARGS: {tool_args['status']}\n"
        f"WAVE_ARGS: {tool_args['wave']}\n\n"
        "Do not dump worker payloads in a blocker report. Do not cite a legacy contract. "
        "Recover sequencing states autonomously; stop only for integrity, binding, quota, or missing-valid-worker evidence.\n"
    )
    return {
        "schema": "agy-phase1-recovery-diagnostic/v1",
        "classification": classification,
        "package_id": package_id,
        "run_id": run_id,
        "counts": counts,
        "current_prompt_schema": schema,
        "current_prompt_sha256": hashlib.sha256(prompt_path.read_bytes()).hexdigest(),
        "lease_ids": lease_ids,
        "exact_reservation_sequences": reservation_sequences,
        "continuation": continuation,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Diagnose guarded Phase-1 recovery without reading translation payloads into chat.")
    parser.add_argument("--package-root", required=True, type=Path)
    parser.add_argument("--work-root", required=True, type=Path)
    parser.add_argument("--commands", required=True, type=Path)
    parser.add_argument("--subagent-events", type=Path, default=Path.home() / ".gemini/config/hooks/subagent_cap_events.jsonl")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--continuation", type=Path)
    args = parser.parse_args(argv)
    try:
        result = diagnose(args.package_root, args.work_root, args.commands, args.subagent_events)
        if args.output:
            atomic_text(args.output, json.dumps(result, ensure_ascii=False, indent=2) + "\n")
        if args.continuation:
            atomic_text(args.continuation, result["continuation"])
        summary = {key: value for key, value in result.items() if key != "continuation"}
        if args.output:
            summary["output"] = str(args.output.resolve())
        if args.continuation:
            summary["continuation_path"] = str(args.continuation.resolve())
        print(json.dumps(summary, ensure_ascii=False, separators=(",", ":")))
        return 0
    except Exception as error:
        print(f"FAIL: {type(error).__name__}: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
