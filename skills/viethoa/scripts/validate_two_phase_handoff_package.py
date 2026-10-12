from __future__ import annotations

import ast
import csv
import hashlib
import json
import re
import stat
import sys
import tempfile
import zipfile
from contextlib import contextmanager
from pathlib import Path, PurePosixPath
from typing import Any, Iterator

BASELINE = "AGY-VIETHOA-HANDOFF/2.5-TWO-PHASE-DRAFT12-PREVIEW-FINAL0-GUARDED"
CONTRACT_VERSION = "2.5.1"
MAX_PHASE1_SUBAGENTS = 12
SEMANTIC_AUTH_SCHEMA = "agy-semantic-origin-authorization/v3"
SEMANTIC_GUARD_SCHEMA = "agy-semantic-origin-guard/v1"
RECHECK_SCHEDULE_SCHEMA = "agy-phase2-recheck-schedule/v1"
SEMANTIC_AUTH_FIELDS = {
    "schema", "contract", "phase", "package_id", "run_id", "manifest_sha256",
    "package_root", "work_root", "controller", "schedule", "challenge_overlay",
    "current_prompt_path", "current_response_path", "response_schema",
    "allowed_run_commands", "challenge_ids_by_batch",
}
PHASE1 = "phase1_parallel_draft"
PHASE2 = "phase2_main_only_final"
POST_PHASE1_ROUTES = [
    "build_demo_patch",
    "external_phase2_antigravity",
    "hermes_cron_phase2",
    "pause",
]
HEX64 = re.compile(r"^[0-9a-f]{64}$")
SAFE_ID = re.compile(r"^[A-Za-z0-9._-]{1,160}$")
FORBIDDEN_SUFFIXES = {
    ".exe", ".dll", ".pak", ".ucas", ".utoc", ".bin", ".asset", ".bundle",
    ".pdb", ".key", ".pem", ".pfx", ".pyc",
}
MAX_FILES = 20_000
MAX_BYTES = 512 * 1024 * 1024
PRIVATE_PATTERNS = (
    re.compile(rb"(?i)[a-z]:[/\\]users[/\\][^/\\\s\"']+"),
    re.compile(rb"(?i)/(?:home|users)/[^/\s\"']+"),
    re.compile(rb"(?i)\\\\users\\[^\\\s\"']+"),
)
COMMON_REQUIRED = {
    "project-manifest.json", "START-HERE.md", "handoff-id-map.csv", "glossary.csv",
    "english-policy.csv", "token-profile.json", "TRANSLATION-PROMPT.txt",
    "host/semantic-authoring-authorization.template.json",
    "tools/controller.py", "tools/finalizer.py", "tools/semantic_response_guard.py",
    "tools/materialize_semantic_authorization_v3.py", "tools/validate_two_phase_handoff_package.py",
    "skill/game-translation-contributor/SKILL.md", "checksums.sha256",
}
P1_REQUIRED = {
    "PHASE1-RULES.md", "draft-evidence-schema.json", "input/full-corpus.csv",
    "schedule/phase1.json", "host/phase1-host-authorization.json",
}
P2_REQUIRED = {
    "PHASE2-RULES.md", "decision-evidence-schema.json", "input/full-corpus-with-draft.csv",
    "schedule/phase2.json", "parent/phase1-acceptance-parent.json",
    "runtime/runtime-feedback.csv", "tools/expand_explicit_decisions_v2.py",
    "tools/materialize_phase2_challenge_overlay.py", "tools/audit_guarded_phase2_provenance.py",
}


class ValidationError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValidationError(message)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def canonical_sha(value: object) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return sha256_bytes(raw)


def safe_relative(name: str) -> str:
    require(name and "\\" not in name and "\x00" not in name, f"unsafe path: {name!r}")
    path = PurePosixPath(name)
    require(not path.is_absolute() and not name.startswith("/"), f"absolute path: {name}")
    require(all(part not in {"", ".", ".."} for part in path.parts), f"unsafe relative path: {name}")
    require(Path(name).suffix.casefold() not in FORBIDDEN_SUFFIXES, f"forbidden file type: {name}")
    return path.as_posix()


def scan_private(name: str, data: bytes) -> None:
    for pattern in PRIVATE_PATTERNS:
        require(pattern.search(data) is None, f"private path bytes in {name}")


@contextmanager
def open_package(path: Path) -> Iterator[Path]:
    if path.is_dir():
        files = [p for p in path.rglob("*") if p.is_file()]
        require(len(files) <= MAX_FILES, "directory file limit exceeded")
        require(sum(p.stat().st_size for p in files) <= MAX_BYTES, "directory byte limit exceeded")
        for file in files:
            require(not file.is_symlink(), f"directory symlink rejected: {file}")
            safe_relative(file.relative_to(path).as_posix())
        yield path
        return
    require(path.is_file() and path.suffix.casefold() == ".zip", "expected package directory or ZIP")
    with zipfile.ZipFile(path) as archive:
        infos = archive.infolist()
        names = [i.filename for i in infos if not i.is_dir()]
        require(len(names) == len(set(names)), "duplicate ZIP member")
        require(len(names) <= MAX_FILES and sum(i.file_size for i in infos) <= MAX_BYTES, "ZIP limits exceeded")
        require(archive.testzip() is None, "ZIP CRC failure")
        for info in infos:
            if info.is_dir():
                continue
            safe_relative(info.filename)
            mode = (info.external_attr >> 16) & 0xFFFF
            require(not stat.S_ISLNK(mode), f"ZIP symlink rejected: {info.filename}")
        with tempfile.TemporaryDirectory(prefix="agy-v24-validate-") as temp:
            root = Path(temp)
            archive.extractall(root)
            yield root


