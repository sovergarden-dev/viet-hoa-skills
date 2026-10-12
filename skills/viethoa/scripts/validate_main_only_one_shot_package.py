from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import shutil
import stat
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath

BASELINE = "AGY-VIETHOA-HANDOFF/2.2-MAIN-ONLY-ONE-SHOT"
BATCH_HEADER = [
    "handoff_id", "domain", "key", "content_type", "speaker", "addressee",
    "source", "reference", "previous_context", "following_context",
    "protected_tokens", "character_limit", "semantic_class",
    "translation_policy", "locked_english_terms", "identity_expected",
    "community_vi_reference", "work_route", "current_translation_vi",
]
MAP_HEADER = ["handoff_id", "domain", "key", "source_sha256"]
POLICY_HEADER = [
    "domain", "key", "source_sha256", "content_type", "semantic_class",
    "translation_policy", "locked_english_terms", "identity_expected",
    "reason", "evidence", "policy_status",
]
POLICIES = {"keep_identity", "translate_with_locked_terms", "translate_full"}
DENIED_TOOLS = ["invoke_subagent", "manage_subagents", "send_message"]
REQUIRED = {
    "project-manifest.json", "START-HERE.md", "handoff-id-map.csv",
    "glossary.csv", "token-profile.json", "decision-evidence-schema.json",
    "TRANSLATION-PROMPT.txt", "input/full-corpus.csv",
    "schedule/phase2.json", "schedule/phase3.json", "tools/controller.py",
    "tools/finalizer.py", "tools/expand_compact_decisions.py",
    "tools/validate_main_only_one_shot_package.py",
    "skill/game-translation-contributor/SKILL.md", "checksums.sha256",
}
FORBIDDEN_SUFFIXES = {
    ".exe", ".dll", ".pak", ".ucas", ".utoc", ".sig", ".bin",
    ".asset", ".bundle",
}
PRIVATE_PATHS = (
    re.compile(rb"[A-Za-z]:[\\/](?:Users|Documents and Settings)[\\/][^\\/\r\n]+", re.I),
    re.compile(rb"/(?:home|Users)/[^/\r\n]+"),
)
HEX64 = re.compile(r"[0-9a-f]{64}")


class InvalidPackage(ValueError):
    pass


def fail(message: str) -> None:
    raise InvalidPackage(message)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def safe_name(name: str) -> str:
    if "\\" in name:
        fail(f"ZIP/path uses backslash: {name}")
    path = PurePosixPath(name)
    if path.is_absolute() or not path.parts or any(part in {"", ".", ".."} for part in path.parts):
        fail(f"unsafe relative path: {name}")
    return path.as_posix()


def load_files(source: Path, max_files: int = 20_000, max_bytes: int = 512 * 1024 * 1024) -> dict[str, bytes]:
    files: dict[str, bytes] = {}
    if source.is_dir():
        paths = sorted(path for path in source.rglob("*") if path.is_file())
        if len(paths) > max_files or sum(path.stat().st_size for path in paths) > max_bytes:
            fail("directory limits exceeded")
        for path in paths:
            files[safe_name(path.relative_to(source).as_posix())] = path.read_bytes()
    elif source.is_file() and source.suffix.lower() == ".zip":
        with zipfile.ZipFile(source) as archive:
            bad = archive.testzip()
            if bad:
                fail(f"ZIP CRC failure: {bad}")
            members = [info for info in archive.infolist() if not info.is_dir()]
            if len(members) > max_files or sum(info.file_size for info in members) > max_bytes:
                fail("ZIP limits exceeded")
            for info in members:
                name = safe_name(info.filename.rstrip("/"))
                mode = (info.external_attr >> 16) & 0xFFFF
                if info.create_system == 3 and stat.S_ISLNK(mode):
                    fail(f"ZIP symlink rejected: {name}")
                if name in files:
                    fail(f"duplicate ZIP member: {name}")
                files[name] = archive.read(info)
    else:
        fail("input must be a directory or ZIP")
    if not files:
        fail("package is empty")
    return files


