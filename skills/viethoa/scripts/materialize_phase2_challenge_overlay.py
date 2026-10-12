from __future__ import annotations

import argparse
import csv
import hashlib
import hmac
import json
import os
import re
import secrets
import sys
from pathlib import Path
from typing import Any

SCHEMA = "agy-phase2-challenge-overlay/v1"
SCHEDULE_SCHEMA = "agy-phase2-schedule/v2"
RECHECK_SCHEDULE_SCHEMA = "agy-phase2-recheck-schedule/v1"
PHASE = "phase2_main_only_final"
SAFE_ID = re.compile(r"[A-Za-z0-9._-]{1,160}")
HEX64 = re.compile(r"[0-9a-f]{64}")
# Antigravity persistently appends U+0020 to this exact keep_identity literal
# during challenge rewrite. Keep the row as a real identity control; never
# use it as a host-private challenge donor.
CHALLENGE_DONOR_SOURCE_EXCLUSIONS = frozenset({"\u2026\u2026\u2026\u3002"})


def canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def keyed(seed: bytes, *parts: str) -> bytes:
    return hmac.new(seed, "\0".join(parts).encode("utf-8"), hashlib.sha256).digest()


def infer_handoff_id_width(ids: list[str]) -> int:
    widths = {len(item) for item in ids}
    if len(widths) != 1:
        raise ValueError("handoff IDs must use one fixed width")
    width = next(iter(widths))
    if width < 1 or width > 64 or any(re.fullmatch(r"[0-9a-f]+", item) is None for item in ids):
        raise ValueError("handoff IDs must be fixed-width lowercase hexadecimal")
    return width


def parse_tokens(value: object, handoff_id: str) -> list[str]:
    if value in (None, ""):
        return []
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError as error:
            raise ValueError(f"protected_tokens invalid: {handoff_id}") from error
    if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value):
        raise ValueError(f"protected_tokens invalid: {handoff_id}")
    return value


def is_mandatory_rewrite(row: dict[str, Any]) -> bool:
    value = row.get("mandatory_rewrite_reasons", "[]")
    if isinstance(value, str):
        try:
            value = json.loads(value or "[]")
        except json.JSONDecodeError as error:
            raise ValueError(f"mandatory rewrite reasons invalid: {row.get('handoff_id')}") from error
    if not isinstance(value, list) or not all(isinstance(reason, str) for reason in value):
        raise ValueError(f"mandatory rewrite reasons invalid: {row.get('handoff_id')}")
    return bool(value)


def corruptions(
    row: dict[str, Any], all_rows: list[dict[str, Any]], forbidden_targets: set[str],
) -> list[tuple[str, str, str | None]]:
    handoff_id = row["handoff_id"]
    target = row["current_translation_vi"]
    source = row["source"]
    candidates: list[tuple[str, str, str | None]] = []
    for token in parse_tokens(row.get("protected_tokens"), handoff_id):
        if token in target:
            changed = target.replace(token, "", 1)
            if changed and changed != target:
                candidates.append(("protected_token_removal", changed, None))
    if source and source != target:
        candidates.append(("source_copy", source, None))
    truncated = target[:-1]
    if truncated and truncated != target:
        candidates.append(("truncation", truncated, None))
    for other in all_rows:
        other_target = other["current_translation_vi"]
        if (
            other["handoff_id"] != handoff_id and other_target
            and other_target != target and other_target not in forbidden_targets
        ):
            candidates.append(("target_swap", other_target, other["handoff_id"]))
            break
    unique: dict[tuple[str, str], tuple[str, str, str | None]] = {}
    for item in candidates:
        unique.setdefault((item[0], item[1]), item)
    return list(unique.values())


def packet_profile(row: dict[str, Any]) -> tuple[str, int]:
    content_class = str(row.get("content_class") or row.get("content_type") or "ui").casefold()
    broad_class = "dialogue" if content_class in {"dialogue", "lore", "narrative"} else "ui"
    explicit_risk = any(
        bool(str(row.get(field, "")).strip())
        for field in ("runtime_flagged", "high_risk", "emotional_flagged")
    )
    structural_risk = is_mandatory_rewrite(row)
    if explicit_risk or structural_risk:
        return broad_class, 30
    if broad_class == "dialogue":
        return broad_class, 60
    if row.get("translation_policy") == "keep_identity":
        return broad_class, 120
    return broad_class, 100