def load_json(root: Path, rel: str) -> dict[str, Any]:
    try:
        value = json.loads((root / rel).read_text(encoding="utf-8"))
    except Exception as error:
        raise ValidationError(f"invalid JSON {rel}: {error}") from error
    require(isinstance(value, dict), f"JSON object required: {rel}")
    return value


def load_csv(root: Path, rel: str) -> tuple[list[str], list[dict[str, str]]]:
    try:
        with (root / rel).open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            fields = list(reader.fieldnames or [])
            rows = [dict(row) for row in reader]
    except Exception as error:
        raise ValidationError(f"invalid CSV {rel}: {error}") from error
    require(bool(fields), f"CSV header missing: {rel}")
    return fields, rows


def parse_checksums(root: Path, members: set[str]) -> None:
    lines = (root / "checksums.sha256").read_text(encoding="utf-8").splitlines()
    declared: dict[str, str] = {}
    for line in lines:
        match = re.fullmatch(r"([0-9a-f]{64})  ([^\r\n]+)", line)
        require(match is not None, f"malformed checksum line: {line!r}")
        digest, raw_name = match.groups()
        name = safe_relative(raw_name)
        require(name != "checksums.sha256", "checksums file cannot hash itself")
        require(name not in declared, f"duplicate checksum path: {name}")
        declared[name] = digest
    expected = members - {"checksums.sha256"}
    require(set(declared) == expected, "checksum coverage mismatch")
    for name, expected_hash in declared.items():
        require(sha256(root / name) == expected_hash, f"checksum mismatch: {name}")


def verify_descriptor(root: Path, descriptor: Any, label: str) -> str:
    require(isinstance(descriptor, dict), f"descriptor object required: {label}")
    rel = descriptor.get("path")
    expected = descriptor.get("sha256")
    require(isinstance(rel, str), f"descriptor path missing: {label}")
    rel = safe_relative(rel)
    require((root / rel).is_file(), f"descriptor file missing: {label} -> {rel}")
    require(isinstance(expected, str) and HEX64.fullmatch(expected) is not None, f"descriptor hash invalid: {label}")
    require(sha256(root / rel) == expected, f"descriptor hash mismatch: {label}")
    return rel


def declared_literal(path: Path, name: str) -> object:
    values: list[object] = []
    for node in ast.parse(path.read_text(encoding="utf-8"), filename=str(path)).body:
        if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == name for target in node.targets):
            require(isinstance(node.value, ast.Constant), f"nonliteral {name}: {path}")
            values.append(node.value.value)
    require(len(values) == 1, f"expected one {name}: {path}")
    return values[0]


