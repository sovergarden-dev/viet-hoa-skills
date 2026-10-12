from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import importlib.util
import json
import os
import sys
from pathlib import Path
from typing import Any

CONTRACT = "AGY-VIETHOA-HANDOFF/2.5-TWO-PHASE-DRAFT12-PREVIEW-FINAL0-GUARDED"
PHASE = "phase2_main_only_final"
FULL_SCHEDULE_SCHEMA = "agy-phase2-schedule/v2"
RECHECK_SCHEDULE_SCHEMA = "agy-phase2-recheck-schedule/v1"
STATE_SCHEMA = "agy-phase2-controller-state/v1"
COMMIT_SCHEMA = "agy-phase2-packet-commit/v1"
SNAPSHOT_SCHEMA = "agy-phase2-full-pass-snapshot/v1"
RECHECK_SNAPSHOT_SCHEMA = "agy-phase2-fresh-recheck-snapshot/v1"
DECISION_INDEX_SCHEMA = "agy-phase2-real-decision-index/v1"
HEX64 = set("0123456789abcdef")


def canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ValueError(f"cannot load pinned module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _json_object_without_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError(f"duplicate JSON key: {key}")
        value[key] = item
    return value


def decode_json_object(raw: bytes, label: str) -> dict[str, Any]:
    if raw.startswith(b"\xef\xbb\xbf"):
        raise ValueError(f"{label} must not contain a BOM")
    value = json.loads(raw.decode("utf-8"), object_pairs_hook=_json_object_without_duplicates)
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object")
    return value


def read_json(
    path: Path, label: str, *, canonical_required: bool = False, allow_single_lf: bool = False,
) -> tuple[dict[str, Any], bytes]:
    raw = path.read_bytes()
    value = decode_json_object(raw, label)
    expected = (
        json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        if allow_single_lf else canonical(value)
    )
    if canonical_required and raw != expected and not (allow_single_lf and raw == expected + b"\n"):
        raise ValueError(f"{label} bytes are not canonical")
    return value, raw


def read_native_response(path: Path, label: str) -> tuple[dict[str, Any], bytes]:
    raw = path.read_bytes()
    return decode_json_object(raw, label), raw


def atomic_bytes(path: Path, payload: bytes, label: str) -> None:
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
        raise RuntimeError(f"{label} atomic readback mismatch")


def atomic_json(path: Path, value: dict[str, Any], label: str) -> None:
    atomic_bytes(path, canonical(value), label)
    readback, _raw = read_json(path, label, canonical_required=True)
    if readback != value:
        raise RuntimeError(f"{label} JSON readback mismatch")


def descriptor_path(descriptor: object, label: str) -> tuple[Path, str]:
    if not isinstance(descriptor, dict) or set(descriptor) != {"path", "sha256"}:
        raise ValueError(f"{label} descriptor invalid")
    path = Path(descriptor["path"]).resolve()
    expected = descriptor["sha256"]
    if not path.is_file() or not isinstance(expected, str) or len(expected) != 64 or set(expected) - HEX64:
        raise ValueError(f"{label} descriptor invalid")
    if digest(path.read_bytes()) != expected:
        raise ValueError(f"{label} hash mismatch")
    return path, expected


def is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def load_context(authorization_path: Path) -> dict[str, Any]:
    authorization_path = authorization_path.resolve()
    auth, auth_raw = read_json(authorization_path, "semantic authorization")
    package_root = Path(auth.get("package_root", "")).resolve()
    work_root = Path(auth.get("work_root", "")).resolve()
    if not package_root.is_dir() or not work_root.is_dir() or is_within(work_root, package_root) or is_within(package_root, work_root):
        raise ValueError("package/work roots invalid")
    guard_path = package_root / "tools/semantic_response_guard.py"
    materializer_path = package_root / "tools/materialize_phase2_challenge_overlay.py"
    if not guard_path.is_file() or not materializer_path.is_file():
        raise ValueError("package-pinned controller dependencies missing")
    guard = load_module(guard_path, "agy_controller_guard")
    guard.validate_authorization(auth)
    controller_path, _controller_hash = descriptor_path(auth["controller"], "controller")
    if controller_path != Path(__file__).resolve():
        raise ValueError("executed controller differs from authorization")
    schedule_path, schedule_hash = descriptor_path(auth["schedule"], "schedule")
    overlay_path, overlay_hash = descriptor_path(auth["challenge_overlay"], "challenge overlay")
    schedule, _schedule_raw = read_json(schedule_path, "schedule")
    overlay, _overlay_raw = read_json(overlay_path, "challenge overlay")
    schedule_schema = schedule.get("schema")
    if schedule_schema not in {FULL_SCHEDULE_SCHEMA, RECHECK_SCHEDULE_SCHEMA}:
        raise ValueError("unsupported Phase-2 schedule schema")
    manifest_path = package_root / "project-manifest.json"
    if not manifest_path.is_file() or digest(manifest_path.read_bytes()) != auth["manifest_sha256"]:
        raise ValueError("manifest binding mismatch")
    manifest, _manifest_raw = read_json(manifest_path, "manifest")
    materializer = load_module(materializer_path, "agy_controller_materializer")
    parent_full_pass: dict[str, Any] | None = None
    if schedule_schema == FULL_SCHEDULE_SCHEMA:
        input_descriptor = manifest.get("inputs", {}).get("full_corpus")
        if not isinstance(input_descriptor, dict) or not isinstance(input_descriptor.get("path"), str):
            raise ValueError("full corpus descriptor missing")
        input_path = (package_root / input_descriptor["path"]).resolve()
        if not is_within(input_path, package_root) or not input_path.is_file():
            raise ValueError("full corpus path invalid")
        input_sha256 = input_descriptor.get("sha256")
        expected_row_count = input_descriptor.get("row_count")
    else:
        parent = schedule.get("parent_full_pass")
        if not isinstance(parent, dict) or set(parent) != {"path", "sha256", "row_count"}:
            raise ValueError("fresh recheck parent descriptor invalid")
        input_path = Path(parent["path"]).resolve()
        if is_within(input_path, package_root) or is_within(input_path, work_root) or not input_path.is_file():
            raise ValueError("fresh recheck parent path invalid")
        input_sha256 = parent.get("sha256")
        expected_row_count = parent.get("row_count")
        parent_full_pass = dict(parent)
    if not isinstance(input_sha256, str) or digest(input_path.read_bytes()) != input_sha256:
        raise ValueError("controller input snapshot hash mismatch")
    rows = materializer.read_rows(input_path)
    if len(rows) != expected_row_count:
        raise ValueError("controller input snapshot row count mismatch")
    prompt_path = Path(auth["current_prompt_path"]).resolve()
    response_path = Path(auth["current_response_path"]).resolve()
    if not is_within(prompt_path, work_root) or not is_within(response_path, work_root):
        raise ValueError("current semantic paths outside work root")
    if prompt_path == response_path:
        raise ValueError("current prompt/response paths collide")
    return {
        "authorization_path": authorization_path,
        "authorization": auth,
        "authorization_sha256": digest(auth_raw),
        "package_root": package_root,
        "work_root": work_root,
        "guard": guard,
        "materializer": materializer,
        "schedule": schedule,
        "schedule_schema": schedule_schema,
        "schedule_sha256": schedule_hash,
        "parent_full_pass": parent_full_pass,
        "overlay": overlay,
        "overlay_sha256": overlay_hash,
        "rows": rows,
        "input_path": input_path,
        "input_sha256": input_sha256,
        "prompt_path": prompt_path,
        "response_path": response_path,
    }


def controller_paths(context: dict[str, Any]) -> dict[str, Path]:
    root = context["work_root"] / "controller" / context["schedule_sha256"]
    return {
        "root": root,
        "state": root / "state.json",
        "commits": root / "commits",
        "prompts": root / "prompts",
        "responses": root / "responses",
        "snapshots": context["work_root"] / "snapshots" / context["schedule_sha256"],
    }


def initial_state(context: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": STATE_SCHEMA,
        "contract": CONTRACT,
        "phase": PHASE,
        "package_id": context["authorization"]["package_id"],
        "run_id": context["authorization"]["run_id"],
        "manifest_sha256": context["authorization"]["manifest_sha256"],
        "authorization_sha256": context["authorization_sha256"],
        "schedule_sha256": context["schedule_sha256"],
        "overlay_sha256": context["overlay_sha256"],
        "next_packet_index": 0,
        "active_packet_id": None,
        "commit_count": 0,
        "commit_head_sha256": None,
        "last_committed_response_sha256": None,
        "finalized": False,
        "snapshot_sha256": None,
        "snapshot_receipt_sha256": None,
    }


def load_state(context: dict[str, Any], paths: dict[str, Path]) -> dict[str, Any]:
    expected = initial_state(context)
    path = paths["state"]
    if not path.exists():
        return expected
    state, _raw = read_json(path, "controller state", canonical_required=True)
    if set(state) != set(expected):
        raise ValueError("controller state fields invalid")
    for key in (
        "schema", "contract", "phase", "package_id", "run_id", "manifest_sha256",
        "authorization_sha256", "schedule_sha256", "overlay_sha256",
    ):
        if state[key] != expected[key]:
            raise ValueError(f"controller state binding mismatch: {key}")
    packet_count = len(context["schedule"]["packets"])
    if (
        not isinstance(state["next_packet_index"], int) or isinstance(state["next_packet_index"], bool)
        or not 0 <= state["next_packet_index"] <= packet_count
        or state["commit_count"] != state["next_packet_index"]
        or state["active_packet_id"] not in {None, *(packet["packet_id"] for packet in context["schedule"]["packets"])}
        or not isinstance(state["finalized"], bool)
    ):
        raise ValueError("controller state counters invalid")
    return state


def packet_by_index(context: dict[str, Any], index: int) -> dict[str, Any]:
    return context["schedule"]["packets"][index]


def expected_prompt(context: dict[str, Any], packet_id: str) -> dict[str, Any]:
    return context["materializer"].build_prompt(
        context["schedule"], context["rows"], context["overlay"], packet_id,
    )


def phase2_edge_whitespace(text: str) -> tuple[str, str]:
    left = text[:len(text) - len(text.lstrip())]
    right = text[len(text.rstrip()):] if text.rstrip() != text else ""
    return left, right


def phase2_string_list(value: object, label: str, handoff_id: str) -> list[str]:
    if value in (None, ""):
        return []
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError as error:
            raise ValueError(f"{label} invalid: {handoff_id}") from error
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"{label} invalid: {handoff_id}")
    return value


