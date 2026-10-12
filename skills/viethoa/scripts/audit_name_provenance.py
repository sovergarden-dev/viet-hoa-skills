#!/usr/bin/env python
"""Validate a viethoa name-provenance policy and ledger with only stdlib."""
from __future__ import annotations

import argparse
import csv
import json
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any

SCHEMA = "viethoa-name-provenance-policy/v1"
HEADERS = [
    "entity_id",
    "source_form",
    "source_script_or_language",
    "project_origin_country",
    "authorial_origin_country",
    "native_authoritative_form",
    "vi_canonical_form",
    "decision_basis",
    "evidence",
    "locked",
    "scope",
    "notes",
]
BASES = {
    "user_lock",
    "creator_official",
    "native_official",
    "national_standard",
    "established_original_market",
    "contextual_vietnamese_convention",
    "needs_review",
}


def _nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _load_policy(path: Path, errors: list[str]) -> dict[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"policy unreadable: {exc}")
        return {}
    if not isinstance(raw, dict):
        errors.append("policy must be a JSON object")
        return {}
    return raw


def validate(
    policy_path: Path,
    ledger_path: Path | None = None,
    *,
    require_resolved: bool = False,
    require_complete: bool = False,
) -> dict[str, Any]:
    errors: list[str] = []
    policy = _load_policy(policy_path, errors)
    for key in (
        "project",
        "project_origin_country",
        "primary_authorial_language",
        "default_name_rule",
        "english_localization_role",
        "ledger_path",
        "audit_status",
    ):
        if not _nonempty(policy.get(key)):
            errors.append(f"policy.{key} must be a non-empty string")
    if policy.get("schema") != SCHEMA:
        errors.append(f"policy.schema must be {SCHEMA!r}")
    if policy.get("default_name_rule") != "creator_or_original_market_canonical_form":
        errors.append("policy.default_name_rule must preserve original-market authority")
    if policy.get("english_localization_role") != "reference_only_not_name_authority":
        errors.append("policy.english_localization_role must keep English reference-only")
    evidence = policy.get("origin_evidence")
    if not isinstance(evidence, list) or not evidence:
        errors.append("policy.origin_evidence must be a non-empty list")
    elif any(not isinstance(item, dict) or not _nonempty(item.get("locator")) for item in evidence):
        errors.append("every origin_evidence entry needs a non-empty locator")

    declared = policy_path.parent / str(policy.get("ledger_path", ""))
    actual = ledger_path or declared
    if ledger_path is not None and declared and declared.resolve() != ledger_path.resolve():
        errors.append("--ledger does not match policy.ledger_path")

    rows: list[dict[str, str]] = []
    try:
        with actual.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames != HEADERS:
                errors.append(f"ledger header must be exactly {','.join(HEADERS)}")
            else:
                rows = list(reader)
    except OSError as exc:
        errors.append(f"ledger unreadable: {exc}")

    seen: set[str] = set()
    needs_review = 0
    locked = 0
    for number, row in enumerate(rows, start=2):
        prefix = f"ledger row {number}"
        entity_id = row.get("entity_id", "").strip()
        if not entity_id:
            errors.append(f"{prefix}: entity_id is required")
        elif entity_id in seen:
            errors.append(f"{prefix}: duplicate entity_id {entity_id!r}")
        seen.add(entity_id)
        for field in (
            "source_form",
            "source_script_or_language",
            "project_origin_country",
            "authorial_origin_country",
            "decision_basis",
            "evidence",
            "scope",
        ):
            if not row.get(field, "").strip():
                errors.append(f"{prefix}: {field} is required")
        if row.get("project_origin_country", "").strip() != str(policy.get("project_origin_country", "")).strip():
            errors.append(f"{prefix}: project_origin_country must match policy")
        basis = row.get("decision_basis", "").strip()
        if basis not in BASES:
            errors.append(f"{prefix}: unknown decision_basis {basis!r}")
        is_locked = row.get("locked", "").strip().lower()
        if is_locked not in {"true", "false"}:
            errors.append(f"{prefix}: locked must be true or false")
        elif is_locked == "true":
            locked += 1
        if basis == "needs_review":
            needs_review += 1
            if is_locked != "false":
                errors.append(f"{prefix}: needs_review must be unlocked")
        else:
            for field in ("native_authoritative_form", "vi_canonical_form"):
                if not row.get(field, "").strip():
                    errors.append(f"{prefix}: {field} is required for resolved entries")
            if is_locked != "true":
                errors.append(f"{prefix}: resolved entries must be locked")
    if require_resolved and needs_review:
        errors.append(f"ledger has {needs_review} needs_review entries")
    if require_complete and policy.get("audit_status") != "complete":
        errors.append("policy.audit_status must be 'complete' for release")

    return {
        "ok": not errors,
        "policy": str(policy_path),
        "ledger": str(actual),
        "rows": len(rows),
        "locked": locked,
        "needs_review": needs_review,
        "errors": errors,
    }


def self_test() -> int:
    with tempfile.TemporaryDirectory(prefix="name-provenance-") as directory:
        root = Path(directory)
        policy = root / "policy.json"
        ledger = root / "ledger.csv"
        policy.write_text(
            json.dumps(
                {
                    "schema": SCHEMA,
                    "project": "fixture",
                    "project_origin_country": "Japan",
                    "primary_authorial_language": "ja",
                    "origin_evidence": [{"locator": "fixture"}],
                    "default_name_rule": "creator_or_original_market_canonical_form",
                    "english_localization_role": "reference_only_not_name_authority",
                    "ledger_path": "ledger.csv",
                    "audit_status": "complete",
                }
            ),
            encoding="utf-8",
        )
        with ledger.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=HEADERS)
            writer.writeheader()
            writer.writerow(
                {
                    "entity_id": "jp-name",
                    "source_form": "イキルカ・シヌカ",
                    "source_script_or_language": "ja",
                    "project_origin_country": "Japan",
                    "authorial_origin_country": "Japan",
                    "native_authoritative_form": "イキルカ・シヌカ",
                    "vi_canonical_form": "Ikiruka Shinuka",
                    "decision_basis": "national_standard",
                    "evidence": "fixture",
                    "locked": "true",
                    "scope": "global",
                    "notes": "fixture",
                }
            )
        good = validate(policy, require_resolved=True, require_complete=True)
        assert good["ok"], good
        with ledger.open("a", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=HEADERS)
            writer.writerow(
                {
                    "entity_id": "unresolved",
                    "source_form": "X",
                    "source_script_or_language": "ja",
                    "project_origin_country": "Japan",
                    "authorial_origin_country": "Japan",
                    "native_authoritative_form": "",
                    "vi_canonical_form": "",
                    "decision_basis": "needs_review",
                    "evidence": "fixture",
                    "locked": "false",
                    "scope": "global",
                    "notes": "fixture",
                }
            )
        bad = validate(policy, require_resolved=True)
        assert not bad["ok"] and bad["needs_review"] == 1, bad
    print(json.dumps({"ok": True, "self_test": "passed"}))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy", type=Path)
    parser.add_argument("--ledger", type=Path)
    parser.add_argument("--require-resolved", action="store_true")
    parser.add_argument("--require-complete", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        return self_test()
    if args.policy is None:
        parser.error("--policy is required unless --self-test is used")
    report = validate(
        args.policy,
        args.ledger,
        require_resolved=args.require_resolved,
        require_complete=args.require_complete,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
