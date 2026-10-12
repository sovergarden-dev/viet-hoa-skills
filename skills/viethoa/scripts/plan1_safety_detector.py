"""Safety Guardrail & Refusal Detector for Plan 1 Localization Workflow.

Scans canonical localization tables post-translation to detect:
1. Hard Refusals & AI Meta-Leaks (deterministic, high-confidence).
2. Blank / Empty targets on non-blank sources for attempted/completed states (deterministic).
3. Raw English Passthrough on non-proper-noun / non-identity rows (deterministic with allowlist).
4. Suspected Covert Softening on sensitive / 18+ / violent lines (advisory heuristic).
5. Explicit unhandled review/exception states (rejected, needs_context).

Emits:
- Sidecar ledger: safety-exception-ledger.jsonl (host-private audit ledger)
- Structured report: with actionable recommendation (clean, manual_fix, vs plan2_handoff)
- Bridge to Plan 2: exports ready-to-run exception plan for external agent dispatch.

Strictly offline and read-only with respect to canonical CSV files.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
from pathlib import Path
from typing import Any

SCHEMA = "viethoa/safety-guardrail-detector/v1"

# Exact canonical state vocabulary per project standards (matches external_agent_handoff.py)
CANONICAL_STATES = {"pending", "translated", "reviewed", "needs_context", "rejected"}
COMPLETED_OR_ATTEMPTED_STATES = {"translated", "reviewed", "rejected", "needs_context"}
PENDING_STATES = {"pending"}

# Deterministic patterns for AI Meta-Leaks & Explicit Safety Refusals (English & Vietnamese)
REFUSAL_META_PATTERNS = [
    re.compile(r"\b(as an ai language model|as an ai assistant|as a large language model)\b", re.IGNORECASE),
    re.compile(r"\b(i cannot|i can't|i am unable to|i'm unable to)\s+(fulfill|assist with|comply with|generate|translate|process this request)\b", re.IGNORECASE),
    re.compile(r"\b(violates? (our|the|my) (safety|content) policy)\b", re.IGNORECASE),
    re.compile(r"\b(i apologize, but i cannot (fulfill|generate|translate|assist))\b", re.IGNORECASE),
    re.compile(r"\b(với tư cách là|là một)\s+(mô hình ngôn ngữ lớn|mô hình ngôn ngữ|trợ lý ảo ai)\b", re.IGNORECASE),
    re.compile(r"\b(tôi không thể (thực hiện yêu cầu|dịch nội dung này|cung cấp nội dung này|hỗ trợ yêu cầu này))\b", re.IGNORECASE),
    re.compile(r"\b(vi phạm chính sách an toàn của chúng tôi)\b", re.IGNORECASE),
    re.compile(r"\b(tôi xin lỗi, nhưng tôi không thể (thực hiện|dịch))\b", re.IGNORECASE),
]

# Regex stems for sensitive terms with explicit word boundaries to prevent false positives
# Note: '18+' uses negative lookahead/lookbehind instead of \b because '+' is a non-word character
STRONG_SENSITIVE_PATTERNS = [
    re.compile(r"(?<!\w)18\+(?!\w)", re.IGNORECASE),
    re.compile(r"\bnsfw\b", re.IGNORECASE),
    re.compile(r"\bblood(y|shed)?\b", re.IGNORECASE),
    re.compile(r"\bgore\b", re.IGNORECASE),
    re.compile(r"\bgory\b", re.IGNORECASE),
    re.compile(r"\bcarnage\b", re.IGNORECASE),
    re.compile(r"\bmutilat\w*\b", re.IGNORECASE),
    re.compile(r"\bdecapitat\w*\b", re.IGNORECASE),
    re.compile(r"\bdisembowel\w*\b", re.IGNORECASE),
    re.compile(r"\btorture\w*\b", re.IGNORECASE),
    re.compile(r"\bmurder\w*\b", re.IGNORECASE),
    re.compile(r"\bslaughter\w*\b", re.IGNORECASE),
    re.compile(r"\bkill\w*\b", re.IGNORECASE),
    re.compile(r"\bsevered\b", re.IGNORECASE),
    re.compile(r"\bcorpse\w*\b", re.IGNORECASE),
    re.compile(r"\bmassacre\w*\b", re.IGNORECASE),
    re.compile(r"\bsexual\w*\b", re.IGNORECASE),
    re.compile(r"\bnude\b", re.IGNORECASE),
    re.compile(r"\bnudity\b", re.IGNORECASE),
    re.compile(r"\brape(d|s)?\b", re.IGNORECASE),
    re.compile(r"\bbạo lực\b", re.IGNORECASE),
    re.compile(r"\bmáu me\b", re.IGNORECASE),
    re.compile(r"\bchém giết\b", re.IGNORECASE),
    re.compile(r"\bmổ bụng\b", re.IGNORECASE),
    re.compile(r"\bchặt đầu\b", re.IGNORECASE),
    re.compile(r"\btra tấn\b", re.IGNORECASE),
    re.compile(r"\btàn sát\b", re.IGNORECASE),
    re.compile(r"\bxác chết\b", re.IGNORECASE),
    re.compile(r"\btình dục\b", re.IGNORECASE),
    re.compile(r"\bkhỏa thân\b", re.IGNORECASE),
    re.compile(r"\bcưỡng hiếp\b", re.IGNORECASE),
]

# Paired sensitive terms: if EN source has term, VI target is expected to retain corresponding concept
SENSITIVE_CONCEPT_PAIRS: dict[str, list[str]] = {
    "blood": ["máu", "huyết"],
    "bloody": ["máu", "đẫm máu"],
    "gore": ["máu me", "ghê rợn", "kinh dị"],
    "torture": ["tra tấn", "hành hạ"],
    "murder": ["giết", "sát hại", "mưu sát"],
    "slaughter": ["tàn sát", "thảm sát", "chém giết"],
    "decapitat": ["chặt đầu", "chém đầu", "trảm thủ"],
    "rape": ["cưỡng hiếp", "hiếp dâm"],
    "sexual": ["tình dục", "khoái lạc"],
    "mutilat": ["cắt xẻo", "phanh thây", "biến dạng", "xẻo thịt"],
}


def digest(data: str | bytes) -> str:
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def scan_canonical_tables(
    workspace: str | Path,
    tables_config: list[dict[str, Any]],
    *,
    run_completed: bool = False,
    softening_ratio_threshold: float = 0.4,
    allow_identity_terms: set[str] | None = None,
    manual_fix_threshold: int = 15,
) -> dict[str, Any]:
    """Scan canonical CSV tables to detect safety guardrail refusals and covert softening.

    Strictly read-only: does not modify canonical CSV files.
    """
    root = Path(workspace).resolve(strict=True)
    exceptions: list[dict[str, Any]] = []
    scanned_row_count = 0
    table_summaries: list[dict[str, Any]] = []

    identity_set = {t.strip().lower() for t in (allow_identity_terms or set()) if t.strip()}

    for tbl in tables_config:
        tid = str(tbl.get("translation_id") or "").strip()
        domain = str(tbl.get("domain") or "").strip()
        rel_path = str(tbl.get("path") or "").strip()
        mapping = tbl.get("mapping") or {}

        if not tid or not domain or not rel_path:
            raise ValueError("each table must declare translation_id, domain, and path")

        csv_path = (root / rel_path).resolve()
        if not csv_path.is_relative_to(root) or not csv_path.is_file():
            raise ValueError(f"canonical CSV missing or escapes workspace: {rel_path}")

        key_col = str(mapping.get("key_column") or "key").strip()
        src_col = str(mapping.get("source_column") or "source").strip()
        tgt_col = str(mapping.get("target_column") or mapping.get("translation_column") or "translation_vi").strip()
        state_col = str(mapping.get("state_column") or "state").strip()
        speaker_col = str(mapping.get("speaker_column") or "speaker").strip()
        notes_col = str(mapping.get("notes_column") or "notes").strip()

        raw_bytes = csv_path.read_bytes()
        reader = csv.DictReader(io.StringIO(raw_bytes.decode("utf-8-sig"), newline=""), strict=True)
        headers = reader.fieldnames or []

        if key_col not in headers or src_col not in headers:
            raise ValueError(f"missing required key or source column in {rel_path}")

        actual_tgt_col = tgt_col
        if actual_tgt_col not in headers:
            if "target" in headers:
                actual_tgt_col = "target"
            else:
                raise ValueError(f"target column '{tgt_col}' missing in canonical CSV {rel_path}")

        tbl_row_count = 0
        tbl_exceptions = 0

        for line_no, row in enumerate(reader, start=2):
            if not row or None in row or all(not (v or "").strip() for v in row.values()):
                continue

            k = str(row.get(key_col) or "").strip()
            if not k:
                continue

            tbl_row_count += 1
            scanned_row_count += 1

            src_val = str(row.get(src_col) or "")
            tgt_val = str(row.get(actual_tgt_col) or "")
            state_val = str(row.get(state_col) or "").strip() if state_col in headers else ""
            speaker_val = str(row.get(speaker_col) or "").strip() if speaker_col in headers else ""

            # Check rows explicitly in pending with empty target:
            # During an in-progress run or initial scan, rows simply not yet translated are NOT hard refusals.
            # Only record as advisory untranslated_sensitive_pending so it surfaces in reports,
            # but do NOT count it towards escalation_refusal_count (which drives plan2 escalation)
            # unless run has been marked as fully completed.
            if state_val in PENDING_STATES and not tgt_val.strip():
                lower_src = src_val.lower()
                matched_hits = [m.group(0) for p in STRONG_SENSITIVE_PATTERNS if (m := p.search(lower_src))]
                if matched_hits:
                    tbl_exceptions += 1
                    exceptions.append({
                        "translation_id": tid,
                        "domain": domain,
                        "key": k,
                        "path": rel_path,
                        "source": src_val,
                        "target": "",
                        "state": state_val,
                        "speaker": speaker_val,
                        "issue_type": "untranslated_sensitive_pending",
                        "confidence": "medium",
                        "evidence": f"Pending row contains sensitive keywords (advisory): {matched_hits[:3]}",
                    })
                continue

            issue_type: str | None = None
            confidence: str = "high"
            evidence: str = ""

            # Check 1: Deterministic Refusal & Meta-Leak (Highest priority)
            for pat in REFUSAL_META_PATTERNS:
                m = pat.search(tgt_val)
                if m:
                    issue_type = "refusal_meta_leak"
                    confidence = "high"
                    evidence = f"Matched AI refusal pattern: '{m.group(0)}'"
                    break

            # Check 2: Explicit rejected state on canonical row
            if not issue_type and state_val == "rejected":
                # Inspect notes/reason column if present for explicit safety keywords
                notes_val = str(row.get(notes_col) or "").lower() if notes_col in headers else ""
                lower_src = src_val.lower()
                has_safety_note = any(kw in notes_val for kw in ["safety", "policy", "refus", "censor", "filter", "18+", "vi phạm", "từ chối"])
                has_sensitive_src = any(p.search(lower_src) for p in STRONG_SENSITIVE_PATTERNS)
                if has_safety_note or has_sensitive_src:
                    issue_type = "refusal_safety_rejected"
                    confidence = "high"
                    evidence = f"Canonical row rejected due to safety guardrail (notes: '{notes_val[:40]}')" if has_safety_note else "Rejected row contains sensitive source keywords"
                else:
                    issue_type = "rejected_state"
                    confidence = "high"
                    evidence = "Canonical row is explicitly marked rejected (QA/review)"

            # Check 3: Explicit needs_context state on canonical row
            if not issue_type and state_val == "needs_context":
                issue_type = "needs_context_state"
                confidence = "high"
                evidence = "Canonical row is marked needs_context and requires intervention"

            # Check 4: Blank / Empty Target on Non-Empty Source for completed/attempted state
            if not issue_type and src_val.strip() and not tgt_val.strip():
                if state_val in COMPLETED_OR_ATTEMPTED_STATES or not state_val:
                    issue_type = "empty_target"
                    confidence = "high"
                    evidence = f"Target is empty on non-pending state ('{state_val}')"

            # Check 3: Raw English Passthrough on Non-Trivial English Source
            if not issue_type and src_val.strip() and tgt_val.strip() == src_val.strip():
                src_clean = src_val.strip().lower()
                if src_clean not in identity_set:
                    words = re.findall(r"[A-Za-z]+", src_val)
                    if len(words) >= 3 and len(src_val) >= 12:
                        lower_src = src_val.lower()
                        has_sensitive_src = any(p.search(lower_src) for p in STRONG_SENSITIVE_PATTERNS)
                        credit_markers = ("developer", "lead artist", "voice acting", "programmer", "sound design", "producer", "animator")
                        is_credits_block = sum(1 for m in credit_markers if m in lower_src) >= 3
                        if has_sensitive_src and not is_credits_block:
                            # A passthrough on sensitive source is a confirmed refusal symptom
                            issue_type = "refusal_safety_rejected"
                            confidence = "high"
                            evidence = f"Target passthrough on sensitive source text ({len(words)} English words)"
                        else:
                            issue_type = "untranslated_passthrough"
                            confidence = "high"
                            evidence = f"Target is identical to source ({len(words)} English words)"

            # Check 6: Suspected Covert Softening (Advisory Heuristic, Medium confidence)
            if not issue_type and src_val.strip() and tgt_val.strip():
                lower_src = src_val.lower()
                lower_tgt = tgt_val.lower()
                matched_hits = [m.group(0) for p in STRONG_SENSITIVE_PATTERNS if (m := p.search(lower_src))]
                if matched_hits:
                    omitted_concepts = []
                    for en_term, vi_equivalents in SENSITIVE_CONCEPT_PAIRS.items():
                        # Word-boundary check on English concept key
                        if re.search(rf"\b{re.escape(en_term)}\w*\b", lower_src, re.IGNORECASE):
                            en_preserved = bool(re.search(rf"\b{re.escape(en_term)}\w*\b", lower_tgt, re.IGNORECASE))
                            if not en_preserved and not any(vi in lower_tgt for vi in vi_equivalents):
                                omitted_concepts.append(en_term)

                    src_len = max(len(src_val), 1)
                    tgt_len = len(tgt_val)
                    ratio = tgt_len / src_len
                    severe_truncation = ratio < softening_ratio_threshold and src_len >= 25

                    if omitted_concepts or severe_truncation:
                        issue_type = "suspected_softening"
                        confidence = "medium"
                        ev_parts = []
                        if omitted_concepts:
                            ev_parts.append(f"sensitive concepts omitted: {omitted_concepts[:3]}")
                        if severe_truncation:
                            ev_parts.append(f"ratio {ratio:.2f} < {softening_ratio_threshold}")
                        evidence = "; ".join(ev_parts)

            if issue_type:
                tbl_exceptions += 1
                exceptions.append({
                    "translation_id": tid,
                    "domain": domain,
                    "key": k,
                    "path": rel_path,
                    "source": src_val,
                    "target": tgt_val,
                    "state": state_val,
                    "speaker": speaker_val,
                    "issue_type": issue_type,
                    "confidence": confidence,
                    "evidence": evidence,
                })

        table_summaries.append({
            "translation_id": tid,
            "domain": domain,
            "path": rel_path,
            "row_count": tbl_row_count,
            "exception_count": tbl_exceptions,
        })

    # Categorize issues into distinct operational buckets:
    # 1. Hard Refusals: Explicit AI meta-leaks, empty targets on completed/attempted rows,
    # AND rows rejected specifically due to safety guardrails (notes or sensitive source).
    hard_refusal_count = sum(1 for e in exceptions if e["issue_type"] in {"refusal_meta_leak", "empty_target", "refusal_safety_rejected"})

    # 2. Sensitive Pending (Advisory during in-progress run, promoted to hard refusal if run_completed=True):
    sensitive_pending_count = sum(1 for e in exceptions if e["issue_type"] == "untranslated_sensitive_pending")

    # 3. Context & Review gaps (Quality issues, not censorship refusals):
    context_gap_count = sum(1 for e in exceptions if e["issue_type"] in {"rejected_state", "needs_context_state"})

    # 4. Passthrough & Heuristic softening issues (Advisory):
    passthrough_count = sum(1 for e in exceptions if e["issue_type"] == "untranslated_passthrough")
    suspected_softening_count = sum(1 for e in exceptions if e["issue_type"] == "suspected_softening")
    total_exceptions = len(exceptions)

    # If run_completed is True, any sensitive pending row left behind was refused/quarantined during the run,
    # so promote sensitive_pending_count to count towards escalation!
    escalation_refusal_count = hard_refusal_count + (sensitive_pending_count if run_completed else 0)

    # Escalation to Plan 2 is driven strictly by confirmed hard refusals (escalation_refusal_count).
    if escalation_refusal_count == 0:
        if suspected_softening_count > 0 or context_gap_count > 0 or passthrough_count > 0 or sensitive_pending_count > 0:
            recommendation = "review_advisory"
            recommendation_reason = (
                f"0 confirmed hard refusals, but found {sensitive_pending_count} sensitive pending, "
                f"{context_gap_count} context/review states, {passthrough_count} passthroughs, "
                f"and {suspected_softening_count} suspected softening lines. "
                "Recommend review in bientaptay."
            )
        else:
            recommendation = "clean"
            recommendation_reason = "No safety guardrail refusals or anomalies detected."
    elif escalation_refusal_count <= manual_fix_threshold:
        recommendation = "manual_fix"
        recommendation_reason = (
            f"{escalation_refusal_count} hard safety refusals found (<= {manual_fix_threshold} threshold). "
            "Recommend quick manual edit in bientaptay."
        )
    else:
        recommendation = "plan2_handoff"
        recommendation_reason = (
            f"{escalation_refusal_count} hard safety refusals found (> {manual_fix_threshold} threshold). "
            "Recommend Plan 2 external agent handoff."
        )

    report = {
        "schema": SCHEMA,
        "scanned_row_count": scanned_row_count,
        "exception_count": total_exceptions,
        "hard_refusal_count": hard_refusal_count,
        "sensitive_pending_count": sensitive_pending_count,
        "escalation_refusal_count": escalation_refusal_count,
        "run_completed": run_completed,
        "context_gap_count": context_gap_count,
        "passthrough_count": passthrough_count,
        "suspected_softening_count": suspected_softening_count,
        "recommendation": recommendation,
        "recommendation_reason": recommendation_reason,
        "manual_fix_threshold": manual_fix_threshold,
        "canonical_modified": False,
        "table_summaries": table_summaries,
        "exceptions": exceptions,
    }
    return report


def emit_safety_ledger_and_report(
    workspace: str | Path,
    tables_config: list[dict[str, Any]],
    ledger_out_path: str | Path,
    report_out_path: str | Path,
    *,
    run_completed: bool = False,
    softening_ratio_threshold: float = 0.4,
    allow_identity_terms: set[str] | None = None,
    manual_fix_threshold: int = 15,
) -> dict[str, Any]:
    """Scan canonical tables, write sidecar safety ledger, and emit structured audit report."""
    root = Path(workspace).resolve(strict=True)
    ledger_file = Path(ledger_out_path).resolve()
    report_file = Path(report_out_path).resolve()

    if not ledger_file.is_relative_to(root) or not report_file.is_relative_to(root):
        raise ValueError("output files must reside within workspace")

    scan_result = scan_canonical_tables(
        root,
        tables_config,
        run_completed=run_completed,
        softening_ratio_threshold=softening_ratio_threshold,
        allow_identity_terms=allow_identity_terms,
        manual_fix_threshold=manual_fix_threshold,
    )

    exceptions = scan_result.pop("exceptions")

    ledger_file.parent.mkdir(parents=True, exist_ok=True)
    with ledger_file.open("w", encoding="utf-8", newline="\n") as stream:
        for exc in exceptions:
            stream.write(json.dumps(exc, ensure_ascii=False) + "\n")

    summary = {
        "schema": SCHEMA,
        "ledger_sha256": digest(ledger_file.read_bytes()),
        "ledger_path": str(ledger_file.relative_to(root)),
        "summary": scan_result,
    }

    report_file.parent.mkdir(parents=True, exist_ok=True)
    report_file.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    return summary


def build_plan2_exception_plan(
    workspace: str | Path,
    tables_config: list[dict[str, Any]],
    ledger_path: str | Path,
    package_id: str,
    project_id: str,
    *,
    token_pattern: str = r"\{[0-9]+\}",
    include_pending: bool = True,
    include_suspected: bool = False,
    allow_explicit_content_handoff: bool = True,
) -> dict[str, Any]:
    """Convert safety exception ledger into a Plan 2 exception plan ready for external agent dispatch."""
    root = Path(workspace).resolve(strict=True)
    ledger_file = Path(ledger_path).resolve(strict=True)

    if not ledger_file.is_relative_to(root):
        raise ValueError("ledger file must reside within workspace")

    selected_identities: list[list[str]] = []
    seen_identities: set[tuple[str, str, str]] = set()
    row_policies: dict[str, dict[str, Any]] = {}

    with ledger_file.open("r", encoding="utf-8") as stream:
        for line in stream:
            line = line.strip()
            if not line:
                continue
            item = json.loads(line)
            issue = item.get("issue_type")

            # Exclude non-censorship context gaps and benign passthroughs from the Plan 2 censorship bypass package
            if issue in {"rejected_state", "needs_context_state", "untranslated_passthrough"}:
                continue

            # Untranslated sensitive pending lines are included by default unless explicitly turned off
            if issue == "untranslated_sensitive_pending" and not include_pending:
                continue

            # Heuristic suspected softening requires explicit opt-in
            if issue == "suspected_softening" and not include_suspected:
                continue

            tid = str(item.get("translation_id") or "").strip()
            domain = str(item.get("domain") or "").strip()
            k = str(item.get("key") or "").strip()
            if not tid or not domain or not k:
                continue

            ident_key = (tid, domain, k)
            if ident_key in seen_identities:
                continue
            seen_identities.add(ident_key)

            ident = [tid, domain, k]
            selected_identities.append(ident)

            pol_key = f"{tid}::{domain}::{k}"
            src_text = str(item.get("source") or "").lower()
            source_has_sensitive_terms = any(p.search(src_text) for p in STRONG_SENSITIVE_PATTERNS)

            is_content_gate = (
                issue in {"refusal_meta_leak", "refusal_safety_rejected", "suspected_softening"}
                or source_has_sensitive_terms
            )
            row_policies[pol_key] = {
                "exception_status": "content_gate" if is_content_gate else "refused",
                "preserve_explicit_content": is_content_gate and allow_explicit_content_handoff,
                "translation_policy": (
                    "preserve explicit/violent content verbatim; do not soften, censor, or omit"
                    if is_content_gate and allow_explicit_content_handoff else "standard"
                ),
            }

    plan_tables = []
    for tbl in tables_config:
        if not isinstance(tbl, dict):
            raise ValueError("each table in tables_config must be an object")
        t_id = str(tbl.get("translation_id") or "").strip()
        t_dom = str(tbl.get("domain") or "").strip()
        t_path = str(tbl.get("path") or "").strip()
        if not t_id or not t_dom or not t_path:
            raise ValueError("each table must declare translation_id, domain, and path")

        mapping = dict(tbl.get("mapping") or {})
        mapping.setdefault("key_column", "key")
        mapping.setdefault("source_column", "source")

        # Resolve target column strictly matching what scan_canonical_tables used:
        # Check canonical CSV header on disk with strict csv.reader if target_column isn't explicit
        csv_file = (root / t_path).resolve()
        if csv_file.is_file():
            raw_bytes = csv_file.read_bytes()
            reader = csv.reader(io.StringIO(raw_bytes.decode("utf-8-sig", errors="replace"), newline=""))
            try:
                headers = [h.strip() for h in next(reader)]
            except (StopIteration, Exception):
                headers = []
            if "translation_vi" in headers:
                mapping["target_column"] = "translation_vi"
            elif "target" in headers:
                mapping["target_column"] = "target"
            else:
                tgt_col_name = mapping.get("target_column") or mapping.get("translation_column") or "translation_vi"
                mapping["target_column"] = str(tgt_col_name).strip()
        else:
            tgt_col_name = mapping.get("target_column") or mapping.get("translation_column") or "translation_vi"
            mapping["target_column"] = str(tgt_col_name).strip()

        mapping.setdefault("state_column", "state")

        plan_tables.append({
            "translation_id": t_id,
            "domain": t_dom,
            "path": t_path,
            "mapping": mapping,
            "token_pattern": tbl.get("token_pattern") or token_pattern,
        })

    plan = {
        "package_id": package_id,
        "project_id": project_id,
        "scope": "exception",
        "allow_explicit_content_handoff": allow_explicit_content_handoff,
        "tables": plan_tables,
        "selected_identities": selected_identities,
        "row_policies": row_policies,
        "re_dispatch_eligible": len(selected_identities) > 0,
    }
    return plan


def main() -> int:
    parser = argparse.ArgumentParser(description="Plan 1 Safety Guardrail Detector & Bridge")
    subparsers = parser.add_subparsers(dest="action", required=True)

    scan_p = subparsers.add_parser("scan")
    scan_p.add_argument("--workspace", type=Path, required=True)
    scan_p.add_argument("--config", type=Path, required=True)
    scan_p.add_argument("--ledger", type=Path, required=True)
    scan_p.add_argument("--report", type=Path, required=True)
    scan_p.add_argument("--threshold", type=int, default=15)
    scan_p.add_argument("--run-completed", action="store_true", default=False)

    bridge_p = subparsers.add_parser("bridge-plan2")
    bridge_p.add_argument("--workspace", type=Path, required=True)
    bridge_p.add_argument("--config", type=Path, required=True)
    bridge_p.add_argument("--ledger", type=Path, required=True)
    bridge_p.add_argument("--package-id", type=str, required=True)
    bridge_p.add_argument("--project-id", type=str, required=True)
    bridge_p.add_argument("--out-plan", type=Path, required=True)
    bridge_p.add_argument("--include-pending", action=argparse.BooleanOptionalAction, default=True)
    bridge_p.add_argument("--include-suspected", action=argparse.BooleanOptionalAction, default=False)

    args = parser.parse_args()

    try:
        if args.action == "scan":
            cfg = json.loads(args.config.read_text(encoding="utf-8"))
            tables = cfg.get("tables", [])
            summary = emit_safety_ledger_and_report(
                args.workspace,
                tables,
                args.ledger,
                args.report,
                run_completed=args.run_completed,
                manual_fix_threshold=args.threshold,
            )
            print(json.dumps({"result": "scanned", "summary": summary, "canonical_modified": False}, ensure_ascii=False))
            return 0
        elif args.action == "bridge-plan2":
            cfg = json.loads(args.config.read_text(encoding="utf-8"))
            tables = cfg.get("tables", [])
            plan = build_plan2_exception_plan(
                args.workspace,
                tables,
                args.ledger,
                args.package_id,
                args.project_id,
                include_pending=args.include_pending,
                include_suspected=args.include_suspected,
            )
            args.out_plan.parent.mkdir(parents=True, exist_ok=True)
            args.out_plan.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            print(json.dumps({"result": "bridged", "exception_count": len(plan["selected_identities"]), "canonical_modified": False}, ensure_ascii=False))
            return 0
    except Exception as exc:
        print(json.dumps({"result": "error", "error": str(exc)}, ensure_ascii=False))
        return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