def read_json(files: dict[str, bytes], name: str) -> dict:
    if name not in files:
        fail(f"missing JSON: {name}")
    try:
        value = json.loads(files[name].decode("utf-8-sig"))
    except Exception as exc:
        fail(f"invalid JSON {name}: {exc}")
    if not isinstance(value, dict):
        fail(f"JSON root must be object: {name}")
    return value


def read_csv(files: dict[str, bytes], name: str) -> tuple[list[str], list[dict[str, str]]]:
    if name not in files:
        fail(f"missing CSV: {name}")
    try:
        reader = csv.DictReader(io.StringIO(files[name].decode("utf-8-sig"), newline=""))
        header = reader.fieldnames or []
        rows = list(reader)
    except Exception as exc:
        fail(f"invalid CSV {name}: {exc}")
    if not header or len(header) != len(set(header)):
        fail(f"invalid CSV header: {name}")
    return header, rows


def full_key_hash(pairs: list[tuple[str, str]]) -> str:
    return digest(b"".join(
        json.dumps([domain, key], ensure_ascii=False, separators=(",", ":")).encode("utf-8") + b"\n"
        for domain, key in pairs
    ))


def source_snapshot_hash(rows: list[dict[str, str]]) -> str:
    return digest(b"".join(
        json.dumps(
            [row["domain"], row["key"], digest(row["source"].encode("utf-8"))],
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8") + b"\n"
        for row in rows
    ))


def parse_checksums(files: dict[str, bytes]) -> None:
    declared: dict[str, str] = {}
    try:
        lines = files["checksums.sha256"].decode("utf-8").splitlines()
    except Exception as exc:
        fail(f"invalid checksums.sha256: {exc}")
    for line in lines:
        if not line.strip():
            continue
        match = re.fullmatch(r"([0-9a-f]{64})\s+\*?(.+)", line)
        if not match:
            fail(f"malformed checksum line: {line!r}")
        name = safe_name(match.group(2))
        if name == "checksums.sha256" or name in declared:
            fail(f"invalid checksum entry: {name}")
        declared[name] = match.group(1)
    expected = set(files) - {"checksums.sha256"}
    if set(declared) != expected:
        fail(f"checksum coverage mismatch: missing={sorted(expected-set(declared))} extra={sorted(set(declared)-expected)}")
    for name, expected_hash in declared.items():
        if digest(files[name]) != expected_hash:
            fail(f"checksum mismatch: {name}")


def pinned_file(files: dict[str, bytes], meta: object, expected_path: str) -> None:
    if not isinstance(meta, dict) or meta.get("path") != expected_path:
        fail(f"manifest path mismatch: {expected_path}")
    if expected_path not in files or meta.get("sha256") != digest(files[expected_path]):
        fail(f"manifest hash mismatch: {expected_path}")


def flatten_schedule(value: dict, phase: str, order: str) -> tuple[list[str], int]:
    if value.get("schema") != "agy-main-only-schedule/v1" or value.get("phase") != phase or value.get("order") != order:
        fail(f"schedule identity mismatch: {phase}")
    packets = value.get("packets")
    if not isinstance(packets, list) or not packets:
        fail(f"schedule packets missing: {phase}")
    flat: list[str] = []
    packet_ids: set[str] = set()
    for packet in packets:
        if not isinstance(packet, dict) or set(packet) != {"batch_id", "handoff_ids"}:
            fail(f"schedule packet schema mismatch: {phase}")
        batch_id = packet["batch_id"]
        ids = packet["handoff_ids"]
        if not isinstance(batch_id, str) or not batch_id or batch_id in packet_ids:
            fail(f"schedule batch ID invalid: {phase}")
        if not isinstance(ids, list) or not ids or not all(isinstance(item, str) and item for item in ids):
            fail(f"schedule handoff IDs invalid: {batch_id}")
        packet_ids.add(batch_id)
        flat.extend(ids)
    if len(flat) != len(set(flat)):
        fail(f"schedule has duplicate IDs: {phase}")
    if value.get("packet_count") != len(packets) or value.get("row_count") != len(flat):
        fail(f"schedule counters mismatch: {phase}")
    return flat, len(packets)


def find_legacy_fields(value: object, path: str = "manifest") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if key in {"lease_id", "lease_expires_at", "max_active_reserved_subagents", "default_active_workers"}:
                fail(f"legacy receiver field in 2.2 package: {path}.{key}")
            find_legacy_fields(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            find_legacy_fields(child, f"{path}[{index}]")


def validate_package(source: Path) -> dict:
    files = load_files(source)
    missing = sorted(REQUIRED - set(files))
    if missing:
        fail(f"required files missing: {missing}")
    for name, data in files.items():
        if Path(name).suffix.lower() in FORBIDDEN_SUFFIXES:
            fail(f"technical binary/asset forbidden: {name}")
        if any(pattern.search(data) for pattern in PRIVATE_PATHS):
            fail(f"private path leaked: {name}")
    parse_checksums(files)

    manifest = read_json(files, "project-manifest.json")
    find_legacy_fields(manifest)
    if manifest.get("contract_version") != "2.2.0" or manifest.get("receiver_control_baseline") != BASELINE:
        fail("main-only 2.2 contract mismatch")
    if not all(isinstance(manifest.get(name), str) and manifest[name] for name in ("package_id", "run_id", "project", "batch_id", "build_id")):
        fail("package/run/project/build identity missing")
    if manifest.get("translation_only") is not True or manifest.get("canonical_write_authority") != "Hermes":
        fail("role boundary mismatch")
    if manifest.get("identity") != {"canonical_key": ["domain", "key"], "handoff_id_mapping": "handoff-id-map.csv"}:
        fail("canonical identity mismatch")
    if manifest.get("host_control") != {
        "required_subagent_limit": 0,
        "denied_tools": DENIED_TOOLS,
        "single_main_agent": True,
        "child_conversations_allowed": False,
        "nested_delegation_allowed": False,
    }:
        fail("host main-only cap-0 contract mismatch")
    if manifest.get("decision_evidence_encoding") != "compact-explicit-v1":
        fail("decision evidence encoding mismatch")

    pinned_file(files, manifest.get("decision_evidence_schema"), "decision-evidence-schema.json")
    tools = manifest.get("tools")
    if not isinstance(tools, dict) or set(tools) != {"controller", "finalizer", "expander", "outbound_validator"}:
        fail("tool manifest mismatch")
    for key, path in {
        "controller": "tools/controller.py",
        "finalizer": "tools/finalizer.py",
        "expander": "tools/expand_compact_decisions.py",
        "outbound_validator": "tools/validate_main_only_one_shot_package.py",
    }.items():
        pinned_file(files, tools[key], path)

    schema = read_json(files, "decision-evidence-schema.json")
    if schema.get("schema") != "agy-explicit-review/v1":
        fail("decision evidence schema mismatch")

    inputs = manifest.get("inputs")
    if not isinstance(inputs, dict) or set(inputs) != {"full_corpus", "handoff_map", "english_policy", "glossary", "token_profile"}:
        fail("input manifest mismatch")
    for key, path in {
        "full_corpus": "input/full-corpus.csv",
        "handoff_map": "handoff-id-map.csv",
        "glossary": "glossary.csv",
        "token_profile": "token-profile.json",
    }.items():
        pinned_file(files, inputs[key], path)
    source_language = str(manifest.get("source_language", "")).casefold()
    if source_language == "english":
        if "english-policy.csv" not in files:
            fail("English source requires english-policy.csv")
        pinned_file(files, inputs["english_policy"], "english-policy.csv")
    elif inputs["english_policy"] is not None and inputs["english_policy"] != {"path": "", "sha256": ""}:
        fail("non-English package has unexpected English policy")

    header, rows = read_csv(files, "input/full-corpus.csv")
    if header != BATCH_HEADER or not rows:
        fail("full corpus schema/rows invalid")
    ids = [row["handoff_id"] for row in rows]
    pairs = [(row["domain"], row["key"]) for row in rows]
    if any(not item for item in ids) or len(ids) != len(set(ids)) or len(pairs) != len(set(pairs)) or any(not all(pair) for pair in pairs):
        fail("full corpus identity invalid")
    full_meta = inputs["full_corpus"]
    if full_meta.get("row_count") != len(rows) or full_meta.get("ordered_full_key_sha256") != full_key_hash(pairs):
        fail("full corpus count/key hash mismatch")
    if manifest.get("source_snapshot_sha256") != source_snapshot_hash(rows):
        fail("source snapshot hash mismatch")

    map_header, map_rows = read_csv(files, "handoff-id-map.csv")
    if map_header != MAP_HEADER or len(map_rows) != len(rows):
        fail("handoff map schema/count mismatch")
    for row, mapped in zip(rows, map_rows):
        if (mapped["handoff_id"], mapped["domain"], mapped["key"]) != (row["handoff_id"], row["domain"], row["key"]):
            fail("handoff map order/identity mismatch")
        if mapped["source_sha256"] != digest(row["source"].encode("utf-8")):
            fail("handoff map source hash mismatch")
        if not row["current_translation_vi"]:
            fail(f"Phase-2 current target blank: {row['handoff_id']}")
        if row["translation_policy"] not in POLICIES:
            fail(f"unresolved/excluded policy in release scope: {row['handoff_id']}")
        try:
            protected = json.loads(row["protected_tokens"] or "[]")
        except Exception as exc:
            fail(f"protected_tokens invalid {row['handoff_id']}: {exc}")
        if not isinstance(protected, list) or not all(isinstance(token, str) and token for token in protected):
            fail(f"protected_tokens invalid: {row['handoff_id']}")
        for token in protected:
            if row["source"].count(token) == 0 or row["current_translation_vi"].count(token) != row["source"].count(token):
                fail(f"declared token mismatch: {row['handoff_id']} {token!r}")
        if row["translation_policy"] == "keep_identity" and not row["identity_expected"]:
            fail(f"keep_identity identity_expected blank: {row['handoff_id']}")

    if source_language == "english":
        policy_header, policy_rows = read_csv(files, "english-policy.csv")
        if policy_header != POLICY_HEADER or len(policy_rows) != len(rows):
            fail("English policy schema/count mismatch")
        for row, policy in zip(rows, policy_rows):
            if (policy["domain"], policy["key"]) != (row["domain"], row["key"]):
                fail("English policy order/identity mismatch")
            if policy["source_sha256"] != digest(row["source"].encode("utf-8")) or policy["policy_status"] != "locked":
                fail("English policy source/status mismatch")
            if policy["translation_policy"] != row["translation_policy"] or policy["identity_expected"] != row["identity_expected"]:
                fail("English policy row mismatch")

    schedules = manifest.get("schedules")
    if not isinstance(schedules, dict) or set(schedules) != {"phase2", "phase3"}:
        fail("schedule manifest mismatch")
    phase2_meta = schedules["phase2"]
    phase3_meta = schedules["phase3"]
    pinned_file(files, phase2_meta, "schedule/phase2.json")
    pinned_file(files, phase3_meta, "schedule/phase3.json")
    phase2_flat, phase2_packets = flatten_schedule(read_json(files, "schedule/phase2.json"), "phase2_language_qa", "forward")
    phase3_flat, phase3_packets = flatten_schedule(read_json(files, "schedule/phase3.json"), "phase3_semantic_audit", "reverse_full_identity_order")
    if phase2_flat != ids or phase3_flat != list(reversed(ids)):
        fail("Phase-2/full or Phase-3/reverse coverage mismatch")
    for meta, phase, order, packets in (
        (phase2_meta, "phase2_language_qa", "forward", phase2_packets),
        (phase3_meta, "phase3_semantic_audit", "reverse_full_identity_order", phase3_packets),
    ):
        if meta.get("phase") != phase or meta.get("order") != order or meta.get("coverage") != "full_corpus" or meta.get("packet_count") != packets:
            fail(f"schedule manifest fields mismatch: {phase}")

    if manifest.get("workflow") != {
        "phase3_gate": "phase2_complete_transition_receipt",
        "resume": "same_package_run_append_only_ledger",
        "one_outbound_master_zip": True,
        "one_final_master_zip": True,
        "phase3_prompt_excludes_phase2_actions_reasons_notes": True,
    }:
        fail("workflow contract mismatch")
    final_name = manifest.get("expected_final_filename")
    if not isinstance(final_name, str) or not final_name.endswith(".zip") or Path(final_name).name != final_name:
        fail("expected final filename invalid")

    return {
        "status": "main_only_one_shot_package_clean",
        "source": str(source),
        "contract": BASELINE,
        "package_id": manifest["package_id"],
        "run_id": manifest["run_id"],
        "rows": len(rows),
        "phase2_packets": phase2_packets,
        "phase3_packets": phase3_packets,
        "ordered_full_key_sha256": full_key_hash(pairs),
        "expected_final_filename": final_name,
    }


def csv_bytes(header: list[str], rows: list[dict[str, str]]) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=header, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode("utf-8-sig")


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def rewrite_checksums(root: Path) -> None:
    files = {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(item for item in root.rglob("*") if item.is_file())
        if path.name != "checksums.sha256"
    }
    (root / "checksums.sha256").write_text(
        "".join(f"{digest(data)}  {name}\n" for name, data in files.items()),
        encoding="utf-8",
    )


def build_fixture(root: Path) -> None:
    source = "Open the gate"
    target = "Mở cổng"
    source_hash = digest(source.encode("utf-8"))
    row = {
        "handoff_id": "h1", "domain": "Game", "key": "UI.OpenGate",
        "content_type": "ui", "speaker": "", "addressee": "",
        "source": source, "reference": "", "previous_context": "",
        "following_context": "", "protected_tokens": "[]",
        "character_limit": "", "semantic_class": "generic_ui",
        "translation_policy": "translate_full", "locked_english_terms": "[]",
        "identity_expected": "", "community_vi_reference": "",
        "work_route": "review_existing", "current_translation_vi": target,
    }
    corpus = csv_bytes(BATCH_HEADER, [row])
    mapping = csv_bytes(MAP_HEADER, [{
        "handoff_id": "h1", "domain": "Game", "key": "UI.OpenGate",
        "source_sha256": source_hash,
    }])
    policy = csv_bytes(POLICY_HEADER, [{
        "domain": "Game", "key": "UI.OpenGate", "source_sha256": source_hash,
        "content_type": "ui", "semantic_class": "generic_ui",
        "translation_policy": "translate_full", "locked_english_terms": "[]",
        "identity_expected": "", "reason": "generic UI", "evidence": "fixture",
        "policy_status": "locked",
    }])
    static = {
        "START-HERE.md": b"fixture\n",
        "TRANSLATION-PROMPT.txt": b"fixture\n",
        "glossary.csv": b"term,translation_vi\n",
        "token-profile.json": b"{}\n",
        "decision-evidence-schema.json": json.dumps({"schema": "agy-explicit-review/v1"}).encode() + b"\n",
        "input/full-corpus.csv": corpus,
        "handoff-id-map.csv": mapping,
        "english-policy.csv": policy,
        "skill/game-translation-contributor/SKILL.md": b"---\nname: fixture\ndescription: fixture\n---\n",
        "tools/controller.py": b"# fixture controller\n",
        "tools/finalizer.py": b"# fixture finalizer\n",
        "tools/expand_compact_decisions.py": b"# fixture expander\n",
        "tools/validate_main_only_one_shot_package.py": Path(__file__).read_bytes(),
    }
    schedules = {
        "phase2": {"schema": "agy-main-only-schedule/v1", "phase": "phase2_language_qa", "order": "forward", "packet_count": 1, "row_count": 1, "packets": [{"batch_id": "p2-001", "handoff_ids": ["h1"]}]},
        "phase3": {"schema": "agy-main-only-schedule/v1", "phase": "phase3_semantic_audit", "order": "reverse_full_identity_order", "packet_count": 1, "row_count": 1, "packets": [{"batch_id": "p3-001", "handoff_ids": ["h1"]}]},
    }
    for phase, value in schedules.items():
        path = f"schedule/{phase}.json"
        static[path] = (json.dumps(value, indent=2) + "\n").encode()
    for name, data in static.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    manifest = {
        "contract_version": "2.2.0", "receiver_control_baseline": BASELINE,
        "package_id": "fixture-package", "run_id": "fixture-run",
        "project": "Fixture", "batch_id": "fixture-batch", "build_id": "1",
        "source_language": "English", "target_language": "Vietnamese",
        "translation_only": True, "canonical_write_authority": "Hermes",
        "identity": {"canonical_key": ["domain", "key"], "handoff_id_mapping": "handoff-id-map.csv"},
        "host_control": {"required_subagent_limit": 0, "denied_tools": DENIED_TOOLS, "single_main_agent": True, "child_conversations_allowed": False, "nested_delegation_allowed": False},
        "decision_evidence_encoding": "compact-explicit-v1",
        "decision_evidence_schema": {"path": "decision-evidence-schema.json", "sha256": digest(static["decision-evidence-schema.json"])},
        "tools": {
            "controller": {"path": "tools/controller.py", "sha256": digest(static["tools/controller.py"])},
            "finalizer": {"path": "tools/finalizer.py", "sha256": digest(static["tools/finalizer.py"])},
            "expander": {"path": "tools/expand_compact_decisions.py", "sha256": digest(static["tools/expand_compact_decisions.py"])},
            "outbound_validator": {"path": "tools/validate_main_only_one_shot_package.py", "sha256": digest(static["tools/validate_main_only_one_shot_package.py"])},
        },
        "source_snapshot_sha256": source_snapshot_hash([row]),
        "inputs": {
            "full_corpus": {"path": "input/full-corpus.csv", "sha256": digest(corpus), "row_count": 1, "ordered_full_key_sha256": full_key_hash([("Game", "UI.OpenGate")])},
            "handoff_map": {"path": "handoff-id-map.csv", "sha256": digest(mapping)},
            "english_policy": {"path": "english-policy.csv", "sha256": digest(policy)},
            "glossary": {"path": "glossary.csv", "sha256": digest(static["glossary.csv"])},
            "token_profile": {"path": "token-profile.json", "sha256": digest(static["token-profile.json"])},
        },
        "schedules": {
            "phase2": {"path": "schedule/phase2.json", "sha256": digest(static["schedule/phase2.json"]), "phase": "phase2_language_qa", "order": "forward", "packet_count": 1, "coverage": "full_corpus"},
            "phase3": {"path": "schedule/phase3.json", "sha256": digest(static["schedule/phase3.json"]), "phase": "phase3_semantic_audit", "order": "reverse_full_identity_order", "packet_count": 1, "coverage": "full_corpus"},
        },
        "workflow": {"phase3_gate": "phase2_complete_transition_receipt", "resume": "same_package_run_append_only_ledger", "one_outbound_master_zip": True, "one_final_master_zip": True, "phase3_prompt_excludes_phase2_actions_reasons_notes": True},
        "expected_final_filename": "Fixture-fixture-package-FINAL-Antigravity.zip",
    }
    write_json(root / "project-manifest.json", manifest)
    rewrite_checksums(root)


def self_test() -> None:
    with tempfile.TemporaryDirectory(prefix="main-only-handoff-") as directory:
        root = Path(directory) / "valid"
        build_fixture(root)
        report = validate_package(root)
        assert report["rows"] == 1 and report["contract"] == BASELINE
        bad = Path(directory) / "bad"
        shutil.copytree(root, bad)
        phase3 = json.loads((bad / "schedule/phase3.json").read_text(encoding="utf-8"))
        phase3["packets"][0]["handoff_ids"] = ["missing"]
        write_json(bad / "schedule/phase3.json", phase3)
        manifest = json.loads((bad / "project-manifest.json").read_text(encoding="utf-8"))
        manifest["schedules"]["phase3"]["sha256"] = digest((bad / "schedule/phase3.json").read_bytes())
        write_json(bad / "project-manifest.json", manifest)
        rewrite_checksums(bad)
        try:
            validate_package(bad)
        except InvalidPackage:
            pass
        else:
            raise AssertionError("bad reverse schedule unexpectedly passed")
    print("PASS main_only_one_shot_package_self_test")


def main(argv: list[str]) -> int:
    if argv == ["--self-test"]:
        self_test()
        return 0
    if len(argv) != 1:
        print("usage: python validate_main_only_one_shot_package.py <handoff-dir-or-zip>|--self-test", file=sys.stderr)
        return 2
    try:
        report = validate_package(Path(argv[0]).resolve())
    except (InvalidPackage, OSError, zipfile.BadZipFile) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