def require_function(path: Path, name: str) -> None:
    functions = {
        node.name for node in ast.parse(path.read_text(encoding="utf-8"), filename=str(path)).body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    require(name in functions, f"required function missing: {name}: {path}")


def verify_semantic_control(root: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    host = manifest.get("host_control")
    require(isinstance(host, dict), "host semantic control missing")
    require(host.get("semantic_guard_required") is True, "semantic guard not required")
    require(host.get("semantic_authorization_schema") == SEMANTIC_AUTH_SCHEMA, "semantic authorization schema mismatch")
    template_rel = host.get("semantic_authorization_template_path")
    require(template_rel == "host/semantic-authoring-authorization.template.json", "semantic authorization template path mismatch")
    require(host.get("semantic_authorization_materialization") == "host-only-after-extraction-before-agent-task", "semantic authorization must be materialized before the agent task")
    require(host.get("challenge_overlay_boundary") == "host-private-outside-package-and-work-roots", "challenge overlay privacy declaration mismatch")
    require(host.get("native_direct_write_only") is True, "native direct-write requirement missing")
    require(host.get("allowed_semantic_write_tool") == "write_to_file", "semantic write tool mismatch")
    expected_private_overlay = manifest.get("phase") == PHASE2
    require(host.get("host_private_challenge_overlay_required") is expected_private_overlay, "host-private challenge overlay phase requirement mismatch")
    require(host.get("host_private_recheck_schedule_required") is expected_private_overlay, "host-private recheck schedule phase requirement mismatch")
    if expected_private_overlay:
        require(host.get("recheck_schedule_schema") == RECHECK_SCHEDULE_SCHEMA, "fresh recheck schedule schema mismatch")

    template = load_json(root, template_rel)
    require(set(template) == SEMANTIC_AUTH_FIELDS, "semantic authorization template fields mismatch")
    require(template.get("schema") == SEMANTIC_AUTH_SCHEMA, "semantic authorization template schema mismatch")
    require(template.get("contract") == BASELINE, "semantic authorization template contract mismatch")
    require(template.get("challenge_overlay") is None and template.get("challenge_ids_by_batch") == {}, "semantic authorization template leaks host-private challenge data")

    tools = manifest.get("tools")
    require(isinstance(tools, dict), "manifest tools missing")
    guard_rel = verify_descriptor(root, tools.get("semantic_guard"), "tools.semantic_guard")
    require(guard_rel == "tools/semantic_response_guard.py", "semantic guard package path mismatch")
    guard = root / guard_rel
    require(declared_literal(guard, "SCHEMA") == SEMANTIC_GUARD_SCHEMA, "semantic guard state schema mismatch")
    require(declared_literal(guard, "AUTH_SCHEMA") == SEMANTIC_AUTH_SCHEMA, "semantic guard authorization schema mismatch")
    require(declared_literal(guard, "CONTRACT") == BASELINE, "semantic guard contract mismatch")

    auth_materializer_rel = verify_descriptor(
        root, tools.get("semantic_authorization_materializer"),
        "tools.semantic_authorization_materializer",
    )
    require(auth_materializer_rel == "tools/materialize_semantic_authorization_v3.py", "semantic authorization materializer package path mismatch")
    auth_materializer = root / auth_materializer_rel
    require(declared_literal(auth_materializer, "AUTH_SCHEMA") == SEMANTIC_AUTH_SCHEMA, "semantic authorization materializer schema mismatch")
    require(declared_literal(auth_materializer, "CONTRACT") == BASELINE, "semantic authorization materializer contract mismatch")

    report = {
        "authorization_schema": SEMANTIC_AUTH_SCHEMA,
        "guard_sha256": sha256(guard),
        "authorization_materializer_sha256": sha256(auth_materializer),
    }
    if manifest.get("phase") == PHASE1:
        for function_name in ("validate_phase1_native_response", "wave_has_exact_reservation", "native_worker_conversation"):
            require_function(guard, function_name)
        report["native_worker_transcript_required"] = True
        controller_rel = verify_descriptor(root, tools.get("controller"), "tools.controller")
        require(controller_rel == "tools/controller.py", "Phase-1 controller package path mismatch")
        controller = root / controller_rel
        controller_literals = {
            "CONTRACT": BASELINE,
            "PHASE": PHASE1,
            "SCHEDULE_SCHEMA": "agy-phase1-schedule/v2",
            "RESPONSE_SCHEMA": "agy-phase1-draft/v2",
            "NORMALIZATION_SCHEMA": "agy-phase1-envelope-normalization/v1",
            "STATE_SCHEMA": "agy-guarded-phase1-controller-state/v1",
            "COMMIT_SCHEMA": "agy-phase1-controller-commit/v1",
            "SNAPSHOT_SCHEMA": "agy-phase1-draft-snapshot/v1",
            "DECISION_INDEX_SCHEMA": "agy-phase1-draft-index/v1",
            "MAX_STAGED_LEASES": MAX_PHASE1_SUBAGENTS,
        }
        for name, expected in controller_literals.items():
            require(declared_literal(controller, name) == expected, f"Phase-1 controller {name} mismatch")
        for function_name in ("normalize_phase1_response", "validate_phase1_structural_response", "verify_commits", "finalize", "run"):
            require_function(controller, function_name)
        report["normalization_schema"] = controller_literals["NORMALIZATION_SCHEMA"]
        report["controller_sha256"] = sha256(controller)
    if manifest.get("phase") == PHASE2:
        controller_rel = verify_descriptor(root, tools.get("controller"), "tools.controller")
        require(controller_rel == "tools/controller.py", "Phase-2 controller package path mismatch")
        controller = root / controller_rel
        controller_literals = {
            "CONTRACT": BASELINE,
            "PHASE": PHASE2,
            "FULL_SCHEDULE_SCHEMA": "agy-phase2-schedule/v2",
            "RECHECK_SCHEDULE_SCHEMA": RECHECK_SCHEDULE_SCHEMA,
            "STATE_SCHEMA": "agy-phase2-controller-state/v1",
            "COMMIT_SCHEMA": "agy-phase2-packet-commit/v1",
            "SNAPSHOT_SCHEMA": "agy-phase2-full-pass-snapshot/v1",
            "RECHECK_SNAPSHOT_SCHEMA": "agy-phase2-fresh-recheck-snapshot/v1",
            "DECISION_INDEX_SCHEMA": "agy-phase2-real-decision-index/v1",
        }
        for name, expected in controller_literals.items():
            require(declared_literal(controller, name) == expected, f"Phase-2 controller {name} mismatch")
        for function_name in ("validate_phase2_structural_rewrites", "verify_commits", "finalize", "run"):
            require_function(controller, function_name)
        require_function(guard, "validate_phase2_target_structure")
        report["mandatory_rewrite_enforced"] = True
        report["controller_sha256"] = sha256(controller)

        auditor_rel = verify_descriptor(root, tools.get("provenance_auditor"), "tools.provenance_auditor")
        require(auditor_rel == "tools/audit_guarded_phase2_provenance.py", "Phase-2 provenance auditor package path mismatch")
        auditor = root / auditor_rel
        auditor_literals = {
            "CONTRACT": BASELINE,
            "AUDIT_SCHEMA": "agy-phase2-provenance-audit/v1",
            "FULL_SCHEDULE_SCHEMA": "agy-phase2-schedule/v2",
            "RECHECK_SCHEDULE_SCHEMA": RECHECK_SCHEDULE_SCHEMA,
        }
        for name, expected in auditor_literals.items():
            require(declared_literal(auditor, name) == expected, f"Phase-2 provenance auditor {name} mismatch")
        for function_name in ("correlate_epoch", "audit_run"):
            require_function(auditor, function_name)
        report["provenance_auditor_sha256"] = sha256(auditor)

        challenge_materializer_rel = verify_descriptor(
            root, tools.get("challenge_materializer"), "tools.challenge_materializer",
        )
        require(challenge_materializer_rel == "tools/materialize_phase2_challenge_overlay.py", "challenge materializer package path mismatch")
        challenge_materializer = root / challenge_materializer_rel
        require(declared_literal(challenge_materializer, "SCHEMA") == "agy-phase2-challenge-overlay/v1", "challenge materializer overlay schema mismatch")
        require(declared_literal(challenge_materializer, "SCHEDULE_SCHEMA") == "agy-phase2-schedule/v2", "challenge materializer schedule schema mismatch")
        require(declared_literal(challenge_materializer, "RECHECK_SCHEDULE_SCHEMA") == RECHECK_SCHEDULE_SCHEMA, "challenge materializer recheck schema mismatch")
        require(declared_literal(challenge_materializer, "PHASE") == PHASE2, "challenge materializer phase mismatch")
        require_function(challenge_materializer, "build_recheck_schedule")
        report["challenge_materializer_sha256"] = sha256(challenge_materializer)

        recheck_materializer_rel = verify_descriptor(
            root, tools.get("recheck_materializer"), "tools.recheck_materializer",
        )
        require(recheck_materializer_rel == "tools/materialize_guarded_phase2_recheck.py", "Phase-2 recheck materializer package path mismatch")
        recheck_materializer = root / recheck_materializer_rel
        require(declared_literal(recheck_materializer, "CONTRACT") == BASELINE, "Phase-2 recheck materializer contract mismatch")
        require(declared_literal(recheck_materializer, "RECHECK_SCHEMA") == RECHECK_SCHEDULE_SCHEMA, "Phase-2 recheck materializer schema mismatch")
        require(declared_literal(recheck_materializer, "PHASE") == PHASE2, "Phase-2 recheck materializer phase mismatch")
        for function_name in ("ensure_work_root", "recheck_commands", "verify", "materialize"):
            require_function(recheck_materializer, function_name)
        report["recheck_materializer_sha256"] = sha256(recheck_materializer)
    return report


def verify_guarded_phase2_schedule(
    schedule: dict[str, Any], real_ids: list[str],
) -> dict[str, Any]:
    require(schedule.get("schema") == "agy-phase2-schedule/v2" and schedule.get("phase") == PHASE2, "Phase-2 guarded schedule schema mismatch")
    packetization = schedule.get("packetization")
    require(isinstance(packetization, dict), "Phase-2 packetization missing")
    method = packetization.get("method")
    if method == "fixed_reverse_contiguous":
        fixed_size = packetization.get("fixed_size")
        require(isinstance(fixed_size, int) and not isinstance(fixed_size, bool) and fixed_size > 0, "Phase-2 fixed packetization size invalid")
    elif method == "risk_profiled_reverse_contiguous":
        require(
            packetization.get("limits") == {"high_risk": 30, "dialogue": 60, "ui": 100, "identity_ui": 120},
            "Phase-2 risk packetization limits invalid",
        )
    else:
        raise ValidationError("Phase-2 packetization method invalid")
    challenge_policy = schedule.get("challenge_policy")
    require(isinstance(challenge_policy, dict), "Phase-2 challenge policy missing")
    require(challenge_policy.get("min_percent_per_packet") == 5, "Phase-2 challenge percent must be 5")
    require(challenge_policy.get("min_slots_per_packet") == 1, "Phase-2 challenge minimum slots must be 1")
    require(challenge_policy.get("actual_rows_host_private") is True, "Phase-2 actual challenges must remain host-private")
    packets = schedule.get("packets")
    require(isinstance(packets, list) and packets, "Phase-2 packets missing")
    packet_ids: set[str] = set()
    flat_real: list[str] = []
    challenge_slots = 0
    forbidden_challenge_fields = {"challenge_ids", "prompt_handoff_ids", "challenge_rows", "challenge_targets"}
    for packet in packets:
        require(isinstance(packet, dict), "Phase-2 packet object required")
        require(not (forbidden_challenge_fields & set(packet)), "Phase-2 schedule leaks challenge identity/data")
        packet_id = packet.get("packet_id")
        require(isinstance(packet_id, str) and SAFE_ID.fullmatch(packet_id) is not None and packet_id not in packet_ids, "Phase-2 packet ID invalid/duplicate")
        packet_ids.add(packet_id)
        packet_real = packet.get("real_handoff_ids")
        prompt_rows_hash = packet.get("real_prompt_rows_sha256")
        slots = packet.get("challenge_slots")
        require(isinstance(packet_real, list) and packet_real and len(packet_real) == len(set(packet_real)) and all(isinstance(item, str) and SAFE_ID.fullmatch(item) is not None for item in packet_real), f"Phase-2 real IDs invalid: {packet_id}")
        require(isinstance(prompt_rows_hash, str) and HEX64.fullmatch(prompt_rows_hash) is not None, f"Phase-2 real prompt rows hash invalid: {packet_id}")
        minimum_slots = max(1, (len(packet_real) * 5 + 99) // 100)
        require(isinstance(slots, int) and not isinstance(slots, bool) and slots >= minimum_slots, f"Phase-2 challenge slot coverage below 5%: {packet_id}")
        flat_real.extend(packet_real)
        challenge_slots += slots
    require(flat_real == list(reversed(real_ids)) and len(flat_real) == len(set(flat_real)), "Phase-2 exact reverse real partition mismatch")

    policy = schedule.get("recheck_policy")
    require(isinstance(policy, dict), "Phase-2 recheck policy missing")
    required_policy = {
        "all_rewritten": True,
        "all_runtime_flagged": True,
        "all_high_risk": True,
        "accepted_sample_min_percent": 10,
        "accepted_sample_method": "stratified_deterministic",
        "accepted_sample_strata_fields": ["domain", "content_class", "translation_policy"],
        "fresh_prompts_hide_prior_decision": True,
    }
    require(all(policy.get(key) == value for key, value in required_policy.items()), "Phase-2 recheck policy mismatch")
    return {"packet_count": len(packets), "challenge_slots": challenge_slots, "order": "exact_reverse"}


def verify_phase1_prompt_rows(schedule: dict[str, Any], rows: list[dict[str, str]]) -> None:
    by_id = {row.get("handoff_id"): row for row in rows}
    require(len(by_id) == len(rows) and None not in by_id, "Phase-1 prompt row identity map invalid")
    leases = schedule.get("leases")
    require(isinstance(leases, list), "Phase-1 leases missing")
    for lease in leases:
        require(isinstance(lease, dict), "Phase-1 lease object required")
        lease_id = lease.get("lease_id")
        lease_ids = lease.get("handoff_ids")
        require(isinstance(lease_ids, list) and all(item in by_id for item in lease_ids), f"Phase-1 prompt row ID missing: {lease_id}")
        expected = canonical_sha([by_id[item] for item in lease_ids])
        require(lease.get("prompt_rows_sha256") == expected, f"Phase-1 prompt rows hash mismatch: {lease_id}")


def verify_phase2_prompt_rows(schedule: dict[str, Any], rows: list[dict[str, str]]) -> None:
    by_id = {row.get("handoff_id"): row for row in rows}
    require(len(by_id) == len(rows) and None not in by_id, "Phase-2 prompt row identity map invalid")
    packets = schedule.get("packets")
    require(isinstance(packets, list), "Phase-2 packets missing")
    for packet in packets:
        require(isinstance(packet, dict), "Phase-2 packet object required")
        packet_id = packet.get("packet_id")
        real_ids = packet.get("real_handoff_ids")
        require(isinstance(real_ids, list) and all(item in by_id for item in real_ids), f"Phase-2 prompt row ID missing: {packet_id}")
        expected = canonical_sha([by_id[item] for item in real_ids])
        require(packet.get("real_prompt_rows_sha256") == expected, f"Phase-2 prompt rows hash mismatch: {packet_id}")


def verify_handoff_id_shape(ids: list[str]) -> int:
    require(bool(ids), "handoff IDs missing")
    widths = {len(item) for item in ids}
    require(len(widths) == 1, "handoff IDs must use one fixed width")
    width = next(iter(widths))
    require(1 <= width <= 64 and all(re.fullmatch(r"[0-9a-f]+", item) is not None for item in ids), "handoff IDs must be fixed-width lowercase hexadecimal")
    return width


def sequence_hash(lines: list[str]) -> str:
    return sha256_bytes("".join(line + "\n" for line in lines).encode("utf-8"))


def key_json(domain: str, key: str) -> str:
    return json.dumps([domain, key], ensure_ascii=False, separators=(",", ":"))


def source_json(domain: str, key: str, source: str) -> str:
    return json.dumps([domain, key, source], ensure_ascii=False, separators=(",", ":"))


def verify_corpus(root: Path, manifest: dict[str, Any], phase: str) -> tuple[list[str], list[dict[str, str]], str]:
    inputs = manifest.get("inputs")
    require(isinstance(inputs, dict), "manifest inputs missing")
    full = inputs.get("full_corpus")
    rel = verify_descriptor(root, full, "inputs.full_corpus")
    fields, rows = load_csv(root, rel)
    required_fields = {
        "handoff_id", "domain", "key", "source", "reference", "translation_policy",
        "identity_expected", "protected_tokens", "current_translation_vi",
    }
    require(required_fields <= set(fields), "full corpus header mismatch")
    require(len(rows) == full.get("row_count") and len(rows) > 0, "full corpus row count mismatch")
    ids = [row["handoff_id"] for row in rows]
    keys = [(row["domain"], row["key"]) for row in rows]
    require(all(SAFE_ID.fullmatch(value or "") for value in ids), "invalid handoff_id")
    require(len(ids) == len(set(ids)), "duplicate handoff_id")
    verify_handoff_id_shape(ids)
    require(len(keys) == len(set(keys)), "duplicate canonical key")
    require(sequence_hash(ids) == full.get("ordered_handoff_id_sha256"), "ordered handoff ID hash mismatch")

    canonical = manifest.get("canonical")
    require(isinstance(canonical, dict), "manifest canonical missing")
    ordered_keys = [key_json(*key) for key in keys]
    source_rows = [source_json(row["domain"], row["key"], row["source"]) for row in rows]
    require(sequence_hash(ordered_keys) == canonical.get("ordered_key_sha256"), "ordered key hash mismatch")
    require(sequence_hash(sorted(ordered_keys)) == canonical.get("exact_key_set_sha256"), "exact key-set hash mismatch")
    require(sequence_hash(source_rows) == canonical.get("source_snapshot_sha256"), "source snapshot hash mismatch")

    map_rel = verify_descriptor(root, inputs.get("handoff_map"), "inputs.handoff_map")
    map_fields, map_rows = load_csv(root, map_rel)
    require({"handoff_id", "domain", "key"} <= set(map_fields), "handoff map header mismatch")
    mapped = [(row["handoff_id"], row["domain"], row["key"]) for row in map_rows]
    expected_map = [(row["handoff_id"], row["domain"], row["key"]) for row in rows]
    require(mapped == expected_map, "handoff map mismatch")

    policy_rel = verify_descriptor(root, inputs.get("english_policy"), "inputs.english_policy")
    policy_fields, policy_rows = load_csv(root, policy_rel)
    require({"domain", "key", "translation_policy", "identity_expected", "policy_status"} <= set(policy_fields), "English policy header mismatch")
    policy_map = {(row["domain"], row["key"]): row for row in policy_rows}
    require(set(policy_map) == set(keys), "English policy key set mismatch")
    for row in rows:
        policy = policy_map[(row["domain"], row["key"])]
        require(policy["policy_status"] == "locked", f"unlocked English policy: {row['handoff_id']}")
        require(row["translation_policy"] == policy["translation_policy"], f"policy mismatch: {row['handoff_id']}")
        require(row["identity_expected"] == policy["identity_expected"], f"identity expectation mismatch: {row['handoff_id']}")
        try:
            tokens = json.loads(row["protected_tokens"] or "[]")
        except Exception as error:
            raise ValidationError(f"protected_tokens JSON invalid: {row['handoff_id']}") from error
        require(isinstance(tokens, list) and all(isinstance(token, str) and token for token in tokens), f"protected token list invalid: {row['handoff_id']}")
        source = row["source"]
        target = row["current_translation_vi"]
        require(all(source.count(token) > 0 for token in tokens), f"declared token absent from source: {row['handoff_id']}")
        if row["translation_policy"] == "keep_identity":
            require(row["identity_expected"] == source, f"keep_identity expectation/source mismatch: {row['handoff_id']}")
            require(target == source, f"keep_identity target mismatch: {row['handoff_id']}")
        elif phase == PHASE1:
            require(target == "", f"Phase-1 non-identity target must be blank: {row['handoff_id']}")
        else:
            require(bool(target.strip()) or (not source.strip() and not target), f"Phase-2 draft target blank: {row['handoff_id']}")
            token_match = all(target.count(token) == source.count(token) for token in tokens)
            try:
                mandatory_reasons = json.loads(row.get("mandatory_rewrite_reasons", "[]") or "[]")
            except json.JSONDecodeError as error:
                raise ValidationError(f"mandatory rewrite reasons invalid: {row['handoff_id']}") from error
            require(isinstance(mandatory_reasons, list) and all(isinstance(reason, str) for reason in mandatory_reasons), f"mandatory rewrite reasons invalid: {row['handoff_id']}")
            require(token_match or "protected_token_mismatch" in mandatory_reasons, f"Phase-2 token mismatch without mandatory rewrite: {row['handoff_id']}")

    verify_descriptor(root, inputs.get("glossary"), "inputs.glossary")
    verify_descriptor(root, inputs.get("token_profile"), "inputs.token_profile")
    return ids, rows, rel


def verify_phase1(
    root: Path, manifest: dict[str, Any], ids: list[str], rows: list[dict[str, str]], input_rel: str,
) -> dict[str, Any]:
    host = manifest.get("host_control")
    require(isinstance(host, dict), "Phase-1 host control missing")
    phase1_cap = host.get("required_subagent_limit")
    require(host.get("required_mode") == PHASE1, "Phase-1 host mode mismatch")
    require(isinstance(phase1_cap, int) and not isinstance(phase1_cap, bool) and 1 <= phase1_cap <= MAX_PHASE1_SUBAGENTS, "Phase-1 host cap must be an integer in 1..12")
    require(set(host.get("denied_tools") or []) == {"manage_subagents", "send_message"}, "Phase-1 denied tools mismatch")
    require(host.get("single_main_coordinator") is True and host.get("one_bound_main_conversation") is True, "Phase-1 main coordinator binding missing")
    require(host.get("child_conversations_allowed") is True and host.get("nested_delegation_allowed") is False, "Phase-1 child/nesting policy mismatch")
    require(host.get("lease_authorization_path") == "host/phase1-host-authorization.json", "Phase-1 auth path mismatch")
    workflow = manifest.get("workflow")
    require(isinstance(workflow, dict), "Phase-1 workflow missing")
    require(workflow.get("hermes_acceptance_required_before_next_route") is True, "Phase-1 acceptance gate missing")
    require(workflow.get("explicit_user_direction_required_after_phase1") is True, "Phase-1 user direction gate missing")
    require(workflow.get("post_phase1_state") == "phase1_accepted_waiting_for_user_direction", "Phase-1 post-acceptance state mismatch")
    require(workflow.get("allowed_next_routes") == POST_PHASE1_ROUTES, "Phase-1 user direction routes mismatch")
    preview = manifest.get("preview_policy")
    require(isinstance(preview, dict) and preview.get("optional_user_selected_route") is True, "Phase-1 demo route must be optional")
    require(preview.get("label") == "PREVIEW_PHASE1_DEMO_NOT_FINAL", "Phase-1 demo label mismatch")

    draft_rel = verify_descriptor(root, manifest.get("draft_evidence_schema"), "draft_evidence_schema")
    draft_schema = load_json(root, draft_rel)
    require(draft_schema.get("$id") == "agy-phase1-draft/v2", "Phase-1 draft schema mismatch")
    schedule_rel = verify_descriptor(root, manifest.get("schedule"), "schedule")
    schedule = load_json(root, schedule_rel)
    require(schedule.get("schema") == "agy-phase1-schedule/v2" and schedule.get("phase") == PHASE1, "Phase-1 schedule schema mismatch")
    require(schedule.get("package_id") == manifest["package_id"] and schedule.get("run_id") == manifest["run_id"], "Phase-1 schedule identity mismatch")
    verify_phase1_prompt_rows(schedule, rows)
    leases = schedule.get("leases")
    require(isinstance(leases, list) and leases, "Phase-1 leases missing")
    require(manifest["schedule"].get("packet_count") == len(leases), "Phase-1 packet count mismatch")
    require(manifest["schedule"].get("max_concurrent_workers") == phase1_cap, "Phase-1 schedule cap mismatch")
    flattened: list[str] = []
    lease_map: dict[str, str] = {}
    for lease in leases:
        require(isinstance(lease, dict), "Phase-1 lease object required")
        lease_id = lease.get("lease_id")
        lease_ids = lease.get("handoff_ids")
        input_hash = lease.get("input_sha256")
        prompt_rows_hash = lease.get("prompt_rows_sha256")
        require(isinstance(lease_id, str) and SAFE_ID.fullmatch(lease_id), "invalid Phase-1 lease ID")
        require(isinstance(lease_ids, list) and lease_ids and all(isinstance(x, str) for x in lease_ids), f"invalid lease IDs: {lease_id}")
        require(isinstance(input_hash, str) and HEX64.fullmatch(input_hash), f"invalid lease input hash: {lease_id}")
        require(isinstance(prompt_rows_hash, str) and HEX64.fullmatch(prompt_rows_hash), f"invalid lease prompt rows hash: {lease_id}")
        if "input_path" in lease:
            require(sha256(root / safe_relative(lease["input_path"])) == input_hash, f"lease input hash mismatch: {lease_id}")
        else:
            require(input_hash == sha256(root / input_rel), f"lease full-corpus input hash mismatch: {lease_id}")
        expected = canonical_sha({
            "package_id": manifest["package_id"], "run_id": manifest["run_id"], "phase": PHASE1,
            "lease_id": lease_id, "handoff_ids": lease_ids, "input_sha256": input_hash,
            "prompt_rows_sha256": prompt_rows_hash,
        })
        require(lease.get("lease_sha256") == expected, f"lease hash mismatch: {lease_id}")
        require(lease_id not in lease_map, f"duplicate lease ID: {lease_id}")
        lease_map[lease_id] = expected
        flattened.extend(lease_ids)
    require(set(flattened) == set(ids) and len(flattened) == len(ids) and len(flattened) == len(set(flattened)), "Phase-1 lease exact partition mismatch")

    auth = load_json(root, "host/phase1-host-authorization.json")
    require(set(auth) == {"schema", "contract", "package_id", "run_id", "manifest_sha256", "max_subagents", "leases"}, "Phase-1 auth fields mismatch active host hook")
    require(auth.get("schema") == "agy-phase1-host-authorization/v1" and auth.get("contract") == BASELINE, "Phase-1 auth schema/contract mismatch")
    require(auth.get("package_id") == manifest["package_id"] and auth.get("run_id") == manifest["run_id"], "Phase-1 auth identity mismatch")
    require(auth.get("manifest_sha256") == sha256(root / "project-manifest.json"), "Phase-1 auth manifest hash mismatch")
    require(auth.get("max_subagents") == phase1_cap, "Phase-1 auth cap mismatch")
    auth_leases = auth.get("leases")
    require(isinstance(auth_leases, list), "Phase-1 auth leases missing")
    actual_auth = {item.get("lease_id"): item.get("lease_sha256") for item in auth_leases if isinstance(item, dict)}
    require(actual_auth == lease_map and len(actual_auth) == len(auth_leases), "Phase-1 auth lease map mismatch")
    return {"lease_count": len(leases), "max_subagents": phase1_cap}


def verify_phase2(root: Path, manifest: dict[str, Any], ids: list[str], rows: list[dict[str, str]]) -> dict[str, Any]:
    host = manifest.get("host_control")
    require(isinstance(host, dict), "Phase-2 host control missing")
    require(host.get("required_mode") == PHASE2 and host.get("required_subagent_limit") == 0, "Phase-2 host mode/cap mismatch")
    require(set(host.get("denied_tools") or []) == {"invoke_subagent", "manage_subagents", "send_message"}, "Phase-2 denied tools mismatch")
    require(host.get("single_main_agent") is True and host.get("child_conversations_allowed") is False and host.get("nested_delegation_allowed") is False, "Phase-2 main-only policy mismatch")
    workflow = manifest.get("workflow")
    require(isinstance(workflow, dict), "Phase-2 workflow missing")
    require(workflow.get("selected_route") == "external_phase2_antigravity", "Phase-2 external route selection missing")
    require(workflow.get("runtime_feedback_optional") is True, "Phase-2 runtime feedback must be optional")
    verify_descriptor(root, manifest.get("parent"), "parent")
    parent = load_json(root, manifest["parent"]["path"])
    require(parent.get("schema") == "agy-phase1-acceptance-parent/v1", "Phase-2 parent schema mismatch")
    require(HEX64.fullmatch(str(parent.get("raw_phase1_return_sha256", ""))) is not None, "Phase-2 raw parent hash invalid")
    snapshot = parent.get("accepted_target_snapshot")
    require(isinstance(snapshot, dict) and snapshot.get("row_count") == len(ids) and HEX64.fullmatch(str(snapshot.get("sha256", ""))) is not None, "Phase-2 accepted snapshot parent invalid")
    mandatory_ids: list[str] = []
    for row in rows:
        try:
            reasons = json.loads(row.get("mandatory_rewrite_reasons", "[]") or "[]")
        except json.JSONDecodeError as error:
            raise ValidationError(f"mandatory rewrite reasons invalid: {row['handoff_id']}") from error
        require(isinstance(reasons, list) and all(isinstance(reason, str) for reason in reasons), f"mandatory rewrite reasons invalid: {row['handoff_id']}")
        if reasons:
            mandatory_ids.append(row["handoff_id"])
    mandatory_hash = canonical_sha(mandatory_ids)
    require(host.get("mandatory_rewrite_count") == len(mandatory_ids), "Phase-2 mandatory rewrite count mismatch")
    require(host.get("mandatory_rewrite_ids_sha256") == mandatory_hash, "Phase-2 mandatory rewrite hash mismatch")
    require(parent.get("mandatory_rewrite_count") == len(mandatory_ids), "Phase-2 parent mandatory rewrite count mismatch")
    require(parent.get("mandatory_rewrite_ids_sha256") == mandatory_hash, "Phase-2 parent mandatory rewrite hash mismatch")
    decision_rel = verify_descriptor(root, manifest.get("decision_evidence_schema"), "decision_evidence_schema")
    decision_schema = load_json(root, decision_rel)
    require(decision_schema.get("schema") == "agy-explicit-review/v2", "Phase-2 decision schema mismatch")
    expander_rel = verify_descriptor(root, manifest["tools"].get("expander"), "tools.expander")
    require(expander_rel == "tools/expand_explicit_decisions_v2.py", "Phase-2 expander path mismatch")
    runtime_rel = verify_descriptor(root, manifest["inputs"].get("runtime_feedback"), "inputs.runtime_feedback")
    _, runtime_rows = load_csv(root, runtime_rel)
    require(len(runtime_rows) == manifest["inputs"]["runtime_feedback"].get("row_count"), "runtime feedback row count mismatch")
    require(workflow.get("runtime_feedback_ingested_before_schedule") is bool(runtime_rows), "Phase-2 runtime feedback workflow flag mismatch")
    schedule_rel = verify_descriptor(root, manifest.get("schedule"), "schedule")
    schedule = load_json(root, schedule_rel)
    require(schedule.get("package_id") == manifest["package_id"] and schedule.get("run_id") == manifest["run_id"], "Phase-2 schedule identity mismatch")
    report = verify_guarded_phase2_schedule(schedule, ids)
    verify_phase2_prompt_rows(schedule, rows)
    require(manifest["schedule"].get("packet_count") == report["packet_count"], "Phase-2 packet count mismatch")
    return report


def validate_package(path: Path) -> dict[str, Any]:
    with open_package(path) as root:
        files = [p for p in root.rglob("*") if p.is_file()]
        members = {safe_relative(p.relative_to(root).as_posix()) for p in files}
        for file in files:
            scan_private(file.relative_to(root).as_posix(), file.read_bytes())
        require(COMMON_REQUIRED <= members, f"missing common files: {sorted(COMMON_REQUIRED - members)}")
        parse_checksums(root, members)
        manifest = load_json(root, "project-manifest.json")
        require(manifest.get("contract_version") == CONTRACT_VERSION and manifest.get("receiver_control_baseline") == BASELINE, "contract baseline mismatch")
        phase = manifest.get("phase")
        require(phase in {PHASE1, PHASE2}, "invalid phase")
        require(manifest.get("translation_only") is True and manifest.get("canonical_write_authority") == "Hermes", "translation-only authority mismatch")
        require(manifest.get("identity") == {"canonical_key": ["domain", "key"], "handoff_id_mapping": "handoff-id-map.csv"}, "canonical identity mismatch")
        require(SAFE_ID.fullmatch(str(manifest.get("package_id", ""))) is not None, "invalid package_id")
        require(SAFE_ID.fullmatch(str(manifest.get("run_id", ""))) is not None, "invalid run_id")
        final_name = manifest.get("expected_final_filename")
        require(isinstance(final_name, str) and final_name.endswith(".zip") and "/" not in final_name and "\\" not in final_name, "invalid expected final filename")
        required = P1_REQUIRED if phase == PHASE1 else P2_REQUIRED
        require(required <= members, f"missing phase files: {sorted(required - members)}")
        tools = manifest.get("tools")
        require(isinstance(tools, dict), "manifest tools missing")
        verify_descriptor(root, tools.get("controller"), "tools.controller")
        verify_descriptor(root, tools.get("finalizer"), "tools.finalizer")
        verify_descriptor(root, tools.get("outbound_validator"), "tools.outbound_validator")
        semantic_report = verify_semantic_control(root, manifest)
        ids, rows, input_rel = verify_corpus(root, manifest, phase)
        phase_report = verify_phase1(root, manifest, ids, rows, input_rel) if phase == PHASE1 else verify_phase2(root, manifest, ids, rows)
        return {
            "status": "two_phase_package_clean", "contract": BASELINE, "phase": phase,
            "package_id": manifest["package_id"], "run_id": manifest["run_id"],
            "row_count": len(rows), "file_count": len(members),
            "semantic_origin": semantic_report, **phase_report,
        }


def self_test() -> None:
    require(safe_relative("input/full-corpus.csv") == "input/full-corpus.csv", "safe path self-test")
    try:
        safe_relative("../escape")
    except ValidationError:
        pass
    else:
        raise AssertionError("unsafe path self-test failed")
    require(canonical_sha({"b": 2, "a": 1}) == canonical_sha({"a": 1, "b": 2}), "canonical hash self-test")
    require(BASELINE.endswith("-GUARDED"), "guarded baseline self-test")
    require(SEMANTIC_AUTH_SCHEMA.endswith("/v3"), "semantic auth schema self-test")
    print("SELF-TEST PASS: v2.5 guarded paths, hashes, semantic constants")


def main(argv: list[str]) -> int:
    if len(argv) == 2 and argv[1] == "--self-test":
        self_test()
        return 0
    if len(argv) != 2:
        print("usage: validate_two_phase_handoff_package.py <handoff-dir-or-zip>|--self-test", file=sys.stderr)
        return 2
    try:
        report = validate_package(Path(argv[1]).resolve())
    except Exception as error:
        print(f"FAIL: {type(error).__name__}: {error}", file=sys.stderr)
        return 1
    print(json.dumps(report, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