def build_schedule(
    rows: list[dict[str, Any]], package_id: str, run_id: str, *, packet_size: int | None,
) -> dict[str, Any]:
    if SAFE_ID.fullmatch(package_id) is None or SAFE_ID.fullmatch(run_id) is None:
        raise ValueError("package/run ID invalid")
    if packet_size is not None and (
        not isinstance(packet_size, int) or isinstance(packet_size, bool) or packet_size < 1
    ):
        raise ValueError("packet size must be a positive integer or null for risk profiling")
    if not isinstance(rows, list) or len(rows) < 2:
        raise ValueError("Phase-2 challenge design requires at least two real rows")
    seen: set[str] = set()
    for row in rows:
        handoff_id = row.get("handoff_id") if isinstance(row, dict) else None
        if not isinstance(handoff_id, str) or SAFE_ID.fullmatch(handoff_id) is None or handoff_id in seen:
            raise ValueError(f"Phase-2 row ID invalid/duplicate: {handoff_id!r}")
        seen.add(handoff_id)
    infer_handoff_id_width(list(seen))
    corpus_size = len(rows)

    def safe_limit(limit: int) -> int:
        result = min(limit, corpus_size - 1)
        while result > 0 and max(1, (result * 5 + 99) // 100) > corpus_size - result:
            result -= 1
        if result < 1:
            raise ValueError("no packet size leaves a host-private challenge parent")
        return result

    reverse_rows = list(reversed(rows))
    groups: list[list[dict[str, Any]]] = []
    if packet_size is not None:
        limit = safe_limit(packet_size)
        groups = [reverse_rows[start:start + limit] for start in range(0, corpus_size, limit)]
        packetization = {"method": "fixed_reverse_contiguous", "fixed_size": limit}
    else:
        current: list[dict[str, Any]] = []
        current_class = ""
        current_limit = 0
        for row in reverse_rows:
            row_class, row_limit = packet_profile(row)
            row_limit = safe_limit(row_limit)
            candidate_limit = min(current_limit, row_limit) if current else row_limit
            if current and (row_class != current_class or len(current) >= candidate_limit):
                groups.append(current)
                current = []
                candidate_limit = row_limit
            if not current:
                current_class = row_class
                current_limit = row_limit
            else:
                current_limit = candidate_limit
            current.append(row)
        if current:
            groups.append(current)
        packetization = {
            "method": "risk_profiled_reverse_contiguous",
            "limits": {"high_risk": 30, "dialogue": 60, "ui": 100, "identity_ui": 120},
        }

    packets: list[dict[str, Any]] = []
    for packet_rows in groups:
        packet_id = f"p2-{len(packets) + 1:05d}"
        packets.append({
            "packet_id": packet_id,
            "real_handoff_ids": [row["handoff_id"] for row in packet_rows],
            "real_prompt_rows_sha256": digest(canonical(packet_rows)),
            "challenge_slots": max(1, (len(packet_rows) * 5 + 99) // 100),
        })
    return {
        "schema": SCHEDULE_SCHEMA,
        "package_id": package_id,
        "run_id": run_id,
        "phase": PHASE,
        "packetization": packetization,
        "challenge_policy": {
            "min_percent_per_packet": 5,
            "min_slots_per_packet": 1,
            "actual_rows_host_private": True,
        },
        "packets": packets,
        "recheck_policy": {
            "all_rewritten": True,
            "all_runtime_flagged": True,
            "all_high_risk": True,
            "accepted_sample_min_percent": 10,
            "accepted_sample_method": "stratified_deterministic",
            "accepted_sample_strata_fields": ["domain", "content_class", "translation_policy"],
            "fresh_prompts_hide_prior_decision": True,
        },
    }


def build_recheck_schedule(
    rows: list[dict[str, Any]], full_pass_decisions: list[dict[str, Any]], *,
    runtime_ids: list[str], high_risk_ids: list[str], package_id: str, run_id: str,
    parent_full_pass_path: Path, seed: bytes, packet_size: int,
) -> dict[str, Any]:
    if SAFE_ID.fullmatch(package_id) is None or SAFE_ID.fullmatch(run_id) is None:
        raise ValueError("package/run ID invalid")
    parent_full_pass_path = parent_full_pass_path.resolve()
    if not parent_full_pass_path.is_file():
        raise ValueError("full-pass parent snapshot missing")
    parent_raw = parent_full_pass_path.read_bytes()
    parent_rows = read_rows(parent_full_pass_path)
    if parent_rows != rows:
        raise ValueError("full-pass parent rows differ from supplied final rows")
    if not isinstance(seed, bytes) or len(seed) != 32:
        raise ValueError("recheck seed must contain exactly 32 bytes")
    if not isinstance(packet_size, int) or isinstance(packet_size, bool) or packet_size < 1:
        raise ValueError("packet size must be a positive integer")
    if not isinstance(rows, list) or len(rows) < 2:
        raise ValueError("fresh recheck requires at least two real rows")
    ids = [row.get("handoff_id") if isinstance(row, dict) else None for row in rows]
    if any(not isinstance(item, str) or SAFE_ID.fullmatch(item) is None for item in ids) or len(ids) != len(set(ids)):
        raise ValueError("fresh recheck row IDs invalid/duplicate")
    infer_handoff_id_width(ids)
    decision_ids = [item.get("handoff_id") if isinstance(item, dict) else None for item in full_pass_decisions]
    if decision_ids != ids:
        raise ValueError("full-pass decision order must equal exact canonical row order")
    actions = [item.get("action") for item in full_pass_decisions]
    if any(action == "needs_context" for action in actions):
        raise ValueError("full-pass unresolved decisions block fresh recheck")
    if any(action not in {"accepted", "rewritten"} for action in actions):
        raise ValueError("full-pass decision action invalid")
    id_set = set(ids)
    for label, values in (("runtime", runtime_ids), ("high-risk", high_risk_ids)):
        if not isinstance(values, list) or len(values) != len(set(values)) or any(item not in id_set for item in values):
            raise ValueError(f"{label} recheck IDs invalid")

    rewritten = [handoff_id for handoff_id, action in zip(ids, actions, strict=True) if action == "rewritten"]
    accepted = [handoff_id for handoff_id, action in zip(ids, actions, strict=True) if action == "accepted"]
    row_map = {row["handoff_id"]: row for row in rows}
    strata: dict[tuple[str, str, str], list[str]] = {}
    for handoff_id in accepted:
        row = row_map[handoff_id]
        domain = row.get("domain", "")
        content_class = row.get("content_class", "")
        translation_policy = row.get("translation_policy", "")
        if not all(isinstance(value, str) for value in (domain, content_class, translation_policy)):
            raise ValueError(f"recheck stratum fields invalid: {handoff_id}")
        strata.setdefault((domain, content_class, translation_policy), []).append(handoff_id)
    accepted_sample: list[str] = []
    for stratum, stratum_ids in sorted(strata.items()):
        count = max(1, (len(stratum_ids) * 10 + 99) // 100)
        ordered = sorted(
            stratum_ids,
            key=lambda item: keyed(seed, "recheck-sample", package_id, run_id, *stratum, item),
        )
        accepted_sample.extend(ordered[:count])
    required = set(rewritten) | set(runtime_ids) | set(high_risk_ids) | set(accepted_sample)
    if len(required) < 2:
        extras = [item for item in accepted if item not in required]
        extras.sort(key=lambda item: keyed(seed, "recheck-donor", package_id, run_id, item))
        if not extras:
            raise ValueError("fresh recheck cannot allocate two selected rows")
        accepted_sample.append(extras[0])
        required.add(extras[0])
    selected = [handoff_id for handoff_id in ids if handoff_id in required]
    selected_rows = [row_map[handoff_id] for handoff_id in selected]
    safe_packet_size = min(packet_size, len(selected_rows) - 1)
    while max(1, (safe_packet_size * 5 + 99) // 100) > len(selected_rows) - safe_packet_size:
        safe_packet_size -= 1
    if safe_packet_size < 1:
        raise ValueError("fresh recheck packet cannot retain a private challenge parent")
    reverse_rows = list(reversed(selected_rows))
    packets: list[dict[str, Any]] = []
    for start in range(0, len(reverse_rows), safe_packet_size):
        packet_rows = reverse_rows[start:start + safe_packet_size]
        packets.append({
            "packet_id": f"p2r-{len(packets) + 1:05d}",
            "real_handoff_ids": [row["handoff_id"] for row in packet_rows],
            "real_prompt_rows_sha256": digest(canonical(packet_rows)),
            "challenge_slots": max(1, (len(packet_rows) * 5 + 99) // 100),
        })
    return {
        "schema": RECHECK_SCHEDULE_SCHEMA,
        "package_id": package_id,
        "run_id": run_id,
        "phase": PHASE,
        "parent_full_pass": {
            "path": str(parent_full_pass_path),
            "sha256": digest(parent_raw),
            "row_count": len(parent_rows),
        },
        "challenge_policy": {
            "min_percent_per_packet": 5,
            "min_slots_per_packet": 1,
            "actual_rows_host_private": True,
        },
        "recheck_policy": {
            "all_rewritten": True,
            "all_runtime_flagged": True,
            "all_high_risk": True,
            "accepted_sample_min_percent": 10,
            "accepted_sample_method": "stratified_deterministic",
            "accepted_sample_strata_fields": ["domain", "content_class", "translation_policy"],
            "fresh_prompts_hide_prior_decision": True,
        },
        "selection": {
            "rewritten_handoff_ids": rewritten,
            "runtime_handoff_ids": list(runtime_ids),
            "high_risk_handoff_ids": list(high_risk_ids),
            "accepted_sample_handoff_ids": accepted_sample,
            "selected_handoff_ids": selected,
            "selected_handoff_ids_sha256": digest(canonical(selected)),
            "accepted_real_count": len(accepted),
            "accepted_sample_minimum": (len(accepted) * 10 + 99) // 100,
        },
        "packets": packets,
    }


def validate_inputs(
    schedule: dict[str, Any], rows: list[dict[str, Any]], package_id: str,
    run_id: str, manifest_sha256: str, seed: bytes,
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    schedule_schema = schedule.get("schema")
    if schedule_schema not in {SCHEDULE_SCHEMA, RECHECK_SCHEDULE_SCHEMA} or schedule.get("phase") != PHASE:
        raise ValueError("Phase-2 schedule schema/phase invalid")
    if schedule.get("package_id") != package_id or schedule.get("run_id") != run_id:
        raise ValueError("Phase-2 schedule package/run mismatch")
    if SAFE_ID.fullmatch(package_id) is None or SAFE_ID.fullmatch(run_id) is None:
        raise ValueError("package/run ID invalid")
    if HEX64.fullmatch(manifest_sha256) is None:
        raise ValueError("manifest SHA-256 invalid")
    if not isinstance(seed, bytes) or len(seed) != 32:
        raise ValueError("challenge seed must contain exactly 32 bytes")
    policy = schedule.get("challenge_policy")
    if policy != {
        "min_percent_per_packet": 5,
        "min_slots_per_packet": 1,
        "actual_rows_host_private": True,
    }:
        raise ValueError("Phase-2 challenge policy invalid")
    recheck = schedule.get("recheck_policy")
    required_recheck = {
        "all_rewritten": True,
        "all_runtime_flagged": True,
        "all_high_risk": True,
        "accepted_sample_min_percent": 10,
        "accepted_sample_method": "stratified_deterministic",
        "accepted_sample_strata_fields": ["domain", "content_class", "translation_policy"],
        "fresh_prompts_hide_prior_decision": True,
    }
    if not isinstance(recheck, dict) or any(recheck.get(key) != value for key, value in required_recheck.items()):
        raise ValueError("Phase-2 recheck policy invalid")
    if not isinstance(rows, list) or not rows:
        raise ValueError("Phase-2 rows missing")
    if schedule_schema == RECHECK_SCHEDULE_SCHEMA:
        parent = schedule.get("parent_full_pass")
        if not isinstance(parent, dict) or set(parent) != {"path", "sha256", "row_count"}:
            raise ValueError("fresh recheck parent descriptor invalid")
        parent_path = Path(parent["path"]).resolve() if isinstance(parent.get("path"), str) else None
        if (
            parent_path is None or not parent_path.is_file()
            or not isinstance(parent.get("sha256"), str) or HEX64.fullmatch(parent["sha256"]) is None
            or digest(parent_path.read_bytes()) != parent["sha256"]
            or parent.get("row_count") != len(rows)
            or read_rows(parent_path) != rows
        ):
            raise ValueError("fresh recheck parent snapshot mismatch")
    row_map: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Phase-2 row invalid")
        handoff_id = row.get("handoff_id")
        source = row.get("source")
        target = row.get("current_translation_vi")
        if (
            not isinstance(handoff_id, str) or SAFE_ID.fullmatch(handoff_id) is None
            or handoff_id in row_map or not isinstance(source, str)
            or not isinstance(target, str) or not target
        ):
            raise ValueError(f"Phase-2 row fields invalid: {handoff_id!r}")
        parse_tokens(row.get("protected_tokens"), handoff_id)
        row_map[handoff_id] = dict(row)
    infer_handoff_id_width(list(row_map))
    packets = schedule.get("packets")
    if not isinstance(packets, list) or not packets:
        raise ValueError("Phase-2 schedule packets missing")
    seen_packets: set[str] = set()
    ordered_real_ids: list[str] = []
    for packet in packets:
        if not isinstance(packet, dict):
            raise ValueError("Phase-2 packet invalid")
        packet_id = packet.get("packet_id")
        real_ids = packet.get("real_handoff_ids")
        slots = packet.get("challenge_slots")
        if not isinstance(packet_id, str) or SAFE_ID.fullmatch(packet_id) is None or packet_id in seen_packets:
            raise ValueError("Phase-2 packet ID invalid/duplicate")
        if (
            not isinstance(real_ids, list) or not real_ids
            or any(not isinstance(item, str) or item not in row_map for item in real_ids)
            or len(set(real_ids)) != len(real_ids)
        ):
            raise ValueError(f"Phase-2 real IDs invalid: {packet_id}")
        minimum_slots = max(1, (len(real_ids) * 5 + 99) // 100)
        if not isinstance(slots, int) or isinstance(slots, bool) or slots < minimum_slots:
            raise ValueError(f"Phase-2 challenge slots below policy: {packet_id}")
        real_rows = [row_map[item] for item in real_ids]
        if digest(canonical(real_rows)) != packet.get("real_prompt_rows_sha256"):
            raise ValueError(f"Phase-2 prompt rows hash mismatch: {packet_id}")
        seen_packets.add(packet_id)
        ordered_real_ids.extend(real_ids)
    if len(ordered_real_ids) != len(set(ordered_real_ids)):
        raise ValueError("Phase-2 schedule real-row partition overlap")
    if schedule_schema == SCHEDULE_SCHEMA:
        expected_ids = list(reversed(list(row_map)))
    else:
        selection = schedule.get("selection")
        if not isinstance(selection, dict) or not isinstance(selection.get("selected_handoff_ids"), list):
            raise ValueError("Phase-2 recheck selection missing")
        expected_ids = list(reversed(selection["selected_handoff_ids"]))
        if any(item not in row_map for item in expected_ids):
            raise ValueError("Phase-2 recheck selected row absent from release rows")
    if ordered_real_ids != expected_ids:
        raise ValueError("Phase-2 schedule real-row partition mismatch")
    return row_map, packets


def build_overlay(
    schedule: dict[str, Any], rows: list[dict[str, Any]], package_id: str,
    run_id: str, manifest_sha256: str, seed: bytes,
) -> dict[str, Any]:
    row_map, packets = validate_inputs(schedule, rows, package_id, run_id, manifest_sha256, seed)
    all_ids = list(row_map)
    release_ids = set(all_ids)
    id_width = infer_handoff_id_width(all_ids)
    total_challenges = sum(packet["challenge_slots"] for packet in packets)
    if id_width <= 4:
        synthetic_pool = [f"{value:0{id_width}x}" for value in range(16 ** id_width) if f"{value:0{id_width}x}" not in release_ids]
        synthetic_pool.sort(key=lambda item: keyed(seed, "challenge-id-pool", package_id, run_id, item))
        if len(synthetic_pool) < total_challenges:
            raise ValueError("fixed-width handoff ID space cannot hold private challenges")
    else:
        synthetic_pool = []
    used_challenges: set[str] = set()
    generated: dict[str, list[dict[str, Any]]] = {}
    donor_scope = (
        set(schedule["selection"]["selected_handoff_ids"])
        if schedule.get("schema") == RECHECK_SCHEDULE_SCHEMA
        else set(row_map)
    )
    donor_order = sorted(
        (
            handoff_id for handoff_id, row in row_map.items()
            if handoff_id in donor_scope
            and row.get("translation_policy") == "keep_identity"
            and row.get("current_translation_vi") == row.get("source")
            and isinstance(row.get("source"), str)
            and bool(row["source"].strip())
            and row["source"] not in CHALLENGE_DONOR_SOURCE_EXCLUSIONS
            and not is_mandatory_rewrite(row)
        ),
        key=lambda item: keyed(seed, "donor-order", package_id, run_id, item),
    )
    if not donor_order:
        raise ValueError("no clean keep_identity rows available for prompt-derivable challenge donors")
    swap_order = sorted(rows, key=lambda item: keyed(seed, "swap-order", package_id, run_id, item["handoff_id"]))
    donor_cursor = 0

    # Constrained packets first prevents a large packet from losing its small donor pool.
    assignment_order = sorted(packets, key=lambda item: (len(all_ids) - len(item["real_handoff_ids"]), item["packet_id"]))
    for packet in assignment_order:
        packet_id = packet["packet_id"]
        packet_ids = set(packet["real_handoff_ids"])
        packet_donors: set[str] = set()
        visible_targets = {row_map[item]["current_translation_vi"] for item in packet_ids}
        entries: list[dict[str, Any]] = []
        for slot in range(packet["challenge_slots"]):
            donor_id: str | None = None
            for _attempt in range(len(donor_order)):
                candidate = donor_order[donor_cursor % len(donor_order)]
                donor_cursor += 1
                if candidate not in packet_ids and candidate not in packet_donors:
                    donor_id = candidate
                    break
            if donor_id is None:
                raise ValueError(f"no eligible private corruption donor outside packet: {packet_id}")
            donor = row_map[donor_id]
            options = corruptions(donor, swap_order, visible_targets)
            if not options:
                raise ValueError(f"no deterministic corruption possible: {donor_id}")
            options.sort(key=lambda item: keyed(seed, "corruption", package_id, run_id, packet_id, str(slot), item[0], item[1]))
            kind, corrupted_target, swap_id = options[0]
            if synthetic_pool:
                challenge_id = synthetic_pool.pop()
            else:
                for counter in range(100_000):
                    challenge_id = keyed(seed, "challenge-id", package_id, run_id, packet_id, str(slot), str(counter)).hex()[:id_width]
                    if challenge_id not in release_ids and challenge_id not in used_challenges:
                        break
                else:
                    raise ValueError("unable to allocate an indistinguishable private challenge ID")
            prompt_row = dict(donor)
            prompt_row["handoff_id"] = challenge_id
            prompt_row["current_translation_vi"] = corrupted_target
            entry: dict[str, Any] = {
                "handoff_id": challenge_id,
                "derived_from_handoff_id": donor_id,
                "prompt_row": prompt_row,
                "expected_target_sha256": digest(donor["source"].encode("utf-8")),
                "expected_target_derivation": "prompt_source_keep_identity",
                "corruption_kind": kind,
            }
            if swap_id is not None:
                entry["corruption_source_handoff_id"] = swap_id
            entries.append(entry)
            packet_donors.add(donor_id)
            used_challenges.add(challenge_id)
        generated[packet_id] = entries

    overlay = {
        "schema": SCHEMA,
        "package_id": package_id,
        "run_id": run_id,
        "manifest_sha256": manifest_sha256,
        "generation": {
            "algorithm": "hmac-sha256/v1",
            "seed_hex": seed.hex(),
            "seed_sha256": digest(seed),
            "parent_visibility": "outside-current-packet",
        },
        "packets": {packet["packet_id"]: generated[packet["packet_id"]] for packet in packets},
    }
    return overlay


def build_prompt(
    schedule: dict[str, Any], rows: list[dict[str, Any]], overlay: dict[str, Any], packet_id: str,
) -> dict[str, Any]:
    generation = overlay.get("generation") if isinstance(overlay, dict) else None
    seed_hex = generation.get("seed_hex") if isinstance(generation, dict) else None
    if not isinstance(seed_hex, str):
        raise ValueError("challenge overlay seed missing")
    try:
        seed = bytes.fromhex(seed_hex)
    except ValueError as error:
        raise ValueError("challenge overlay seed invalid") from error
    package_id = overlay.get("package_id")
    run_id = overlay.get("run_id")
    manifest_sha256 = overlay.get("manifest_sha256")
    if not isinstance(package_id, str) or not isinstance(run_id, str) or not isinstance(manifest_sha256, str):
        raise ValueError("challenge overlay identity invalid")
    expected_overlay = build_overlay(schedule, rows, package_id, run_id, manifest_sha256, seed)
    if canonical(expected_overlay) != canonical(overlay):
        raise ValueError("challenge overlay differs from deterministic materialization")
    row_map = {row["handoff_id"]: row for row in rows}
    matching = [item for item in schedule["packets"] if item["packet_id"] == packet_id]
    if len(matching) != 1:
        raise ValueError("Phase-2 prompt packet absent/duplicate")
    packet = matching[0]
    real_rows = [dict(row_map[item]) for item in packet["real_handoff_ids"]]
    challenges = overlay["packets"][packet_id]
    slots: dict[int, list[dict[str, Any]]] = {}
    for item in challenges:
        if len(real_rows) > 1:
            position = 1 + int.from_bytes(
                keyed(seed, "prompt-position", package_id, run_id, packet_id, item["handoff_id"]), "big",
            ) % (len(real_rows) - 1)
        else:
            position = int.from_bytes(
                keyed(seed, "prompt-position", package_id, run_id, packet_id, item["handoff_id"]), "big",
            ) % 2
        slots.setdefault(position, []).append(dict(item["prompt_row"]))
    for position, values in slots.items():
        values.sort(key=lambda row: keyed(seed, "prompt-order", package_id, run_id, packet_id, str(position), row["handoff_id"]))
    prompt_rows: list[dict[str, Any]] = []
    for position in range(len(real_rows) + 1):
        prompt_rows.extend(slots.get(position, []))
        if position < len(real_rows):
            prompt_rows.append(real_rows[position])
    return {
        "schema": "agy-review-prompt/v2",
        "package_id": package_id,
        "run_id": run_id,
        "phase": PHASE,
        "batch_id": packet_id,
        "rows": prompt_rows,
    }


def materialize_prompt(output: Path, prompt: dict[str, Any]) -> dict[str, Any]:
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = canonical(prompt)
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
    if readback != payload or json.loads(readback.decode("utf-8")) != prompt:
        raise RuntimeError("semantic prompt atomic readback mismatch")
    return {
        "schema": "agy-phase2-prompt-materialization-receipt/v1",
        "prompt_path": str(output),
        "prompt_sha256": digest(readback),
        "batch_id": prompt["batch_id"],
        "row_count": len(prompt["rows"]),
    }


def materialize_schedule(output: Path, schedule: dict[str, Any]) -> dict[str, Any]:
    if schedule.get("schema") not in {SCHEDULE_SCHEMA, RECHECK_SCHEDULE_SCHEMA}:
        raise ValueError("Phase-2 schedule schema invalid")
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(schedule, ensure_ascii=False, indent=2).encode("utf-8") + b"\n"
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
    if readback != payload or json.loads(readback.decode("utf-8")) != schedule:
        raise RuntimeError("Phase-2 schedule atomic readback mismatch")
    return {
        "schema": "agy-phase2-schedule-materialization-receipt/v1",
        "schedule_path": str(output),
        "schedule_sha256": digest(readback),
        "schedule_schema": schedule["schema"],
        "packet_count": len(schedule["packets"]),
    }


def materialize_overlay(output: Path, overlay: dict[str, Any]) -> dict[str, Any]:
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(overlay, ensure_ascii=False, indent=2).encode("utf-8") + b"\n"
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
    if readback != payload or json.loads(readback.decode("utf-8")) != overlay:
        raise RuntimeError("challenge overlay atomic readback mismatch")
    return {
        "schema": "agy-phase2-challenge-materialization-receipt/v1",
        "overlay_path": str(output),
        "overlay_sha256": digest(readback),
        "challenge_count": sum(len(entries) for entries in overlay["packets"].values()),
        "seed_sha256": overlay["generation"]["seed_sha256"],
    }


def read_rows(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return [dict(row) for row in csv.DictReader(stream)]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Materialize host-private Phase-2 challenges.")
    parser.add_argument("--schedule", type=Path, required=True)
    parser.add_argument("--rows-csv", type=Path, required=True)
    parser.add_argument("--package-id", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--manifest-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seed-hex")
    args = parser.parse_args(argv)
    seed = bytes.fromhex(args.seed_hex) if args.seed_hex else secrets.token_bytes(32)
    schedule = json.loads(args.schedule.read_text(encoding="utf-8-sig"))
    overlay = build_overlay(
        schedule, read_rows(args.rows_csv), args.package_id, args.run_id,
        args.manifest_sha256, seed,
    )
    receipt = materialize_overlay(args.output, overlay)
    print(json.dumps(receipt, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as error:
        print(f"FAIL: {type(error).__name__}: {error}", file=sys.stderr)
        raise SystemExit(1)
