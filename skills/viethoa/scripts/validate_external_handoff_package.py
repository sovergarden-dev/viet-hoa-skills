from __future__ import annotations

import csv
import hashlib
import io
import json
from collections import Counter
import re
import shutil
import stat
import sys
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path, PurePosixPath

PHASE_ACTIONS = {
    "phase0_policy_audit": {"accepted", "propose_change", "needs_context"},
    "phase1_bulk": {"translated", "needs_context"},
    "phase2_language_qa": {"accepted", "rewritten", "needs_context"},
    "phase3_semantic_audit": {"accepted", "rewritten", "needs_context"},
}
POLICIES = {
    "keep_identity",
    "translate_with_locked_terms",
    "translate_full",
    "exclude_or_keep_technical",
    "needs_policy_context",
}
POLICY_STATUSES = {"locked", "receiver_review", "needs_user_decision"}
POLICY_HEADER = [
    "domain", "key", "source_sha256", "content_type", "semantic_class",
    "translation_policy", "locked_english_terms", "identity_expected",
    "reason", "evidence", "policy_status",
]
MAP_HEADER = ["handoff_id", "domain", "key", "source_sha256"]
BATCH_HEADER = [
    "handoff_id", "domain", "key", "content_type", "speaker", "addressee",
    "source", "reference", "previous_context", "following_context",
    "protected_tokens", "character_limit", "semantic_class",
    "translation_policy", "locked_english_terms", "identity_expected",
    "community_vi_reference", "work_route", "current_translation_vi",
]
PHASE0_OUTPUT_HEADER = [
    "handoff_id", "domain", "key", "review_action",
    "proposed_translation_policy", "proposed_locked_english_terms",
    "proposed_identity_expected", "reason", "notes",
]
TRANSLATION_OUTPUT_HEADER = [
    "handoff_id", "domain", "key", "translation_vi", "review_action",
    "reason_codes", "notes",
]
FORBIDDEN_SUFFIXES = {
    ".exe", ".dll", ".pak", ".ucas", ".utoc", ".sig", ".bin",
    ".asset", ".bundle",
}
PRIVATE_PATHS = (
    re.compile(rb"[A-Za-z]:[\\/](?:Users|Documents and Settings)[\\/][^\\/\r\n]+", re.I),
    re.compile(rb"/(?:home|Users)/[^/\r\n]+"),
)
HEX64 = re.compile(r"[0-9a-f]{64}")
RECEIVER_BASELINES = {
    "AGY-VIETHOA-HANDOFF/2.0",
    "AGY-VIETHOA-HANDOFF/2.1",
}
DECISION_EVIDENCE_ENCODINGS = {"full-object-v1", "compact-explicit-v1"}


class InvalidPackage(ValueError):
    pass


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fail(message: str) -> None:
    raise InvalidPackage(message)


def safe_name(name: str) -> str:
    if "\\" in name:
        fail(f"ZIP/path uses backslash: {name}")
    path = PurePosixPath(name)
    if path.is_absolute() or not path.parts or any(p in {"", ".", ".."} for p in path.parts):
        fail(f"unsafe relative path: {name}")
    return path.as_posix()


def load_files(
    source: Path,
    *,
    max_files: int = 20_000,
    max_expanded_bytes: int = 512 * 1024 * 1024,
) -> dict[str, bytes]:
    files: dict[str, bytes] = {}
    if max_files < 1 or max_expanded_bytes < 1:
        fail("archive limits must be positive")
    if source.is_dir():
        paths = sorted(p for p in source.rglob("*") if p.is_file())
        if len(paths) > max_files:
            fail(f"file-count ceiling exceeded: {len(paths)} > {max_files}")
        expanded = sum(path.stat().st_size for path in paths)
        if expanded > max_expanded_bytes:
            fail(
                f"expanded-size ceiling exceeded: {expanded} > {max_expanded_bytes}"
            )
        for path in paths:
            name = safe_name(path.relative_to(source).as_posix())
            files[name] = path.read_bytes()
    elif source.is_file() and source.suffix.lower() == ".zip":
        with zipfile.ZipFile(source) as archive:
            bad = archive.testzip()
            if bad:
                fail(f"ZIP CRC failure: {bad}")
            members = [info for info in archive.infolist() if not info.is_dir()]
            if len(members) > max_files:
                fail(f"ZIP file-count ceiling exceeded: {len(members)} > {max_files}")
            expanded = sum(info.file_size for info in members)
            if expanded > max_expanded_bytes:
                fail(
                    f"ZIP expanded-size ceiling exceeded: "
                    f"{expanded} > {max_expanded_bytes}"
                )
            seen: set[str] = set()
            for info in members:
                name = safe_name(info.filename.rstrip("/"))
                mode = (info.external_attr >> 16) & 0xFFFF
                if info.create_system == 3 and stat.S_ISLNK(mode):
                    fail(f"ZIP symlink member rejected: {name}")
                if name in seen:
                    fail(f"duplicate ZIP member: {name}")
                seen.add(name)
                files[name] = archive.read(info)
    else:
        fail("input must be a handoff directory or .zip")
    if not files:
        fail("handoff package is empty")
    return files


def read_json(files: dict[str, bytes], name: str) -> dict:
    if name not in files:
        fail(f"missing required file: {name}")
    try:
        value = json.loads(files[name].decode("utf-8-sig"))
    except Exception as exc:
        fail(f"invalid JSON {name}: {exc}")
    if not isinstance(value, dict):
        fail(f"JSON root must be object: {name}")
    return value


def read_csv(files: dict[str, bytes], name: str) -> tuple[list[str], list[dict[str, str]]]:
    if name not in files:
        fail(f"missing required file: {name}")
    try:
        stream = io.StringIO(files[name].decode("utf-8-sig"), newline="")
        reader = csv.DictReader(stream)
        header = reader.fieldnames or []
        rows = list(reader)
    except Exception as exc:
        fail(f"invalid CSV {name}: {exc}")
    if not header or len(set(header)) != len(header):
        fail(f"missing/duplicate CSV header: {name}")
    return header, rows


def full_key_hash(keys: list[tuple[str, str]]) -> str:
    payload = b"".join(
        json.dumps([domain, key], ensure_ascii=False, separators=(",", ":")).encode("utf-8") + b"\n"
        for domain, key in keys
    )
    return digest(payload)


def source_snapshot_hash(rows: list[tuple[str, str, str]]) -> str:
    payload = b"".join(
        json.dumps([domain, key, source_hash], ensure_ascii=False, separators=(",", ":")).encode("utf-8") + b"\n"
        for domain, key, source_hash in rows
    )
    return digest(payload)


def immutable_rows_hash(rows: list[dict[str, str]]) -> str:
    payload = b"".join(
        json.dumps(
            [row.get(field, "") for field in BATCH_HEADER],
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8") + b"\n"
        for row in rows
    )
    return digest(payload)


def term_count(text: str, term: str) -> int:
    left = r"(?<!\w)" if term[:1].isalnum() else ""
    right = r"(?!\w)" if term[-1:].isalnum() else ""
    return len(re.findall(left + re.escape(term) + right, text))


def extract_tokens(text: str, profile: dict) -> list[str]:
    extractors = profile.get("extractors")
    if not isinstance(extractors, list) or not extractors:
        fail("token profile extractors missing")
    supported = {"brace", "printf", "rich_text", "escaped_controls", "square_brackets"}
    if any(name not in supported for name in extractors):
        fail("token profile contains unsupported extractor")

    matches: list[tuple[int, int, str]] = []
    if "brace" in extractors:
        matches.extend(
            (match.start(), match.end(), match.group(0))
            for match in re.finditer(r"\{[^{}\r\n]+\}", text)
        )
    if "printf" in extractors:
        flags = r"[-+#0']*" if profile.get(
            "printf_requires_no_whitespace_after_percent"
        ) is True else r"[-+#0 ']*"
        printf = rf"%(?:{flags}\d*(?:\.\d+)?(?:hh|h|ll|l|j|z|t|L)?[diuoxXfFeEgGaAcspn%])"
        matches.extend(
            (match.start(), match.end(), match.group(0))
            for match in re.finditer(printf, text)
        )
    if "rich_text" in extractors:
        tags = profile.get("known_rich_text_tags")
        if not isinstance(tags, list) or not all(
            isinstance(tag, str) and re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]*", tag)
            for tag in tags
        ):
            fail("token profile known_rich_text_tags invalid")
        if tags:
            tag_names = "|".join(re.escape(tag) for tag in tags)
            # Unity/TMP accepts both `<tag=value>` and `<tag value>` forms.
            rich = rf"</?(?:{tag_names})(?:=[^<>]*|\s+[^<>]*?)?\s*/?>"
            matches.extend(
                (match.start(), match.end(), match.group(0))
                for match in re.finditer(rich, text)
            )
    if "escaped_controls" in extractors:
        matches.extend(
            (match.start(), match.end(), match.group(0))
            for match in re.finditer(r"\\(?:n|r|t|0)", text)
        )
    if "square_brackets" in extractors:
        # The bracketed prose may be translated, but the structural delimiters
        # must remain balanced and occur the same number of times.
        matches.extend(
            (index, index + 1, char)
            for index, char in enumerate(text)
            if char in "[]"
        )

    compare = profile.get("compare", {})
    if isinstance(compare, dict) and compare.get("physical_newlines") is True:
        matches.extend(
            (match.start(), match.end(), match.group(0))
            for match in re.finditer(r"\r\n|\r|\n|\t", text)
        )
    return [token for _, _, token in sorted(matches)]


