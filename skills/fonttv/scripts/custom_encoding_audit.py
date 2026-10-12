#!/usr/bin/env python3
"""Read-only semantic audit for fonts consumed through a legacy/custom encoding.

For every mapping entry it checks the tuple
    (source character, encoded ID(s), expected glyph identity,
     actual glyph identity, ink/outline, metrics)
against a font inventory exported by a format adapter
(JSON schema ``fonttv/font-inventory/v1``). A record existing at an ID proves
nothing about the glyph drawn there.

Two inventory origins (capability boundary):

- ``--adapter-script`` + ``--adapter-sha256`` (``inventory_origin: adapter_executed``):
  the tool re-hashes the adapter, runs it without a shell on ``--font-file``
  with a fresh invocation id and a temp output path, and audits exactly that
  output. Only this origin can reach ``mapping_verified``.
- ``--inventory`` (``inventory_origin: external``): a pre-generated or
  handwritten declaration. Records are not re-derived, so the result is capped
  at ``inventory_only`` and never exits 0 as a semantic audit; with
  ``--accept-external-inventory-for-planning`` a clean run reports
  ``PLANNING_ONLY`` (still exit 4). Exit 0 is only ``PASS``.

Hashes bind metadata to bytes, not derivation: ``--font-file`` is always
hashed by the tool, and identity is strong only when the tool itself checks it
(native-encoding resolver, or re-hashed glyph evidence bound to the same font
hash). Evidence adds meaning to a slot; it never creates records, ink or
metrics.

The tool never parses proprietary font binaries itself and never writes to
inputs. It cannot prove archive binding or runtime rendering:
``runtime_bound`` is always NOT_RUN.

Exit codes: 0 PASS, 1 FAIL, 2 input error, 3 NOT_SUPPORTED, 4 INCOMPLETE/PLANNING_ONLY.
"""
from __future__ import annotations

import argparse
import codecs
import csv
import hashlib
import itertools
import json
import math
import os
import secrets
import subprocess
import sys
import tempfile
import time
import unicodedata
from pathlib import Path

TOOL_VERSION = "2.0.0"
ADAPTER_PROTOCOL = "fonttv-adapter/v1"
ADAPTER_EXIT_UNSUPPORTED = 3
OUT_SCHEMA = "fonttv/custom-encoding-audit/v1"
INVENTORY_SCHEMA = "fonttv/font-inventory/v1"
MAPPING_SCHEMA = "fonttv/encoding-map/v1"
EVIDENCE_SCHEMA = "fonttv/glyph-evidence/v1"
IDENTITY_POLICY = "fonttv/identity-evidence/v2"
EXIT = {"PASS": 0, "FAIL": 1, "INPUT_ERROR": 2, "NOT_SUPPORTED": 3, "INCOMPLETE": 4, "PLANNING_ONLY": 4}
CHECKS = ("record_present", "mapping_correct", "outline_nonempty", "metrics_valid")
NON_WAIVABLE_CHECKS = ("record_present", "mapping_correct", "outline_nonempty")
WAIVABLE_CHECKS = ("metrics_valid",)
WAIVER_FIELDS = ("reason", "approved_by", "scope")
ARTIFACT_IDENTITY_SOURCES = {"build_manifest", "reference_render_diff", "pixel_match", "human_review"}
STRONG_IDENTITY_SOURCES = ARTIFACT_IDENTITY_SOURCES | {"native_encoding"}
WEAK_IDENTITY_SOURCES = {"ai_vision", "ocr", "guess", "filename"}
EVIDENCE_TYPES = ARTIFACT_IDENTITY_SOURCES | {"encoding_table"}
ADAPTER_PROVENANCE = ("name", "version", "inventory_method")
NORMALIZATIONS = {"NFC", "NFD", "none"}
PASSTHROUGH = {"none", "ascii_printable"}
COMPOSE_POLICIES = {"precomposed", "base_plus_combining"}
LOOKUPS = {"binary_search", "hash", "direct_index", "unknown"}
ADVANCE_RATIO_WARN = (0.8, 1.6)
STROKE_BASES = {"đ": "d", "Đ": "D"}
MAX_LISTED = 25


class InputError(Exception):
    pass


class NotSupported(Exception):
    def __init__(self, message: str, execution: dict | None = None):
        super().__init__(message)
        self.execution = execution


class AdapterFailed(Exception):
    def __init__(self, message: str, execution: dict):
        super().__init__(message)
        self.execution = execution


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def nfc(text: str) -> str:
    return unicodedata.normalize("NFC", text)


def label(char: str) -> str:
    return " ".join(f"U+{ord(c):04X}" for c in char)


def parse_id(value, where: str) -> int:
    if isinstance(value, bool):
        raise InputError(f"{where}: id must be an integer")
    if isinstance(value, int):
        result = value
    elif isinstance(value, str) and value.strip():
        text = value.strip()
        try:
            result = int(text, 16) if text.lower().startswith("0x") else int(text, 10)
        except ValueError as exc:
            raise InputError(f"{where}: bad id {value!r}") from exc
    else:
        raise InputError(f"{where}: missing id")
    if result < 0:
        raise InputError(f"{where}: negative id {result}")
    return result


def parse_char(entry: dict, where: str) -> str:
    char = entry.get("char")
    if char is None and entry.get("codepoint"):
        text = str(entry["codepoint"]).upper().replace("U+", "")
        try:
            char = "".join(chr(int(part, 16)) for part in text.split())
        except ValueError as exc:
            raise InputError(f"{where}: bad codepoint {entry['codepoint']!r}") from exc
    if not isinstance(char, str) or not char:
        raise InputError(f"{where}: missing char/codepoint")
    return nfc(char)


def make_contract(meta: dict, entries: list[dict], source: str) -> dict:
    normalization = meta.get("normalization") or "NFC"
    passthrough = meta.get("passthrough") or "none"
    compose = meta.get("compose_policy") or "precomposed"
    if normalization not in NORMALIZATIONS:
        raise InputError(f"mapping normalization must be one of {sorted(NORMALIZATIONS)}")
    if passthrough not in PASSTHROUGH:
        raise InputError(f"mapping passthrough must be one of {sorted(PASSTHROUGH)}")
    if compose not in COMPOSE_POLICIES:
        raise InputError(f"mapping compose_policy must be one of {sorted(COMPOSE_POLICIES)}")
    id_max = meta.get("id_max")
    if id_max is not None:
        id_max = parse_id(id_max, "mapping id_max")
    errors: list[str] = []
    forward: dict[str, tuple[tuple[int, ...], tuple[str, ...]]] = {}
    reverse: dict[tuple[int, ...], str] = {}
    expected_by_id: dict[int, str] = {}
    for entry in entries:
        char, ids, glyphs = entry["char"], entry["ids"], entry["glyphs"]
        if char in forward and forward[char][0] != ids:
            errors.append(f"duplicate_char: {char!r} ({label(char)}) mapped to {list(forward[char][0])} and {list(ids)}")
            continue
        if ids in reverse and reverse[ids] != char:
            errors.append(f"non_injective: ids {list(ids)} used by {reverse[ids]!r} and {char!r}")
            continue
        forward[char] = (ids, glyphs)
        reverse[ids] = char
        for id_, glyph in zip(ids, glyphs):
            if id_max is not None and id_ > id_max:
                errors.append(f"id_out_of_range: {id_} > id_max {id_max} for {char!r}")
            if passthrough == "ascii_printable" and 0x20 <= id_ <= 0x7E and glyph != chr(id_):
                errors.append(f"passthrough_collision: id {id_} is ASCII {chr(id_)!r} but mapped to glyph {glyph!r}")
            previous = expected_by_id.get(id_)
            if previous is not None and previous != glyph:
                errors.append(f"conflicting_expected_identity: id {id_} expected as {previous!r} and {glyph!r}")
            expected_by_id.setdefault(id_, glyph)
    return {
        "source": source,
        "name": meta.get("name"),
        "normalization": normalization,
        "passthrough": passthrough,
        "compose_policy": compose,
        "id_max": id_max,
        "entry_count": len(entries),
        "forward": forward,
        "reverse": reverse,
        "errors": errors,
    }