def validate_phase2_structural_rewrites(response: dict[str, Any], prompt: dict[str, Any]) -> None:
    prompt_map = {row["handoff_id"]: row for row in prompt["rows"]}
    for decision in response.get("decisions", []):
        handoff_id = decision.get("handoff_id")
        prompt_row = prompt_map.get(handoff_id)
        if not isinstance(prompt_row, dict):
            raise ValueError(f"Phase-2 decision prompt row missing: {handoff_id}")
        try:
            mandatory = json.loads(prompt_row.get("mandatory_rewrite_reasons", "[]") or "[]")
        except json.JSONDecodeError as error:
            raise ValueError(f"mandatory rewrite reasons invalid: {handoff_id}") from error
        if mandatory and decision.get("action") != "rewritten":
            raise ValueError(f"mandatory rewrite row cannot be accepted or deferred: {handoff_id}")
        if decision.get("action") != "rewritten":
            continue
        target = decision.get("translation_vi")
        if not isinstance(target, str):
            raise ValueError(f"Phase-2 rewritten target invalid: {handoff_id}")
        source = prompt_row.get("source", "")
        if prompt_row.get("translation_policy") != "keep_identity" and source.strip() and target == source:
            raise ValueError(f"Phase-2 source-copy rewrite invalid: {handoff_id}")
        if target == prompt_row.get("current_translation_vi"):
            raise ValueError(f"Phase-2 rewritten target is unchanged: {handoff_id}")
        tokens = collections.Counter(
            token for token in phase2_string_list(prompt_row.get("protected_tokens"), "protected_tokens", handoff_id)
            if token != "__NEWLINE__"
        )
        if any(target.count(token) != count for token, count in tokens.items()):
            raise ValueError(f"Phase-2 protected token mismatch: {handoff_id}")
        if source.count("\n") != target.count("\n"):
            raise ValueError(f"Phase-2 physical newline mismatch: {handoff_id}")
        if phase2_edge_whitespace(source) != phase2_edge_whitespace(target):
            raise ValueError(f"Phase-2 edge whitespace mismatch: {handoff_id}")
        locked = phase2_string_list(prompt_row.get("locked_english_terms"), "locked_english_terms", handoff_id)
        if any(source.count(term) != target.count(term) for term in locked):
            raise ValueError(f"Phase-2 locked term mismatch: {handoff_id}")


