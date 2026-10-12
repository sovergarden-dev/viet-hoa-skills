"""Directional Pronoun Consistency Validator (viethoa/pronoun-consistency-validator/v1).

Validates directional Vietnamese pronoun consistency across dialogue lines:
- Speaker -> Listener directional matrix (self-pronoun vs call-pronoun).
- Stage-based progression (early, mid, late relationship stages).
- Emotion-driven exceptions (hostile, rebellious, intimate).
- Gender-neutral guardrails for unknown-gender characters.
- Strict read-only audit: does NOT mutate canonical files.

Attribution: Concept inspired by kann420/VH-Workflow-Skill (MIT License) and
hardened into an automated validator with directional checking & false-positive filters.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import re
import unicodedata
from pathlib import Path
from typing import Any

SCHEMA = "viethoa/pronoun-consistency-validator/v1"

# Common personal pronouns in Vietnamese
ALL_SELF_PRONOUNS = {
    "tôi", "tao", "ta", "em", "anh", "chị", "con", "cháu", "ông", "bà",
    "mẹ", "cha", "bố", "ba", "má", "thầy", "u",
    "mình", "tớ", "chúng tôi", "chúng tao", "chúng ta", "chúng em", "chúng mình",
    "bần đạo", "lão phu", "tiểu bối", "bổn tọa", "trẫm"
}

# Second-person direct addressee pronouns (used to call the listener directly)
DIRECT_CALL_PRONOUNS = {
    "mày", "mi", "ngươi", "em", "anh", "chị", "con", "cháu", "cô", "chú", "bác", "ông", "bà",
    "cậu", "bạn", "ngài", "thầy", "sư phụ", "chàng", "nàng",
    "các bạn", "mọi người", "các ngươi", "chúng mày", "quý vị", "toàn đội"
}

# Third-person mentions (referring to an absent third party or object - NOT a 2nd-person addressee call)
THIRD_PERSON_MENTIONS = {
    "hắn", "nó", "họ", "gã đó", "kẻ đó", "chúng nó", "ả đó", "tên đó", "thằng đó"
}

ALL_CALL_PRONOUNS = DIRECT_CALL_PRONOUNS | THIRD_PERSON_MENTIONS

# Common false-positive compounds where a pronoun word is actually a noun classifier, title, insult, or adjective
COMPOUND_FALSE_POSITIVES = {
    "con đường", "con phố", "con dao", "con sông", "con suối", "con mắt", "con cá", "con mèo", "con chó", "con người",
    "con số", "con bé", "con đực", "con cái", "con tàu", "con thoi", "con tim",
    "con đĩ", "con khốn", "con ranh", "con điếm", "con nhỏ", "con mụ", "thỏ con", "bé con",
    "cô thỏ", "cậu nhóc",
    "cô đơn", "cô độc", "cô lập", "cô giáo", "cô bé", "cô dâu", "cô ả",
    "anh dũng", "anh hùng", "anh minh", "anh rể", "anh họ", "anh em",
    "anh trai", "anh cả", "anh hai", "chị dâu", "chị họ", "chị em", "chị gái", "chị cả", "chị hai",
    "em gái", "em trai", "em họ", "em út",
    "một mình", "tự mình", "chính mình", "bản thân mình", "cho riêng mình",
    "bác bỏ", "bác ái", "bác học", "bác sĩ",
    "chú ý", "chú giải", "chú trọng", "chú tâm", "chú rể", "chú bé",
    "ông tơ", "bà chúa", "bà mối", "ông trùm", "ông bà", "ông già", "bà già",
    "thằng cha", "thằng khốn", "thằng nhãi", "thằng bé", "thằng dốt"
}
COMPOUND_FALSE_POSITIVES_VIEW = {unicodedata.normalize("NFKC", c).casefold() for c in COMPOUND_FALSE_POSITIVES}

LEFT_MODIFIERS = {"các", "mấy", "đám", "lũ", "nhóm", "lời", "tiếng", "theo", "nhờ"}
RIGHT_DEMONSTRATIVES = {"ấy", "đó", "này", "kia"}
RIGHT_KINSHIP_TRAITS = {"trai", "gái", "cả", "hai", "ba", "út", "họ", "dâu", "rể"}


def find_standalone_occurrences(text: str, pronoun: str, allow_demonstratives: bool = True) -> list[int]:
    """Find token indices of a pronoun that appear standalone, filtering out modifiers, compounds, and demonstratives."""
    norm_text = unicodedata.normalize("NFKC", text).casefold()
    p_norm = unicodedata.normalize("NFKC", pronoun).casefold()
    words = re.findall(r"\b[a-zà-ỹđ0-9_-]+\b", norm_text)
    indices = []
    for i, w in enumerate(words):
        if w != p_norm:
            continue
        prev_w = words[i - 1] if i > 0 else ""
        next_w = words[i + 1] if i + 1 < len(words) else ""

        # Check bigrams in compounds
        if prev_w and f"{prev_w} {w}" in COMPOUND_FALSE_POSITIVES_VIEW:
            continue
        if next_w and f"{w} {next_w}" in COMPOUND_FALSE_POSITIVES_VIEW:
            continue
        # Check left modifier context (group quantifiers, reportive possessives)
        if prev_w in LEFT_MODIFIERS:
            continue
        # Check right demonstratives (kinship/title pronouns only, when allowed)
        if allow_demonstratives and p_norm in {"anh", "em", "chị", "cô", "chú", "bác", "ông", "bà", "cậu", "bạn", "con", "cháu"} and next_w in RIGHT_DEMONSTRATIVES:
            continue
        # Check right kinship traits
        if p_norm in {"anh", "chị", "em"} and next_w in RIGHT_KINSHIP_TRAITS:
            continue

        indices.append(i)
    return indices


def extract_pronouns(text: str) -> dict[str, set[str]]:
    """Extract candidate self and call pronouns from Vietnamese text, suppressing common compounds."""
    norm_text = unicodedata.normalize("NFKC", text).casefold()
    cleaned = norm_text

    # Suppress known compound phrases by masking them with whitespace of exact length
    for comp in COMPOUND_FALSE_POSITIVES:
        comp_norm = unicodedata.normalize("NFKC", comp).casefold()
        if comp_norm in cleaned:
            cleaned = cleaned.replace(comp_norm, " " * len(comp_norm))

    words = re.findall(r"\b[a-zà-ỹđ0-9_-]+\b", cleaned)
    found_self = set()
    found_call = set()

    for w in words:
        if w in ALL_SELF_PRONOUNS:
            found_self.add(w)
        if w in ALL_CALL_PRONOUNS:
            found_call.add(w)

    # Check two-word phrases like "chúng tôi", "các bạn", "sư phụ", etc.
    for phrase in ALL_SELF_PRONOUNS:
        phrase_norm = unicodedata.normalize("NFKC", phrase).casefold()
        if " " in phrase_norm and re.search(rf"\b{re.escape(phrase_norm)}\b", cleaned):
            found_self.add(phrase)
    for phrase in ALL_CALL_PRONOUNS:
        phrase_norm = unicodedata.normalize("NFKC", phrase).casefold()
        if " " in phrase_norm and re.search(rf"\b{re.escape(phrase_norm)}\b", cleaned):
            found_call.add(phrase)

    return {"self": found_self, "call": found_call}


def infer_scene_listeners(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Infer missing listener from conversation turn-taking within the same context/scene block."""
    context_groups: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        cid = str(r.get("context_id") or r.get("scene") or "").strip()
        context_groups.setdefault(cid, []).append(r)

    inferred_rows = []
    for cid, g_rows in context_groups.items():
        if cid and len(g_rows) > 1:
            speakers = [str(r.get("speaker") or "").strip() for r in g_rows if str(r.get("speaker") or "").strip()]
            unique_speakers = list(dict.fromkeys(speakers))
            for r in g_rows:
                r_copy = dict(r)
                if not r_copy.get("listener") and len(unique_speakers) == 2:
                    current_spk = str(r_copy.get("speaker") or "").strip()
                    if current_spk in unique_speakers:
                        other_spk = unique_speakers[1] if current_spk == unique_speakers[0] else unique_speakers[0]
                        r_copy["listener"] = other_spk
                        r_copy["listener_inferred"] = True
                inferred_rows.append(r_copy)
        else:
            inferred_rows.extend(g_rows)

    return inferred_rows