def rich_text_nesting_signature(text: str, profile: dict) -> tuple:
    tags = profile.get("known_rich_text_tags", [])
    tag_names = "|".join(re.escape(tag) for tag in tags)
    rich = re.compile(rf"</?(?:{tag_names})(?:=[^<>]*|\s+[^<>]*?)?\s*/?>")
    roots: list[tuple[str, list]] = []
    stack: list[tuple[str, str, list]] = []

    for match in rich.finditer(text):
        raw = match.group(0)
        closing = raw.startswith("</")
        name_match = re.match(r"</?([A-Za-z][A-Za-z0-9_-]*)", raw)
        if name_match is None:
            fail("invalid rich-text token")
        name = name_match.group(1)
        if closing:
            if not stack or stack[-1][0] != name:
                fail("invalid rich-text nesting")
            stack.pop()
            continue

        node: tuple[str, list] = (raw, [])
        children = stack[-1][2] if stack else roots
        children.append(node)
        if not raw.endswith("/>") and name.casefold() != "br":
            stack.append((name, raw, node[1]))

    if stack:
        fail("unclosed rich-text tag")

    preserve_order = profile.get("compare", {}).get("order") is True

    def freeze(node: tuple[str, list]) -> tuple:
        label, children = node
        frozen = [freeze(child) for child in children]
        if not preserve_order:
            frozen.sort()
        return label, tuple(frozen)

    frozen_roots = [freeze(node) for node in roots]
    if not preserve_order:
        frozen_roots.sort()
    return tuple(frozen_roots)


def validate_token_preservation(
    source_text: str,
    target_text: str,
    profile: dict,
    pair: tuple[str, str],
) -> None:
    source_tokens = extract_tokens(source_text, profile)
    target_tokens = extract_tokens(target_text, profile)
    compare = profile.get("compare", {})
    if not isinstance(compare, dict):
        fail("token profile compare rules missing")
    if compare.get("multiset") is True:
        if Counter(source_tokens) != Counter(target_tokens):
            fail(f"actual source/target token multiset mismatch: {pair!r}")
    elif source_tokens != target_tokens:
        fail(f"actual source/target token sequence mismatch: {pair!r}")
    if compare.get("order") is True and source_tokens != target_tokens:
        fail(f"actual source/target token order mismatch: {pair!r}")
    if compare.get("nesting") is True:
        if "rich_text" not in profile.get("extractors", []):
            fail("token profile nesting comparison requires rich_text extractor")
        if rich_text_nesting_signature(source_text, profile) != rich_text_nesting_signature(
            target_text, profile
        ):
            fail(f"actual source/target rich-text nesting mismatch: {pair!r}")


