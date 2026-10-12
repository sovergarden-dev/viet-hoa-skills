from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any

REPLACEMENTS = (
    (
        'return {"decision": "deny", "reason": "staged wave lacks one exact native worker reservation; invoke the full wave before select"}',
        'return {"decision": "deny", "reason": "RECOVERABLE_SEQUENCE: staged wave lacks one exact native worker reservation; invoke the full staged wave before SELECT, then retry SELECT without stopping or reporting"}',
    ),
    (
        '                state = bind_conversation(state, conversation)\n                batch_id, prompt_hash, raw = validate_direct_response(args["CodeContent"], state)',
        '                current_prompt_path = resolve_path(state["authorization"]["current_prompt_path"], "current_prompt_path")\n                current_prompt = json.loads(current_prompt_path.read_text(encoding="utf-8"))\n                if state["mode"] == PHASE1 and current_prompt.get("schema") == "agy-semantic-wave/v1":\n                    return {"decision": "deny", "reason": "RECOVERABLE_SEQUENCE: current prompt is a wave wrapper; run exact SELECT after full-wave reservation before writing one selected response, without stopping or reporting"}\n                state = bind_conversation(state, conversation)\n                batch_id, prompt_hash, raw = validate_direct_response(args["CodeContent"], state)',
    ),
    (
        'return {"decision": "deny", "reason": "raw payload is not byte-exact in a native worker transcript; retry the worker and never author or repair it in main"}',
        'return {"decision": "deny", "reason": "RECOVERABLE_WORKER_RETRY: raw payload is not byte-exact in a native worker transcript; retry only the selected lease with one fresh worker, then resubmit raw bytes without stopping or reporting"}',
    ),
)


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def atomic_write(path: Path, raw: bytes) -> None:
    temporary = path.with_name(path.name + ".tmp-recoverable-denial")
    with temporary.open("wb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)
    if path.read_bytes() != raw:
        raise RuntimeError(f"atomic readback mismatch: {path}")


def promote(active: Path, template: Path, state: Path) -> dict[str, Any]:
    active = Path(active).resolve()
    template = Path(template).resolve()
    state = Path(state).resolve()
    state_value = json.loads(state.read_text(encoding="utf-8-sig"))
    if not isinstance(state_value, dict) or state_value.get("mode") != "inactive":
        raise ValueError("recoverable denial policy promotion requires semantic guard inactive")
    active_raw = active.read_bytes()
    template_raw = template.read_bytes()
    if active_raw != template_raw:
        raise ValueError("active/template semantic guards differ before promotion")
    decoded = active_raw.decode("utf-8")
    newline = "\r\n" if "\r\n" in decoded else "\n"
    text = decoded.replace("\r\n", "\n")
    changed = 0
    for old, new in REPLACEMENTS:
        count = text.count(old)
        if count == 1:
            text = text.replace(old, new)
            changed += 1
        elif count == 0 and new in text:
            continue
        else:
            raise ValueError(f"recoverable denial patch anchor count invalid: {count}")
    if newline == "\r\n":
        text = text.replace("\n", "\r\n")
    raw = text.encode("utf-8")
    atomic_write(template, raw)
    atomic_write(active, raw)
    if active.read_bytes() != template.read_bytes():
        raise RuntimeError("active/template mismatch after promotion")
    return {
        "status": "promoted" if changed else "already_promoted",
        "changes": changed,
        "sha256": sha256(raw),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Promote recoverable sequencing denials only after the active guarded run is closed.")
    parser.add_argument("--active", required=True, type=Path)
    parser.add_argument("--template", required=True, type=Path)
    parser.add_argument("--state", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        print(json.dumps(promote(args.active, args.template, args.state), separators=(",", ":")))
        return 0
    except Exception as error:
        print(f"FAIL: {type(error).__name__}: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