def scan_dialogue_rows(
    rows: list[dict[str, Any]],
    matrix_data: dict[str, Any],
    *,
    default_stage: str = "all",
    infer_listeners: bool = True,
) -> dict[str, Any]:
    """Scan dialogue rows against the directional pronoun matrix with deterministic precedence."""
    if infer_listeners:
        rows = infer_scene_listeners(rows)

    matrices = matrix_data.get("matrices", [])
    characters = {k.strip().lower(): v for k, v in matrix_data.get("characters", {}).items()}
    special_rules = matrix_data.get("special_rules", {})

    forbidden_gendered = set(special_rules.get("forbidden_gendered_pronouns_for_unknown", []))
    group_call_pronouns = set(special_rules.get("group_call_pronouns", []))

    # Index matrix rules by (speaker, listener, stage)
    rule_lookup: dict[tuple[str, str, str], dict[str, Any]] = {}
    for rule in matrices:
        spk = str(rule.get("speaker", "")).strip().lower()
        lis = str(rule.get("listener", "")).strip().lower()
        stg = str(rule.get("stage", "all")).strip().lower()
        key = (spk, lis, stg)
        if key not in rule_lookup:
            rule_lookup[key] = rule

    violations: list[dict[str, Any]] = []
    scanned_dialogue_count = 0
    unmatched_pairs_count = 0

    for i, row in enumerate(rows):
        key = str(row.get("key") or i)
        speaker = str(row.get("speaker") or "").strip()
        listener = str(row.get("listener") or "").strip()
        stage = str(row.get("stage") or default_stage).strip().lower()
        source = str(row.get("source") or row.get("source_en") or "")
        target = str(row.get("target") or row.get("translation_vi") or "")
        emotion = str(row.get("emotion") or row.get("notes") or "").strip().lower()

        if not target.strip():
            continue

        # Skip UI, item, or system rows without speaker
        if not speaker:
            continue

        scanned_dialogue_count += 1
        extracted = extract_pronouns(target)
        found_self = extracted["self"]
        found_call = extracted["call"]

        # Rule Check 1: Unknown-gender character protection on listener
        l_low = listener.lower() if listener else ""
        if l_low and l_low in characters:
            listener_meta = characters[l_low]
            if listener_meta.get("gender") == "unknown":
                gendered_used = set()
                for p in found_call.intersection(forbidden_gendered):
                    # Suppress false positives on compounds and modifier contexts (e.g. "lời anh", "anh trai")
                    # but strictly forbid gendered demonstratives (e.g. "cô ấy") when speaking to unknown-gender entities
                    if not find_standalone_occurrences(target, p, allow_demonstratives=False):
                        continue
                    gendered_used.add(p)

                if gendered_used:
                    violations.append({
                        "key": key,
                        "speaker": speaker,
                        "listener": listener,
                        "source": source,
                        "target": target,
                        "issue_type": "gendered_pronoun_on_unknown",
                        "severity": "high",
                        "evidence": f"Used gendered call pronouns {sorted(gendered_used)} for unknown-gender listener '{listener}'",
                        "allowed": sorted(special_rules.get("allowed_neutral_pronouns_for_unknown", [])),
                    })
                    continue

        # Rule Check 2: Deterministic 6-tier precedence lookup for directional rules
        s_low = speaker.lower()
        l_low = listener.lower() if listener else "*"

        precedence_keys = [
            (s_low, l_low, stage),
            (s_low, l_low, "all"),
            (s_low, "*", stage),
            (s_low, "*", "all"),
            ("*", l_low, stage),
            ("*", l_low, "all"),
        ]

        best_rule = None
        matched_precedence_tier = -1
        for tier, p_key in enumerate(precedence_keys):
            if p_key in rule_lookup:
                best_rule = rule_lookup[p_key]
                matched_precedence_tier = tier
                break

        if not best_rule:
            if listener:
                unmatched_pairs_count += 1
            continue

        allowed_self = set(best_rule.get("self_pronouns", []))
        allowed_call = set(best_rule.get("call_pronouns", []))

        # Check emotion exceptions
        emotion_exceptions = best_rule.get("emotion_exceptions", {})
        matched_emotion_key = None
        for emo_k in emotion_exceptions:
            if emo_k in emotion:
                matched_emotion_key = emo_k
                break

        if matched_emotion_key:
            emo_rule = emotion_exceptions[matched_emotion_key]
            allowed_self.update(emo_rule.get("self_pronouns", []))
            allowed_call.update(emo_rule.get("call_pronouns", []))

        # Allow universal group call pronouns
        allowed_call.update(group_call_pronouns)

        # Disallow unauthorized self-pronouns that violate the matrix
        unauthorized_self = set()
        has_valid_self = bool(found_self.intersection(allowed_self))
        for p in found_self:
            if p not in allowed_self and p not in allowed_call:
                # "mình" can serve as a reflexive pronoun (equivalent to oneself/myself)
                if p == "mình":
                    # If target already has an authorized self pronoun AND mình appears after perception verbs / prepositions
                    if has_valid_self and re.search(r"\b(thấy|cảm thấy|nhận thấy|nghĩ|coi|xem|cho|với|về|của|ở|chằm chằm|vào|đến)\s+(?:riêng\s+|chính\s+|tự\s+)?mình\b", target.lower()):
                        continue
                    if re.search(r"\b(cho|với|về|của|ở|chằm chằm|vào|đến|thấy|cảm thấy|nghĩ|coi|xem|một|tự|chính|riêng)\s+(?:riêng\s+|chính\s+|tự\s+)?mình\b|\b(?:riêng|chính|tự|một)\s+mình\b", target.lower()):
                        continue
                # Suppress if pronoun only appears in authorized modifier contexts (e.g. "lời anh", "các em", "em ấy")
                if not find_standalone_occurrences(target, p):
                    continue
                if p in {"tao", "tôi", "em", "anh", "chị", "con", "cháu", "mẹ", "cha", "bố", "ba", "má", "mình", "tớ"}:
                    unauthorized_self.add(p)

        # Disallow unauthorized 2nd-person direct addressee call-pronouns that violate the matrix
        unauthorized_call = set()
        for p in found_call:
            # Only flag genuine 2nd-person direct addressee pronouns, NEVER 3rd-person mentions (hắn, nó, họ)
            if p in DIRECT_CALL_PRONOUNS and p not in allowed_call and p not in allowed_self:
                # Polite honorific address like "thưa bà", "thưa ông" is permitted when addressing elders/superiors
                if p in {"ông", "bà"} and ("thưa bà" in target.lower() or "thưa ông" in target.lower()):
                    continue
                # Suppress if pronoun only appears in authorized modifier contexts (e.g. "lời anh", "các em", "em ấy")
                if not find_standalone_occurrences(target, p):
                    continue
                # Flag direct address call pronouns that violate relationship matrix
                if p in {"mày", "mi", "ngươi", "cô", "chú", "bác", "ông", "bà", "cậu", "bạn", "anh", "em", "chị", "con", "cháu"}:
                    unauthorized_call.add(p)

        if unauthorized_self or unauthorized_call:
            violations.append({
                "key": key,
                "speaker": speaker,
                "listener": listener or "(speaker_default)",
                "stage": stage,
                "source": source,
                "target": target,
                "issue_type": "pronoun_drift",
                "severity": "medium",
                "unauthorized_self": sorted(unauthorized_self),
                "unauthorized_call": sorted(unauthorized_call),
                "allowed_self": sorted(allowed_self),
                "allowed_call": sorted(allowed_call),
                "precedence_tier": matched_precedence_tier,
                "rationale": f"Pronoun drift detected for pair '{speaker}' -> '{listener or '*'}' (stage={stage}).",
            })

    return {
        "schema": SCHEMA,
        "scanned_dialogue_count": scanned_dialogue_count,
        "drift_count": len(violations),
        "unmatched_pairs_count": unmatched_pairs_count,
        "canonical_modified": False,
        "violations": violations,
    }