def validate_bound_response(
    context: dict[str, Any], response: dict[str, Any], prompt: dict[str, Any], prompt_raw: bytes,
) -> None:
    context["guard"].validate_phase2_response(response, prompt, context["authorization"])
    validate_phase2_structural_rewrites(response, prompt)
    if response.get("prompt_sha256") != digest(prompt_raw):
        raise ValueError("response prompt hash mismatch")


def expected_commit(
    context: dict[str, Any], packet_index: int, prompt: dict[str, Any], prompt_raw: bytes,
    response: dict[str, Any], response_raw: bytes, previous_hash: str | None,
) -> dict[str, Any]:
    packet = packet_by_index(context, packet_index)
    real_ids = packet["real_handoff_ids"]
    real_set = set(real_ids)
    challenge_targets = context["authorization"]["challenge_ids_by_batch"].get(packet["packet_id"], {})
    decision_map = {decision["handoff_id"]: decision for decision in response["decisions"]}
    real_decisions = [decision_map[handoff_id] for handoff_id in real_ids]
    challenge_receipts = []
    for handoff_id, expected_target_sha256 in sorted(challenge_targets.items()):
        decision = decision_map[handoff_id]
        target_sha256 = digest(decision["translation_vi"].encode("utf-8"))
        challenge_receipts.append({
            "handoff_id": handoff_id,
            "expected_target_sha256": expected_target_sha256,
            "response_target_sha256": target_sha256,
        })
    if set(decision_map) != real_set | set(challenge_targets):
        raise ValueError("response decision set differs from packet")
    return {
        "schema": COMMIT_SCHEMA,
        "contract": CONTRACT,
        "phase": PHASE,
        "package_id": context["authorization"]["package_id"],
        "run_id": context["authorization"]["run_id"],
        "schedule_sha256": context["schedule_sha256"],
        "packet_index": packet_index,
        "batch_id": packet["packet_id"],
        "prompt_sha256": digest(prompt_raw),
        "response_sha256": digest(response_raw),
        "previous_commit_sha256": previous_hash,
        "real_decisions": real_decisions,
        "challenge_receipts": challenge_receipts,
    }


