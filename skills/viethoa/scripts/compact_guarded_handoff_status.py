from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from collections import Counter
from pathlib import Path
from typing import Any

SCHEMA = "agy-compact-guarded-status/v1"
ACTIVE_MODES = {"phase1_parallel_draft", "phase2_main_only_final"}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_object(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"{label} unreadable: {path}") from error
    if not isinstance(value, dict):
        raise ValueError(f"{label} is not an object: {path}")
    return value


def read_jsonl(path: Path, label: str) -> list[dict[str, Any]]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError) as error:
        raise ValueError(f"{label} unreadable: {path}") from error
    rows: list[dict[str, Any]] = []
    for number, line in enumerate(lines, 1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as error:
            raise ValueError(f"{label} invalid JSON at line {number}") from error
        if not isinstance(value, dict) or value.get("sequence") != len(rows) + 1:
            raise ValueError(f"{label} sequence invalid at line {number}")
        rows.append(value)
    return rows


def require_binding(value: dict[str, Any], package_id: str, run_id: str, label: str) -> None:
    mode = value.get("mode")
    if mode in ACTIVE_MODES and (value.get("package_id") != package_id or value.get("run_id") != run_id):
        raise ValueError(f"{label} binding mismatch")


def reservation_count(state: dict[str, Any]) -> int:
    reservations = state.get("reservations")
    if isinstance(reservations, dict):
        total = 0
        for entry in reservations.values():
            if not isinstance(entry, dict) or not isinstance(entry.get("pending"), dict):
                raise ValueError("subagent reservations invalid")
            for lease_ids in entry["pending"].values():
                if not isinstance(lease_ids, list):
                    raise ValueError("subagent reservations invalid")
                total += len(lease_ids)
        return total
    value = state.get("reserved", 0)
    if not isinstance(value, int) or value < 0:
        raise ValueError("subagent reserved count invalid")
    return value


def controller_summary(path: Path, package_id: str, run_id: str, expected: int | None) -> tuple[dict[str, Any], str | None]:
    if not path.exists():
        return {
            "state": "uninitialized",
            "pending": expected,
            "staged": 0,
            "committed": 0,
            "finalized": False,
        }, None
    state = read_object(path, "controller state")
    if state.get("package_id") != package_id or state.get("run_id") != run_id:
        raise ValueError("controller binding mismatch")
    statuses = state.get("lease_status")
    if not isinstance(statuses, dict) or any(not isinstance(value, str) for value in statuses.values()):
        raise ValueError("controller lease status invalid")
    counts = Counter(statuses.values())
    allowed = {"pending", "staged", "committed"}
    if set(counts) - allowed:
        raise ValueError("controller lease state invalid")
    if expected is not None and len(statuses) != expected:
        raise ValueError("controller lease count mismatch")
    return {
        "pending": counts["pending"],
        "staged": counts["staged"],
        "committed": counts["committed"],
        "finalized": bool(state.get("finalized")),
    }, sha256(path)


def atomic_json(path: Path, value: object) -> None:
    path = path.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    temp = path.with_name(path.name + ".tmp")
    with temp.open("wb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temp, path)


def build(args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, Any]]:
    release_path = Path(args.release_lock).resolve()
    subagent_path = Path(args.subagent_state).resolve()
    semantic_path = Path(args.semantic_state).resolve()
    controller_path = Path(args.controller_state).resolve()
    semantic_events_path = Path(args.semantic_events).resolve()
    subagent_events_path = Path(args.subagent_events).resolve()

    release = read_object(release_path, "release lock")
    package_id = release.get("package_id")
    run_id = release.get("run_id")
    phase = release.get("phase")
    if not all(isinstance(item, str) and item for item in (package_id, run_id, phase)):
        raise ValueError("release lock identity missing")
    expected = release.get("lease_count")
    if expected is not None and (not isinstance(expected, int) or expected < 0):
        raise ValueError("release lock lease count invalid")

    subagent = read_object(subagent_path, "subagent state")
    semantic = read_object(semantic_path, "semantic state")
    require_binding(subagent, package_id, run_id, "subagent")
    require_binding(semantic, package_id, run_id, "semantic")

    semantic_events = read_jsonl(semantic_events_path, "semantic events")
    if semantic_events:
        last = semantic_events[-1]
        if last.get("sequence") != semantic.get("event_sequence") or last.get("entry_sha256") != semantic.get("last_event_sha256"):
            raise ValueError("semantic event head mismatch")
    elif semantic.get("event_sequence") not in (0, None) or semantic.get("last_event_sha256") is not None:
        raise ValueError("semantic event head mismatch")

    subagent_events = read_jsonl(subagent_events_path, "subagent events")
    reservations = sum(
        event.get("action") == "reserve" and event.get("package_id") == package_id and event.get("run_id") == run_id
        for event in subagent_events
    )
    controller, controller_sha = controller_summary(controller_path, package_id, run_id, expected)
    translation_started = bool(
        release.get("translation_started") or reservations or (controller.get("committed") or 0) > 0
    )
    model = release.get("dispatch_model") or release.get("model")

    summary = {
        "status": "ok",
        "package_id": package_id,
        "run_id": run_id,
        "phase": phase,
        "dispatch": release.get("state"),
        "model": model,
        "subagent": {
            "mode": subagent.get("mode"),
            "limit": subagent.get("max_subagents", subagent.get("limit")),
            "reserved": reservation_count(subagent),
        },
        "semantic": {
            "mode": semantic.get("mode"),
            "conversation_bound": bool(semantic.get("main_conversation_id")),
            "event_sequence": semantic.get("event_sequence"),
        },
        "controller": controller,
        "translation_started": translation_started,
        "report": str(Path(args.output).resolve()),
    }
    report = {
        "schema": SCHEMA,
        **summary,
        "evidence": {
            "release_lock": {"path": str(release_path), "sha256": sha256(release_path)},
            "subagent_state": {"path": str(subagent_path), "sha256": sha256(subagent_path)},
            "semantic_state": {"path": str(semantic_path), "sha256": sha256(semantic_path)},
            "semantic_events": {
                "path": str(semantic_events_path),
                "count": len(semantic_events),
                "head": semantic_events[-1].get("entry_sha256") if semantic_events else None,
            },
            "subagent_events": {
                "path": str(subagent_events_path),
                "count": len(subagent_events),
                "reservations_for_run": reservations,
            },
            "controller_state": {
                "path": str(controller_path),
                "sha256": controller_sha,
            },
        },
    }
    return summary, report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--release-lock", required=True)
    parser.add_argument("--subagent-state", required=True)
    parser.add_argument("--semantic-state", required=True)
    parser.add_argument("--semantic-events", required=True)
    parser.add_argument("--subagent-events", required=True)
    parser.add_argument("--controller-state", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    try:
        summary, report = build(args)
        atomic_json(Path(args.output), report)
        print(json.dumps(summary, ensure_ascii=False, separators=(",", ":")))
        return 0
    except Exception as error:
        print(f"FAIL: {type(error).__name__}: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