def token_vectors_hash(vectors: list[dict]) -> str:
    payload = json.dumps(
        vectors,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return digest(payload)


def validate_token_profile(profile: dict) -> None:
    vectors = profile.get("test_vectors")
    if not isinstance(vectors, list) or len(vectors) < 2:
        fail("token profile requires positive and negative test vectors")
    normalized: list[dict] = []
    has_positive = False
    has_negative = False
    for index, vector in enumerate(vectors):
        if not isinstance(vector, dict):
            fail(f"token profile test vector must be object: {index}")
        text = vector.get("text")
        expected = vector.get("tokens")
        if not isinstance(text, str) or not isinstance(expected, list) or not all(
            isinstance(token, str) and token for token in expected
        ):
            fail(f"token profile test vector invalid: {index}")
        actual = extract_tokens(text, profile)
        if actual != expected:
            fail(f"token profile test vector mismatch: {index}")
        has_positive = has_positive or bool(expected)
        has_negative = has_negative or not expected
        normalized.append({"text": text, "tokens": expected})
    if not has_positive or not has_negative:
        fail("token profile needs at least one positive and one negative vector")
    if profile.get("project_test_vectors_sha256") != token_vectors_hash(normalized):
        fail("token profile test-vector hash mismatch")


def parse_checksums(files: dict[str, bytes]) -> None:
    name = "checksums.sha256"
    if name not in files:
        fail("checksums.sha256 missing")
    declared: dict[str, str] = {}
    for raw in files[name].decode("utf-8").splitlines():
        if not raw.strip():
            continue
        match = re.fullmatch(r"([0-9a-f]{64})\s+\*?(.+)", raw)
        if not match:
            fail(f"malformed checksum line: {raw!r}")
        rel = safe_name(match.group(2))
        if rel == name or rel in declared:
            fail(f"invalid/duplicate checksum entry: {rel}")
        declared[rel] = match.group(1)
    expected = set(files) - {name}
    if set(declared) != expected:
        fail(f"checksum coverage mismatch: missing={sorted(expected-set(declared))}, extra={sorted(set(declared)-expected)}")
    for rel, expected_hash in declared.items():
        if digest(files[rel]) != expected_hash:
            fail(f"checksum mismatch: {rel}")


def validate_package(source: Path) -> dict:
    files = load_files(source)
    required = {
        "project-manifest.json", "work-queue.json", "handoff-id-map.csv",
        "glossary.csv", "START-HERE.md", "protected-tokens.md",
        "batch-schema.json", "output-schema.json", "token-profile.json",
        "TRANSLATION-PROMPT.txt", "checksums.sha256",
    }
    missing = sorted(required - set(files))
    if missing:
        fail(f"required files missing: {missing}")
    for name, data in files.items():
        if Path(name).suffix.lower() in FORBIDDEN_SUFFIXES:
            fail(f"translation-only package contains technical binary/asset: {name}")
        for pattern in PRIVATE_PATHS:
            if pattern.search(data):
                fail(f"private absolute path leaked: {name}")
    parse_checksums(files)

    project = read_json(files, "project-manifest.json")
    queue = read_json(files, "work-queue.json")
    source_language = str(project.get("source_language", "")).casefold()
    if project.get("contract_version") != "1.0.0":
        fail("unsupported/missing external contract_version")
    if project.get("translation_only") is not True or project.get("canonical_write_authority") != "Hermes":
        fail("role boundary missing from project manifest")
    if project.get("identity") != {
        "canonical_key": ["domain", "key"],
        "handoff_id_mapping": "handoff-id-map.csv",
    }:
        fail("project canonical identity contract mismatch")
    if project.get("batch_schema_sha256") != digest(files["batch-schema.json"]):
        fail("project batch schema hash mismatch")
    if project.get("output_schema_sha256") != digest(files["output-schema.json"]):
        fail("project output schema hash mismatch")
    receiver_baseline = project.get(
        "receiver_control_baseline", "AGY-VIETHOA-HANDOFF/2.0"
    )
    if receiver_baseline not in RECEIVER_BASELINES:
        fail("unsupported receiver_control_baseline")
    legacy_receiver = receiver_baseline == "AGY-VIETHOA-HANDOFF/2.0"
    receiver_cap = project.get(
        "max_active_reserved_subagents", 4 if legacy_receiver else None
    )
    if (
        not isinstance(receiver_cap, int)
        or isinstance(receiver_cap, bool)
        or receiver_cap < 1
        or receiver_cap > 7
        or (legacy_receiver and receiver_cap != 4)
    ):
        fail("invalid receiver subagent cap")
    default_workers = project.get("default_active_workers", 1 if legacy_receiver else None)
    if (
        not isinstance(default_workers, int)
        or isinstance(default_workers, bool)
        or default_workers not in {1, 2}
        or default_workers > receiver_cap
    ):
        fail("invalid default_active_workers")
    decision_encoding = project.get("decision_evidence_encoding", "full-object-v1")
    if decision_encoding not in DECISION_EVIDENCE_ENCODINGS:
        fail("unsupported decision_evidence_encoding")
    if legacy_receiver and decision_encoding != "full-object-v1":
        fail("legacy receiver baseline cannot use compact decision evidence")
    if decision_encoding == "compact-explicit-v1":
        schema_name = project.get("decision_evidence_schema")
        expander_name = project.get("decision_evidence_expander")
        if schema_name != "decision-evidence-schema.json":
            fail("compact decision evidence schema path mismatch")
        if expander_name != "tools/expand_compact_decisions.py":
            fail("compact decision expander path mismatch")
        if schema_name not in files or expander_name not in files:
            fail("compact decision schema/expander missing")
        if project.get("decision_evidence_schema_sha256") != digest(files[schema_name]):
            fail("compact decision schema hash mismatch")
        if project.get("decision_evidence_expander_sha256") != digest(files[expander_name]):
            fail("compact decision expander hash mismatch")
        decision_schema = read_json(files, schema_name)
        if decision_schema.get("schema") != "agy-explicit-review/v1":
            fail("compact decision schema identity mismatch")
    token_profile = read_json(files, "token-profile.json")
    if project.get("token_profile_file") != "token-profile.json":
        fail("project token_profile_file mismatch")
    if project.get("token_profile_id") != token_profile.get("token_profile_id"):
        fail("project token_profile_id mismatch")
    if project.get("token_profile_sha256") != digest(files["token-profile.json"]):
        fail("project token profile hash mismatch")
    validate_token_profile(token_profile)
    if queue.get("authority") != "derived_cache_rebuild_from_packet_manifests_acceptance_receipts_and_merge_ledger":
        fail("work queue must declare derived-cache authority")
    phases = project.get("phase_contract")
    if phases != list(PHASE_ACTIONS):
        fail("phase_contract must be exact Phase 0/1/2/3 order")
    batch_schema = read_json(files, "batch-schema.json")
    if batch_schema.get("columns") != BATCH_HEADER:
        fail("batch-schema.json columns mismatch")
    output_schema = read_json(files, "output-schema.json")
    if (
        output_schema.get("phase0_columns") != PHASE0_OUTPUT_HEADER
        or output_schema.get("translation_phase_columns")
        != TRANSLATION_OUTPUT_HEADER
    ):
        fail("output-schema.json columns mismatch")

    map_header, map_rows = read_csv(files, "handoff-id-map.csv")
    if map_header != MAP_HEADER or not map_rows:
        fail("handoff-id-map.csv schema/rows invalid")
    handoff_ids: set[str] = set()
    full_keys: set[tuple[str, str]] = set()
    ordered_keys: list[tuple[str, str]] = []
    mapping: dict[str, tuple[str, str, str]] = {}
    for row in map_rows:
        hid = row["handoff_id"]
        pair = (row["domain"], row["key"])
        source_hash = row["source_sha256"]
        if not hid or hid in handoff_ids or not all(pair) or pair in full_keys or not HEX64.fullmatch(source_hash):
            fail(f"invalid/duplicate handoff mapping: {hid!r} {pair!r}")
        handoff_ids.add(hid)
        full_keys.add(pair)
        ordered_keys.append(pair)
        mapping[hid] = (pair[0], pair[1], source_hash)
    ordered_hash = full_key_hash(ordered_keys)
    if project.get("ordered_full_key_sha256") != ordered_hash:
        fail("project ordered_full_key_sha256 mismatch")

    policy: dict[tuple[str, str], dict[str, str]] = {}
    if source_language == "english":
        policy_header, policy_rows = read_csv(files, "english-policy.csv")
        if policy_header != POLICY_HEADER:
            fail("english-policy.csv header mismatch")
        for row in policy_rows:
            pair = (row["domain"], row["key"])
            rule = row["translation_policy"]
            if pair in policy or pair not in full_keys or rule not in POLICIES:
                fail(f"invalid/duplicate English policy row: {pair!r}")
            if row["policy_status"] not in POLICY_STATUSES:
                fail(f"invalid English policy status: {pair!r}")
            matching_map = next((v for v in mapping.values() if v[:2] == pair), None)
            if matching_map is None or row["source_sha256"] != matching_map[2]:
                fail(f"English policy source hash mismatch: {pair!r}")
            if rule == "keep_identity" and (not row["identity_expected"] or not row["reason"] or not row["evidence"]):
                fail(f"keep_identity lacks exact target/reason/evidence: {pair!r}")
            if rule != "keep_identity" and row["identity_expected"]:
                fail(f"identity_expected set outside keep_identity: {pair!r}")
            terms = row["locked_english_terms"]
            if terms:
                try:
                    parsed_terms = json.loads(terms)
                except Exception as exc:
                    fail(f"locked_english_terms must be JSON list for {pair!r}: {exc}")
                if not isinstance(parsed_terms, list) or not all(isinstance(x, str) and x for x in parsed_terms):
                    fail(f"invalid locked_english_terms for {pair!r}")
            policy[pair] = row
        if set(policy) != full_keys:
            fail("English policy full-key coverage mismatch")

    active_phase = queue.get("active_phase")
    if active_phase not in PHASE_ACTIONS:
        fail(f"unknown active phase: {active_phase!r}")
    if source_language == "english" and active_phase != "phase0_policy_audit" and project.get("policy_ready_for_bulk") is not True:
        fail("English Phase 1+ requires policy_ready_for_bulk=true")
    if (
        source_language == "english"
        and active_phase != "phase0_policy_audit"
        and any(row["policy_status"] != "locked" for row in policy.values())
    ):
        fail("English Phase 1+ requires every policy row to be locked")
    parent = queue.get("parent_phase_sha256")
    if active_phase == "phase0_policy_audit" and parent is not None:
        fail("Phase 0 parent must be null")
    if source_language == "english" and active_phase != "phase0_policy_audit" and not (isinstance(parent, str) and HEX64.fullmatch(parent)):
        fail("English Phase 1+ requires Hermes acceptance parent hash")

    queue_packets = queue.get("packets")
    if not isinstance(queue_packets, list) or not queue_packets:
        fail("work queue has no packets")
    packet_ids: set[str] = set()
    union: list[tuple[str, str]] = []
    for entry in queue_packets:
        if not isinstance(entry, dict):
            fail("work queue packet entry must be object")
        packet_id = entry.get("packet_id")
        if not isinstance(packet_id, str) or not packet_id or packet_id in packet_ids:
            fail(f"invalid/duplicate packet id: {packet_id!r}")
        packet_ids.add(packet_id)
        base = f"packets/{packet_id}"
        packet_manifest = read_json(files, f"{base}/packet-manifest.json")
        if packet_manifest.get("contract_version") != project["contract_version"]:
            fail(f"packet contract version mismatch: {packet_id}")
        attempt = packet_manifest.get("attempt")
        if not isinstance(attempt, int) or isinstance(attempt, bool) or attempt < 1:
            fail(f"packet attempt invalid: {packet_id}")
        if entry.get("attempt") != attempt:
            fail(f"work queue packet attempt mismatch: {packet_id}")
        if not isinstance(packet_manifest.get("lease_id"), str) or not packet_manifest["lease_id"]:
            fail(f"packet lease_id missing: {packet_id}")
        try:
            expiry = datetime.fromisoformat(
                str(packet_manifest.get("lease_expires_at", "")).replace("Z", "+00:00")
            )
        except ValueError:
            fail(f"packet lease_expires_at invalid: {packet_id}")
        if expiry.tzinfo is None:
            fail(f"packet lease_expires_at lacks timezone: {packet_id}")
        for token_field in ("estimated_input_tokens", "estimated_output_tokens"):
            value = packet_manifest.get(token_field)
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                fail(f"packet {token_field} invalid: {packet_id}")
        if packet_manifest.get("token_profile_id") != project["token_profile_id"]:
            fail(f"packet token_profile_id mismatch: {packet_id}")
        if packet_manifest.get("token_profile_sha256") != project["token_profile_sha256"]:
            fail(f"packet token profile hash mismatch: {packet_id}")

        batch_name = f"{base}/{packet_manifest.get('input_filename', 'batch.csv')}"
        batch_header, batch_rows = read_csv(files, batch_name)
        if batch_header != BATCH_HEADER:
            fail(f"packet batch schema mismatch: {packet_id}")
        phase = packet_manifest.get("phase")
        if phase != active_phase or entry.get("phase_state") not in {"pending", "in_progress", "complete"}:
            fail(f"packet phase/state mismatch: {packet_id}")
        if packet_manifest.get("permitted_review_actions") != sorted(PHASE_ACTIONS[phase]):
            fail(f"packet permitted_review_actions mismatch: {packet_id}")
        if packet_manifest.get("parent_phase_sha256") != parent:
            fail(f"packet parent hash mismatch: {packet_id}")
        packet_keys: list[tuple[str, str]] = []
        seen_packet: set[tuple[str, str]] = set()
        for row in batch_rows:
            hid = row["handoff_id"]
            pair = (row["domain"], row["key"])
            if hid not in mapping or mapping[hid][:2] != pair or pair in seen_packet or pair in union:
                fail(f"packet mapping/overlap error: {packet_id} {hid!r} {pair!r}")
            source_hash = digest(row["source"].encode("utf-8"))
            if source_hash != mapping[hid][2]:
                fail(f"packet source hash mismatch: {packet_id} {pair!r}")
            if phase in {"phase0_policy_audit", "phase1_bulk"}:
                if row["current_translation_vi"]:
                    fail(f"{phase} must have blank current_translation_vi: {packet_id} {pair!r}")
            # Phase 2/3 may carry a blank current target only for unresolved rows.
            # The output gate still forbids `accepted`/`rewritten` with a blank
            # target and requires `needs_context` to return a specific question.

            if source_language == "english":
                policy_row = policy[pair]
                for field in (
                    "content_type", "semantic_class", "translation_policy",
                    "locked_english_terms", "identity_expected",
                ):
                    if row[field] != policy_row[field]:
                        fail(f"packet English policy field mismatch {field}: {packet_id} {pair!r}")
                rule = policy_row["translation_policy"]
                if phase != "phase0_policy_audit" and rule in {
                    "exclude_or_keep_technical", "needs_policy_context",
                }:
                    fail(f"unresolved/excluded policy leaked into {phase}: {packet_id} {pair!r}")
                if rule == "keep_identity" and policy_row["identity_expected"] != row["source"]:
                    fail(f"keep_identity expected target must equal exact source: {packet_id} {pair!r}")
                for term in json.loads(policy_row["locked_english_terms"] or "[]"):
                    if term_count(row["source"], term) == 0:
                        fail(f"locked term absent from source {term!r}: {packet_id} {pair!r}")
            seen_packet.add(pair)
            packet_keys.append(pair)
        packet_hash = full_key_hash(packet_keys)
        batch_hash = digest(files[batch_name])
        immutable_hash = immutable_rows_hash(batch_rows)
        if (
            packet_manifest.get("row_count") != len(batch_rows)
            or packet_manifest.get("ordered_full_key_sha256") != packet_hash
        ):
            fail(f"packet manifest count/key hash mismatch: {packet_id}")
        if packet_manifest.get("input_payload_sha256") != batch_hash:
            fail(f"packet manifest input payload hash mismatch: {packet_id}")
        if packet_manifest.get("immutable_rows_sha256") != immutable_hash:
            fail(f"packet manifest immutable rows hash mismatch: {packet_id}")
        if (
            entry.get("row_count") != len(batch_rows)
            or entry.get("ordered_full_key_sha256") != packet_hash
            or entry.get("input_payload_sha256") != batch_hash
        ):
            fail(f"work queue packet mismatch: {packet_id}")
        union.extend(packet_keys)
    if set(union) != full_keys or len(union) != len(full_keys):
        fail("packet union does not equal exact project full-key set")
    manifest_packets = project.get("packets")
    manifest_ids = {
        item if isinstance(item, str) else item.get("packet_id")
        for item in manifest_packets or []
    }
    if manifest_ids != packet_ids:
        fail("project manifest packet set mismatch")
    if queue.get("total_packets") != len(packet_ids):
        fail("work queue total_packets mismatch")

    source_snapshot = source_snapshot_hash([
        (domain, key, mapping[hid][2])
        for hid, (domain, key, _) in mapping.items()
    ])
    if project.get("source_snapshot_sha256") != source_snapshot:
        fail("project source_snapshot_sha256 mismatch")
    if source_language == "english":
        if project.get("english_policy_sha256") != digest(files["english-policy.csv"]):
            fail("project english_policy_sha256 mismatch")
    elif project.get("english_policy_sha256") not in {None, ""}:
        fail("non-English project must not pin an English policy")
    if project.get("glossary_sha256") != digest(files["glossary.csv"]):
        fail("project glossary_sha256 mismatch")

    expected_input_mode = project.get("input_mode")
    if expected_input_mode not in {"translation_new", "community_baseline", "phase_rework"}:
        fail("project input_mode invalid")
    for entry in queue_packets:
        packet_id = entry["packet_id"]
        packet_manifest = read_json(files, f"packets/{packet_id}/packet-manifest.json")
        if packet_manifest.get("source_snapshot_sha256") != source_snapshot:
            fail(f"packet source snapshot mismatch: {packet_id}")
        if packet_manifest.get("english_policy_sha256") != project.get("english_policy_sha256"):
            fail(f"packet English policy hash mismatch: {packet_id}")
        if packet_manifest.get("glossary_sha256") != project.get("glossary_sha256"):
            fail(f"packet glossary hash mismatch: {packet_id}")

    return {
        "status": "external_handoff_package_clean",
        "source": str(source),
        "files": len(files),
        "receiver_control_baseline": receiver_baseline,
        "max_active_reserved_subagents": receiver_cap,
        "decision_evidence_encoding": decision_encoding,
        "phase": active_phase,
        "packets": len(packet_ids),
        "rows": len(full_keys),
        "ordered_full_key_sha256": ordered_hash,
    }


def validate_phase_output(package_source: Path, output_source: Path) -> dict:
    if output_source.is_file() and output_source.suffix.lower() == ".csv":
        fail(
            "bare phase-output CSV rejected; return a directory/ZIP with "
            "phase-receipt.json and checksums.sha256"
        )

    files = load_files(package_source)
    package_report = validate_package(package_source)
    project = read_json(files, "project-manifest.json")
    queue = read_json(files, "work-queue.json")
    token_profile = read_json(files, "token-profile.json")
    phase = queue["active_phase"]

    returned = load_files(output_source)
    parse_checksums(returned)
    receipt = read_json(returned, "phase-receipt.json")
    if receipt.get("phase") != phase:
        fail("return receipt phase mismatch")
    packet_id = receipt.get("packet_id")
    queue_entry = next(
        (entry for entry in queue["packets"] if entry.get("packet_id") == packet_id),
        None,
    )
    if queue_entry is None:
        fail(f"return receipt references unknown packet: {packet_id!r}")

    packet_base = f"packets/{packet_id}"
    packet_manifest = read_json(files, f"{packet_base}/packet-manifest.json")
    receipt_bindings = {
        "contract_version": project.get("contract_version"),
        "project": project.get("project"),
        "batch_id": project.get("batch_id"),
        "attempt": packet_manifest.get("attempt"),
        "lease_id": packet_manifest.get("lease_id"),
        "parent_phase_sha256": packet_manifest.get("parent_phase_sha256"),
        "input_payload_sha256": packet_manifest.get("input_payload_sha256"),
        "source_snapshot_sha256": packet_manifest.get("source_snapshot_sha256"),
        "english_policy_sha256": packet_manifest.get("english_policy_sha256"),
        "glossary_sha256": packet_manifest.get("glossary_sha256"),
        "token_profile_sha256": packet_manifest.get("token_profile_sha256"),
        "ordered_full_key_sha256": packet_manifest.get("ordered_full_key_sha256"),
    }
    for field, expected in receipt_bindings.items():
        if receipt.get(field) != expected:
            fail(f"return receipt {field} mismatch")
    if receipt.get("status") != "phase_output_pending_hermes_acceptance":
        fail("return receipt status mismatch")

    batch_name = f"{packet_base}/{packet_manifest.get('input_filename', 'batch.csv')}"
    batch_header, batch_rows = read_csv(files, batch_name)
    if batch_header != BATCH_HEADER:
        fail(f"packet batch schema mismatch: {packet_id}")

    output_meta = receipt.get("output")
    if not isinstance(output_meta, dict):
        fail("return receipt output must be an object")
    output_name = output_meta.get("filename")
    if not isinstance(output_name, str):
        fail("return receipt output filename missing")
    output_name = safe_name(output_name)
    if output_name != packet_manifest.get("output_filename"):
        fail("return output filename mismatch")
    expected_return_files = {"phase-receipt.json", "checksums.sha256", output_name}
    if set(returned) != expected_return_files:
        fail(
            "return package file set mismatch: "
            f"missing={sorted(expected_return_files-set(returned))}, "
            f"extra={sorted(set(returned)-expected_return_files)}"
        )

    map_header, map_rows = read_csv(files, "handoff-id-map.csv")
    if map_header != MAP_HEADER:
        fail("handoff-id-map.csv schema invalid")
    full_mapping = {
        row["handoff_id"]: (row["domain"], row["key"], row["source_sha256"])
        for row in map_rows
    }
    expected_ids = [row["handoff_id"] for row in batch_rows]
    mapping = {hid: full_mapping[hid] for hid in expected_ids}
    input_by_hid = {row["handoff_id"]: row for row in batch_rows}

    policy: dict[tuple[str, str], dict[str, str]] = {}
    if str(project.get("source_language", "")).casefold() == "english":
        policy_header, policy_rows = read_csv(files, "english-policy.csv")
        if policy_header != POLICY_HEADER:
            fail("english-policy.csv schema invalid")
        policy = {(row["domain"], row["key"]): row for row in policy_rows}

    expected_header = (
        PHASE0_OUTPUT_HEADER
        if phase == "phase0_policy_audit"
        else TRANSLATION_OUTPUT_HEADER
    )
    output_header, output_rows = read_csv(returned, output_name)
    if output_header != expected_header:
        fail(f"phase output header mismatch: {output_name}")
    actual_ids = [row["handoff_id"] for row in output_rows]
    if actual_ids != expected_ids:
        fail("phase output ordered identity mismatch")
    output_keys = [(row["domain"], row["key"]) for row in output_rows]
    output_key_hash = full_key_hash(output_keys)
    output_hash = digest(returned[output_name])
    if receipt.get("row_count") != len(output_rows):
        fail("return receipt row_count mismatch")
    if receipt.get("ordered_full_key_sha256") != output_key_hash:
        fail("return receipt ordered_full_key_sha256 mismatch")
    if output_meta.get("row_count") != len(output_rows):
        fail("return receipt output row_count mismatch")
    if output_meta.get("ordered_full_key_sha256") != output_key_hash:
        fail("return receipt output ordered_full_key_sha256 mismatch")
    if output_meta.get("sha256") != output_hash:
        fail("return receipt output SHA-256 mismatch")

    accepted_actions = PHASE_ACTIONS[phase]
    action_counts: dict[str, int] = {}
    unresolved: list[str] = []
    for row in output_rows:
        hid = row["handoff_id"]
        pair = (row["domain"], row["key"])
        action = row["review_action"]
        if hid not in mapping or mapping[hid][:2] != pair:
            fail(f"output identity mismatch: {hid!r} {pair!r}")
        if action not in accepted_actions:
            fail(f"invalid action for {phase}: {action!r}")
        action_counts[action] = action_counts.get(action, 0) + 1
        if action == "needs_context":
            unresolved.append(hid)

        if phase == "phase0_policy_audit":
            proposal = row["proposed_translation_policy"]
            if action == "propose_change" and (
                proposal not in POLICIES or not row["reason"]
            ):
                fail(f"Phase 0 proposal lacks valid policy/reason: {pair!r}")
            if proposal == "keep_identity" and not row["proposed_identity_expected"]:
                fail(f"Phase 0 keep_identity proposal lacks expected target: {pair!r}")
            if row["proposed_locked_english_terms"]:
                try:
                    parsed_terms = json.loads(row["proposed_locked_english_terms"])
                except Exception as exc:
                    fail(f"invalid proposed locked terms {pair!r}: {exc}")
                if not isinstance(parsed_terms, list) or not all(
                    isinstance(term, str) and term for term in parsed_terms
                ):
                    fail(f"proposed locked terms must be nonempty strings: {pair!r}")
            if action == "needs_context" and not (row["reason"] or row["notes"]):
                fail(f"Phase 0 needs_context lacks a specific question: {pair!r}")
            continue

        target = row["translation_vi"]
        try:
            reason_codes = json.loads(row["reason_codes"] or "[]")
        except Exception as exc:
            fail(f"reason_codes must be a JSON list for {pair!r}: {exc}")
        if not isinstance(reason_codes, list) or not all(
            isinstance(code, str) and code for code in reason_codes
        ):
            fail(f"reason_codes must contain nonempty strings: {pair!r}")
        if action == "needs_context":
            if target or not row["notes"]:
                fail(f"needs_context must have blank target + question: {pair!r}")
            continue
        if not target:
            fail(f"nonblank target required: {pair!r}")

        input_row = input_by_hid[hid]
        source_text = input_row["source"]
        current = input_row["current_translation_vi"]
        rule = policy.get(pair, {}).get("translation_policy")
        if rule == "keep_identity" and target != policy[pair]["identity_expected"]:
            fail(f"identity target mismatch: {pair!r}")
        if rule in {"translate_full", "translate_with_locked_terms"} and target == source_text:
            fail(f"unexplained exact English residual: {pair!r}")
        if rule == "translate_with_locked_terms":
            for term in json.loads(policy[pair]["locked_english_terms"] or "[]"):
                if term_count(source_text, term) != term_count(target, term):
                    fail(f"locked English term count mismatch {term!r}: {pair!r}")

        validate_token_preservation(source_text, target, token_profile, pair)
        try:
            protected = json.loads(input_row["protected_tokens"] or "[]")
        except Exception as exc:
            fail(f"protected_tokens must be a JSON list for {pair!r}: {exc}")
        if not isinstance(protected, list) or not all(
            isinstance(token, str) and token for token in protected
        ):
            fail(f"protected_tokens must contain nonempty strings: {pair!r}")
        for token in protected:
            source_count = source_text.count(token)
            if source_count == 0 or target.count(token) != source_count:
                fail(f"declared protected token mismatch {token!r}: {pair!r}")

        if phase in {"phase2_language_qa", "phase3_semantic_audit"}:
            if action == "accepted" and target != current:
                fail(f"accepted row changed current translation: {pair!r}")
            if action == "rewritten" and (
                target == current or not (reason_codes or row["notes"])
            ):
                fail(f"rewritten row lacks a changed target/reason: {pair!r}")

    if receipt.get("action_counts") != action_counts:
        fail("return receipt action_counts mismatch")
    if receipt.get("unresolved_handoff_ids") != unresolved:
        fail("return receipt unresolved_handoff_ids mismatch")

    return {
        "status": "external_phase_return_package_clean",
        "phase": phase,
        "packet_id": packet_id,
        "rows": len(output_rows),
        "action_counts": action_counts,
        "unresolved_handoff_ids": unresolved,
        "package_ordered_full_key_sha256": package_report["ordered_full_key_sha256"],
        "return_package_sha256": (
            digest(output_source.read_bytes())
            if output_source.is_file()
            else None
        ),
        "output": {"filename": output_name, "sha256": digest(returned[output_name])},
        "receipt_sha256": digest(returned["phase-receipt.json"]),
    }


def csv_bytes(header: list[str], rows: list[dict[str, str]]) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=header, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode("utf-8-sig")


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def build_fixture(root: Path) -> None:
    source = "Shadow Strike"
    source_hash = digest(source.encode("utf-8"))
    pair = ("Game", "Skill.ShadowStrike.Name")
    hid = "h000001"
    packet_id = "packet-0001"
    packet_hash = full_key_hash([pair])
    snapshot_hash = source_snapshot_hash([(pair[0], pair[1], source_hash)])

    map_rows = [{
        "handoff_id": hid,
        "domain": pair[0],
        "key": pair[1],
        "source_sha256": source_hash,
    }]
    policy_rows = [{
        "domain": pair[0], "key": pair[1], "source_sha256": source_hash,
        "content_type": "ui_short", "semantic_class": "skill_name",
        "translation_policy": "keep_identity", "locked_english_terms": "[]",
        "identity_expected": source, "reason": "standalone skill name",
        "evidence": "current table/property path", "policy_status": "receiver_review",
    }]
    batch_rows = [{
        "handoff_id": hid, "domain": pair[0], "key": pair[1],
        "content_type": "ui_short", "speaker": "", "addressee": "",
        "source": source, "reference": "", "previous_context": "",
        "following_context": "", "protected_tokens": "[]",
        "character_limit": "", "semantic_class": "skill_name",
        "translation_policy": "keep_identity", "locked_english_terms": "[]",
        "identity_expected": source, "community_vi_reference": "",
        "work_route": "policy_audit", "current_translation_vi": "",
    }]

    map_bytes = csv_bytes(MAP_HEADER, map_rows)
    policy_bytes = csv_bytes(POLICY_HEADER, policy_rows)
    glossary_bytes = csv_bytes(
        ["term", "translation_vi", "rule", "locked", "evidence"],
        [],
    )
    batch = csv_bytes(BATCH_HEADER, batch_rows)
    policy_hash = digest(policy_bytes)
    glossary_hash = digest(glossary_bytes)
    batch_schema_bytes = (
        json.dumps(
            {"schema_version": 1, "columns": BATCH_HEADER},
            ensure_ascii=False,
            indent=2,
        ) + "\n"
    ).encode("utf-8")
    output_schema_bytes = (
        json.dumps(
            {
                "schema_version": 1,
                "phase0_columns": PHASE0_OUTPUT_HEADER,
                "translation_phase_columns": TRANSLATION_OUTPUT_HEADER,
            },
            ensure_ascii=False,
            indent=2,
        ) + "\n"
    ).encode("utf-8")
    token_vectors = [
        {
            "text": r"Use {player} <b>%02d</b>\n",
            "tokens": ["{player}", "<b>", "%02d", "</b>", r"\n"],
        },
        {"text": "Gain 10% for accuracy", "tokens": []},
    ]
    token_profile = {
        "token_profile_id": "fixture-tags-v1",
        "schema_version": 1,
        "extractors": ["brace", "printf", "rich_text", "escaped_controls"],
        "compare": {"multiset": True, "order": False, "nesting": True},
        "known_rich_text_tags": ["b", "color"],
        "printf_requires_no_whitespace_after_percent": True,
        "test_vectors": token_vectors,
        "project_test_vectors_sha256": token_vectors_hash(token_vectors),
    }
    token_profile_bytes = (
        json.dumps(token_profile, ensure_ascii=False, indent=2) + "\n"
    ).encode("utf-8")

    packet_manifest = {
        "contract_version": "1.0.0", "schema_version": 1,
        "project": "Fixture", "batch_id": "fixture-001",
        "packet_id": packet_id, "attempt": 1,
        "lease_id": "fixture-lease-0001",
        "lease_expires_at": "2099-01-01T00:00:00Z",
        "phase": "phase0_policy_audit", "parent_phase_sha256": None,
        "source_snapshot_sha256": snapshot_hash,
        "english_policy_sha256": policy_hash,
        "glossary_sha256": glossary_hash,
        "token_profile_id": token_profile["token_profile_id"],
        "token_profile_sha256": digest(token_profile_bytes),
        "row_count": 1, "estimated_input_tokens": 10,
        "estimated_output_tokens": 10,
        "first_handoff_id": hid, "last_handoff_id": hid,
        "ordered_full_key_sha256": packet_hash,
        "immutable_rows_sha256": immutable_rows_hash(batch_rows),
        "input_filename": "batch.csv", "input_payload_sha256": digest(batch),
        "output_filename": f"policy-audit_{packet_id}.csv",
        "output_format": "csv", "semantic_group": "skills",
        "permitted_review_actions": sorted(PHASE_ACTIONS["phase0_policy_audit"]),
    }
    project = {
        "contract_version": "1.0.0", "schema_version": 1,
        "project": "Fixture", "batch_id": "fixture-001",
        "build_id": "1", "source_language": "English",
        "target_language": "Vietnamese", "input_mode": "translation_new",
        "translation_only": True, "canonical_write_authority": "Hermes",
        "identity": {
            "canonical_key": ["domain", "key"],
            "handoff_id_mapping": "handoff-id-map.csv",
        },
        "source_snapshot_sha256": snapshot_hash,
        "ordered_full_key_sha256": packet_hash,
        "batch_schema_sha256": digest(batch_schema_bytes),
        "output_schema_sha256": digest(output_schema_bytes),
        "english_policy_sha256": policy_hash,
        "glossary_sha256": glossary_hash,
        "token_profile_id": token_profile["token_profile_id"],
        "token_profile_file": "token-profile.json",
        "token_profile_sha256": digest(token_profile_bytes),
        "phase_contract": list(PHASE_ACTIONS),
        "policy_ready_for_bulk": False,
        "output_format": "csv",
        "immutable_columns": ["handoff_id", "domain", "key"],
        "packets": [{"packet_id": packet_id}],
    }
    queue = {
        "schema_version": 1,
        "authority": "derived_cache_rebuild_from_packet_manifests_acceptance_receipts_and_merge_ledger",
        "project": "Fixture", "active_phase": "phase0_policy_audit",
        "parent_phase_sha256": None,
        "packets": [{
            "packet_id": packet_id, "attempt": 1,
            "semantic_group": "skills", "row_count": 1,
            "ordered_full_key_sha256": packet_hash, "phase_state": "pending",
            "input_payload_sha256": digest(batch),
            "output_filename": f"policy-audit_{packet_id}.csv",
            "accepted_output_sha256": None,
        }],
        "completed_packets": 0, "total_packets": 1, "status": "pending",
    }
    files: dict[str, bytes] = {
        "START-HERE.md": b"fixture\n",
        "TRANSLATION-PROMPT.txt": b"fixture\n",
        "protected-tokens.md": b"fixture\n",
        "batch-schema.json": batch_schema_bytes,
        "output-schema.json": output_schema_bytes,
        "token-profile.json": token_profile_bytes,
        "handoff-id-map.csv": map_bytes,
        "english-policy.csv": policy_bytes,
        "glossary.csv": glossary_bytes,
        f"packets/{packet_id}/batch.csv": batch,
    }
    for name, value in {
        "project-manifest.json": project,
        "work-queue.json": queue,
        f"packets/{packet_id}/packet-manifest.json": packet_manifest,
    }.items():
        files[name] = (
            json.dumps(value, ensure_ascii=False, indent=2) + "\n"
        ).encode("utf-8")
    files["checksums.sha256"] = "".join(
        f"{digest(data)}  {name}\n" for name, data in sorted(files.items())
    ).encode("utf-8")
    for name, data in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)