def commit_paths(paths: dict[str, Path], packet_index: int, packet_id: str) -> tuple[Path, Path, Path]:
    stem = f"{packet_index + 1:06d}-{packet_id}"
    return (
        paths["commits"] / f"{stem}.json",
        paths["prompts"] / f"{stem}.json",
        paths["responses"] / f"{stem}.json",
    )


def verify_commits(context: dict[str, Any], paths: dict[str, Path], state: dict[str, Any]) -> list[dict[str, Any]]:
    commits: list[dict[str, Any]] = []
    previous_hash: str | None = None
    for index in range(state["commit_count"]):
        packet = packet_by_index(context, index)
        commit_path, prompt_path, response_path = commit_paths(paths, index, packet["packet_id"])
        try:
            commit, commit_raw = read_json(commit_path, "commit evidence", canonical_required=True)
            prompt, prompt_raw = read_json(prompt_path, "prompt evidence", canonical_required=True)
            response, response_raw = read_native_response(response_path, "response evidence")
        except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as error:
            raise ValueError(f"commit evidence invalid: {error}") from error
        expected_prompt_value = expected_prompt(context, packet["packet_id"])
        if prompt != expected_prompt_value:
            raise ValueError(f"commit evidence prompt mismatch: {packet['packet_id']}")
        validate_bound_response(context, response, prompt, prompt_raw)
        expected = expected_commit(context, index, prompt, prompt_raw, response, response_raw, previous_hash)
        if commit != expected:
            raise ValueError(f"commit evidence mismatch: {packet['packet_id']}")
        previous_hash = digest(commit_raw)
        commits.append(commit)
    if previous_hash != state["commit_head_sha256"]:
        raise ValueError("commit evidence head mismatch")
    return commits


