from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

PHASE_ACTIONS = {
    "phase1_parallel_draft": ("verify", "init", "wave", "select", "commit", "status", "finalize"),
    "phase2_main_only_final": ("next", "commit", "status", "finalize"),
}


def actions_for_phase(phase: str) -> tuple[str, ...]:
    try:
        return PHASE_ACTIONS[phase]
    except KeyError as error:
        raise ValueError(f"unsupported phase: {phase}") from error


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"{label} unreadable: {path}") from error
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    return value


def verify_phase2_challenge_overlay(schedule: dict[str, Any], overlay: dict[str, Any]) -> dict[str, int]:
    schedule_packets = schedule.get("packets")
    overlay_packets = overlay.get("packets")
    if not isinstance(schedule_packets, list) or not schedule_packets:
        raise ValueError("Phase-2 schedule packets missing")
    if not isinstance(overlay_packets, dict) or not overlay_packets:
        raise ValueError("challenge overlay packets missing")
    slots_by_packet: dict[str, int] = {}
    real_ids_by_packet: dict[str, set[str]] = {}
    for packet in schedule_packets:
        if not isinstance(packet, dict):
            raise ValueError("Phase-2 schedule packet invalid")
        packet_id = packet.get("packet_id")
        slots = packet.get("challenge_slots")
        real_ids = packet.get("real_handoff_ids")
        if (
            not isinstance(packet_id, str)
            or packet_id in slots_by_packet
            or not isinstance(slots, int)
            or isinstance(slots, bool)
            or slots < 1
            or not isinstance(real_ids, list)
            or not all(isinstance(item, str) for item in real_ids)
        ):
            raise ValueError("Phase-2 challenge slot declaration invalid")
        slots_by_packet[packet_id] = slots
        real_ids_by_packet[packet_id] = set(real_ids)
    if set(overlay_packets) != set(slots_by_packet):
        raise ValueError("challenge slot packet coverage mismatch")
    seen: set[str] = set()
    count = 0
    for packet_id, entries in overlay_packets.items():
        if not isinstance(entries, list) or len(entries) != slots_by_packet[packet_id]:
            raise ValueError("challenge slot count mismatch")
        for item in entries:
            if not isinstance(item, dict):
                raise ValueError("challenge overlay row invalid")
            handoff_id = item.get("handoff_id")
            prompt_row = item.get("prompt_row")
            if (
                not isinstance(handoff_id, str)
                or handoff_id in seen
                or handoff_id in real_ids_by_packet[packet_id]
                or not isinstance(prompt_row, dict)
                or prompt_row.get("handoff_id") != handoff_id
            ):
                raise ValueError("challenge overlay identity invalid")
            source = prompt_row.get("source")
            current = prompt_row.get("current_translation_vi")
            if (
                item.get("expected_target_derivation") != "prompt_source_keep_identity"
                or prompt_row.get("translation_policy") != "keep_identity"
                or not isinstance(source, str)
                or not isinstance(current, str)
                or current == source
                or item.get("expected_target_sha256") != hashlib.sha256(source.encode("utf-8")).hexdigest()
            ):
                raise ValueError("challenge target is not prompt-derivable")
            if not source.strip():
                raise ValueError("challenge source is whitespace-only")
            if source in {"\u2026\u2026\u2026\u3002"}:
                raise ValueError("challenge donor source is excluded")
            seen.add(handoff_id)
            count += 1
    return {
        "challenge_count": count,
        "prompt_derivable_challenge_count": count,
        "unique_challenge_ids": len(seen),
    }


def require_file(root: Path, relative: str, expected_hash: str | None, label: str) -> Path:
    path = (root / relative).resolve()
    try:
        path.relative_to(root)
    except ValueError as error:
        raise ValueError(f"{label} escapes package root") from error
    if not path.is_file():
        raise ValueError(f"{label} missing: {path}")
    if expected_hash and sha256(path) != expected_hash:
        raise ValueError(f"{label} hash mismatch")
    return path