def scan_canonical_csv(
    csv_path: str | Path,
    matrix_path: str | Path,
    *,
    key_column: str = "key",
    source_column: str = "source",
    target_column: str = "translation_vi",
    speaker_column: str = "speaker",
    listener_column: str = "listener",
    context_column: str = "context_id",
    notes_column: str = "notes",
    infer_listeners: bool = True,
) -> dict[str, Any]:
    """Scan a canonical CSV against a pronoun matrix JSON file."""
    c_p = Path(csv_path).resolve(strict=True)
    m_p = Path(matrix_path).resolve(strict=True)

    matrix_data = json.loads(m_p.read_text(encoding="utf-8"))
    with c_p.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        rows = []
        for r in reader:
            rows.append({
                "key": r.get(key_column, ""),
                "source": r.get(source_column, ""),
                "target": r.get(target_column, ""),
                "speaker": r.get(speaker_column, ""),
                "listener": r.get(listener_column, ""),
                "context_id": r.get(context_column, "") or r.get("context", "") or r.get("scene", ""),
                "notes": r.get(notes_column, ""),
            })

    res = scan_dialogue_rows(rows, matrix_data, infer_listeners=infer_listeners)
    res["path"] = str(c_p)
    res["matrix_path"] = str(m_p)
    return res


def main() -> int:
    parser = argparse.ArgumentParser(description="Directional Pronoun Consistency Validator")
    parser.add_argument("--csv", type=Path, required=True, help="Path to canonical CSV table")
    parser.add_argument("--matrix", type=Path, required=True, help="Path to pronoun matrix JSON file")
    parser.add_argument("--key-col", default="key", help="Key column name")
    parser.add_argument("--source-col", default="source", help="Source text column name")
    parser.add_argument("--target-col", default="translation_vi", help="Target text column name")
    parser.add_argument("--speaker-col", default="speaker", help="Speaker column name")
    parser.add_argument("--listener-col", default="listener", help="Listener column name")
    parser.add_argument("--context-col", default="context_id", help="Context/scene column name")
    parser.add_argument("--no-infer-listeners", action="store_true", help="Disable conversational listener inference")
    parser.add_argument("--out-report", type=Path, help="Optional output JSON report path")

    args = parser.parse_args()
    try:
        res = scan_canonical_csv(
            args.csv,
            args.matrix,
            key_column=args.key_col,
            source_column=args.source_col,
            target_column=args.target_col,
            speaker_column=args.speaker_col,
            listener_column=args.listener_col,
            context_column=args.context_col,
            infer_listeners=not args.no_infer_listeners,
        )

        if args.out_report:
            args.out_report.parent.mkdir(parents=True, exist_ok=True)
            args.out_report.write_text(json.dumps(res, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        print(json.dumps({
            "result": "scanned",
            "scanned_dialogue_count": res["scanned_dialogue_count"],
            "drift_count": res["drift_count"],
            "unmatched_pairs_count": res.get("unmatched_pairs_count", 0),
            "canonical_modified": False,
        }, ensure_ascii=False))
        return 0 if res["drift_count"] == 0 else 1
    except Exception as exc:
        print(json.dumps({"result": "error", "error": str(exc)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