def clean_committed_response(context: dict[str, Any], state: dict[str, Any]) -> None:
    path = context["response_path"]
    if not path.exists():
        return
    raw = path.read_bytes()
    if state["last_committed_response_sha256"] != digest(raw):
        raise ValueError("unexpected uncommitted response blocks next packet")
    path.unlink()


def next_packet(context: dict[str, Any], paths: dict[str, Path], state: dict[str, Any]) -> dict[str, Any]:
    verify_commits(context, paths, state)
    if state["finalized"]:
        return {"status": "finalized", "packet_count": state["commit_count"]}
    if state["active_packet_id"] is not None:
        packet_id = state["active_packet_id"]
        prompt = expected_prompt(context, packet_id)
        payload = canonical(prompt)
        if context["prompt_path"].exists() and context["prompt_path"].read_bytes() != payload:
            raise ValueError("active prompt bytes changed")
        if not context["prompt_path"].exists():
            context["materializer"].materialize_prompt(context["prompt_path"], prompt)
        return {"status": "prompt_ready", "batch_id": packet_id, "prompt_sha256": digest(payload)}
    clean_committed_response(context, state)
    if state["next_packet_index"] == len(context["schedule"]["packets"]):
        return {"status": "stage_complete", "commit_count": state["commit_count"], "commit_head_sha256": state["commit_head_sha256"]}
    packet = packet_by_index(context, state["next_packet_index"])
    state["active_packet_id"] = packet["packet_id"]
    atomic_json(paths["state"], state, "controller state")
    prompt = expected_prompt(context, packet["packet_id"])
    context["materializer"].materialize_prompt(context["prompt_path"], prompt)
    return {"status": "prompt_ready", "batch_id": packet["packet_id"], "prompt_sha256": digest(canonical(prompt))}


def commit_packet(context: dict[str, Any], paths: dict[str, Path], state: dict[str, Any]) -> dict[str, Any]:
    commits = verify_commits(context, paths, state)
    if state["active_packet_id"] is None:
        raise ValueError("no active packet to commit")
    index = state["next_packet_index"]
    packet = packet_by_index(context, index)
    if packet["packet_id"] != state["active_packet_id"]:
        raise ValueError("active packet/state mismatch")
    prompt, prompt_raw = read_json(context["prompt_path"], "current prompt", canonical_required=True)
    if prompt != expected_prompt(context, packet["packet_id"]):
        raise ValueError("current prompt differs from authorized packet")
    response, response_raw = read_native_response(context["response_path"], "current response")
    validate_bound_response(context, response, prompt, prompt_raw)
    previous_hash = digest(canonical(commits[-1])) if commits else None
    if previous_hash != state["commit_head_sha256"]:
        raise ValueError("commit head drift before write")
    evidence = expected_commit(context, index, prompt, prompt_raw, response, response_raw, previous_hash)
    commit_path, prompt_archive, response_archive = commit_paths(paths, index, packet["packet_id"])
    atomic_bytes(prompt_archive, prompt_raw, "prompt evidence")
    atomic_bytes(response_archive, response_raw, "response evidence")
    evidence_payload = canonical(evidence)
    if commit_path.exists() and commit_path.read_bytes() != evidence_payload:
        raise ValueError("existing commit evidence conflicts")
    atomic_bytes(commit_path, evidence_payload, "commit evidence")
    state["next_packet_index"] = index + 1
    state["active_packet_id"] = None
    state["commit_count"] = index + 1
    state["commit_head_sha256"] = digest(evidence_payload)
    state["last_committed_response_sha256"] = digest(response_raw)
    atomic_json(paths["state"], state, "controller state")
    context["response_path"].unlink(missing_ok=True)
    return {
        "status": "committed",
        "batch_id": packet["packet_id"],
        "commit_path": str(commit_path),
        "commit_sha256": digest(evidence_payload),
    }