def load_mapping(path: Path) -> dict:
    if not path.is_file():
        raise InputError(f"mapping not found: {path}")
    entries: list[dict] = []
    if path.suffix.lower() == ".csv":
        with path.open(encoding="utf-8-sig", newline="") as handle:
            for line_no, row in enumerate(csv.DictReader(handle), start=2):
                where = f"{path.name}:{line_no}"
                char = parse_char(row, where)
                raw = row.get("id") or row.get("charID") or row.get("byte")
                id_ = parse_id(raw, where)
                entries.append({"char": char, "ids": (id_,), "glyphs": (char,)})
        return make_contract({"name": path.stem}, entries, f"mapping:{path.name}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise InputError(f"mapping JSON unreadable: {type(exc).__name__}: {exc}") from exc
    if isinstance(data, dict) and "entries" in data:
        if data.get("schema") not in (None, MAPPING_SCHEMA):
            raise NotSupported(f"mapping schema {data.get('schema')!r} is not {MAPPING_SCHEMA}")
        meta, raw_entries = data, data["entries"]
    elif isinstance(data, dict):
        meta = {"name": path.stem}
        raw_entries = [{"char": key, "id": value} for key, value in data.items()]
    else:
        raise InputError("mapping JSON must be an object")
    if not isinstance(raw_entries, list):
        raise InputError("mapping entries must be a list")
    for index, raw in enumerate(raw_entries):
        where = f"{path.name}:entries[{index}]"
        if not isinstance(raw, dict):
            raise InputError(f"{where}: entry must be an object")
        char = parse_char(raw, where)
        if "ids" in raw:
            if not isinstance(raw["ids"], list) or not raw["ids"]:
                raise InputError(f"{where}: ids must be a non-empty list")
            ids = tuple(parse_id(value, where) for value in raw["ids"])
        else:
            ids = (parse_id(raw.get("id", raw.get("charID", raw.get("byte"))), where),)
        glyphs = raw.get("glyphs")
        if glyphs is None:
            if len(ids) > 1:
                raise InputError(f"{where}: multi-id entry needs 'glyphs' (expected identity per id)")
            glyphs = (char,)
        else:
            if not isinstance(glyphs, list) or len(glyphs) != len(ids) or not all(isinstance(g, str) and g for g in glyphs):
                raise InputError(f"{where}: 'glyphs' must list one identity string per id")
            glyphs = tuple(nfc(g) for g in glyphs)
        entries.append({"char": char, "ids": ids, "glyphs": glyphs})
    return make_contract(meta, entries, f"mapping:{path.name}")


def codec_mapping(name: str, compose_policy: str | None) -> dict:
    try:
        info = codecs.lookup(name)
    except LookupError as exc:
        raise InputError(f"unknown codec {name!r}") from exc
    entries = []
    for byte in range(256):
        try:
            char = bytes([byte]).decode(info.name)
        except UnicodeDecodeError:
            continue
        if len(char) != 1:
            raise NotSupported(f"codec {name!r} is not a single-byte charmap")
        if unicodedata.category(char) == "Cc":
            continue
        entries.append({"char": char, "ids": (byte,), "glyphs": (char,)})
    if len(entries) < 128:
        raise NotSupported(f"codec {name!r} does not look like a single-byte charmap")
    default_compose = "base_plus_combining" if info.name == "cp1258" else "precomposed"
    meta = {"name": info.name, "normalization": "NFC", "compose_policy": compose_policy or default_compose, "id_max": 255}
    return make_contract(meta, entries, f"codec:{info.name}")


def lookup_char(char: str, contract: dict):
    hit = contract["forward"].get(char)
    if hit:
        return list(hit[0]), list(hit[1])
    if contract["passthrough"] == "ascii_printable" and len(char) == 1 and 0x20 <= ord(char) <= 0x7E:
        return [ord(char)], [char]
    return None


def decompose_encode(char: str, contract: dict):
    """Encode as precomposed head + combining marks (Windows-1258 style)."""
    decomposed = unicodedata.normalize("NFD", char)
    base, marks = decomposed[0], decomposed[1:]
    if not marks:
        return None
    for size in range(len(marks), -1, -1):
        for chosen in itertools.combinations(range(len(marks)), size):
            head = nfc(base + "".join(marks[i] for i in chosen))
            head_hit = lookup_char(head, contract) if len(head) == 1 else None
            if head_hit is None:
                continue
            ids, glyphs = list(head_hit[0]), list(head_hit[1])
            for i, mark in enumerate(marks):
                if i in chosen:
                    continue
                mark_hit = lookup_char(mark, contract)
                if mark_hit is None:
                    break
                ids += mark_hit[0]
                glyphs += mark_hit[1]
            else:
                return ids, glyphs
    return None


def encode(text: str, contract: dict):
    form = contract["normalization"]
    if form != "none":
        text = unicodedata.normalize(form, text)
    ids: list[int] = []
    glyphs: list[str] = []
    unencodable: list[dict] = []
    for index, char in enumerate(text):
        hit = lookup_char(char, contract)
        if hit is None and contract["compose_policy"] == "base_plus_combining":
            hit = decompose_encode(char, contract)
        if hit is None:
            unencodable.append({"index": index, "char": char, "codepoints": label(char)})
            continue
        ids += hit[0]
        glyphs += hit[1]
    return ids, glyphs, unencodable


def decode(ids: list[int], contract: dict) -> str:
    reverse = contract["reverse"]
    longest = max((len(key) for key in reverse), default=1)
    out, i = [], 0
    while i < len(ids):
        for size in range(min(longest, len(ids) - i), 0, -1):
            key = tuple(ids[i:i + size])
            if key in reverse:
                out.append(reverse[key])
                i += size
                break
        else:
            if contract["passthrough"] == "ascii_printable" and 0x20 <= ids[i] <= 0x7E:
                out.append(chr(ids[i]))
            else:
                out.append("\ufffd")
            i += 1
    return "".join(out)


def load_json(path: Path, what: str):
    if not path.is_file():
        raise InputError(f"{what} not found: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise InputError(f"{what} JSON unreadable: {type(exc).__name__}: {exc}") from exc


def load_inventory(path: Path) -> dict:
    return validate_inventory(load_json(path, "inventory"))


def run_adapter(script: Path, pinned_sha: str | None, font_file: Path, timeout: float) -> tuple[dict, dict]:
    """Run a hash-pinned adapter on the font (argv list, no shell) and return the inventory it just produced."""
    if not script.is_file():
        raise InputError(f"adapter script not found: {script}")
    if not is_sha(pinned_sha):
        raise InputError("--adapter-sha256 must be the 64-hex SHA-256 of the adapter script")
    script_sha = sha256_file(script)
    if script_sha != pinned_sha.lower():
        raise InputError(f"adapter script hashes to {script_sha}, not the pinned {pinned_sha.lower()}")
    font_before = sha256_file(font_file)
    invocation_id = secrets.token_hex(16)
    with tempfile.TemporaryDirectory(prefix="fonttv-adapter-") as tmp:
        output = Path(tmp) / "inventory.json"
        argv = [sys.executable, str(script.resolve()), "--input", str(font_file.resolve()), "--output", str(output),
                "--invocation-id", invocation_id, "--protocol", ADAPTER_PROTOCOL]
        execution = {
            "protocol": ADAPTER_PROTOCOL, "script": str(script), "script_sha256": script_sha,
            "argv_contract": ["<python>", "<adapter>", "--input", "<font>", "--output", "<temp json>",
                              "--invocation-id", "<id>", "--protocol", ADAPTER_PROTOCOL],
            "invocation_id": invocation_id, "exit_code": None, "generated_inventory_sha256": None,
            "input_unchanged": None, "stderr_tail": None,
        }
        started = time.time()
        try:
            proc = subprocess.run(argv, cwd=tmp, stdin=subprocess.DEVNULL, capture_output=True, timeout=timeout, check=False)
        except subprocess.TimeoutExpired:
            raise AdapterFailed(f"adapter exceeded {timeout}s", execution) from None
        execution["exit_code"] = proc.returncode
        execution["stderr_tail"] = proc.stderr.decode("utf-8", "replace")[-600:] or None
        execution["input_unchanged"] = sha256_file(font_file) == font_before
        if not execution["input_unchanged"]:
            raise AdapterFailed("adapter modified the input font", execution)
        if proc.returncode == ADAPTER_EXIT_UNSUPPORTED:
            raise NotSupported(f"adapter reports unsupported input: {execution['stderr_tail'] or 'no reason given'}", execution)
        if proc.returncode != 0:
            raise AdapterFailed(f"adapter exited {proc.returncode}", execution)
        if not output.is_file() or output.stat().st_mtime < started - 2:
            raise AdapterFailed("adapter did not write a fresh inventory to the temp output path", execution)
        raw = output.read_bytes()
    execution["generated_inventory_sha256"] = hashlib.sha256(raw).hexdigest()
    try:
        data = json.loads(raw.decode("utf-8"))
    except ValueError as exc:
        raise AdapterFailed(f"adapter output is not JSON: {exc}", execution) from None
    invocation = data.get("invocation") if isinstance(data, dict) else None
    if not isinstance(invocation, dict) or invocation.get("id") != invocation_id or invocation.get("protocol") != ADAPTER_PROTOCOL:
        raise AdapterFailed("adapter output does not carry this run's invocation id/protocol", execution)
    if "evidence" in data:
        raise AdapterFailed("adapter output must not carry identity evidence; pass --identity-evidence instead", execution)
    try:
        return validate_inventory(data), execution, raw
    except NotSupported as exc:
        raise NotSupported(str(exc), execution) from None
    except InputError as exc:
        raise AdapterFailed(f"adapter output invalid: {exc}", execution) from None


def cli_evidence(specs: list[str]) -> list[dict]:
    """--identity-evidence TYPE=PATH entries; the tool hashes the files itself."""
    entries = []
    for index, spec in enumerate(specs or []):
        kind, sep, raw = spec.partition("=")
        if not sep or kind not in EVIDENCE_TYPES:
            raise InputError(f"--identity-evidence {spec!r}: use TYPE=PATH with TYPE in {sorted(EVIDENCE_TYPES)}")
        path = Path(raw)
        if not path.is_file():
            raise InputError(f"identity evidence not found: {path}")
        entries.append({"id": f"cli-{index}", "type": kind, "path": str(path.resolve()), "sha256": sha256_file(path)})
    return entries


def enrich_adapter_identity(records: list[dict], evidence: dict[str, dict], resolver) -> bool:
    """Adapter records carry geometry only; identity comes from verified evidence, else the native resolver."""
    resolved = False
    for record in records:
        if not isinstance(record, dict):
            continue
        sources = record.get("identity_source") or []
        sources = [sources] if isinstance(sources, str) else list(sources)
        record["identity_source"] = [s for s in sources if s == "native_encoding"] if record.get("glyph_identity") else []
        record["identity_evidence"] = []
        try:
            id_ = parse_id(record.get("id"), "record")
        except InputError:
            continue
        for ev in evidence.values():
            if ev["status"] == "VERIFIED" and id_ in ev["slots"]:
                if record.get("glyph_identity") is None:
                    record["glyph_identity"] = ev["slots"][id_]
                if ev["type"] not in record["identity_source"]:
                    record["identity_source"].append(ev["type"])
                record["identity_evidence"].append(ev["id"])
                resolved = True
        if record.get("glyph_identity") is None and resolver is not None and resolver(id_) is not None:
            record["glyph_identity"] = resolver(id_)
            record["identity_source"] = ["native_encoding"]
            resolved = True
    return resolved


def validate_inventory(data) -> dict:
    if not isinstance(data, dict):
        raise InputError("inventory JSON must be an object")
    if data.get("schema") != INVENTORY_SCHEMA:
        raise NotSupported(f"inventory schema {data.get('schema')!r} is not {INVENTORY_SCHEMA}")
    adapter = data.get("adapter")
    if not isinstance(adapter, dict):
        raise NotSupported("inventory has no adapter block; cannot tell what was measured")
    if adapter.get("supported") is False:
        raise NotSupported(f"adapter {adapter.get('name')!r} reports unsupported input: {adapter.get('reason', 'no reason given')}")
    caps = adapter.get("capabilities")
    if not isinstance(caps, list) or "records" not in caps:
        raise NotSupported("adapter capabilities must include 'records'")
    records = data.get("records")
    if not isinstance(records, list):
        raise NotSupported("inventory records must be a list")
    lookup = data.get("lookup", "unknown")
    if lookup not in LOOKUPS:
        raise InputError(f"inventory lookup must be one of {sorted(LOOKUPS)}")
    return data


def is_sha(value) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value.lower())


def canonical_json(value) -> str:
    """Stable JSON: sorted keys, NFC strings, no invocation nonce."""
    def norm(item):
        if isinstance(item, str):
            return unicodedata.normalize("NFC", item)
        if isinstance(item, dict):
            return {k: norm(v) for k, v in item.items() if k != "invocation"}
        if isinstance(item, list):
            return [norm(v) for v in item]
        return item

    return json.dumps(norm(value), sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def canonical_inventory(data: dict) -> str:
    """Hash of the adapter inventory with the per-run invocation removed."""
    body = {k: data.get(k) for k in ("schema", "font", "sha256", "lookup", "adapter", "records")}
    return hashlib.sha256(canonical_json(body).encode("utf-8")).hexdigest()


def _strip_path_spelling(value):
    """Reduce any ``*_file`` path to its basename, recursively.

    The digest must depend on content, not on where a file happens to live.
    Probe: the same font audited with an absolute corpus path and with a
    relative one produced digests 7b3b28c9 / c6ffa978, because ``roundtrip``
    echoes ``text_file`` verbatim. That made ``proof_level_check`` report a
    stale report for a byte-identical rerun whenever the manifest carried a
    relative path. The content hashes (``*_sha256``) stay authoritative.
    """
    if isinstance(value, dict):
        return {(k): (_strip_path_spelling(v) if not (isinstance(k, str) and k.endswith("_file") and isinstance(v, str))
                      else os.path.basename(v.replace("\\", "/")))
                for k, v in value.items()}
    if isinstance(value, list):
        return [_strip_path_spelling(v) for v in value]
    return value


def semantic_digest(report: dict) -> str:
    """Hash of every field that can change a proof decision.

    Invocation nonces, warnings and path spellings are omitted: a proof must not
    change because the project moved or a caller wrote a path differently.
    """
    entry_keys = ("id", "char", "source_char", "record_present", "mapping_correct", "outline_nonempty",
                  "metrics_valid", "actual_identity", "identity_evidence", "ink_status", "x_advance", "status")
    inventory = report.get("inventory") or {}
    payload = {
        "verdict": report.get("verdict"),
        "proof_level": report.get("proof_level"),
        "font_sha256": ((report.get("inputs") or {}).get("font_sha256") or ""),
        "mapping_sha256": ((report.get("inputs") or {}).get("mapping_sha256") or ""),
        "adapter_sha256": ((report.get("adapter_execution") or {}).get("script_sha256") or ""),
        "encoding_contract": report.get("encoding_contract"),
        "identity_evidence_policy": report.get("identity_evidence_policy"),
        "binding_status": inventory.get("binding_status"),
        "font_hash_matches": inventory.get("font_hash_matches"),
        "adapter_input_matches": inventory.get("adapter_input_matches"),
        "evidence_status": [(e.get("id"), e.get("type"), e.get("status")) for e in inventory.get("evidence") or []],
        "structural_result": report.get("structural_result"),
        "semantic_result": report.get("semantic_result"),
        "entries": [{k: row.get(k) for k in entry_keys} for row in report.get("entries") or []],
        "summary": report.get("summary"),
        "roundtrip": _strip_path_spelling(report.get("roundtrip")),
        "waived": report.get("waived"),
        "errors": report.get("errors"),
    }
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def split_results(rows: list[dict], errors: list[str], binding: dict, origin: str, roundtrip) -> tuple[dict, dict]:
    """Structural proof is record/ink/metrics from this run. Semantic proof is identity and round-trip."""
    def gate(check: str, allowed: set[str]) -> str:
        if not rows:
            return "FAIL"
        return "PASS" if all(row[check] in allowed for row in rows) else "FAIL"

    coverage = gate("record_present", {"PASS"})
    outline = gate("outline_nonempty", {"PASS"})
    metrics = gate("metrics_valid", {"PASS", "WAIVED"})
    rederived = origin == "adapter_executed"
    structural_blockers = [e for e in errors if not e.startswith("mapping:")]
    structural_pass = (rederived and binding.get("status") == "PASS" and not structural_blockers
                       and coverage == outline == metrics == "PASS")
    if any(row["mapping_correct"] == "FAIL" for row in rows):
        mapping = "FAIL"
    elif rows and all(row["mapping_correct"] == "PASS" for row in rows):
        mapping = "PASS"
    elif any(row["mapping_correct"] == "UNVERIFIED" for row in rows):
        mapping = "UNVERIFIED"
    else:
        mapping = "NOT_RUN"
    trip = roundtrip["status"] if roundtrip else "NOT_RUN"
    semantic_pass = mapping == "PASS" and trip in ("PASS", "NOT_RUN") and not any(e.startswith("mapping:") for e in errors)
    semantic_status = "PASS" if semantic_pass else ("FAIL" if mapping == "FAIL" or trip == "FAIL" else "INCOMPLETE")
    return (
        {"records_rederived": rederived, "coverage": coverage, "outline_ink": outline,
         "metrics": metrics, "status": "PASS" if structural_pass else "FAIL"},
        {"mapping": mapping, "roundtrip": trip, "status": semantic_status},
    )


def bind_font(font_file: Path, inventory: dict, errors: list[str]) -> dict:
    """Hash the font bytes ourselves; the inventory's own hash claims are only compared, never trusted."""
    if not font_file.is_file():
        raise InputError(f"font file not found: {font_file}")
    actual = sha256_file(font_file)
    adapter = inventory["adapter"]
    declared, adapter_input = inventory.get("sha256"), adapter.get("input_sha256")
    names = [n for n in (inventory.get("font"), inventory.get("source_path")) if n]
    binding = {
        "font_file": str(font_file),
        "font_sha256": actual,
        "declared_font_sha256": declared,
        "adapter_input_sha256": adapter_input,
        "font_hash_matches": is_sha(declared) and declared.lower() == actual,
        "adapter_input_matches": is_sha(adapter_input) and adapter_input.lower() == actual,
        "name_consistent": all(Path(str(n).replace("\\", "/")).name == font_file.name for n in names),
        "adapter_provenance_complete": all(str(adapter.get(k) or "").strip() for k in ADAPTER_PROVENANCE),
    }
    checks = (
        ("font_hash_matches", f"inventory sha256 {declared!r} is not the sha256 of {font_file.name} ({actual})"),
        ("adapter_input_matches", f"adapter.input_sha256 {adapter_input!r} is not the sha256 of {font_file.name}"),
        ("name_consistent", f"inventory font/source_path {names} does not name {font_file.name}"),
        ("adapter_provenance_complete", f"adapter needs non-empty {list(ADAPTER_PROVENANCE)}"),
    )
    for key, message in checks:
        if not binding[key]:
            errors.append(f"binding: {message}")
    binding["status"] = "PASS" if all(binding[key] for key, _ in checks) else "FAIL"
    return binding


def load_evidence(inventory: dict, root: Path, font_sha: str) -> dict[str, dict]:
    """Re-hash every evidence artifact the inventory cites; a declared hash alone proves nothing."""
    entries = inventory.get("evidence") or []
    if not isinstance(entries, list):
        raise InputError("inventory evidence must be a list")
    result: dict[str, dict] = {}
    for index, entry in enumerate(entries):
        where = f"evidence[{index}]"
        if not isinstance(entry, dict) or not str(entry.get("id") or "").strip():
            raise InputError(f"{where}: needs an id")
        ev_id, ev_type = entry["id"], entry.get("type")
        if ev_id in result:
            raise InputError(f"{where}: duplicate evidence id {ev_id!r}")
        if ev_type not in EVIDENCE_TYPES:
            raise InputError(f"{where}: type must be one of {sorted(EVIDENCE_TYPES)}")
        item = {"id": ev_id, "type": ev_type, "path": entry.get("path"), "declared_sha256": entry.get("sha256"),
                "status": "VERIFIED", "slots": {}, "reason": None}
        result[ev_id] = item
        path = Path(str(entry.get("path") or ""))
        if not entry.get("path") or not is_sha(entry.get("sha256")):
            item.update(status="INVALID", reason="evidence needs path and sha256")
            continue
        path = path if path.is_absolute() else root / path
        try:
            actual = sha256_file(path)
            data = json.loads(path.read_text(encoding="utf-8"))
        except OSError:
            item.update(status="MISSING", reason=f"{entry['path']} not found under evidence root")
            continue
        except ValueError:
            item.update(status="INVALID", reason="evidence is not JSON")
            continue
        item["sha256"] = actual
        if actual != entry["sha256"].lower():
            item.update(status="HASH_MISMATCH", reason=f"{entry['path']} hashes to {actual}")
            continue
        if not isinstance(data, dict) or data.get("schema") != EVIDENCE_SCHEMA or data.get("type") != ev_type:
            item.update(status="INVALID", reason=f"evidence must be {EVIDENCE_SCHEMA} of type {ev_type}")
            continue
        if ev_type != "encoding_table" and str(data.get("font_sha256") or "").lower() != font_sha:
            item.update(status="WRONG_FONT", reason="evidence describes different font bytes")
            continue
        slots = data.get("slots")
        if not isinstance(slots, dict):
            item.update(status="INVALID", reason="evidence needs a slots object {id: identity}")
            continue
        try:
            item["slots"] = {parse_id(k, f"{where} slot"): nfc(str(v)) for k, v in slots.items()}
        except InputError as exc:
            item.update(status="INVALID", reason=str(exc))
    return result


def native_resolver(adapter: dict, evidence: dict[str, dict]):
    """Return (resolve(id) -> char | None, description, reason) for adapter.native_encoding."""
    native = adapter.get("native_encoding")
    if not isinstance(native, dict) or not str(native.get("resolver") or "").strip():
        return None, None, "adapter declares no native_encoding with a resolver"
    table_id = native.get("table_evidence")
    if table_id:
        table = evidence.get(table_id)
        if not table or table["type"] != "encoding_table" or table["status"] != "VERIFIED":
            return None, None, f"native_encoding table evidence {table_id!r} not verified"
        return table["slots"].get, f"table:{table['sha256']}", None
    name = native.get("name")
    try:
        info = codecs.lookup(str(name))
    except LookupError:
        return None, None, f"native_encoding {name!r} is neither a Python codec nor backed by table_evidence"

    def resolve(id_: int):
        if id_ > 255:
            return None
        try:
            char = bytes([id_]).decode(info.name)
        except UnicodeDecodeError:
            return None
        return char if len(char) == 1 else None

    return resolve, f"python_codec:{info.name}", None


def load_allowlist(path: Path | None) -> dict[tuple[int, str], dict]:
    """Only metrics_valid can be waived; identity, ink and presence never can."""
    if path is None:
        return {}
    data = load_json(path, "allowlist")
    rows = data.get("entries") if isinstance(data, dict) else data
    if not isinstance(rows, list):
        raise InputError("allowlist must be a list or {'entries': [...]}")
    result = {}
    for index, row in enumerate(rows):
        where = f"allowlist[{index}]"
        if not isinstance(row, dict):
            raise InputError(f"{where}: entry must be an object")
        check = row.get("check")
        if check in NON_WAIVABLE_CHECKS:
            raise InputError(f"{where}: {check} cannot be waived; remap or fix the slot instead")
        if check not in WAIVABLE_CHECKS:
            raise InputError(f"{where}: check must be one of {list(WAIVABLE_CHECKS)}")
        missing = [k for k in WAIVER_FIELDS if not isinstance(row.get(k), str) or not row[k].strip()]
        if missing:
            raise InputError(f"{where}: waiver needs non-empty {missing}")
        if row.get("approver_type") != "human":
            raise InputError(f"{where}: approver_type must be 'human'")
        key = (parse_id(row.get("id"), where), check)
        if key in result:
            raise InputError(f"{where}: duplicate waiver for id {key[0]} {check}")
        result[key] = {k: row[k].strip() for k in WAIVER_FIELDS} | {"approver_type": "human"}
    return result


def is_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def ink_status(record: dict, caps: set[str]) -> tuple[str, str]:
    if "ink" in caps and "ink_pixels" in record:
        pixels = record["ink_pixels"]
        if not is_number(pixels):
            return "INVALID", "ink_pixels is not a number"
        return ("INK", f"{pixels} ink pixels") if pixels > 0 else ("EMPTY", "0 ink pixels")
    if "ink" in caps and isinstance(record.get("ink_bbox"), list) and len(record["ink_bbox"]) == 4:
        x0, y0, x1, y1 = record["ink_bbox"]
        area = (x1 - x0) * (y1 - y0)
        return ("INK", f"ink bbox area {area}") if area > 0 else ("EMPTY", "ink bbox has no area")
    if "uv" in caps and isinstance(record.get("uv"), list) and len(record["uv"]) == 4:
        u0, v0, u1, v1 = record["uv"]
        if u0 == u1 or v0 == v1:
            return "EMPTY", "zero-area UV: no glyph image"
        return "UV_ONLY", "UV has area but ink was not measured"
    return "NOT_RUN", "adapter provided no ink or UV evidence"


def make_identity_verifier(evidence: dict[str, dict], resolver, resolver_desc, resolver_reason):
    def verify_identity(id_: int, actual: str, record: dict, sources: list[str]) -> tuple[str, list[str]]:
        refs = record.get("identity_evidence") or []
        refs = [refs] if isinstance(refs, str) else list(refs)
        notes, verified = [], False
        for ref in refs:
            if ref not in evidence:
                notes.append(f"unknown evidence id {ref!r}")
        for source in sources:
            if source == "native_encoding":
                if resolver is None:
                    notes.append(f"native_encoding: {resolver_reason}")
                    continue
                got = resolver(id_)
                if got is None:
                    notes.append(f"native_encoding ({resolver_desc}): id {id_} undefined")
                elif nfc(got) != actual:
                    return "CONTRADICTED", notes + [f"native_encoding ({resolver_desc}) resolves id {id_} to {got!r}"]
                else:
                    verified = True
                    notes.append(f"native_encoding verified via {resolver_desc}")
            elif source in ARTIFACT_IDENTITY_SOURCES:
                typed = [evidence[r] for r in refs if r in evidence and evidence[r]["type"] == source]
                if not typed:
                    notes.append(f"{source}: claimed without an evidence artifact")
                for ev in typed:
                    if ev["status"] != "VERIFIED":
                        notes.append(f"{source}: evidence {ev['id']} {ev['status']} ({ev['reason']})")
                    elif id_ not in ev["slots"]:
                        notes.append(f"{source}: evidence {ev['id']} has no slot {id_}")
                    elif ev["slots"][id_] != actual:
                        return "CONTRADICTED", notes + [f"{source}: evidence {ev['id']} says slot {id_} is {ev['slots'][id_]!r}"]
                    else:
                        verified = True
                        notes.append(f"{source}: evidence {ev['id']} verified ({ev['sha256']})")
            else:
                notes.append(f"{source}: weak or unknown source, ignored")
        return ("VERIFIED" if verified else "UNVERIFIED"), notes

    return verify_identity


def check_record(char: str, id_: int, record: dict | None, caps: set[str], by_char_record, warnings: list[str],
                 verify_identity) -> dict:
    whitespace = all(c.isspace() for c in char)
    is_mark = all(unicodedata.combining(c) for c in char)
    row = {
        "char": char, "codepoints": label(char), "id": id_,
        "expected_identity": char, "actual_identity": None, "identity_source": [], "identity_evidence": [],
        "ink_status": None, "x_advance": None,
        "record_present": "PASS" if record is not None else "FAIL",
        "mapping_correct": "NOT_RUN", "outline_nonempty": "NOT_RUN", "metrics_valid": "NOT_RUN",
        "runtime_bound": "NOT_RUN", "reasons": [],
    }
    if record is None:
        row["reasons"].append(f"no record with id {id_}")
        return row
    if "glyph_identity" in caps:
        actual = record.get("glyph_identity")
        sources = record.get("identity_source") or []
        sources = [sources] if isinstance(sources, str) else list(sources)
        row["actual_identity"], row["identity_source"] = actual, sources
        unknown = [s for s in sources if s not in STRONG_IDENTITY_SOURCES | WEAK_IDENTITY_SOURCES]
        if unknown:
            warnings.append(f"id {id_}: unknown identity_source {unknown} treated as weak")
        if actual is None:
            row["mapping_correct"] = "UNVERIFIED"
            row["reasons"].append("glyph identity unknown")
        elif nfc(str(actual)) != char:
            row["mapping_correct"] = "FAIL"
            row["reasons"].append(f"expected {char!r} but record draws {actual!r}")
        else:
            status, notes = verify_identity(id_, char, record, sources)
            row["identity_evidence"] = notes
            if status == "VERIFIED":
                row["mapping_correct"] = "PASS"
            elif status == "CONTRADICTED":
                row["mapping_correct"] = "FAIL"
                row["reasons"].append(f"identity {actual!r} contradicted by evidence")
            else:
                row["mapping_correct"] = "UNVERIFIED"
                row["reasons"].append(f"identity {actual!r} has no verified evidence ({sources or 'no sources'})")
    status, why = ink_status(record, caps)
    row["ink_status"] = status
    if whitespace:
        row["outline_nonempty"] = "PASS"
        if status == "INK":
            warnings.append(f"id {id_}: whitespace {char!r} has ink")
    elif status == "INK":
        row["outline_nonempty"] = "PASS"
    elif status in ("EMPTY", "INVALID"):
        row["outline_nonempty"] = "FAIL"
        row["reasons"].append(why)
    elif status == "UV_ONLY":
        row["outline_nonempty"] = "UNVERIFIED"
        row["reasons"].append(why)
    else:
        row["reasons"].append(why)
    if "metrics" in caps:
        advance = record.get("x_advance")
        row["x_advance"] = advance
        problems = []
        if not is_number(advance):
            problems.append("x_advance missing or not a number")
        elif is_mark and advance < 0:
            problems.append(f"combining glyph has negative advance {advance}")
        elif not is_mark and advance <= 0:
            problems.append(f"visible/spacing glyph has advance {advance}")
        for key in ("height", "y_offset"):
            if key in record and not is_number(record[key]):
                problems.append(f"{key} is not a number")
        if is_number(record.get("height")) and record["height"] < 0:
            problems.append("negative height")
        row["metrics_valid"] = "FAIL" if problems else "PASS"
        row["reasons"] += problems
        base = STROKE_BASES.get(char) or unicodedata.normalize("NFD", char)[0]
        base_record = by_char_record(base) if base != char and not is_mark else None
        if not problems and base_record and is_number(base_record.get("x_advance")) and base_record["x_advance"] > 0:
            ratio = advance / base_record["x_advance"]
            if not ADVANCE_RATIO_WARN[0] <= ratio <= ADVANCE_RATIO_WARN[1]:
                warnings.append(f"id {id_} {char!r}: advance {advance} is {ratio:.2f}x base {base!r} ({base_record['x_advance']})")
    return row


def apply_allowlist(row: dict, allow: dict[tuple[int, str], dict], waived: list[dict], used: set) -> None:
    for check in WAIVABLE_CHECKS:
        waiver = allow.get((row["id"], check))
        if waiver is None or row[check] != "FAIL":
            continue
        waived.append({"id": row["id"], "char": row["char"], "check": check, "was": row[check],
                       "original_reasons": list(row["reasons"]), **waiver})
        row[f"{check}_original"] = row[check]
        row[check] = "WAIVED"
        row["waiver"] = waiver
        used.add((row["id"], check))


def row_status(row: dict) -> str:
    if any(row[c] == "WAIVED" for c in NON_WAIVABLE_CHECKS):
        return "FAIL"
    values = [row[c] for c in CHECKS]
    if "FAIL" in values:
        return "FAIL"
    if any(v in ("NOT_RUN", "UNVERIFIED") for v in values):
        return "INCOMPLETE"
    return "PASS"


def read_text_corpus(path: Path) -> str:
    if not path.is_file():
        raise InputError(f"text corpus not found: {path}")
    return path.read_text(encoding="utf-8").replace("\r", "").replace("\n", "")


def audit(args) -> dict:
    contract = codec_mapping(args.codec, args.compose_policy) if args.codec else load_mapping(args.mapping)
    if args.compose_policy and not args.codec:
        contract["compose_policy"] = args.compose_policy
    if not args.font_file.is_file():
        raise InputError(f"font file not found: {args.font_file}")
    allow = load_allowlist(args.allowlist)
    execution = None
    if args.adapter_script:
        inventory, execution, raw_inventory = run_adapter(
            args.adapter_script, args.adapter_sha256, args.font_file, args.adapter_timeout)
        execution["inventory_canonical_sha256"] = canonical_inventory(json.loads(raw_inventory.decode("utf-8")))
        if args.save_generated_inventory:
            args.save_generated_inventory.parent.mkdir(parents=True, exist_ok=True)
            args.save_generated_inventory.write_bytes(raw_inventory)
        inventory["evidence"] = cli_evidence(args.identity_evidence)
        evidence_root = Path(".")
    else:
        if args.identity_evidence:
            raise InputError("--identity-evidence is for adapter runs; external inventories cite evidence[] themselves")
        inventory = load_inventory(args.inventory)
        evidence_root = args.evidence_root or args.inventory.resolve().parent
    origin = "adapter_executed" if execution else "external"
    caps = set(inventory["adapter"]["capabilities"])
    warnings: list[str] = []
    errors = [f"mapping: {e}" for e in contract["errors"]]
    binding = bind_font(args.font_file, inventory, errors)
    evidence = load_evidence(inventory, evidence_root, binding["font_sha256"])
    resolver, resolver_desc, resolver_reason = native_resolver(inventory["adapter"], evidence)
    if execution and enrich_adapter_identity(inventory["records"], evidence, resolver):
        caps.add("glyph_identity")
    verify_identity = make_identity_verifier(evidence, resolver, resolver_desc, resolver_reason)

    by_id: dict[int, dict] = {}
    order: list[int] = []
    duplicates: list[int] = []
    for index, record in enumerate(inventory["records"]):
        if not isinstance(record, dict):
            errors.append(f"inventory: records[{index}] is not an object")
            continue
        try:
            id_ = parse_id(record.get("id"), f"records[{index}]")
        except InputError as exc:
            errors.append(f"inventory: {exc}")
            continue
        order.append(id_)
        if id_ in by_id:
            duplicates.append(id_)
        else:
            by_id[id_] = record
    for id_ in sorted(set(duplicates)):
        errors.append(f"inventory: duplicate id {id_} (lookup result is ambiguous)")
    unsorted_at = [i for i in range(1, len(order)) if order[i] <= order[i - 1]]
    sorted_required = args.require_sorted or inventory.get("lookup") == "binary_search"
    if unsorted_at:
        message = f"inventory: ids not strictly ascending at record positions {unsorted_at[:MAX_LISTED]}"
        (errors if sorted_required else warnings).append(message)

    def by_char_record(char: str):
        hit = lookup_char(char, contract)
        return by_id.get(hit[0][0]) if hit and len(hit[0]) == 1 else None

    targets: dict[tuple[int, str], str] = {}
    for char, (ids, glyphs) in contract["forward"].items():
        for id_, glyph in zip(ids, glyphs):
            targets.setdefault((id_, glyph), char)

    roundtrip = None
    if args.text:
        text = read_text_corpus(args.text)
        ids, glyphs, unencodable = encode(text, contract)
        for id_, glyph in zip(ids, glyphs):
            targets.setdefault((id_, glyph), glyph)
        expected_text = nfc(text if contract["normalization"] == "none" else unicodedata.normalize(contract["normalization"], text))
        decoded = decode(ids, contract)
        lookup_mismatches = []
        rendered = []
        for position, (id_, glyph) in enumerate(zip(ids, glyphs)):
            record = by_id.get(id_)
            actual = record.get("glyph_identity") if record else None
            rendered.append(actual if isinstance(actual, str) else "\ufffd")
            if actual is None or nfc(str(actual)) != glyph:
                if len(lookup_mismatches) < MAX_LISTED:
                    lookup_mismatches.append({"position": position, "id": id_, "expected": glyph, "actual": actual})
        nfd_ids, _, nfd_bad = encode(unicodedata.normalize("NFD", text), contract)
        roundtrip = {
            "text_file": str(args.text),
            "text_sha256": sha256_file(args.text),
            "chars": len(text),
            "encoded_ids": len(ids),
            "unencodable": unencodable[:MAX_LISTED],
            "unencodable_count": len(unencodable),
            "decode_matches_input": nfc(decoded) == expected_text if not unencodable else False,
            "font_lookup_matches_input": not lookup_mismatches and not unencodable and nfc("".join(rendered)) == expected_text,
            "font_lookup_mismatches": lookup_mismatches,
            "nfd_input_same_ids": nfd_ids == ids and not nfd_bad,
            "encoded_file_matches": None,
        }
        if not roundtrip["nfd_input_same_ids"]:
            warnings.append("NFD input encodes differently from NFC input; the text pipeline must normalize before encoding")
        if args.encoded:
            if not args.encoded.is_file():
                raise InputError(f"encoded byte file not found: {args.encoded}")
            if any(i > 255 for i in ids):
                roundtrip["encoded_file_matches"] = "NOT_SUPPORTED"
                warnings.append("--encoded compares single bytes; mapping uses ids > 255")
            else:
                actual_bytes = args.encoded.read_bytes()
                roundtrip["encoded_file_sha256"] = sha256_file(args.encoded)
                roundtrip["encoded_file_matches"] = actual_bytes == bytes(ids)
                if not roundtrip["encoded_file_matches"]:
                    first = next((i for i, (a, b) in enumerate(zip(actual_bytes, bytes(ids))) if a != b), min(len(actual_bytes), len(ids)))
                    roundtrip["encoded_first_difference"] = first
        ok = (roundtrip["decode_matches_input"] and roundtrip["font_lookup_matches_input"]
              and roundtrip["encoded_file_matches"] in (None, True, "NOT_SUPPORTED"))
        roundtrip["status"] = "PASS" if ok else "FAIL"

    rows, waived, used = [], [], set()
    for (id_, glyph), source_char in sorted(targets.items(), key=lambda item: (item[0][0], item[0][1])):
        row = check_record(glyph, id_, by_id.get(id_), caps, by_char_record, warnings, verify_identity)
        row = {"source_char": source_char, **row}
        apply_allowlist(row, allow, waived, used)
        row["status"] = row_status(row)
        rows.append(row)
    for id_, check in sorted(set(allow) - used):
        warnings.append(f"unused waiver: id {id_} {check} (no FAIL to waive)")

    summary = {check: {s: sum(1 for r in rows if r[check] == s) for s in ("PASS", "FAIL", "UNVERIFIED", "NOT_RUN", "WAIVED")} for check in CHECKS}
    summary["runtime_bound"] = {"NOT_RUN": len(rows)}
    if errors or any(r["status"] == "FAIL" for r in rows) or (roundtrip and roundtrip["status"] == "FAIL"):
        verdict = "FAIL"
    elif any(r["status"] == "INCOMPLETE" for r in rows) or not rows:
        verdict = "INCOMPLETE"
    else:
        verdict = "PASS"
    structural_result, semantic_result = split_results(rows, errors, binding, origin, roundtrip)
    if origin == "adapter_executed" and structural_result["status"] == "PASS" and semantic_result["status"] == "PASS":
        proof_level = "mapping_verified"
    elif origin == "adapter_executed" and structural_result["status"] == "PASS":
        proof_level = "structurally_verified"
    else:
        proof_level = "inventory_only"
    if origin == "external":
        proof_level = "inventory_only"
        if verdict == "PASS":
            verdict = "PLANNING_ONLY" if args.accept_external_inventory_for_planning else "INCOMPLETE"
        warnings.append("external inventory is a declaration: records were not re-derived from the font in this run, "
                        "so the result is capped at inventory_only; use --adapter-script for mapping verification")
    if not rows:
        warnings.append("mapping produced no entries to check")

    result = {
        "schema": OUT_SCHEMA,
        "tool": "custom_encoding_audit.py",
        "tool_version": TOOL_VERSION,
        "route": "B_custom_or_legacy_encoding",
        "identity_evidence_policy": IDENTITY_POLICY,
        "inventory_origin": origin,
        "records_rederived": origin == "adapter_executed",
        "structural_result": structural_result,
        "semantic_result": semantic_result,
        "proof_cap": "mapping_verified" if origin == "adapter_executed" else "inventory_only",
        "semantic_digest": None,
        "inventory_canonical_sha256": (execution or {}).get("inventory_canonical_sha256"),
        "adapter_execution": execution,
        "inputs": {
            "mapping": str(args.mapping) if args.mapping else None,
            "mapping_sha256": sha256_file(args.mapping) if args.mapping else None,
            "codec": args.codec,
            "inventory": str(args.inventory) if args.inventory else None,
            "inventory_sha256": sha256_file(args.inventory) if args.inventory else execution["generated_inventory_sha256"],
            "font_file": binding["font_file"],
            "font_sha256": binding["font_sha256"],
            "evidence_root": str(evidence_root),
            "allowlist": str(args.allowlist) if args.allowlist else None,
        },
        "encoding_contract": {k: contract[k] for k in ("source", "name", "normalization", "passthrough", "compose_policy", "id_max", "entry_count")},
        "inventory": {
            "font": inventory.get("font"),
            "declared_font_sha256": binding["declared_font_sha256"],
            "adapter_input_sha256": binding["adapter_input_sha256"],
            "font_hash_matches": binding["font_hash_matches"],
            "adapter_input_matches": binding["adapter_input_matches"],
            "name_consistent": binding["name_consistent"],
            "adapter_provenance_complete": binding["adapter_provenance_complete"],
            "binding_status": binding["status"],
            "native_encoding_resolver": resolver_desc or resolver_reason,
            "evidence": [{k: v for k, v in ev.items() if k != "slots"} for ev in evidence.values()],
            "adapter": inventory["adapter"],
            "lookup": inventory.get("lookup", "unknown"),
            "record_count": len(order),
            "duplicate_ids": sorted(set(duplicates)),
            "strictly_ascending": not unsorted_at,
            "sorted_required": sorted_required,
        },
        "entries": rows,
        "summary": summary,
        "roundtrip": roundtrip,
        "waived": waived,
        "errors": errors,
        "warnings": warnings,
        "verdict": verdict,
        "exit_code": EXIT[verdict],
        "proof_level": proof_level,
        "does_not_prove": [
            "that the audited bytes are the ones inside the live archive",
            "runtime rendering, clipping or visual quality",
            "that the mapping table matches the shipped encoder unless --encoded was checked",
            "that a stored copy of this report was produced by an adapter run; a checker must re-execute",
        ],
    }
    result["semantic_digest"] = semantic_digest(result)
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Read-only semantic audit: custom/legacy encoding -> font records. "
                                                 "Record presence alone never passes.")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--mapping", type=Path, help="mapping JSON (fonttv/encoding-map/v1 or {char: id}) or CSV (char|codepoint,id)")
    source.add_argument("--codec", help="single-byte Python codec used as the contract, e.g. cp1252, cp1258")
    origin = parser.add_mutually_exclusive_group(required=True)
    origin.add_argument("--adapter-script", type=Path, help="hash-pinned adapter run on --font-file (only origin that can reach mapping_verified)")
    origin.add_argument("--inventory", type=Path, help="external/pre-generated inventory: a declaration, capped at inventory_only")
    parser.add_argument("--adapter-sha256", help="expected SHA-256 of --adapter-script")
    parser.add_argument("--save-generated-inventory", type=Path,
                        help="write the exact adapter inventory bytes from this run (adapter mode only)")
    parser.add_argument("--adapter-timeout", type=float, default=120.0, help="seconds before the adapter run fails")
    parser.add_argument("--identity-evidence", action="append", metavar="TYPE=PATH",
                        help="glyph evidence (fonttv/glyph-evidence/v1) for adapter runs; repeatable")
    parser.add_argument("--accept-external-inventory-for-planning", action="store_true",
                        help="label a clean external inventory PLANNING_ONLY; still exits 4, never a semantic audit")
    parser.add_argument("--font-file", type=Path, help="REQUIRED: the exact font bytes to audit; hashed by this tool")
    parser.add_argument("--evidence-root", type=Path, help="root for external inventory evidence[] paths (default: inventory directory)")
    parser.add_argument("--text", type=Path, help="UTF-8 corpus for the Unicode -> ids -> font lookup round-trip")
    parser.add_argument("--encoded", type=Path, help="bytes the real encoder produced for --text (single-byte ids)")
    parser.add_argument("--allowlist", type=Path, help="JSON [{id, check: metrics_valid, reason, approved_by, approver_type: human, scope}]; "
                                                      "record_present/mapping_correct/outline_nonempty are never waivable (exit 2)")
    parser.add_argument("--compose-policy", choices=sorted(COMPOSE_POLICIES), help="override mapping compose_policy")
    parser.add_argument("--require-sorted", action="store_true", help="fail when record ids are not strictly ascending")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    if args.encoded and not args.text:
        parser.error("--encoded requires --text")
    if args.output:
        inputs = [p for p in (args.mapping, args.inventory, args.adapter_script, args.font_file, args.text, args.encoded,
                              args.allowlist, args.save_generated_inventory) if p]
        if any(args.output.resolve() == p.resolve() for p in inputs):
            parser.error("refusing to overwrite an input file")
    try:
        if args.font_file is None:
            raise InputError("--font-file is required: an inventory is only evidence about bytes this tool hashed itself")
        if args.save_generated_inventory and not args.adapter_script:
            raise InputError("--save-generated-inventory requires --adapter-script")
        result = audit(args)
    except NotSupported as exc:
        result = {"schema": OUT_SCHEMA, "verdict": "NOT_SUPPORTED", "exit_code": EXIT["NOT_SUPPORTED"], "reason": str(exc),
                  "proof_level": None, "adapter_execution": exc.execution}
    except AdapterFailed as exc:
        result = {"schema": OUT_SCHEMA, "verdict": "FAIL", "exit_code": EXIT["FAIL"], "error": str(exc),
                  "proof_level": "inventory_only", "inventory_origin": "adapter_executed", "records_rederived": False,
                  "adapter_execution": exc.execution}
    except InputError as exc:
        result = {"schema": OUT_SCHEMA, "verdict": "INPUT_ERROR", "exit_code": EXIT["INPUT_ERROR"], "error": str(exc), "proof_level": None}
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
    sys.stdout.buffer.write((text + "\n").encode("utf-8"))
    return result["exit_code"]


if __name__ == "__main__":
    sys.exit(main())
