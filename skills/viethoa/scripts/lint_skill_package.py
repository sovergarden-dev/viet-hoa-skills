from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import re
import sys
from pathlib import Path


def main(root_arg: str) -> int:
    root = Path(root_arg).resolve()
    errors: list[str] = []
    warnings: list[str] = []
    files = sorted(p for p in root.rglob("*") if p.is_file())
    rel = {p.relative_to(root).as_posix() for p in files}

    for path in files:
        if path.stat().st_size == 0:
            errors.append(f"empty file: {path.relative_to(root).as_posix()}")

    skill = root / "SKILL.md"
    core = ""
    if not skill.exists():
        errors.append("SKILL.md missing")
    else:
        core = skill.read_text(encoding="utf-8")
        if not core.startswith(("---\n", "---\r\n")):
            errors.append("SKILL.md missing YAML frontmatter")
        for field in ("name:", "description:", "version:"):
            if field not in core[:3000]:
                errors.append(f"frontmatter missing {field[:-1]}")

    binding_re = re.compile(
        r"`((?:references|templates|scripts|assets)/[A-Za-z0-9._/-]+)`"
    )
    linked: set[str] = set()
    for path in files:
        if path.suffix.lower() not in {".md", ".txt"}:
            continue
        try:
            body = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            warnings.append(f"non-UTF8 text: {path.relative_to(root).as_posix()}")
            continue
        for target in binding_re.findall(body):
            linked.add(target)
            if target not in rel:
                errors.append(
                    f"dangling package link in {path.relative_to(root).as_posix()}: {target}"
                )

    # Bare reference names in core resolve under references/.
    for name in set(re.findall(r"`([A-Za-z0-9._-]+\.md)`", core)):
        target = f"references/{name}"
        if target not in rel:
            errors.append(f"missing core reference: {target}")

    required = [
        "canonical", "stable key", "protected", "atomic", "runtime qa",
        "dlc", "needs_context", "proper nouns",
        "bounded continuous run", "deterministic batch lifecycle",
        "english-source semantic policy", "cron-tuning",
        "source-faithful", "anti-domestication",
    ]
    lower = core.lower()
    for phrase in required:
        if phrase not in lower:
            errors.append(f"required core concept missing: {phrase}")
    if "antigravity" in lower and "di sản" not in lower and "nghỉ hưu" not in lower and "retired" not in lower:
        errors.append("active Antigravity route returned to core")
    if "scripts/external_agent_handoff.py" not in core:
        errors.append("generic external agent handoff script missing from core")
    if "scripts/plan1_safety_detector.py" not in core:
        errors.append("plan1 safety detector script missing from core")
    retired = (root / "references/plan2-operating-contract.md").read_text(encoding="utf-8").lower()
    for phrase in (
        "english-policy audit", "preview_phase1_demo_not_final",
        "community-baseline route", "preview-grade draft",
        "main-only final language & semantic review",
        "2.5-two-phase-draft12-preview-final0-guarded",
        "agy-semantic-origin-authorization/v3", "retired 2.15.0",
    ):
        if phrase not in retired:
            errors.append(f"retired Plan 2 contract missing: {phrase}")

    required_paths = {
        "references/source-faithful-translation-policy.md",
        "references/plan1-safety-guardrail-detection.md",
        "references/generic-external-agent-handoff.md",
        "references/english-source-semantic-policy.md",
        "references/antigravity-two-phase-handoff.md",
        "references/antigravity-three-phase-handoff.md",
        "references/antigravity-multi-host-receiver.md",
        "references/promise-mascot-agency-two-phase-postmortem.md",
        "references/token-efficient-external-handoff.md",
        "templates/english-policy.csv",
        "templates/external-batch.csv",
        "templates/external-batch-schema.json",
        "templates/external-output-schema.json",
        "templates/external-token-profile.json",
        "templates/external-merge-ledger.jsonl",
        "templates/external-project-manifest.json",
        "templates/external-project-manifest-phase2.json",
        "templates/draft-evidence-schema.json",
        "templates/phase1-host-authorization.json",
        "templates/phase1-acceptance-parent.json",
        "templates/external-work-queue.json",
        "templates/external-packet-manifest.json",
        "templates/external-phase-receipt.json",
        "templates/handoff-id-map.csv",
        "templates/preview-phase1-manifest.json",
        "templates/community-baseline-alignment.csv",
        "templates/external-start-here.md",
        "templates/external-phase-acceptance.json",
        "templates/external-phase0-output.csv",
        "templates/external-translation-output.csv",
        "templates/decision-evidence-schema.json",
        "scripts/expand_compact_decisions.py",
        "scripts/validate_external_handoff_package.py",
        "scripts/validate_main_only_one_shot_package.py",
        "scripts/validate_two_phase_handoff_package.py",
        "scripts/guarded_phase1_controller.py",
        "scripts/expand_explicit_decisions_v2.py",
        "scripts/materialize_semantic_authorization_v3.py",
        "scripts/materialize_phase2_challenge_overlay.py",
        "scripts/materialize_guarded_phase2_recheck.py",
        "scripts/export_antigravity_receiver_kit.py",
        "scripts/install_antigravity_receiver_kit.py",
        "scripts/guarded_phase2_controller.py",
        "scripts/audit_guarded_phase2_provenance.py",
        "templates/semantic-authoring-authorization.json",
        "templates/phase2-schedule.json",
        "templates/phase2-challenge-overlay.json",
        "templates/phase2-recheck-schedule.json",
    }
    for target in sorted(required_paths - rel):
        errors.append(f"required external-handoff artifact missing: {target}")

    json_templates = [
        "templates/project-state.json",
        "templates/external-project-manifest.json",
        "templates/external-project-manifest-phase2.json",
        "templates/draft-evidence-schema.json",
        "templates/phase1-host-authorization.json",
        "templates/phase1-acceptance-parent.json",
        "templates/external-work-queue.json",
        "templates/external-packet-manifest.json",
        "templates/external-phase-receipt.json",
        "templates/external-phase-acceptance.json",
        "templates/external-batch-schema.json",
        "templates/external-output-schema.json",
        "templates/external-token-profile.json",
        "templates/preview-phase1-manifest.json",
        "templates/semantic-authoring-authorization.json",
        "templates/phase2-schedule.json",
        "templates/phase2-challenge-overlay.json",
        "templates/phase2-recheck-schedule.json",
    ]
    for target in json_templates:
        if target not in rel:
            continue
        try:
            json.loads((root / target).read_text(encoding="utf-8"))
        except Exception as exc:
            errors.append(f"invalid JSON template {target}: {exc}")

    validator = None
    validator_path = root / "scripts/validate_external_handoff_package.py"
    if validator_path.exists():
        try:
            spec = importlib.util.spec_from_file_location(
                "viethoa_external_handoff_validator", validator_path
            )
            if spec is None or spec.loader is None:
                raise RuntimeError("unable to load module spec")
            validator = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(validator)
        except Exception as exc:
            errors.append(f"cannot load external handoff validator: {exc}")

    if validator is not None:
        csv_contracts = {
            "templates/external-batch.csv": validator.BATCH_HEADER,
            "templates/external-phase0-output.csv": validator.PHASE0_OUTPUT_HEADER,
            "templates/external-translation-output.csv": validator.TRANSLATION_OUTPUT_HEADER,
        }
        for target, expected in csv_contracts.items():
            if target not in rel:
                continue
            try:
                with (root / target).open(
                    "r", encoding="utf-8-sig", newline=""
                ) as stream:
                    header = next(csv.reader(stream))
                if header != expected:
                    errors.append(f"CSV contract header mismatch: {target}")
            except Exception as exc:
                errors.append(f"invalid CSV contract {target}: {exc}")

        try:
            batch_schema = json.loads(
                (root / "templates/external-batch-schema.json").read_text(
                    encoding="utf-8"
                )
            )
            if batch_schema.get("columns") != validator.BATCH_HEADER:
                errors.append("external-batch-schema.json columns mismatch")
        except Exception as exc:
            errors.append(f"invalid external batch schema: {exc}")
        try:
            output_schema = json.loads(
                (root / "templates/external-output-schema.json").read_text(
                    encoding="utf-8"
                )
            )
            if (
                output_schema.get("phase0_columns") != validator.PHASE0_OUTPUT_HEADER
                or output_schema.get("translation_phase_columns")
                != validator.TRANSLATION_OUTPUT_HEADER
            ):
                errors.append("external-output-schema.json columns mismatch")
        except Exception as exc:
            errors.append(f"invalid external output schema: {exc}")
        try:
            token_profile = json.loads(
                (root / "templates/external-token-profile.json").read_text(
                    encoding="utf-8"
                )
            )
            validator.validate_token_profile(token_profile)
        except Exception as exc:
            errors.append(f"invalid external token profile: {exc}")

    ledger = root / "templates/external-merge-ledger.jsonl"
    if ledger.exists():
        required_ledger_fields = {
            "schema_version", "packet_id", "attempt", "phase",
            "accepted_output_sha256", "canonical_before_sha256",
            "canonical_after_sha256", "remainder_ordered_full_key_sha256",
            "acceptance_receipt_sha256", "result",
        }
        try:
            ledger_rows = [
                json.loads(line)
                for line in ledger.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            if not ledger_rows:
                errors.append("external merge ledger template has no row")
            for index, row in enumerate(ledger_rows, 1):
                if not isinstance(row, dict) or not required_ledger_fields <= set(row):
                    errors.append(f"external merge ledger row {index} schema mismatch")
        except Exception as exc:
            errors.append(f"invalid external merge ledger JSONL: {exc}")

    policy = root / "templates/english-policy.csv"
    if policy.exists():
        header = policy.read_text(encoding="utf-8").splitlines()[0].split(",")
        expected = [
            "domain", "key", "source_sha256", "content_type",
            "semantic_class", "translation_policy", "locked_english_terms",
            "identity_expected", "reason", "evidence", "policy_status",
        ]
        if header != expected:
            errors.append("english-policy.csv header mismatch")

    community_template = root / "templates/community-baseline-alignment.csv"
    if community_template.exists():
        header = community_template.read_text(encoding="utf-8").splitlines()[0].split(",")
        expected = [
            "domain", "key", "current_source_sha256", "community_artifact_sha256",
            "community_build_id", "community_vi_reference", "alignment_method",
            "alignment_confidence", "work_route", "reasons",
        ]
        if header != expected:
            errors.append("community-baseline-alignment.csv header mismatch")

    preview_template = root / "templates/preview-phase1-manifest.json"
    if preview_template.exists():
        preview = json.loads(preview_template.read_text(encoding="utf-8"))
        labels = preview.get("artifact_labels", [])
        if "PREVIEW_PHASE1_DEMO_NOT_FINAL" not in labels:
            errors.append("preview manifest label must include PREVIEW_PHASE1_DEMO_NOT_FINAL")
        if preview.get("selected_route") != "build_demo_patch":
            errors.append("preview manifest must identify optional build_demo_patch route")
        if preview.get("phase_gate_state") != "phase1_demo_ready_waiting_for_user_direction":
            errors.append("preview manifest must return to the user-direction checkpoint")
        if preview.get("canonical_merge_allowed") is not False:
            errors.append("preview manifest must forbid canonical merge")
        if preview.get("public_release_allowed") is not False:
            errors.append("preview manifest must forbid public release")
        if preview.get("buildpatch_promotion_allowed") is not False:
            errors.append("preview manifest must forbid buildpatch promotion")

    policy_ref = root / "references/english-source-semantic-policy.md"
    if policy_ref.exists():
        policy_text = policy_ref.read_text(encoding="utf-8")
        for enum in (
            "keep_identity", "translate_with_locked_terms", "translate_full",
            "exclude_or_keep_technical", "needs_policy_context",
        ):
            if enum not in policy_text:
                errors.append(f"English policy enum missing: {enum}")

    antigravity_ref = root / "references/antigravity-two-phase-handoff.md"
    if antigravity_ref.exists():
        contract = antigravity_ref.read_text(encoding="utf-8").lower()
        for phrase in (
            "agy-viethoa-handoff/2.5-two-phase-draft12-preview-final0-guarded",
            "phase 1", "phase 2", "phase1_parallel_draft", "phase2_main_only_final",
            "preview_phase1_demo_not_final", "phase1_accepted_waiting_for_user_direction",
            "phase1_demo_ready_waiting_for_user_direction", "build_demo_patch",
            "external_phase2_antigravity", "hermes_cron_phase2",
            "parent_phase_sha256", "parent_full_pass", "handoff_id",
            "12/13", "reserved=0", "agy-semantic-origin-authorization/v3",
            "materialize_guarded_phase2_recheck.py", "audit_guarded_phase2_provenance.py", "buildpatch",
        ):
            if phrase not in contract:
                errors.append(f"Antigravity v2.5 contract missing: {phrase}")

    handoff_ref = root / "references/external-translation-handoff.md"
    if handoff_ref.exists():
        handoff = handoff_ref.read_text(encoding="utf-8")
        for phrase in (
            "AGY-VIETHOA-HANDOFF/2.5-TWO-PHASE-DRAFT12-PREVIEW-FINAL0-GUARDED",
            "input/full-corpus.csv",
            "schedule/phase1.json",
            "host/phase1-host-authorization.json",
            "input/full-corpus-with-draft.csv",
            "schedule/phase2.json",
            "parent/phase1-acceptance-parent.json",
            "tools/controller.py",
            "tools/finalizer.py",
            "tools/audit_guarded_phase2_provenance.py",
            "parent_full_pass",
            "một return ZIP",
            "một final ZIP",
        ):
            if phrase not in handoff:
                errors.append(f"external handoff contract missing: {phrase}")
        for legacy in (
            "├── manifest.json",
            "example-output.<json|csv>",
            "Prefer `keyed_json`",
        ):
            if legacy in handoff:
                errors.append(f"legacy/ambiguous external handoff contract: {legacy}")

    report = {
        "root": str(root),
        "files": len(files),
        "errors": errors,
        "warnings": warnings,
        "skill_bytes": skill.stat().st_size if skill.exists() else 0,
        "skill_sha256": hashlib.sha256(skill.read_bytes()).hexdigest()
        if skill.exists() else None,
        "linked_package_paths": len(linked),
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: python scripts/lint_skill_package.py <skill_root>")
    raise SystemExit(main(sys.argv[1]))
