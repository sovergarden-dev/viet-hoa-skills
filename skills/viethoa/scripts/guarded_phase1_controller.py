from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import importlib.util
import json
import os
import shutil
import sys
import zipfile
from pathlib import Path
from typing import Any

CONTRACT = "AGY-VIETHOA-HANDOFF/2.5-TWO-PHASE-DRAFT12-PREVIEW-FINAL0-GUARDED"
PHASE = "phase1_parallel_draft"
SCHEDULE_SCHEMA = "agy-phase1-schedule/v2"
RESPONSE_SCHEMA = "agy-phase1-draft/v2"
WAVE_SCHEMA = "agy-semantic-wave/v1"
NORMALIZATION_SCHEMA = "agy-phase1-envelope-normalization/v1"
STATE_SCHEMA = "agy-guarded-phase1-controller-state/v1"
COMMIT_SCHEMA = "agy-phase1-controller-commit/v1"
SNAPSHOT_SCHEMA = "agy-phase1-draft-snapshot/v1"
DECISION_INDEX_SCHEMA = "agy-phase1-draft-index/v1"
MAX_STAGED_LEASES = 12


def phase1_wave_limit(context: dict[str, Any]) -> int:
    host = context.get("manifest", {}).get("host_control", {})
    maximum = host.get("required_subagent_limit")
    if maximum is None:
        maximum = context.get("authorization", {}).get("max_subagents")
    if isinstance(maximum, bool) or not isinstance(maximum, int) or not 1 <= maximum <= MAX_STAGED_LEASES:
        raise ValueError("Phase-1 configured subagent limit must be in 1..12")
    return maximum


def canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256(path: Path) -> str:
    return digest(path.read_bytes())