def write_snapshot_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError("snapshot rows missing")
    fieldnames = list(rows[0])
    if any(list(row) != fieldnames for row in rows):
        raise ValueError("snapshot row fields/order mismatch")
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with temporary.open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=fieldnames, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        readback = [dict(row) for row in csv.DictReader(stream)]
    if readback != rows:
        raise RuntimeError("snapshot CSV atomic readback mismatch")


def finalize(context: dict[str, Any], paths: dict[str, Path], state: dict[str, Any]) -> dict[str, Any]:
    commits = verify_commits(context, paths, state)
    if state["active_packet_id"] is not None or state["commit_count"] != len(context["schedule"]["packets"]):
        raise ValueError("cannot finalize before exact packet coverage")
    decisions: dict[str, dict[str, Any]] = {}
    action_counts = {"accepted": 0, "rewritten": 0, "needs_context": 0}
    for commit in commits:
        for decision in commit["real_decisions"]:
            handoff_id = decision["handoff_id"]
            if handoff_id in decisions:
                raise ValueError(f"duplicate real decision: {handoff_id}")
            decisions[handoff_id] = decision
            action_counts[decision["action"]] += 1
    input_ids = [row["handoff_id"] for row in context["rows"]]
    is_recheck = context["schedule_schema"] == RECHECK_SCHEDULE_SCHEMA
    required_ids = context["schedule"]["selection"]["selected_handoff_ids"] if is_recheck else input_ids
    if set(decisions) != set(required_ids) or len(decisions) != len(required_ids):
        raise ValueError("final real decision coverage mismatch")
    unresolved = [handoff_id for handoff_id in required_ids if decisions[handoff_id]["action"] == "needs_context"]
    if unresolved:
        raise ValueError(f"unresolved rows block finalization: {len(unresolved)}")
    output_rows: list[dict[str, Any]] = []
    for row in context["rows"]:
        output = dict(row)
        decision = decisions.get(row["handoff_id"])
        if decision is not None and decision["action"] == "rewritten":
            output["current_translation_vi"] = decision["translation_vi"]
        output_rows.append(output)
    snapshot_name = "fresh-recheck-final-snapshot" if is_recheck else "full-pass-snapshot"
    snapshot_csv = paths["snapshots"] / f"{snapshot_name}.csv"
    snapshot_receipt = paths["snapshots"] / f"{snapshot_name}.json"
    write_snapshot_csv(snapshot_csv, output_rows)
    snapshot_hash = digest(snapshot_csv.read_bytes())
    decision_index_path = paths["snapshots"] / f"{snapshot_name}-decisions.json"
    decision_index = {
        "schema": DECISION_INDEX_SCHEMA,
        "contract": CONTRACT,
        "phase": PHASE,
        "stage": "fresh_recheck" if is_recheck else "full_review",
        "package_id": context["authorization"]["package_id"],
        "run_id": context["authorization"]["run_id"],
        "schedule_sha256": context["schedule_sha256"],
        "snapshot_sha256": snapshot_hash,
        "decision_count": len(required_ids),
        "ordered_handoff_ids_sha256": digest(canonical(required_ids)),
        "decisions": [decisions[handoff_id] for handoff_id in required_ids],
    }
    atomic_json(decision_index_path, decision_index, "real decision index")
    decision_index_hash = digest(decision_index_path.read_bytes())
    receipt = {
        "schema": RECHECK_SNAPSHOT_SCHEMA if is_recheck else SNAPSHOT_SCHEMA,
        "contract": CONTRACT,
        "phase": PHASE,
        "package_id": context["authorization"]["package_id"],
        "run_id": context["authorization"]["run_id"],
        "manifest_sha256": context["authorization"]["manifest_sha256"],
        "authorization_sha256": context["authorization_sha256"],
        "schedule_sha256": context["schedule_sha256"],
        "overlay_sha256": context["overlay_sha256"],
        "input_sha256": context["input_sha256"],
        "snapshot_csv": str(snapshot_csv),
        "snapshot_sha256": snapshot_hash,
        "decision_index": str(decision_index_path),
        "decision_index_sha256": decision_index_hash,
        "row_count": len(output_rows),
        "ordered_handoff_ids_sha256": digest(canonical(input_ids)),
        "action_counts": action_counts,
        "unresolved_count": 0,
        "commit_count": len(commits),
        "commit_head_sha256": state["commit_head_sha256"],
    }
    if is_recheck:
        receipt["parent_full_pass"] = context["parent_full_pass"]
        receipt["selected_row_count"] = len(required_ids)
        receipt["selected_handoff_ids_sha256"] = context["schedule"]["selection"]["selected_handoff_ids_sha256"]
    atomic_json(snapshot_receipt, receipt, "fresh recheck snapshot receipt" if is_recheck else "full-pass snapshot receipt")
    state["finalized"] = True
    state["snapshot_sha256"] = snapshot_hash
    state["snapshot_receipt_sha256"] = digest(snapshot_receipt.read_bytes())
    atomic_json(paths["state"], state, "controller state")
    return {
        "status": "finalized",
        "snapshot_csv": str(snapshot_csv),
        "snapshot_receipt": str(snapshot_receipt),
        "snapshot_sha256": snapshot_hash,
        "decision_index": str(decision_index_path),
        "decision_index_sha256": decision_index_hash,
        "row_count": len(output_rows),
    }