def atomic_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("wb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def atomic_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = text.replace("\r\n", "\n").encode("utf-8")
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("wb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)
    if path.read_bytes() != raw:
        raise RuntimeError("bootstrap prompt readback mismatch")


def render_phase1_bootstrap_prompt(authorization: dict[str, Any], commands: list[dict[str, Any]]) -> str:
    if authorization.get("phase") != "phase1_parallel_draft":
        raise ValueError("Phase-1 bootstrap requires Phase-1 authorization")
    required_actions = ("wave", "select", "commit", "finalize")
    by_name: dict[str, dict[str, Any]] = {}
    for item in commands:
        if not isinstance(item, dict) or set(item) != {"name", "cwd", "command_line"}:
            raise ValueError("bootstrap command shape invalid")
        name = item["name"]
        if not isinstance(name, str) or name in by_name or not isinstance(item["cwd"], str) or not isinstance(item["command_line"], str):
            raise ValueError("bootstrap command value invalid")
        by_name[name] = item
    if not set(required_actions) <= set(by_name):
        raise ValueError("Phase-1 bootstrap commands missing")
    for field in ("package_id", "run_id", "current_prompt_path", "current_response_path"):
        if not isinstance(authorization.get(field), str) or not authorization[field]:
            raise ValueError(f"bootstrap authorization {field} missing")
    exact_args = {
        name: {"CommandLine": by_name[name]["command_line"], "Cwd": by_name[name]["cwd"]}
        for name in required_actions
    }
    return f"""You are the single bound Phase-1 coordinator for package `{authorization['package_id']}` / run `{authorization['run_id']}`. This host-generated bootstrap is the only permitted starting context while the semantic guard is active.\n\nDo not read START-HERE.md, PHASE1-RULES.md, TRANSLATION-PROMPT.txt, the contributor skill, schedule, authorization, state, or any other file. Do not list directories or run helper commands. Before `wave`, no current prompt exists, so those reads are correctly denied.\n\nFor every `run_command`, copy one complete object below byte-for-byte. Do not change `CommandLine`, `Cwd`, quotes, slashes, flags, or add shell syntax. First tool call: use `wave` exactly.\n\nBEGIN_EXACT_CONTROLLER_ARGS\n{json.dumps(exact_args, ensure_ascii=False, separators=(',', ':'))}\nEND_EXACT_CONTROLLER_ARGS\n\nAfter `wave` returns `wave_staged`, make exactly one `view_file` call with `AbsolutePath` exactly `{authorization['current_prompt_path']}` and no `ContentOffset`. Do not paginate or repeat the read: this package caps the complete wave wrapper for one view. Read that single complete wave wrapper, then issue exactly one native `invoke_subagent` call containing every staged lease and no others. For each nested semantic prompt, set worker `Prompt` to one minified JSON `agy-phase1-worker-invocation/v1` object with exactly `schema`, `instructions`, `expected_prompt_sha256`, `response_schema`, and `semantic_prompt`. Copy the nested prompt unchanged into `semantic_prompt`; copy its `prompt_sha256_by_batch` value unchanged into `expected_prompt_sha256`; set `response_schema` to `agy-phase1-draft/v2`; `instructions` must contain `DO NOT CALL TOOLS` and require one bare valid UTF-8 JSON object with exactly `schema,batch_id,prompt_sha256,rows`; minified or pretty-printed is allowed, while BOM, code fences, prose, and duplicate keys are forbidden. Every `rows` item must have exactly `handoff_id,translation_vi,review_action,notes`; `target`, `status`, and every other alias are forbidden.\n\nWorker instructions: author Vietnamese only from the nested prompt; source is authoritative; reference, context, and current translation are context only; satisfy every `qa_obligations_json` required translation; preserve protected tokens, locked English terms, edge whitespace, and physical newlines; keep an exact `keep_identity` source unchanged; otherwise return a nonblank faithful Vietnamese target. Return rows exactly once and in prompt order. Copy each `handoff_id`; put the authored target only in string field `translation_vi`; set `review_action` only to `translated` or `provisional_needs_context`; set string field `notes`; add no package/run/phase/lease/marker fields. Do not call tools, inspect files, delegate, or write shared state.\n\nWhen all workers from that wave return, call exact `select`, then read only that same exact current-prompt path. Select one matching raw worker result, direct-write it unchanged with `write_to_file` to `TargetFile` exactly `{authorization['current_response_path']}`, `Overwrite: true`, and no `ArtifactMetadata`; do not reserialize, repair, or read the response back manually. Host PostToolUse performs the readback. Then call exact `commit`. Repeat `select` → exact current-prompt read → unchanged raw write → `commit` until `select` reports `wave_committed`; then call exact `wave` again. When `wave` reports all leases committed, call exact `finalize` and stop.\n\nOn any denial or controller result outside these states, stop and report only the guard/controller message. Do not retry by guessing commands, changing files, resetting guards, or dumping worker payloads.\n"""


def render_phase2_bootstrap_prompt(authorization: dict[str, Any], commands: list[dict[str, Any]]) -> str:
    if authorization.get("phase") != "phase2_main_only_final":
        raise ValueError("Phase-2 bootstrap requires Phase-2 authorization")
    required_actions = ("next", "commit", "finalize")
    by_name: dict[str, dict[str, Any]] = {}
    for item in commands:
        if not isinstance(item, dict) or set(item) != {"name", "cwd", "command_line"}:
            raise ValueError("bootstrap command shape invalid")
        name = item["name"]
        if not isinstance(name, str) or name in by_name or not isinstance(item["cwd"], str) or not isinstance(item["command_line"], str):
            raise ValueError("bootstrap command value invalid")
        by_name[name] = item
    if not set(required_actions) <= set(by_name):
        raise ValueError("Phase-2 bootstrap commands missing")
    for field in ("package_id", "run_id", "current_prompt_path", "current_response_path"):
        if not isinstance(authorization.get(field), str) or not authorization[field]:
            raise ValueError(f"bootstrap authorization {field} missing")
    exact_args = {
        name: {"CommandLine": by_name[name]["command_line"], "Cwd": by_name[name]["cwd"]}
        for name in required_actions
    }
    return f"""Bound Phase-2 main agent: `{authorization['package_id']}` / `{authorization['run_id']}`. This is main-agent-only: Do not invoke subagents or generate semantic decisions with scripts/terminal.\n\nRETAIN THIS RESPONSE CONTRACT THROUGH CONTEXT COMPACTION. Top level is exactly `schema,batch_id,prompt_sha256,decisions`; schema is `agy-explicit-review/v2`. Accepted is exactly `handoff_id,action,review_codes,notes`, action `accepted`, with at least three distinct codes from `source_fidelity,context_fit,natural_vi,glossary_policy,tokens_format,ui_fit,keep_identity,proper_noun_policy`. Rewritten is exactly `handoff_id,action,translation_vi,reason_codes,notes`, action `rewritten`, with a nonblank changed target and nonempty reason-code list. Needs-context is exactly `handoff_id,action,question`. Never use `accept`, `rewrite`, `rows`, aliases, package/run/count fields, ranges, wildcards, or omission defaults. If one write is rejected, stop; never probe variants.\n\nDo not read package, authorization, overlay, schedule, state, ledger, or docs. The first tool call must use exact `next`; for every run command copy one complete object below byte-for-byte.\n\nBEGIN_EXACT_CONTROLLER_ARGS\n{json.dumps(exact_args, ensure_ascii=False, separators=(',', ':'))}\nEND_EXACT_CONTROLLER_ARGS\n\nOn `packet_ready`, read `{authorization['current_prompt_path']}` exactly once using `view_file` with no ContentOffset. Review every row in exact order against source, reference/context, glossary, natural Vietnamese, and token/format policy. `keep_identity` requires target=source byte-for-byte including edge whitespace. Verify visible `identity_expected_codepoints` and `identity_expected_utf8_hex`; close the JSON string immediately after the final declared byte and never add/remove spaces.\n\nWrite one bare UTF-8 JSON object to `{authorization['current_response_path']}` using native `write_to_file`, Overwrite=true, no ArtifactMetadata/fence/prose/BOM/duplicate keys. Minified or pretty-printed is allowed. Copy exact batch ID and prompt hash. Accepted preserves current target byte-for-byte; rewritten must be source-grounded and structurally valid.\n\nRun exact `commit`, then exact `next`; repeat. Run `finalize` exactly once only after `next` says all packets committed. Stop at `phase2_full_pass_accepted_waiting_for_fresh_recheck` and report exact IDs/counts/paths/hashes. Hermes separately authorizes recheck.\n"""


def command_prefix(receiver_python: Path, controller: Path, authorization: Path, shell: str) -> str:
    python_text = str(receiver_python)
    if shell == "powershell":
        if any(character.isspace() for character in python_text):
            raise ValueError("PowerShell guarded execution requires a whitespace-free Python path")
        if any(character in python_text for character in '"\'`;&|<>(){}'):
            raise ValueError("PowerShell guarded execution Python path contains unsafe characters")
        return f'{python_text} -X utf8 -B "{controller}" --authorization "{authorization}"'
    raise ValueError(f"unsupported receiver shell: {shell}")


def run_checked(command: list[str], cwd: Path, label: str) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(command, cwd=cwd, text=True, capture_output=True, check=False)
    if result.returncode:
        detail = (result.stderr or result.stdout).strip()
        raise RuntimeError(f"{label} failed ({result.returncode}): {detail}")
    return result


def build(args: argparse.Namespace) -> dict[str, Any]:
    package_root = Path(args.package_root).resolve()
    work_root = Path(args.work_root).resolve()
    private_root = Path(args.host_private_root).resolve()
    receiver_python = Path(args.python).resolve()
    semantic_guard = Path(args.semantic_guard).resolve()

    manifest_path = package_root / "project-manifest.json"
    if not package_root.is_dir() or not manifest_path.is_file():
        raise ValueError("package root or project-manifest.json missing")
    if not receiver_python.is_file() or not semantic_guard.is_file():
        raise ValueError("receiver Python or semantic guard missing")
    if package_root == work_root or package_root in work_root.parents or work_root in package_root.parents:
        raise ValueError("work root must be outside package root")
    if private_root == package_root or package_root in private_root.parents or private_root in package_root.parents:
        raise ValueError("host-private root must be outside package root")
    if private_root == work_root or work_root in private_root.parents or private_root in work_root.parents:
        raise ValueError("host-private root must be outside work root")

    manifest = read_json(manifest_path, "manifest")
    package_id = manifest.get("package_id")
    run_id = manifest.get("run_id")
    phase = manifest.get("phase")
    if not all(isinstance(item, str) and item for item in (package_id, run_id, phase)):
        raise ValueError("manifest identity missing")
    actions = actions_for_phase(phase)

    tools = manifest.get("tools")
    schedule_spec = manifest.get("schedule")
    if not isinstance(tools, dict) or not isinstance(schedule_spec, dict):
        raise ValueError("manifest tool or schedule descriptors missing")
    controller_spec = tools.get("controller")
    materializer_spec = tools.get("semantic_authorization_materializer")
    if not isinstance(controller_spec, dict) or not isinstance(materializer_spec, dict):
        raise ValueError("manifest controller or materializer descriptor missing")

    controller = require_file(package_root, controller_spec.get("path", ""), controller_spec.get("sha256"), "controller")
    schedule = require_file(package_root, schedule_spec.get("path", ""), schedule_spec.get("sha256"), "schedule")
    materializer = require_file(package_root, materializer_spec.get("path", ""), materializer_spec.get("sha256"), "materializer")

    host_control = manifest.get("host_control")
    if not isinstance(host_control, dict):
        raise ValueError("manifest host control missing")
    challenge_overlay: Path | None = None
    challenge_verification = {
        "challenge_count": 0,
        "prompt_derivable_challenge_count": 0,
        "unique_challenge_ids": 0,
    }
    if host_control.get("host_private_challenge_overlay_required"):
        if not args.challenge_overlay:
            raise ValueError("Phase 2 requires a host-private challenge overlay")
        challenge_overlay = Path(args.challenge_overlay).resolve()
        if not challenge_overlay.is_file():
            raise ValueError("challenge overlay missing")
        overlay_value = read_json(challenge_overlay, "challenge overlay")
        if (
            overlay_value.get("package_id") != package_id
            or overlay_value.get("run_id") != run_id
            or overlay_value.get("manifest_sha256") != sha256(manifest_path)
        ):
            raise ValueError("challenge overlay identity mismatch")
        challenge_verification = verify_phase2_challenge_overlay(
            read_json(schedule, "schedule"), overlay_value
        )

    authorization = private_root / "semantic-authorization.json"
    commands_path = private_root / "allowed-commands.json"
    report_path = private_root / "host-preparation-receipt.json"
    prefix = command_prefix(receiver_python, controller, authorization, args.receiver_shell)
    commands = [
        {
            "name": action,
            "cwd": str(package_root),
            "command_line": f"{prefix} {action}",
        }
        for action in actions
    ]

    private_root.mkdir(parents=True, exist_ok=False)
    work_root.mkdir(parents=True, exist_ok=True)
    atomic_json(commands_path, commands)
    materialize_command = [
        str(receiver_python), "-B", str(materializer),
        "--package-root", str(package_root),
        "--work-root", str(work_root),
        "--manifest", str(manifest_path),
        "--controller", str(controller),
        "--schedule", str(schedule),
        "--current-prompt", str(work_root / "current" / "prompt.json"),
        "--current-response", str(work_root / "current" / "response.json"),
        "--commands-json", str(commands_path),
        "--guard", str(semantic_guard),
        "--output", str(authorization),
    ]
    if challenge_overlay is not None:
        materialize_command.extend(("--challenge-overlay", str(challenge_overlay)))
    materialization = run_checked(materialize_command, package_root, "semantic authorization materialization")
    try:
        materialization_receipt = json.loads(materialization.stdout)
    except json.JSONDecodeError as error:
        raise RuntimeError("semantic authorization materializer did not return JSON") from error
    if (
        not isinstance(materialization_receipt, dict)
        or materialization_receipt.get("package_id") != package_id
        or materialization_receipt.get("run_id") != run_id
        or materialization_receipt.get("phase") != phase
        or materialization_receipt.get("challenge_count") != challenge_verification["challenge_count"]
        or materialization_receipt.get("prompt_derivable_challenge_count", challenge_verification["prompt_derivable_challenge_count"])
        != challenge_verification["prompt_derivable_challenge_count"]
    ):
        raise RuntimeError("semantic authorization materialization receipt mismatch")
    materialization_receipt = {
        **materialization_receipt,
        "prompt_derivable_challenge_count": challenge_verification["prompt_derivable_challenge_count"],
        "unique_challenge_ids": challenge_verification["unique_challenge_ids"],
    }
    authorized = read_json(authorization, "semantic authorization")
    if authorized.get("allowed_run_commands") != commands:
        raise RuntimeError("materialized authorization command allowlist mismatch")
    bootstrap_prompt = (
        Path(args.bootstrap_output).resolve()
        if args.bootstrap_output
        else private_root.parent / f"{package_id}-USER-SEND-ONCE.txt"
    )
    if bootstrap_prompt.exists():
        raise FileExistsError(f"bootstrap prompt already exists: {bootstrap_prompt}")
    if bootstrap_prompt == package_root or package_root in bootstrap_prompt.parents or bootstrap_prompt == work_root or work_root in bootstrap_prompt.parents:
        raise ValueError("bootstrap prompt must remain outside package and work roots")
    renderer = render_phase1_bootstrap_prompt if phase == "phase1_parallel_draft" else render_phase2_bootstrap_prompt
    atomic_text(bootstrap_prompt, renderer(authorized, commands))

    probe_action = "verify" if phase == "phase1_parallel_draft" else "status"
    probe_command = next(item["command_line"] for item in commands if item["name"] == probe_action)
    probe = run_checked(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", probe_command],
        package_root,
        "receiver shell probe",
    )
    try:
        probe_json = json.loads(probe.stdout)
    except json.JSONDecodeError as error:
        raise RuntimeError("receiver shell probe did not return JSON") from error

    receipt = {
        "schema": "agy-guarded-host-preparation-receipt/v1",
        "status": "prepared",
        "package_id": package_id,
        "run_id": run_id,
        "phase": phase,
        "package_root": str(package_root),
        "work_root": str(work_root),
        "host_private_root": str(private_root),
        "receiver_shell": args.receiver_shell,
        "shell_probe_action": probe_action,
        "shell_probe": True,
        "probe_result": probe_json,
        "authorization": {"path": str(authorization), "sha256": sha256(authorization)},
        "semantic_materialization": materialization_receipt,
        "commands": {"path": str(commands_path), "sha256": sha256(commands_path), "count": len(commands)},
        "bootstrap_prompt": None if bootstrap_prompt is None else {"path": str(bootstrap_prompt), "sha256": sha256(bootstrap_prompt)},
        "semantic_guard": {"path": str(semantic_guard), "sha256": sha256(semantic_guard)},
        "manifest": {"path": str(manifest_path), "sha256": sha256(manifest_path)},
    }
    atomic_json(report_path, receipt)
    return {
        "status": "prepared",
        "package_id": package_id,
        "run_id": run_id,
        "phase": phase,
        "shell_probe": True,
        "challenge_count": materialization_receipt["challenge_count"],
        "prompt_derivable_challenge_count": materialization_receipt["prompt_derivable_challenge_count"],
        "authorization": str(authorization),
        "bootstrap_prompt": None if bootstrap_prompt is None else str(bootstrap_prompt),
        "report": str(report_path),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Prepare guarded handoff host state with compact output.")
    parser.add_argument("--package-root", required=True)
    parser.add_argument("--work-root", required=True)
    parser.add_argument("--host-private-root", required=True)
    parser.add_argument("--python", required=True)
    parser.add_argument("--semantic-guard", required=True)
    parser.add_argument("--receiver-shell", choices=("powershell",), default="powershell")
    parser.add_argument("--challenge-overlay")
    parser.add_argument("--bootstrap-output")
    args = parser.parse_args(argv)
    try:
        summary = build(args)
        print(json.dumps(summary, ensure_ascii=False, separators=(",", ":")))
        return 0
    except Exception as error:
        print(f"FAIL: {type(error).__name__}: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
