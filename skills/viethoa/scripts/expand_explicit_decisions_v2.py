from __future__ import annotations

import argparse
import csv
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any

OUTPUT_FIELDS = [
    "handoff_id", "domain", "key", "translation_vi", "review_action",
    "review_codes", "reason_codes", "notes",
]
TOP_LEVEL_FIELDS = {"schema", "batch_id", "prompt_sha256", "decisions"}
REVIEW_CODES = {
    "source_fidelity", "context_fit", "natural_vi", "glossary_policy",
    "tokens_format", "ui_fit", "keep_identity", "proper_noun_policy",
}
HEX64 = re.compile(r"[0-9a-f]{64}")


def read_batch(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows or not {"handoff_id", "domain", "key", "current_translation_vi"} <= set(rows[0]):
        raise ValueError("batch is empty or missing required columns")
    ids = [row["handoff_id"] for row in rows]
    if any(not value for value in ids) or len(ids) != len(set(ids)):
        raise ValueError("batch handoff_id values must be nonblank and unique")
    return rows


def load_decisions(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_bytes().decode("utf-8"))
    if not isinstance(value, dict) or set(value) != TOP_LEVEL_FIELDS:
        raise ValueError("v2 response has wrong top-level fields")
    if value["schema"] != "agy-explicit-review/v2":
        raise ValueError("v2 response schema mismatch")
    if not isinstance(value["batch_id"], str) or not value["batch_id"]:
        raise ValueError("v2 response batch_id missing")
    if not isinstance(value["prompt_sha256"], str) or HEX64.fullmatch(value["prompt_sha256"]) is None:
        raise ValueError("v2 response prompt_sha256 invalid")
    if not isinstance(value["decisions"], list):
        raise ValueError("v2 response decisions must be an array")
    return value


def validate_decisions(value: dict[str, Any], rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    decisions = value["decisions"]
    input_ids = [row["handoff_id"] for row in rows]
    output_ids = [item.get("handoff_id") if isinstance(item, dict) else None for item in decisions]
    if output_ids != input_ids:
        raise ValueError("v2 decision partition/order must equal exact input order")
    validated: list[dict[str, Any]] = []
    for item in decisions:
        handoff_id = item["handoff_id"]
        action = item.get("action")
        if action == "accepted":
            if set(item) != {"handoff_id", "action", "review_codes", "notes"}:
                raise ValueError(f"accepted fields invalid: {handoff_id}")
            codes = item["review_codes"]
            if not isinstance(codes, list) or len(codes) < 3 or len(codes) != len(set(codes)) or not set(codes) <= REVIEW_CODES:
                raise ValueError(f"accepted review_codes invalid: {handoff_id}")
            if not isinstance(item["notes"], str):
                raise ValueError(f"accepted notes invalid: {handoff_id}")
        elif action == "rewritten":
            if set(item) != {"handoff_id", "action", "translation_vi", "reason_codes", "notes"}:
                raise ValueError(f"rewritten fields invalid: {handoff_id}")
            if not isinstance(item["translation_vi"], str) or not item["translation_vi"].strip():
                raise ValueError(f"rewritten target blank: {handoff_id}")
            reasons = item["reason_codes"]
            if not isinstance(reasons, list) or not reasons or not all(isinstance(reason, str) and reason for reason in reasons):
                raise ValueError(f"rewritten reason_codes invalid: {handoff_id}")
            if not isinstance(item["notes"], str):
                raise ValueError(f"rewritten notes invalid: {handoff_id}")
        elif action == "needs_context":
            if set(item) != {"handoff_id", "action", "question"}:
                raise ValueError(f"needs_context fields invalid: {handoff_id}")
            if not isinstance(item["question"], str) or not item["question"].strip():
                raise ValueError(f"needs_context question blank: {handoff_id}")
        else:
            raise ValueError(f"unknown action: {handoff_id}")
        validated.append(item)
    return validated


def expand(batch_path: Path, response_path: Path, output_path: Path) -> None:
    rows = read_batch(batch_path)
    decisions = validate_decisions(load_decisions(response_path), rows)
    output: list[dict[str, str]] = []
    for row, item in zip(rows, decisions, strict=True):
        action = item["action"]
        if action == "accepted":
            target = row["current_translation_vi"]
            if not target:
                raise ValueError(f"accepted current target is blank: {row['handoff_id']}")
            review_codes = item["review_codes"]
            reason_codes: list[str] = []
            notes = item["notes"]
        elif action == "rewritten":
            target = item["translation_vi"]
            if target == row["current_translation_vi"]:
                raise ValueError(f"rewritten target is unchanged: {row['handoff_id']}")
            review_codes = []
            reason_codes = item["reason_codes"]
            notes = item["notes"]
        else:
            target = ""
            review_codes = []
            reason_codes = []
            notes = item["question"].strip()
        output.append({
            "handoff_id": row["handoff_id"],
            "domain": row["domain"],
            "key": row["key"],
            "translation_vi": target,
            "review_action": action,
            "review_codes": json.dumps(review_codes, ensure_ascii=False, separators=(",", ":")),
            "reason_codes": json.dumps(reason_codes, ensure_ascii=False, separators=(",", ":")),
            "notes": notes,
        })

    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_name(f".{output_path.name}.{os.getpid()}.tmp")
    with temporary.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_FIELDS)
        writer.writeheader()
        writer.writerows(output)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, output_path)
    with output_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reread = list(csv.DictReader(handle))
    if [row["handoff_id"] for row in reread] != [row["handoff_id"] for row in rows]:
        raise ValueError("v2 output readback identity/order mismatch")


def self_test() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        batch = root / "batch.csv"
        response = root / "response.json"
        output = root / "output.csv"
        with batch.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=["handoff_id", "domain", "key", "current_translation_vi"])
            writer.writeheader()
            writer.writerows([
                {"handoff_id": "a", "domain": "d", "key": "1", "current_translation_vi": "Giữ"},
                {"handoff_id": "b", "domain": "d", "key": "2", "current_translation_vi": "Cũ"},
            ])
        response.write_text(json.dumps({
            "schema": "agy-explicit-review/v2", "batch_id": "p2-1", "prompt_sha256": "a" * 64,
            "decisions": [
                {"handoff_id": "a", "action": "accepted", "review_codes": ["source_fidelity", "context_fit", "natural_vi"], "notes": ""},
                {"handoff_id": "b", "action": "rewritten", "translation_vi": "Mới", "reason_codes": ["fidelity"], "notes": ""},
            ],
        }, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        expand(batch, response, output)
        with output.open("r", encoding="utf-8-sig", newline="") as handle:
            result = list(csv.DictReader(handle))
        assert [row["review_action"] for row in result] == ["accepted", "rewritten"]
    print("SELF-TEST PASS: v2 per-row decisions, expansion, atomic write, readback")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("batch", nargs="?", type=Path)
    parser.add_argument("response", nargs="?", type=Path)
    parser.add_argument("output", nargs="?", type=Path)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return
    if not all((args.batch, args.response, args.output)):
        parser.error("batch response output are required unless --self-test is used")
    expand(args.batch, args.response, args.output)


if __name__ == "__main__":
    main()