def read_json(path: Path, label: str) -> dict[str, Any]:
    raw = path.read_bytes()
    value = json.loads(raw.decode("utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object")
    return value


def _json_object_without_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError(f"duplicate JSON key: {key}")
        value[key] = item
    return value


def decode_native_response(raw: bytes, label: str) -> dict[str, Any]:
    if raw.startswith(b"\xef\xbb\xbf"):
        raise ValueError(f"{label} must not contain a BOM")
    value = json.loads(raw.decode("utf-8"), object_pairs_hook=_json_object_without_duplicates)
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be one bare JSON object")
    return value


def atomic_bytes(path: Path, raw: bytes, label: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp-guarded-p1")
    with temp.open("wb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temp, path)
    if path.read_bytes() != raw:
        raise RuntimeError(f"{label} atomic readback mismatch")


def atomic_json(path: Path, value: object, label: str) -> None:
    raw = canonical(value)
    atomic_bytes(path, raw, label)
    if json.loads(path.read_text(encoding="utf-8")) != value:
        raise RuntimeError(f"{label} JSON readback mismatch")


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows or any(None in row for row in rows):
        raise ValueError("Phase-1 input CSV malformed or empty")
    return rows


def atomic_rows(path: Path, rows: list[dict[str, str]], label: str) -> None:
    if not rows:
        raise ValueError(f"{label} rows empty")
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp-guarded-p1")
    with temp.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temp, path)
    if read_rows(path) != rows:
        raise RuntimeError(f"{label} CSV readback mismatch")


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ValueError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def controller_paths(work_root: Path) -> dict[str, Path]:
    root = work_root / "controller"
    return {
        "root": root,
        "state": root / "state.json",
        "commits": root / "commits",
        "archive": root / "archive",
        "snapshots": root / "snapshots",
        "return_stage": root / "final-return",
        "returns": root / "returns",
    }


def load_context(authorization_path: Path) -> dict[str, Any]:
    authorization_path = authorization_path.resolve()
    auth_raw = authorization_path.read_bytes()
    auth = json.loads(auth_raw.decode("utf-8"))
    if not isinstance(auth, dict):
        raise ValueError("semantic authorization must be an object")
    package_root = Path(auth["package_root"]).resolve()
    work_root = Path(auth["work_root"]).resolve()
    controller_path = Path(auth["controller"]["path"]).resolve()
    if Path(__file__).resolve() != controller_path:
        raise ValueError("running controller differs from authorized controller")
    guard_path = package_root / "tools/semantic_response_guard.py"
    guard = load_module(guard_path, "guarded_p1_semantic_guard")
    guard.validate_authorization(auth)
    if auth.get("phase") != PHASE:
        raise ValueError("Phase-1 controller requires Phase-1 authorization")
    manifest_path = package_root / "project-manifest.json"
    manifest = read_json(manifest_path, "project manifest")
    if manifest.get("package_id") != auth["package_id"] or manifest.get("run_id") != auth["run_id"]:
        raise ValueError("manifest/authorization identity mismatch")
    schedule_path = Path(auth["schedule"]["path"]).resolve()
    schedule = read_json(schedule_path, "Phase-1 schedule")
    if schedule.get("schema") != SCHEDULE_SCHEMA or schedule.get("phase") != PHASE:
        raise ValueError("Phase-1 schedule schema invalid")
    if schedule.get("package_id") != auth["package_id"] or schedule.get("run_id") != auth["run_id"]:
        raise ValueError("Phase-1 schedule identity mismatch")
    input_descriptor = manifest.get("inputs", {}).get("full_corpus")
    if not isinstance(input_descriptor, dict):
        raise ValueError("Phase-1 input descriptor missing")
    input_path = (package_root / input_descriptor["path"]).resolve()
    if sha256(input_path) != input_descriptor.get("sha256"):
        raise ValueError("Phase-1 input hash mismatch")
    rows = read_rows(input_path)
    if input_descriptor.get("row_count") != len(rows):
        raise ValueError("Phase-1 input row count mismatch")
    by_id = {row["handoff_id"]: row for row in rows}
    if len(by_id) != len(rows):
        raise ValueError("Phase-1 input IDs duplicate")
    leases = schedule.get("leases")
    if not isinstance(leases, list) or not leases:
        raise ValueError("Phase-1 leases missing")
    flattened: list[str] = []
    lease_by_id: dict[str, dict[str, Any]] = {}
    for lease in leases:
        if not isinstance(lease, dict) or not isinstance(lease.get("lease_id"), str):
            raise ValueError("Phase-1 lease invalid")
        lease_id = lease["lease_id"]
        ids = lease.get("handoff_ids")
        if lease_id in lease_by_id or not isinstance(ids, list) or not ids or any(item not in by_id for item in ids):
            raise ValueError(f"Phase-1 lease identity invalid: {lease_id}")
        prompt_rows = [by_id[item] for item in ids]
        if digest(canonical(prompt_rows)) != lease.get("prompt_rows_sha256"):
            raise ValueError(f"Phase-1 lease prompt hash mismatch: {lease_id}")
        lease_by_id[lease_id] = lease
        flattened.extend(ids)
    if flattened != [row["handoff_id"] for row in rows] or len(flattened) != len(set(flattened)):
        raise ValueError("Phase-1 leases are not one exact ordered partition")
    return {
        "authorization_path": authorization_path,
        "authorization": auth,
        "authorization_sha256": digest(auth_raw),
        "package_root": package_root,
        "work_root": work_root,
        "manifest": manifest,
        "manifest_sha256": sha256(manifest_path),
        "schedule": schedule,
        "schedule_sha256": sha256(schedule_path),
        "input_path": input_path,
        "input_sha256": sha256(input_path),
        "rows": rows,
        "by_id": by_id,
        "leases": leases,
        "lease_by_id": lease_by_id,
        "guard": guard,
        "paths": controller_paths(work_root),
    }


def initial_state(context: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": STATE_SCHEMA,
        "contract": CONTRACT,
        "package_id": context["authorization"]["package_id"],
        "run_id": context["authorization"]["run_id"],
        "authorization_sha256": context["authorization_sha256"],
        "manifest_sha256": context["manifest_sha256"],
        "schedule_sha256": context["schedule_sha256"],
        "input_sha256": context["input_sha256"],
        "lease_status": {lease["lease_id"]: "pending" for lease in context["leases"]},
        "current_batch_id": None,
        "commit_count": 0,
        "commit_head_sha256": None,
        "finalized": False,
        "snapshot_sha256": None,
        "snapshot_receipt_sha256": None,
        "decision_index_sha256": None,
        "return_zip_sha256": None,
    }


def save_state(path: Path, state: dict[str, Any]) -> None:
    atomic_json(path, state, "Phase-1 controller state")


def load_state(context: dict[str, Any], create: bool = True) -> dict[str, Any]:
    path = context["paths"]["state"]
    if not path.exists():
        if not create:
            raise ValueError("Phase-1 controller state missing")
        state = initial_state(context)
        save_state(path, state)
        return state
    state = read_json(path, "Phase-1 controller state")
    expected = {
        "schema": STATE_SCHEMA,
        "contract": CONTRACT,
        "package_id": context["authorization"]["package_id"],
        "run_id": context["authorization"]["run_id"],
        "authorization_sha256": context["authorization_sha256"],
        "manifest_sha256": context["manifest_sha256"],
        "schedule_sha256": context["schedule_sha256"],
        "input_sha256": context["input_sha256"],
    }
    if any(state.get(key) != value for key, value in expected.items()):
        raise ValueError("Phase-1 controller state binding mismatch")
    if set(state.get("lease_status", {})) != set(context["lease_by_id"]):
        raise ValueError("Phase-1 controller lease state mismatch")
    return state


def verify_commits(context: dict[str, Any], state: dict[str, Any]) -> list[dict[str, Any]]:
    commit_dir = context["paths"]["commits"]
    files = sorted(commit_dir.glob("*.json")) if commit_dir.exists() else []
    if len(files) != state.get("commit_count"):
        raise ValueError("Phase-1 commit evidence count mismatch")
    previous = None
    commits: list[dict[str, Any]] = []
    seen: set[str] = set()
    for sequence, path in enumerate(files, 1):
        raw = path.read_bytes()
        try:
            value = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ValueError("Phase-1 commit evidence is not canonical") from error
        if not isinstance(value, dict) or canonical(value) != raw:
            raise ValueError("Phase-1 commit evidence is not canonical")
        entry_hash = value.get("entry_sha256")
        core = dict(value)
        core.pop("entry_sha256", None)
        if value.get("schema") != COMMIT_SCHEMA or value.get("sequence") != sequence or value.get("previous_entry_sha256") != previous or digest(canonical(core)) != entry_hash:
            raise ValueError("Phase-1 commit evidence chain invalid")
        lease_id = value.get("lease_id")
        if lease_id not in context["lease_by_id"] or lease_id in seen:
            raise ValueError("Phase-1 commit lease invalid")
        prompt_path = Path(value["prompt_archive_path"])
        response_path = Path(value["response_archive_path"])
        if sha256(prompt_path) != value.get("prompt_sha256") or sha256(response_path) != value.get("response_sha256"):
            raise ValueError("Phase-1 archived evidence hash mismatch")
        raw_response_path = Path(value["raw_response_archive_path"])
        normalization_path = Path(value["normalization_receipt_path"])
        if sha256(raw_response_path) != value.get("raw_response_sha256") or sha256(normalization_path) != value.get("normalization_receipt_sha256"):
            raise ValueError("Phase-1 raw/normalization evidence hash mismatch")
        normalization = read_json(normalization_path, "Phase-1 normalization receipt")
        if normalization.get("schema") != NORMALIZATION_SCHEMA or normalization.get("lease_id") != lease_id:
            raise ValueError("Phase-1 normalization receipt binding mismatch")
        if normalization.get("raw_response_sha256") != value.get("raw_response_sha256") or normalization.get("normalized_response_sha256") != value.get("response_sha256"):
            raise ValueError("Phase-1 normalization receipt hash mismatch")
        response = read_json(response_path, "archived Phase-1 response")
        target_hashes = {
            row["handoff_id"]: digest(row["translation_vi"].encode("utf-8"))
            for row in response.get("rows", [])
            if isinstance(row, dict) and isinstance(row.get("handoff_id"), str) and isinstance(row.get("translation_vi"), str)
        }
        if response.get("batch_id") != lease_id or target_hashes != normalization.get("target_utf8_sha256_by_handoff_id"):
            raise ValueError("Phase-1 archived response/target-hash binding mismatch")
        seen.add(lease_id)
        previous = entry_hash
        commits.append(value)
    if previous != state.get("commit_head_sha256"):
        raise ValueError("Phase-1 commit head mismatch")
    committed = {lease_id for lease_id, status in state["lease_status"].items() if status == "committed"}
    if committed != seen:
        raise ValueError("Phase-1 committed lease state/evidence mismatch")
    return commits


def build_prompt(context: dict[str, Any], lease_id: str) -> dict[str, Any]:
    lease = context["lease_by_id"][lease_id]
    package_id = context["authorization"]["package_id"]
    run_id = context["authorization"]["run_id"]
    lease_sha256 = lease["lease_sha256"]
    return {
        "schema": "agy-semantic-prompt/v1",
        "package_id": package_id,
        "run_id": run_id,
        "phase": PHASE,
        "batch_id": lease_id,
        "lease_sha256": lease_sha256,
        "invocation_marker": f"AGY_LEASE_V1::{package_id}::{run_id}::{lease_id}::{lease_sha256}",
        "rows": [context["by_id"][item] for item in lease["handoff_ids"]],
    }


def stage(context: dict[str, Any], state: dict[str, Any], lease_id: str, allow_pending: bool) -> dict[str, Any]:
    status = state["lease_status"].get(lease_id)
    if status not in ({"pending", "staged"} if allow_pending else {"staged"}):
        raise ValueError(f"Phase-1 lease cannot be staged: {lease_id}")
    prompt = build_prompt(context, lease_id)
    atomic_json(Path(context["authorization"]["current_prompt_path"]), prompt, "Phase-1 current prompt")
    response_path = Path(context["authorization"]["current_response_path"])
    if response_path.exists():
        response_path.unlink()
    next_state = dict(state)
    next_state["lease_status"] = dict(state["lease_status"])
    next_state["lease_status"][lease_id] = "staged"
    next_state["current_batch_id"] = lease_id
    save_state(context["paths"]["state"], next_state)
    return {"status": "staged", "batch_id": lease_id, "prompt_path": str(Path(context["authorization"]["current_prompt_path"])), "prompt_sha256": digest(canonical(prompt))}


def next_lease(context: dict[str, Any]) -> dict[str, Any]:
    state = load_state(context)
    verify_commits(context, state)
    wave_limit = phase1_wave_limit(context)
    staged_count = sum(value == "staged" for value in state["lease_status"].values())
    if staged_count < wave_limit:
        for lease in context["leases"]:
            if state["lease_status"][lease["lease_id"]] == "pending":
                return stage(context, state, lease["lease_id"], True)
    for lease in context["leases"]:
        if state["lease_status"][lease["lease_id"]] == "staged":
            return stage(context, state, lease["lease_id"], True)
    return {"status": "all_leases_committed", "committed": state["commit_count"], "remaining_staged": 0}


def stage_wave(context: dict[str, Any]) -> dict[str, Any]:
    state = load_state(context)
    verify_commits(context, state)
    wave_limit = phase1_wave_limit(context)
    if state.get("current_batch_id") is not None:
        raise ValueError("current lease must be committed before staging a wave")
    if any(value == "staged" for value in state["lease_status"].values()):
        raise ValueError("staged wave must be committed before staging another")
    lease_ids = [
        lease["lease_id"] for lease in context["leases"]
        if state["lease_status"][lease["lease_id"]] == "pending"
    ][:wave_limit]
    if not lease_ids:
        return {"status": "all_leases_committed", "committed": state["commit_count"], "lease_ids": []}
    prompts = [build_prompt(context, lease_id) for lease_id in lease_ids]
    wave = {
        "schema": WAVE_SCHEMA,
        "package_id": context["authorization"]["package_id"],
        "run_id": context["authorization"]["run_id"],
        "phase": PHASE,
        "lease_ids": lease_ids,
        "prompt_sha256_by_batch": {prompt["batch_id"]: digest(canonical(prompt)) for prompt in prompts},
        "prompts": prompts,
    }
    atomic_json(Path(context["authorization"]["current_prompt_path"]), wave, "Phase-1 current wave")
    response_path = Path(context["authorization"]["current_response_path"])
    if response_path.exists():
        response_path.unlink()
    next_state = dict(state)
    next_state["lease_status"] = dict(state["lease_status"])
    for lease_id in lease_ids:
        next_state["lease_status"][lease_id] = "staged"
    next_state["current_batch_id"] = None
    save_state(context["paths"]["state"], next_state)
    return {
        "status": "wave_staged",
        "lease_ids": lease_ids,
        "lease_count": len(lease_ids),
        "prompt_path": str(Path(context["authorization"]["current_prompt_path"])),
        "prompt_sha256": digest(canonical(wave)),
    }


def select_lease(context: dict[str, Any]) -> dict[str, Any]:
    state = load_state(context)
    verify_commits(context, state)
    current = state.get("current_batch_id")
    if isinstance(current, str) and state["lease_status"].get(current) == "staged":
        return {"status": "already_selected", "batch_id": current, "prompt_path": str(Path(context["authorization"]["current_prompt_path"]))}
    for lease in context["leases"]:
        if state["lease_status"][lease["lease_id"]] == "staged":
            return stage(context, state, lease["lease_id"], False)
    return {"status": "wave_committed", "committed": state["commit_count"], "remaining_staged": 0}


def edge_whitespace(text: str) -> tuple[str, str]:
    left = text[:len(text) - len(text.lstrip())]
    right = text[len(text.rstrip()):] if text.rstrip() != text else ""
    return left, right


def validate_phase1_structural_response(value: dict[str, Any], prompt: dict[str, Any]) -> None:
    for response_row, prompt_row in zip(value.get("rows", []), prompt.get("rows", [])):
        handoff_id = prompt_row["handoff_id"]
        source = prompt_row["source"]
        target = response_row["translation_vi"]
        policy = prompt_row["translation_policy"]
        if policy != "keep_identity" and source.strip() and target == source:
            raise ValueError(f"unexpected source copy: {handoff_id}")
        try:
            declared = json.loads(prompt_row.get("protected_tokens", "[]"))
        except json.JSONDecodeError as error:
            raise ValueError(f"protected token declaration invalid: {handoff_id}") from error
        if not isinstance(declared, list) or not all(isinstance(item, str) for item in declared):
            raise ValueError(f"protected token declaration invalid: {handoff_id}")
        tokens = collections.Counter(item for item in declared if item != "__NEWLINE__")
        if any(source.count(token) != count for token, count in tokens.items()):
            raise ValueError(f"stale protected token declaration: {handoff_id}")
        if any(target.count(token) != count for token, count in tokens.items()):
            raise ValueError(f"protected token mismatch: {handoff_id}")
        if source.count("\n") != target.count("\n"):
            raise ValueError(f"physical newline mismatch: {handoff_id}")
        if edge_whitespace(source) != edge_whitespace(target):
            raise ValueError(f"edge whitespace mismatch: {handoff_id}")
        try:
            locked = json.loads(prompt_row.get("locked_english_terms", "[]"))
        except json.JSONDecodeError as error:
            raise ValueError(f"locked term declaration invalid: {handoff_id}") from error
        if not isinstance(locked, list) or not all(isinstance(item, str) for item in locked):
            raise ValueError(f"locked term declaration invalid: {handoff_id}")
        if any(source.count(term) != target.count(term) for term in locked):
            raise ValueError(f"locked term mismatch: {handoff_id}")
        if "\ufffd" in target or any(0xD800 <= ord(character) <= 0xDFFF for character in target):
            raise ValueError(f"unicode corruption: {handoff_id}")


def normalize_phase1_response(
    value: object, prompt: dict[str, Any], raw_sha256: str, raw_is_canonical: bool,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if not isinstance(value, dict) or set(value) != {"schema", "batch_id", "prompt_sha256", "rows"}:
        raise ValueError("Phase-1 native response envelope fields invalid")
    if value.get("schema") not in {RESPONSE_SCHEMA, "agy-semantic-prompt/v1"}:
        raise ValueError("Phase-1 native response envelope schema is not normalizable")
    normalized = dict(value)
    changed_fields: list[str] = []
    if not raw_is_canonical:
        changed_fields.append("json_format")
    if normalized["schema"] != RESPONSE_SCHEMA:
        normalized["schema"] = RESPONSE_SCHEMA
        changed_fields.append("schema")
    target_hashes = {
        row["handoff_id"]: digest(row["translation_vi"].encode("utf-8"))
        for row in normalized.get("rows", [])
        if isinstance(row, dict) and isinstance(row.get("handoff_id"), str) and isinstance(row.get("translation_vi"), str)
    }
    if len(target_hashes) != len(normalized.get("rows", [])):
        raise ValueError("Phase-1 native response target strings invalid")
    receipt = {
        "schema": NORMALIZATION_SCHEMA,
        "package_id": prompt["package_id"],
        "run_id": prompt["run_id"],
        "lease_id": prompt["batch_id"],
        "raw_response_sha256": raw_sha256,
        "normalized_response_sha256": None,
        "changed_fields": changed_fields,
        "target_utf8_sha256_by_handoff_id": target_hashes,
    }
    return normalized, receipt


def commit(context: dict[str, Any]) -> dict[str, Any]:
    state = load_state(context)
    verify_commits(context, state)
    lease_id = state.get("current_batch_id")
    if not isinstance(lease_id, str) or state["lease_status"].get(lease_id) != "staged":
        raise ValueError("no staged Phase-1 lease to commit")
    prompt_path = Path(context["authorization"]["current_prompt_path"])
    response_path = Path(context["authorization"]["current_response_path"])
    prompt_raw = prompt_path.read_bytes()
    response_raw = response_path.read_bytes()
    prompt = json.loads(prompt_raw.decode("utf-8"))
    native_response = decode_native_response(response_raw, "Phase-1 native response")
    response_canonical = json.dumps(
        native_response, ensure_ascii=False, separators=(",", ":"),
    ).encode("utf-8")
    if canonical(prompt) != prompt_raw:
        raise ValueError("Phase-1 prompt must be canonical JSON")
    context["guard"].load_prompt(context["authorization"])
    if native_response.get("prompt_sha256") != digest(prompt_raw):
        raise ValueError("Phase-1 response prompt hash mismatch")
    response, normalization = normalize_phase1_response(
        native_response, prompt, digest(response_raw), response_raw == response_canonical,
    )
    context["guard"].validate_phase1_response(response, prompt)
    validate_phase1_structural_response(response, prompt)
    normalized_raw = json.dumps(response, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    normalization["normalized_response_sha256"] = digest(normalized_raw)
    sequence = state["commit_count"] + 1
    archive_dir = context["paths"]["archive"] / f"{sequence:06d}-{lease_id}"
    prompt_archive = archive_dir / "prompt.json"
    response_archive = archive_dir / "response.json"
    raw_response_archive = archive_dir / "raw-response.json"
    normalization_archive = archive_dir / "normalization.json"
    atomic_bytes(prompt_archive, prompt_raw, "Phase-1 prompt archive")
    atomic_bytes(raw_response_archive, response_raw, "Phase-1 raw response archive")
    atomic_bytes(response_archive, normalized_raw, "Phase-1 normalized response archive")
    atomic_json(normalization_archive, normalization, "Phase-1 normalization receipt")
    core = {
        "schema": COMMIT_SCHEMA,
        "sequence": sequence,
        "previous_entry_sha256": state["commit_head_sha256"],
        "package_id": context["authorization"]["package_id"],
        "run_id": context["authorization"]["run_id"],
        "lease_id": lease_id,
        "prompt_sha256": digest(prompt_raw),
        "raw_response_sha256": digest(response_raw),
        "response_sha256": digest(normalized_raw),
        "prompt_archive_path": str(prompt_archive.resolve()),
        "response_archive_path": str(response_archive.resolve()),
        "raw_response_archive_path": str(raw_response_archive.resolve()),
        "normalization_receipt_path": str(normalization_archive.resolve()),
        "normalization_receipt_sha256": sha256(normalization_archive),
        "handoff_ids": [row["handoff_id"] for row in response["rows"]],
    }
    evidence = dict(core)
    evidence["entry_sha256"] = digest(canonical(core))
    evidence_path = context["paths"]["commits"] / f"{sequence:06d}-{lease_id}.json"
    atomic_json(evidence_path, evidence, "Phase-1 commit evidence")
    next_state = dict(state)
    next_state["lease_status"] = dict(state["lease_status"])
    next_state["lease_status"][lease_id] = "committed"
    next_state["current_batch_id"] = None
    next_state["commit_count"] = sequence
    next_state["commit_head_sha256"] = evidence["entry_sha256"]
    save_state(context["paths"]["state"], next_state)
    verify_commits(context, next_state)
    return {"status": "committed", "batch_id": lease_id, "sequence": sequence, "evidence_path": str(evidence_path), "entry_sha256": evidence["entry_sha256"]}


def collect_responses(context: dict[str, Any], commits: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for item in commits:
        response = read_json(Path(item["response_archive_path"]), "archived Phase-1 response")
        for row in response["rows"]:
            handoff_id = row["handoff_id"]
            if handoff_id in result:
                raise ValueError("duplicate Phase-1 committed row")
            result[handoff_id] = row
    return result


def build_return_zip(context: dict[str, Any], snapshot: Path, index_path: Path, receipt_path: Path) -> Path:
    stage = context["paths"]["return_stage"]
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir(parents=True)
    shutil.copy2(snapshot, stage / "phase1-draft.csv")
    shutil.copy2(index_path, stage / "draft-index.json")
    shutil.copy2(receipt_path, stage / "receipt.json")
    shutil.copytree(context["paths"]["commits"], stage / "commits")
    shutil.copytree(context["paths"]["archive"], stage / "archive")
    files = sorted(path for path in stage.rglob("*") if path.is_file())
    checksum_bytes = "".join(f"{sha256(path)}  {path.relative_to(stage).as_posix()}\n" for path in files).encode("utf-8")
    atomic_bytes(stage / "checksums.sha256", checksum_bytes, "Phase-1 return checksums")
    name = context["manifest"].get("expected_final_filename")
    if not isinstance(name, str) or not name.lower().endswith(".zip") or Path(name).name != name:
        raise ValueError("Phase-1 expected final filename invalid")
    output = context["paths"]["returns"] / name
    output.parent.mkdir(parents=True, exist_ok=True)
    temp = output.with_name(output.name + ".tmp-guarded-p1")
    with zipfile.ZipFile(temp, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(item for item in stage.rglob("*") if item.is_file()):
            archive.write(path, path.relative_to(stage).as_posix())
    os.replace(temp, output)
    with zipfile.ZipFile(output) as archive:
        if archive.testzip() is not None:
            raise RuntimeError("Phase-1 return ZIP CRC failure")
    return output


def finalize(context: dict[str, Any]) -> dict[str, Any]:
    state = load_state(context)
    commits = verify_commits(context, state)
    if any(value != "committed" for value in state["lease_status"].values()):
        raise ValueError("Phase-1 finalization blocked by uncommitted leases")
    decisions = collect_responses(context, commits)
    input_ids = [row["handoff_id"] for row in context["rows"]]
    if set(decisions) != set(input_ids) or len(decisions) != len(input_ids):
        raise ValueError("Phase-1 final committed coverage mismatch")
    output_rows: list[dict[str, str]] = []
    for row in context["rows"]:
        output = dict(row)
        output["current_translation_vi"] = decisions[row["handoff_id"]]["translation_vi"]
        output_rows.append(output)
    snapshot = context["paths"]["snapshots"] / "phase1-draft.csv"
    atomic_rows(snapshot, output_rows, "Phase-1 draft snapshot")
    snapshot_hash = sha256(snapshot)
    index_path = context["paths"]["snapshots"] / "phase1-draft-index.json"
    index = {
        "schema": DECISION_INDEX_SCHEMA,
        "contract": CONTRACT,
        "package_id": context["authorization"]["package_id"],
        "run_id": context["authorization"]["run_id"],
        "snapshot_sha256": snapshot_hash,
        "row_count": len(output_rows),
        "rows": [decisions[item] for item in input_ids],
    }
    atomic_json(index_path, index, "Phase-1 draft index")
    receipt_path = context["paths"]["snapshots"] / "phase1-draft-receipt.json"
    receipt = {
        "schema": SNAPSHOT_SCHEMA,
        "contract": CONTRACT,
        "package_id": context["authorization"]["package_id"],
        "run_id": context["authorization"]["run_id"],
        "manifest_sha256": context["manifest_sha256"],
        "authorization_sha256": context["authorization_sha256"],
        "schedule_sha256": context["schedule_sha256"],
        "input_sha256": context["input_sha256"],
        "snapshot_csv": str(snapshot.resolve()),
        "snapshot_sha256": snapshot_hash,
        "decision_index": str(index_path.resolve()),
        "decision_index_sha256": sha256(index_path),
        "row_count": len(output_rows),
        "commit_count": len(commits),
        "commit_head_sha256": state["commit_head_sha256"],
        "provisional_needs_context_count": sum(row["review_action"] == "provisional_needs_context" for row in decisions.values()),
    }
    atomic_json(receipt_path, receipt, "Phase-1 draft receipt")
    return_zip = build_return_zip(context, snapshot, index_path, receipt_path)
    next_state = dict(state)
    next_state["finalized"] = True
    next_state["snapshot_sha256"] = snapshot_hash
    next_state["snapshot_receipt_sha256"] = sha256(receipt_path)
    next_state["decision_index_sha256"] = sha256(index_path)
    next_state["return_zip_sha256"] = sha256(return_zip)
    save_state(context["paths"]["state"], next_state)
    return {
        "status": "finalized",
        "snapshot_csv": str(snapshot),
        "snapshot_sha256": snapshot_hash,
        "snapshot_receipt": str(receipt_path),
        "decision_index": str(index_path),
        "return_zip": str(return_zip),
        "return_zip_sha256": sha256(return_zip),
        "row_count": len(output_rows),
    }


def status(context: dict[str, Any]) -> dict[str, Any]:
    state = load_state(context)
    verify_commits(context, state)
    return {
        "status": "ok",
        "pending": sum(value == "pending" for value in state["lease_status"].values()),
        "staged": sum(value == "staged" for value in state["lease_status"].values()),
        "committed": sum(value == "committed" for value in state["lease_status"].values()),
        "current_batch_id": state["current_batch_id"],
        "finalized": state["finalized"],
        "commit_head_sha256": state["commit_head_sha256"],
    }


def run(authorization_path: Path, action: str, lease_id: str | None = None) -> dict[str, Any]:
    context = load_context(authorization_path)
    if action in {"verify", "init"}:
        state = load_state(context)
        verify_commits(context, state)
        return status(context)
    if action == "next":
        return next_lease(context)
    if action == "wave":
        return stage_wave(context)
    if action == "select":
        return select_lease(context)
    if action == "commit":
        return commit(context)
    if action == "status":
        return status(context)
    if action == "finalize":
        return finalize(context)
    raise ValueError(f"unknown Phase-1 controller action: {action}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Guarded Phase-1 draft controller")
    parser.add_argument("--authorization", required=True, type=Path)
    parser.add_argument("action", choices=("verify", "init", "next", "wave", "select", "commit", "status", "finalize"))
    args = parser.parse_args(argv)
    try:
        print(json.dumps(run(args.authorization, args.action), ensure_ascii=False, separators=(",", ":")))
        return 0
    except Exception as error:
        print(f"FAIL: {type(error).__name__}: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
