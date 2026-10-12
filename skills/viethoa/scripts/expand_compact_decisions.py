from __future__ import annotations

import argparse
import csv
import json
import os
import tempfile
from pathlib import Path
from typing import Any

OUTPUT_FIELDS = [
    "handoff_id",
    "domain",
    "key",
    "translation_vi",
    "review_action",
    "reason_codes",
    "notes",
]
TOP_LEVEL_FIELDS = {"schema", "accepted_ids", "rewritten", "needs_context"}


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
        raise ValueError("compact response has wrong top-level fields")
    if value["schema"] != "agy-explicit-review/v1":
        raise ValueError("compact response has wrong schema")
    if not all(isinstance(value[name], list) for name in ("accepted_ids", "rewritten", "needs_context")):
        raise ValueError("compact response collections must be arrays")
    return value


def index_decisions(value: dict[str, Any], input_ids: set[str]) -> dict[str, tuple[str, dict[str, Any] | None]]:
    indexed: dict[str, tuple[str, dict[str, Any] | None]] = {}

    def add(handoff_id: Any, action: str, item: dict[str, Any] | None) -> None:
        if not isinstance(handoff_id, str) or not handoff_id:
            raise ValueError(f"{action} handoff_id must be a nonblank string")
        if handoff_id in indexed:
            raise ValueError(f"duplicate decision: {handoff_id}")
        indexed[handoff_id] = (action, item)

    for handoff_id in value["accepted_ids"]:
        add(handoff_id, "accepted", None)
    for item in value["rewritten"]:
        if not isinstance(item, dict) or set(item) != {"handoff_id", "translation_vi", "reason_codes", "notes"}:
            raise ValueError("rewritten decision has wrong fields")
        target = item["translation_vi"]
        reasons = item["reason_codes"]
        if not isinstance(target, str) or not target:
            raise ValueError("rewritten translation_vi must be nonblank")
        if not isinstance(reasons, list) or not reasons or not all(isinstance(reason, str) and reason for reason in reasons):
            raise ValueError("rewritten reason_codes must be a nonempty string array")
        if not isinstance(item["notes"], str):
            raise ValueError("rewritten notes must be a string")
        add(item["handoff_id"], "rewritten", item)
    for item in value["needs_context"]:
        if not isinstance(item, dict) or set(item) != {"handoff_id", "question"}:
            raise ValueError("needs_context decision has wrong fields")
        if not isinstance(item["question"], str) or not item["question"].strip():
            raise ValueError("needs_context question must be nonblank")
        add(item["handoff_id"], "needs_context", item)

    output_ids = set(indexed)
    missing = sorted(input_ids - output_ids)
    extra = sorted(output_ids - input_ids)
    if missing or extra:
        raise ValueError(f"decision partition mismatch: missing={missing[:5]} extra={extra[:5]}")
    return indexed


def expand(batch_path: Path, response_path: Path, output_path: Path) -> None:
    rows = read_batch(batch_path)
    decisions = index_decisions(load_decisions(response_path), {row["handoff_id"] for row in rows})
    output: list[dict[str, str]] = []
    for row in rows:
        handoff_id = row["handoff_id"]
        action, item = decisions[handoff_id]
        if action == "accepted":
            target = row["current_translation_vi"]
            if not target:
                raise ValueError(f"accepted current target is blank: {handoff_id}")
            reasons = []
            notes = ""
        elif action == "rewritten":
            assert item is not None
            target = item["translation_vi"]
            if target == row["current_translation_vi"]:
                raise ValueError(f"rewritten target is unchanged: {handoff_id}")
            reasons = item["reason_codes"]
            notes = item["notes"]
        else:
            assert item is not None
            target = ""
            reasons = []
            notes = item["question"].strip()
        output.append({
            "handoff_id": handoff_id,
            "domain": row["domain"],
            "key": row["key"],
            "translation_vi": target,
            "review_action": action,
            "reason_codes": json.dumps(reasons, ensure_ascii=False, separators=(",", ":")),
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
    reread = list(csv.DictReader(output_path.open("r", encoding="utf-8-sig", newline="")))
    if [row["handoff_id"] for row in reread] != [row["handoff_id"] for row in rows]:
        raise ValueError("output readback identity/order mismatch")


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
                {"handoff_id": "c", "domain": "d", "key": "3", "current_translation_vi": "Mơ hồ"},
            ])
        response.write_text(json.dumps({
            "schema": "agy-explicit-review/v1",
            "accepted_ids": ["a"],
            "rewritten": [{"handoff_id": "b", "translation_vi": "Mới", "reason_codes": ["fidelity"], "notes": ""}],
            "needs_context": [{"handoff_id": "c", "question": "Ai đang nói?"}],
        }, ensure_ascii=False), encoding="utf-8")
        expand(batch, response, output)
        rows = list(csv.DictReader(output.open("r", encoding="utf-8-sig", newline="")))
        assert [row["review_action"] for row in rows] == ["accepted", "rewritten", "needs_context"]
        bad = json.loads(response.read_text(encoding="utf-8"))
        bad["accepted_ids"] = []
        response.write_text(json.dumps(bad, ensure_ascii=False), encoding="utf-8")
        try:
            expand(batch, response, output)
        except ValueError as exc:
            assert "missing=['a']" in str(exc)
        else:
            raise AssertionError("missing accepted ID was not rejected")
    print("SELF-TEST PASS: explicit partition, expansion, readback, and missing-ID rejection")


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