def status(context: dict[str, Any], paths: dict[str, Path], state: dict[str, Any]) -> dict[str, Any]:
    verify_commits(context, paths, state)
    return {
        "status": "finalized" if state["finalized"] else ("prompt_ready" if state["active_packet_id"] else "ready"),
        "next_packet_index": state["next_packet_index"],
        "packet_count": len(context["schedule"]["packets"]),
        "active_packet_id": state["active_packet_id"],
        "commit_count": state["commit_count"],
        "commit_head_sha256": state["commit_head_sha256"],
        "snapshot_sha256": state["snapshot_sha256"],
    }


def run(authorization_path: Path, action: str) -> dict[str, Any]:
    context = load_context(authorization_path)
    paths = controller_paths(context)
    state = load_state(context, paths)
    # ponytail: host guard serializes exact controller commands; add an OS file lock if parallel command execution is introduced.
    if action == "next":
        return next_packet(context, paths, state)
    if action == "commit":
        return commit_packet(context, paths, state)
    if action == "status":
        return status(context, paths, state)
    if action == "finalize":
        return finalize(context, paths, state)
    raise ValueError(f"unsupported controller action: {action}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Guarded Phase-2 exact-packet controller.")
    parser.add_argument("--authorization", type=Path, required=True)
    parser.add_argument("action", choices=("next", "commit", "status", "finalize"))
    args = parser.parse_args(argv)
    print(json.dumps(run(args.authorization, args.action), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, UnicodeError, ValueError, RuntimeError, json.JSONDecodeError) as error:
        print(f"FAIL: {type(error).__name__}: {error}", file=sys.stderr)
        raise SystemExit(1)
