from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any

ACCEPTANCE_SCHEMA = "agy-phase1-partial-acceptance-parent/v1"


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def read_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"{label} unreadable: {path}") from error
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    return value


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), [dict(row) for row in reader]


def edge_whitespace(text: str) -> tuple[str, str]:
    left = text[: len(text) - len(text.lstrip())]
    right = text[len(text.rstrip()):] if text.rstrip() != text else ""
    return left, right


def json_string_list(value: str, label: str) -> list[str]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as error:
        raise ValueError(f"{label} is not JSON") from error
    if not isinstance(parsed, list) or not all(isinstance(item, str) for item in parsed):
        raise ValueError(f"{label} must be a string array")
    return parsed


def classify_row(source: dict[str, str], decision: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    if decision.get("handoff_id") != source.get("handoff_id"):
        reasons.append("handoff_id_mismatch")
    target = decision.get("translation_vi")
    if not isinstance(target, str):
        return reasons + ["target_not_string"]
    action = decision.get("review_action")
    if action not in {"translated", "provisional_needs_context"}:
        reasons.append("invalid_review_action")
    if not isinstance(decision.get("notes"), str):
        reasons.append("notes_not_string")
    original = source.get("source", "")
    if original.strip() and not target.strip():
        reasons.append("blank_target")
    policy = source.get("translation_policy")
    if policy == "keep_identity":
        if target != original:
            reasons.append("identity_mismatch")
    elif original.strip() and target == original:
        reasons.append("unexpected_source_copy")
    declared = json_string_list(source.get("protected_tokens", "[]"), "protected_tokens")
    token_counts = collections.Counter(token for token in declared if token != "__NEWLINE__")
    if any(original.count(token) != count for token, count in token_counts.items()):
        reasons.append("stale_declared_token")
    if any(target.count(token) != count for token, count in token_counts.items()):
        reasons.append("protected_token_mismatch")
    if original.count("\n") != target.count("\n"):
        reasons.append("physical_newline_mismatch")
    if edge_whitespace(original) != edge_whitespace(target):
        reasons.append("edge_whitespace_mismatch")
    locked = json_string_list(source.get("locked_english_terms", "[]"), "locked_english_terms")
    if any(original.count(term) != target.count(term) for term in locked):
        reasons.append("locked_term_mismatch")
    if "\ufffd" in target or any(0xD800 <= ord(character) <= 0xDFFF for character in target):
        reasons.append("unicode_corruption")
    return list(dict.fromkeys(reasons))


PHASE2_CARRY_BLOCKERS = {
    "handoff_id_mismatch",
    "target_not_string",
    "blank_target",
    "stale_declared_token",
    "unicode_corruption",
}


def classify_phase1_remainder_route(reason_sets: list[list[str]]) -> dict[str, Any]:
    blockers = collections.Counter(
        reason for reasons in reason_sets for reason in reasons if reason in PHASE2_CARRY_BLOCKERS
    )
    if blockers:
        return {
            "direct_phase2_eligible": False,
            "recommended_next": "reissue_phase1_exact_remainder",
            "carry_blockers": dict(sorted(blockers.items())),
        }
    return {
        "direct_phase2_eligible": True,
        "recommended_next": "await_user_direction",
        "allowed_next_routes": [
            "build_demo_patch",
            "external_phase2_antigravity",
            "hermes_cron_phase2",
            "pause",
        ],
        "carry_blockers": {},
    }


def atomic_bytes(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp-phase1-acceptance")
    with temporary.open("wb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)
    if path.read_bytes() != raw:
        raise RuntimeError(f"atomic readback mismatch: {path}")


def write_json(path: Path, value: object) -> None:
    atomic_bytes(path, (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))


def write_csv(path: Path, rows: list[dict[str, str]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp-phase1-acceptance")
    with temporary.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)
    _header, readback = read_csv(path)
    if readback != rows:
        raise RuntimeError(f"CSV readback mismatch: {path}")


def accept(
    package_root: Path,
    work_root: Path,
    return_zip: Path,
    canonical: Path,
    provenance_report: Path,
    output_root: Path,
) -> dict[str, Any]:
    package_root = package_root.resolve()
    work_root = work_root.resolve()
    return_zip = return_zip.resolve()
    canonical = canonical.resolve()
    provenance_report = provenance_report.resolve()
    output_root = output_root.resolve()
    if output_root.exists():
        raise ValueError("Phase-1 acceptance output already exists")
    manifest = read_json(package_root / "project-manifest.json", "manifest")
    receipt = read_json(work_root / "controller/snapshots/phase1-draft-receipt.json", "snapshot receipt")
    index = read_json(work_root / "controller/snapshots/phase1-draft-index.json", "decision index")
    provenance = read_json(provenance_report, "provenance report")
    if not str(provenance.get("status", "")).startswith("PASS"):
        raise ValueError("provenance report is not accepted")
    package_id = manifest.get("package_id")
    run_id = manifest.get("run_id")
    if any(value.get("package_id") != package_id or value.get("run_id") != run_id for value in (receipt, index, provenance)):
        raise ValueError("Phase-1 acceptance package/run mismatch")
    source_header, source_rows = read_csv(package_root / "input/full-corpus.csv")
    decisions = index.get("rows")
    if not isinstance(decisions, list) or len(decisions) != len(source_rows):
        raise ValueError("Phase-1 decision count mismatch")
    if [row.get("handoff_id") for row in decisions] != [row.get("handoff_id") for row in source_rows]:
        raise ValueError("Phase-1 decision order/key mismatch")
    canonical_raw = canonical.read_bytes()
    _canonical_header, canonical_rows = read_csv(canonical)
    if any(row.get("state") != "pending" or row.get("translation_vi") != "" for row in canonical_rows):
        raise ValueError("canonical is not untouched/unstarted")
    if len(canonical_rows) != len(source_rows):
        raise ValueError("canonical/source row count mismatch")
    snapshot = Path(receipt["snapshot_csv"])
    if digest(snapshot.read_bytes()) != receipt.get("snapshot_sha256") or receipt.get("row_count") != len(source_rows):
        raise ValueError("snapshot receipt mismatch")
    if digest(return_zip.read_bytes()) == "":
        raise ValueError("return ZIP hash impossible")
    output_root.mkdir(parents=True)
    raw_copy = output_root / return_zip.name
    shutil.copy2(return_zip, raw_copy)
    if raw_copy.read_bytes() != return_zip.read_bytes():
        raise RuntimeError("raw return copy mismatch")
    clean: list[dict[str, str]] = []
    remainder: list[dict[str, str]] = []
    remainder_reason_sets: list[list[str]] = []
    reason_occurrences: collections.Counter[str] = collections.Counter()
    output_fields = source_header + ["phase1_translation_vi", "phase1_review_action", "phase1_notes", "rejection_reasons"]
    for source, decision in zip(source_rows, decisions):
        reasons = classify_row(source, decision)
        output = dict(source)
        output.update({
            "phase1_translation_vi": decision["translation_vi"],
            "phase1_review_action": decision["review_action"],
            "phase1_notes": decision["notes"],
            "rejection_reasons": "|".join(reasons),
        })
        if reasons:
            remainder.append(output)
            remainder_reason_sets.append(reasons)
            reason_occurrences.update(reasons)
        else:
            clean.append(output)
    if len(clean) + len(remainder) != len(source_rows):
        raise RuntimeError("Phase-1 acceptance partition mismatch")
    phase2_route = classify_phase1_remainder_route(remainder_reason_sets)
    clean_path = output_root / "phase1-clean.csv"
    remainder_path = output_root / "phase1-remainder.csv"
    write_csv(clean_path, clean, output_fields)
    write_csv(remainder_path, remainder, output_fields)
    qa = {
        "schema": "agy-phase1-structural-qa/v1",
        "package_id": package_id,
        "run_id": run_id,
        "row_count": len(source_rows),
        "clean_rows": len(clean),
        "remainder_rows": len(remainder),
        "reason_occurrences": dict(sorted(reason_occurrences.items())),
        "unique_flagged_rows": len(remainder),
        "phase2_route": phase2_route,
        "clean_csv_sha256": digest(clean_path.read_bytes()),
        "remainder_csv_sha256": digest(remainder_path.read_bytes()),
    }
    qa_path = output_root / "phase1-structural-qa.json"
    write_json(qa_path, qa)
    parent = {
        "schema": ACCEPTANCE_SCHEMA,
        "status": "full_phase1_accepted" if not remainder else "partial_phase1_accepted_rework_required",
        "ready_for_phase2": not remainder,
        "package_id": package_id,
        "run_id": run_id,
        "manifest_sha256": digest((package_root / "project-manifest.json").read_bytes()),
        "canonical_parent_sha256": digest(canonical_raw),
        "raw_return_zip": str(raw_copy),
        "raw_return_zip_sha256": digest(raw_copy.read_bytes()),
        "source_row_count": len(source_rows),
        "clean_rows": len(clean),
        "remainder_rows": len(remainder),
        **phase2_route,
        "clean_csv": str(clean_path),
        "clean_csv_sha256": qa["clean_csv_sha256"],
        "remainder_csv": str(remainder_path),
        "remainder_csv_sha256": qa["remainder_csv_sha256"],
        "structural_qa": str(qa_path),
        "structural_qa_sha256": digest(qa_path.read_bytes()),
        "provenance_report": str(provenance_report),
        "provenance_report_sha256": digest(provenance_report.read_bytes()),
        "canonical_untouched": True,
    }
    parent_path = output_root / "phase1-partial-acceptance-parent.json"
    write_json(parent_path, parent)
    return {
        "status": parent["status"],
        "ready_for_phase2": parent["ready_for_phase2"],
        "clean_rows": len(clean),
        "remainder_rows": len(remainder),
        **phase2_route,
        "output_root": str(output_root),
        "parent": str(parent_path),
        "parent_sha256": digest(parent_path.read_bytes()),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Accept a guarded Phase-1 return into clean and deterministic remainder snapshots.")
    parser.add_argument("--package-root", required=True, type=Path)
    parser.add_argument("--work-root", required=True, type=Path)
    parser.add_argument("--return-zip", required=True, type=Path)
    parser.add_argument("--canonical", required=True, type=Path)
    parser.add_argument("--provenance-report", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        print(json.dumps(accept(args.package_root, args.work_root, args.return_zip, args.canonical, args.provenance_report, args.output_root), ensure_ascii=False, separators=(",", ":")))
        return 0
    except Exception as error:
        print(f"FAIL: {type(error).__name__}: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