def rewrite_checksums(root: Path) -> None:
    files = {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(p for p in root.rglob("*") if p.is_file())
        if path.name != "checksums.sha256"
    }
    (root / "checksums.sha256").write_text(
        "".join(f"{digest(data)}  {name}\n" for name, data in files.items()),
        encoding="utf-8",
    )


def rewrite_fixture_batch(root: Path, updates: dict[str, str]) -> None:
    packet_id = "packet-0001"
    batch_path = root / f"packets/{packet_id}/batch.csv"
    with batch_path.open("r", encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    rows[0].update(updates)
    batch = csv_bytes(BATCH_HEADER, rows)
    batch_path.write_bytes(batch)

    manifest_path = root / f"packets/{packet_id}/packet-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["input_payload_sha256"] = digest(batch)
    manifest["immutable_rows_sha256"] = immutable_rows_hash(rows)
    write_json(manifest_path, manifest)

    queue_path = root / "work-queue.json"
    queue = json.loads(queue_path.read_text(encoding="utf-8"))
    queue["packets"][0]["input_payload_sha256"] = digest(batch)
    write_json(queue_path, queue)
    rewrite_checksums(root)


def rewrite_fixture_phase(
    root: Path,
    phase: str,
    *,
    current_translation_vi: str,
    policy_rule: str,
) -> None:
    if phase not in PHASE_ACTIONS or policy_rule not in POLICIES:
        raise ValueError("invalid fixture phase/policy")
    packet_id = "packet-0001"
    parent = None if phase == "phase0_policy_audit" else "a" * 64
    output_names = {
        "phase0_policy_audit": f"policy-audit_{packet_id}.csv",
        "phase1_bulk": f"translated_{packet_id}.csv",
        "phase2_language_qa": f"qa_{packet_id}.csv",
        "phase3_semantic_audit": f"audited_{packet_id}.csv",
    }

    policy_path = root / "english-policy.csv"
    with policy_path.open("r", encoding="utf-8-sig", newline="") as stream:
        policy_rows = list(csv.DictReader(stream))
    policy_rows[0]["translation_policy"] = policy_rule
    policy_rows[0]["identity_expected"] = (
        "Shadow Strike" if policy_rule == "keep_identity" else ""
    )
    policy_rows[0]["policy_status"] = (
        "receiver_review" if phase == "phase0_policy_audit" else "locked"
    )
    policy_bytes = csv_bytes(POLICY_HEADER, policy_rows)
    policy_path.write_bytes(policy_bytes)

    batch_path = root / f"packets/{packet_id}/batch.csv"
    with batch_path.open("r", encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    rows[0]["translation_policy"] = policy_rule
    rows[0]["identity_expected"] = policy_rows[0]["identity_expected"]
    rows[0]["current_translation_vi"] = current_translation_vi
    rows[0]["work_route"] = (
        "policy_audit" if phase == "phase0_policy_audit"
        else "translate_missing" if phase == "phase1_bulk"
        else "review_existing"
    )
    batch = csv_bytes(BATCH_HEADER, rows)
    batch_path.write_bytes(batch)

    project_path = root / "project-manifest.json"
    project = json.loads(project_path.read_text(encoding="utf-8"))
    project["input_mode"] = (
        "translation_new"
        if phase in {"phase0_policy_audit", "phase1_bulk"}
        else "phase_rework"
    )
    project["policy_ready_for_bulk"] = phase != "phase0_policy_audit"
    project["english_policy_sha256"] = digest(policy_bytes)
    write_json(project_path, project)

    manifest_path = root / f"packets/{packet_id}/packet-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["phase"] = phase
    manifest["parent_phase_sha256"] = parent
    manifest["english_policy_sha256"] = digest(policy_bytes)
    manifest["input_payload_sha256"] = digest(batch)
    manifest["immutable_rows_sha256"] = immutable_rows_hash(rows)
    manifest["output_filename"] = output_names[phase]
    manifest["permitted_review_actions"] = sorted(PHASE_ACTIONS[phase])
    write_json(manifest_path, manifest)

    queue_path = root / "work-queue.json"
    queue = json.loads(queue_path.read_text(encoding="utf-8"))
    queue["active_phase"] = phase
    queue["parent_phase_sha256"] = parent
    queue["packets"][0]["input_payload_sha256"] = digest(batch)
    queue["packets"][0]["output_filename"] = output_names[phase]
    queue["packets"][0]["accepted_output_sha256"] = None
    write_json(queue_path, queue)
    rewrite_checksums(root)


def build_return_fixture(
    root: Path,
    package_root: Path,
    *,
    action: str | None = None,
    target: str | None = None,
    reason_codes: list[str] | None = None,
    notes: str = "",
) -> None:
    package_files = load_files(package_root)
    project = read_json(package_files, "project-manifest.json")
    queue = read_json(package_files, "work-queue.json")
    packet_id = queue["packets"][0]["packet_id"]
    packet_manifest = read_json(
        package_files, f"packets/{packet_id}/packet-manifest.json"
    )
    phase = packet_manifest["phase"]
    output_name = packet_manifest["output_filename"]
    if phase == "phase0_policy_audit":
        selected_action = action or "accepted"
        output_rows = [{
            "handoff_id": "h000001", "domain": "Game",
            "key": "Skill.ShadowStrike.Name", "review_action": selected_action,
            "proposed_translation_policy": "",
            "proposed_locked_english_terms": "",
            "proposed_identity_expected": "", "reason": "", "notes": notes,
        }]
        output = csv_bytes(PHASE0_OUTPUT_HEADER, output_rows)
    else:
        default_actions = {
            "phase1_bulk": "translated",
            "phase2_language_qa": "accepted",
            "phase3_semantic_audit": "accepted",
        }
        selected_action = action or default_actions[phase]
        if target is None:
            target = (
                "Shadow Strike"
                if phase == "phase1_bulk"
                else "Đòn Đánh Bóng Tối"
            )
        output_rows = [{
            "handoff_id": "h000001", "domain": "Game",
            "key": "Skill.ShadowStrike.Name", "translation_vi": target,
            "review_action": selected_action,
            "reason_codes": json.dumps(reason_codes or [], ensure_ascii=False),
            "notes": notes,
        }]
        output = csv_bytes(TRANSLATION_OUTPUT_HEADER, output_rows)
    receipt = {
        "contract_version": project["contract_version"], "schema_version": 1,
        "project": project["project"], "batch_id": project["batch_id"],
        "packet_id": packet_id, "attempt": packet_manifest["attempt"],
        "lease_id": packet_manifest["lease_id"],
        "phase": packet_manifest["phase"],
        "parent_phase_sha256": packet_manifest["parent_phase_sha256"],
        "input_payload_sha256": packet_manifest["input_payload_sha256"],
        "source_snapshot_sha256": packet_manifest["source_snapshot_sha256"],
        "english_policy_sha256": packet_manifest["english_policy_sha256"],
        "glossary_sha256": packet_manifest["glossary_sha256"],
        "token_profile_sha256": packet_manifest["token_profile_sha256"],
        "ordered_full_key_sha256": packet_manifest["ordered_full_key_sha256"],
        "row_count": len(output_rows),
        "action_counts": {selected_action: len(output_rows)},
        "unresolved_handoff_ids": (
            ["h000001"] if selected_action == "needs_context" else []
        ),
        "output": {
            "filename": output_name, "row_count": len(output_rows),
            "ordered_full_key_sha256": packet_manifest["ordered_full_key_sha256"],
            "sha256": digest(output),
        },
        "validator_version": "fixture",
        "status": "phase_output_pending_hermes_acceptance",
    }
    root.mkdir(parents=True, exist_ok=True)
    (root / output_name).write_bytes(output)
    write_json(root / "phase-receipt.json", receipt)
    rewrite_checksums(root)


def self_test() -> None:
    token_profile = {
        "extractors": ["brace", "printf", "rich_text", "escaped_controls"],
        "known_rich_text_tags": ["b", "color"],
        "printf_requires_no_whitespace_after_percent": True,
    }
    token_text = r"Use {player} <b>%02d</b>\n"
    assert extract_tokens(token_text, token_profile) == [
        "{player}", "<b>", "%02d", "</b>", r"\n",
    ]
    assert extract_tokens("Gain 10% for accuracy", token_profile) == []
    assert extract_tokens("<color=#FF0000>Text</color>", token_profile) == [
        "<color=#FF0000>", "</color>",
    ]
    assert rich_text_nesting_signature(
        "<size=50><color=#FF0000>Text</color></size>", token_profile
    )
    bracket_profile = dict(token_profile)
    bracket_profile["extractors"] = token_profile["extractors"] + ["square_brackets"]
    assert extract_tokens("Tăng [Nội lực]", bracket_profile) == ["[", "]"]
    token_profile["test_vectors"] = [
        {"text": token_text, "tokens": ["{player}", "<b>", "%02d", "</b>", r"\n"]},
        {"text": "Gain 10% for accuracy", "tokens": []},
    ]
    token_profile["project_test_vectors_sha256"] = token_vectors_hash(
        token_profile["test_vectors"]
    )
    validate_token_profile(token_profile)
    wrong_profile = dict(token_profile)
    wrong_profile["project_test_vectors_sha256"] = "0" * 64
    try:
        validate_token_profile(wrong_profile)
    except InvalidPackage:
        pass
    else:
        raise AssertionError("wrong token-profile test-vector hash unexpectedly passed")

    try:
        validate_token_preservation(
            "Use {player} %02d", "Dùng {player}", token_profile,
            ("Game", "Token.Test"),
        )
    except InvalidPackage:
        pass
    else:
        raise AssertionError("actual source/target token mismatch unexpectedly passed")

    nesting_profile = dict(token_profile)
    nesting_profile["compare"] = {"multiset": True, "order": False, "nesting": True}
    try:
        validate_token_preservation(
            "<b><color>Text</color></b>",
            "<b>Text</b><color>Text</color>",
            nesting_profile,
            ("Game", "Token.Nesting"),
        )
    except InvalidPackage:
        pass
    else:
        raise AssertionError("changed rich-text nesting unexpectedly passed")

    with tempfile.TemporaryDirectory(prefix="viethoa-handoff-test-") as temp:
        root = Path(temp) / "valid"
        build_fixture(root)
        validate_package(root)

        compact = Path(temp) / "compact-v21"
        shutil.copytree(root, compact)
        decision_schema_path = compact / "decision-evidence-schema.json"
        expander_path = compact / "tools" / "expand_compact_decisions.py"
        write_json(decision_schema_path, {
            "schema_version": 1,
            "schema": "agy-explicit-review/v1",
        })
        expander_path.parent.mkdir(parents=True, exist_ok=True)
        expander_path.write_text("# checksum-pinned fixture\n", encoding="utf-8")
        compact_project_path = compact / "project-manifest.json"
        compact_project = json.loads(compact_project_path.read_text(encoding="utf-8"))
        compact_project.update({
            "receiver_control_baseline": "AGY-VIETHOA-HANDOFF/2.1",
            "max_active_reserved_subagents": 7,
            "default_active_workers": 2,
            "decision_evidence_encoding": "compact-explicit-v1",
            "decision_evidence_schema": "decision-evidence-schema.json",
            "decision_evidence_schema_sha256": digest(decision_schema_path.read_bytes()),
            "decision_evidence_expander": "tools/expand_compact_decisions.py",
            "decision_evidence_expander_sha256": digest(expander_path.read_bytes()),
        })
        write_json(compact_project_path, compact_project)
        rewrite_checksums(compact)
        compact_report = validate_package(compact)
        assert compact_report["max_active_reserved_subagents"] == 7
        assert compact_report["decision_evidence_encoding"] == "compact-explicit-v1"

        bad_compact_cap = Path(temp) / "compact-bad-cap"
        shutil.copytree(compact, bad_compact_cap)
        bad_cap_project_path = bad_compact_cap / "project-manifest.json"
        bad_cap_project = json.loads(bad_cap_project_path.read_text(encoding="utf-8"))
        bad_cap_project["max_active_reserved_subagents"] = 8
        write_json(bad_cap_project_path, bad_cap_project)
        rewrite_checksums(bad_compact_cap)
        try:
            validate_package(bad_compact_cap)
        except InvalidPackage:
            pass
        else:
            raise AssertionError("compact package cap 8 unexpectedly passed")

        bad_compact_hash = Path(temp) / "compact-bad-expander-hash"
        shutil.copytree(compact, bad_compact_hash)
        bad_hash_project_path = bad_compact_hash / "project-manifest.json"
        bad_hash_project = json.loads(bad_hash_project_path.read_text(encoding="utf-8"))
        bad_hash_project["decision_evidence_expander_sha256"] = "0" * 64
        write_json(bad_hash_project_path, bad_hash_project)
        rewrite_checksums(bad_compact_hash)
        try:
            validate_package(bad_compact_hash)
        except InvalidPackage:
            pass
        else:
            raise AssertionError("compact package wrong expander hash unexpectedly passed")

        archive = Path(temp) / "valid.zip"
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for path in sorted(p for p in root.rglob("*") if p.is_file()):
                zf.write(path, path.relative_to(root).as_posix())
        validate_package(archive)

        legacy = Path(temp) / "legacy-packet-contract"
        shutil.copytree(root, legacy)
        legacy_manifest_path = legacy / "packets/packet-0001/packet-manifest.json"
        legacy_manifest = json.loads(legacy_manifest_path.read_text(encoding="utf-8"))
        del legacy_manifest["input_payload_sha256"]
        write_json(legacy_manifest_path, legacy_manifest)
        rewrite_checksums(legacy)
        try:
            validate_package(legacy)
        except InvalidPackage:
            pass
        else:
            raise AssertionError("legacy packet contract unexpectedly passed")

        phase0_seeded = Path(temp) / "phase0-seeded-current"
        shutil.copytree(root, phase0_seeded)
        rewrite_fixture_batch(phase0_seeded, {"current_translation_vi": "Bản nháp"})
        try:
            validate_package(phase0_seeded)
        except InvalidPackage:
            pass
        else:
            raise AssertionError("Phase 0 seeded current_translation_vi unexpectedly passed")

        phase0 = Path(temp) / "phase0-output.csv"
        phase0.write_bytes(csv_bytes(
            [
                "handoff_id", "domain", "key", "review_action",
                "proposed_translation_policy", "proposed_locked_english_terms",
                "proposed_identity_expected", "reason", "notes",
            ],
            [{
                "handoff_id": "h000001", "domain": "Game", "key": "Skill.ShadowStrike.Name",
                "review_action": "accepted", "proposed_translation_policy": "",
                "proposed_locked_english_terms": "", "proposed_identity_expected": "",
                "reason": "", "notes": "",
            }],
        ))
        try:
            validate_phase_output(root, phase0)
        except InvalidPackage:
            pass
        else:
            raise AssertionError("bare CSV without receipt/checksums unexpectedly passed")

        returned = Path(temp) / "return-valid"
        build_return_fixture(returned, root)
        validate_phase_output(root, returned)

        phase1 = Path(temp) / "phase1-valid"
        shutil.copytree(root, phase1)
        rewrite_fixture_phase(
            phase1, "phase1_bulk",
            current_translation_vi="", policy_rule="keep_identity",
        )
        validate_package(phase1)
        phase1_return = Path(temp) / "phase1-return-valid"
        build_return_fixture(phase1_return, phase1, target="Shadow Strike")
        validate_phase_output(phase1, phase1_return)

        phase1_unresolved = Path(temp) / "phase1-unresolved-policy"
        shutil.copytree(root, phase1_unresolved)
        rewrite_fixture_phase(
            phase1_unresolved, "phase1_bulk",
            current_translation_vi="", policy_rule="needs_policy_context",
        )
        try:
            validate_package(phase1_unresolved)
        except InvalidPackage:
            pass
        else:
            raise AssertionError("Phase 1 unresolved English policy unexpectedly passed")

        phase1_unlocked = Path(temp) / "phase1-unlocked-policy"
        shutil.copytree(phase1, phase1_unlocked)
        unlocked_policy_path = phase1_unlocked / "english-policy.csv"
        unlocked_policy = unlocked_policy_path.read_bytes().replace(
            b",locked\r\n", b",receiver_review\r\n"
        ).replace(b",locked\n", b",receiver_review\n")
        unlocked_policy_path.write_bytes(unlocked_policy)
        unlocked_project_path = phase1_unlocked / "project-manifest.json"
        unlocked_project = json.loads(
            unlocked_project_path.read_text(encoding="utf-8")
        )
        unlocked_project["english_policy_sha256"] = digest(unlocked_policy)
        write_json(unlocked_project_path, unlocked_project)
        unlocked_manifest_path = (
            phase1_unlocked / "packets/packet-0001/packet-manifest.json"
        )
        unlocked_manifest = json.loads(
            unlocked_manifest_path.read_text(encoding="utf-8")
        )
        unlocked_manifest["english_policy_sha256"] = digest(unlocked_policy)
        write_json(unlocked_manifest_path, unlocked_manifest)
        rewrite_checksums(phase1_unlocked)
        try:
            validate_package(phase1_unlocked)
        except InvalidPackage:
            pass
        else:
            raise AssertionError("Phase 1 unlocked English policy unexpectedly passed")

        phase2 = Path(temp) / "phase2-valid"
        shutil.copytree(root, phase2)
        rewrite_fixture_phase(
            phase2, "phase2_language_qa",
            current_translation_vi="Đòn Đánh Bóng Tối",
            policy_rule="translate_full",
        )
        validate_package(phase2)

        phase2_unresolved = Path(temp) / "phase2-unresolved-current"
        shutil.copytree(root, phase2_unresolved)
        rewrite_fixture_phase(
            phase2_unresolved, "phase2_language_qa",
            current_translation_vi="", policy_rule="translate_full",
        )
        validate_package(phase2_unresolved)
        phase2_unresolved_return = Path(temp) / "phase2-unresolved-return"
        build_return_fixture(
            phase2_unresolved_return, phase2_unresolved,
            action="needs_context", target="", notes="Ai đang nói với ai trong cảnh này?",
        )
        validate_phase_output(phase2_unresolved, phase2_unresolved_return)

        phase2_return = Path(temp) / "phase2-return-valid"
        build_return_fixture(
            phase2_return, phase2,
            action="accepted", target="Đòn Đánh Bóng Tối",
        )
        validate_phase_output(phase2, phase2_return)

        phase2_changed_accepted = Path(temp) / "phase2-changed-accepted"
        build_return_fixture(
            phase2_changed_accepted, phase2,
            action="accepted", target="Đòn Bóng Tối",
        )
        try:
            validate_phase_output(phase2, phase2_changed_accepted)
        except InvalidPackage:
            pass
        else:
            raise AssertionError("Phase 2 accepted changed target unexpectedly passed")

        phase2_unchanged_rewrite = Path(temp) / "phase2-unchanged-rewrite"
        build_return_fixture(
            phase2_unchanged_rewrite, phase2,
            action="rewritten", target="Đòn Đánh Bóng Tối",
            reason_codes=["TERM"],
        )
        try:
            validate_phase_output(phase2, phase2_unchanged_rewrite)
        except InvalidPackage:
            pass
        else:
            raise AssertionError("Phase 2 unchanged rewritten target unexpectedly passed")

        phase3 = Path(temp) / "phase3-valid"
        shutil.copytree(root, phase3)
        rewrite_fixture_phase(
            phase3, "phase3_semantic_audit",
            current_translation_vi="Đòn Đánh Bóng Tối",
            policy_rule="translate_full",
        )
        validate_package(phase3)
        phase3_return = Path(temp) / "phase3-return-valid"
        build_return_fixture(
            phase3_return, phase3,
            action="accepted", target="Đòn Đánh Bóng Tối",
        )
        validate_phase_output(phase3, phase3_return)

        wrong_receipt = Path(temp) / "return-wrong-receipt"
        shutil.copytree(returned, wrong_receipt)
        receipt_path = wrong_receipt / "phase-receipt.json"
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        receipt["phase"] = "phase1_bulk"
        write_json(receipt_path, receipt)
        rewrite_checksums(wrong_receipt)
        try:
            validate_phase_output(root, wrong_receipt)
        except InvalidPackage:
            pass
        else:
            raise AssertionError("wrong receipt phase unexpectedly passed")

        wrong_count = Path(temp) / "return-wrong-count"
        shutil.copytree(returned, wrong_count)
        count_receipt_path = wrong_count / "phase-receipt.json"
        count_receipt = json.loads(count_receipt_path.read_text(encoding="utf-8"))
        count_receipt["row_count"] = 99
        write_json(count_receipt_path, count_receipt)
        rewrite_checksums(wrong_count)
        try:
            validate_phase_output(root, wrong_count)
        except InvalidPackage:
            pass
        else:
            raise AssertionError("wrong receipt row_count unexpectedly passed")

        wrong_input = Path(temp) / "return-wrong-input-hash"
        shutil.copytree(returned, wrong_input)
        input_receipt_path = wrong_input / "phase-receipt.json"
        input_receipt = json.loads(input_receipt_path.read_text(encoding="utf-8"))
        input_receipt["input_payload_sha256"] = "f" * 64
        write_json(input_receipt_path, input_receipt)
        rewrite_checksums(wrong_input)
        try:
            validate_phase_output(root, wrong_input)
        except InvalidPackage:
            pass
        else:
            raise AssertionError("wrong receipt input payload hash unexpectedly passed")

        bad = Path(temp) / "bad"
        shutil.copytree(root, bad)
        policy = bad / "english-policy.csv"
        policy.write_bytes(policy.read_bytes().replace(b"keep_identity", b"translate_full"))
        try:
            validate_package(bad)
        except InvalidPackage:
            pass
        else:
            raise AssertionError("corrupted package unexpectedly passed")

        traversal = Path(temp) / "traversal.zip"
        with zipfile.ZipFile(traversal, "w") as zf:
            zf.writestr("../escape.txt", "bad")
        try:
            validate_package(traversal)
        except InvalidPackage:
            pass
        else:
            raise AssertionError("ZIP traversal unexpectedly passed")

        symlink_zip = Path(temp) / "symlink.zip"
        with zipfile.ZipFile(symlink_zip, "w") as zf:
            link = zipfile.ZipInfo("link")
            link.create_system = 3
            link.external_attr = 0o120777 << 16
            zf.writestr(link, "target")
        try:
            load_files(symlink_zip)
        except InvalidPackage:
            pass
        else:
            raise AssertionError("ZIP symlink member unexpectedly passed")

        bounded_zip = Path(temp) / "bounded.zip"
        with zipfile.ZipFile(bounded_zip, "w") as zf:
            zf.writestr("a.txt", "aa")
            zf.writestr("b.txt", "bb")
        try:
            load_files(bounded_zip, max_files=1)
        except InvalidPackage:
            pass
        else:
            raise AssertionError("ZIP file-count ceiling unexpectedly passed")
        try:
            load_files(bounded_zip, max_expanded_bytes=3)
        except InvalidPackage:
            pass
        else:
            raise AssertionError("ZIP expanded-size ceiling unexpectedly passed")
    print("PASS external_handoff_package_self_test")


def main(argv: list[str]) -> int:
    if argv == ["--self-test"]:
        self_test()
        return 0
    if len(argv) not in {1, 3} or (len(argv) == 3 and argv[1] != "--output"):
        print(
            "usage: python validate_external_handoff_package.py <handoff-dir-or-zip> [--output <return-dir-or-zip>]|--self-test",
            file=sys.stderr,
        )
        return 2
    try:
        package = Path(argv[0]).resolve()
        report = (
            validate_phase_output(package, Path(argv[2]).resolve())
            if len(argv) == 3
            else validate_package(package)
        )
    except (InvalidPackage, OSError, zipfile.BadZipFile) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
