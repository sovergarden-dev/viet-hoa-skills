"""Domestication & Euphemism Detector for Game Localization (viethoa/domestication-detector/v1).

Scans localization tables (CSV / JSON) to detect deviations from Source-Fidelity:
1. Banned Euphemisms / Softening on 18+ content (e.g. HORNY -> Hưng phấn).
2. Bureaucratic / Administrative Mismatches on adult content (e.g. PERVERSION -> Đồi trụy).
3. Out-of-Genre Archaic Loanwords in modern/sci-fi settings (e.g. Trenchcoat -> Áo măng tô).
4. Brand / Mascot Flattening (e.g. WeatherBear -> Dự báo thời tiết).

Strictly read-only: inspects data without modifying canonical files.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import re
from pathlib import Path
from typing import Any

SCHEMA = "viethoa/domestication-detector/v1"

# Default rules for detection: (rule_id, category, source_regex, target_regex, rationale)
DEFAULT_RULES: list[dict[str, Any]] = [
    {
        "rule_id": "horny_euphemism",
        "category": "banned_euphemism",
        "source_pattern": re.compile(r"\bhorny\b", re.IGNORECASE),
        "target_pattern": re.compile(r"\bhưng\s*phấn\b|\bphấn\s*khởi\b", re.IGNORECASE),
        "rationale": "HORNY refers to sexual arousal / lust; softening to 'hưng phấn' turns an adult stat into mild excitement.",
    },
    {
        "rule_id": "perversion_bureaucratic",
        "category": "bureaucratic_softening",
        "source_pattern": re.compile(r"\bperversion\b|\bpervert(ed)?\b", re.IGNORECASE),
        "target_pattern": re.compile(r"\bđồi\s*trụy\b", re.IGNORECASE),
        "rationale": "PERVERSION in adult fiction refers to kink / deviance / being a pervert; 'đồi trụy' is administrative legal jargon.",
    },
    {
        "rule_id": "trenchcoat_archaic_loanword",
        "category": "archaic_loanword",
        "source_pattern": re.compile(r"\btrenchcoat\b|\btrench\s*coat\b", re.IGNORECASE),
        "target_pattern": re.compile(r"\bmăng\s*tô\b", re.IGNORECASE),
        "rationale": "'Măng tô' (manteau) is a French colonial-era loanword out of place in a modern / cyberpunk aesthetic.",
    },
    {
        "rule_id": "weatherbear_brand_flattening",
        "category": "brand_flattening",
        "source_pattern": re.compile(r"\bweatherbear\b", re.IGNORECASE),
        "target_pattern": re.compile(r"^dự\s*báo\s*thời\s*tiết$|\bthời\s*tiết\b", re.IGNORECASE),
        "rationale": "WeatherBear is a fictional brand/mascot app name; flattening to generic 'dự báo thời tiết' destroys creator IP.",
    },
]


def load_rules(rules_path: str | Path | None = None) -> list[dict[str, Any]]:
    """Load detection rules from an external JSON file or return DEFAULT_RULES."""
    if rules_path is None:
        return DEFAULT_RULES

    p = Path(rules_path).resolve(strict=True)
    raw_rules = json.loads(p.read_text(encoding="utf-8"))
    compiled_rules: list[dict[str, Any]] = []

    for r in raw_rules:
        compiled_rules.append({
            "rule_id": str(r.get("rule_id") or "custom_rule"),
            "category": str(r.get("category") or "custom"),
            "source_pattern": re.compile(str(r["source_pattern"]), re.IGNORECASE),
            "target_pattern": re.compile(str(r["target_pattern"]), re.IGNORECASE),
            "rationale": str(r.get("rationale") or ""),
        })

    return compiled_rules


def scan_pairs(
    items: list[dict[str, Any]],
    rules: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Scan list of translation items: dict with 'key', 'source', 'target', optional 'domain'."""
    active_rules = rules if rules is not None else DEFAULT_RULES
    violations: list[dict[str, Any]] = []

    for item in items:
        k = str(item.get("key") or "")
        src = str(item.get("source") or "")
        tgt = str(item.get("target") or "")
        domain = str(item.get("domain") or "default")

        if not src.strip() or not tgt.strip():
            continue

        for rule in active_rules:
            s_pat: re.Pattern = rule["source_pattern"]
            t_pat: re.Pattern = rule["target_pattern"]

            s_match = s_pat.search(src)
            t_match = t_pat.search(tgt)

            if s_match and t_match:
                violations.append({
                    "rule_id": rule["rule_id"],
                    "category": rule["category"],
                    "domain": domain,
                    "key": k,
                    "source": src,
                    "target": tgt,
                    "source_match": s_match.group(0),
                    "target_match": t_match.group(0),
                    "rationale": rule["rationale"],
                })

    return violations


def scan_canonical_csv(
    csv_path: str | Path,
    *,
    key_col: str = "key",
    source_col: str = "source",
    target_col: str = "translation_vi",
    domain: str = "main",
    rules: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Scan a single canonical CSV file for domestication & softening violations."""
    p = Path(csv_path).resolve(strict=True)
    raw = p.read_bytes()
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig"), newline=""))
    headers = reader.fieldnames or []

    actual_target = target_col
    if actual_target not in headers and "target" in headers:
        actual_target = "target"

    items = []
    for row in reader:
        if not row:
            continue
        items.append({
            "key": row.get(key_col, ""),
            "source": row.get(source_col, ""),
            "target": row.get(actual_target, ""),
            "domain": domain,
        })

    violations = scan_pairs(items, rules=rules)
    return {
        "schema": SCHEMA,
        "path": str(p),
        "scanned_count": len(items),
        "violation_count": len(violations),
        "canonical_modified": False,
        "violations": violations,
    }


def scan_localization_dict_json(
    json_path: str | Path,
    rules: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Scan a key-value dictionary JSON (e.g. master_localization_dict.json)."""
    p = Path(json_path).resolve(strict=True)
    data = json.loads(p.read_text(encoding="utf-8"))
    items = []
    if isinstance(data, dict):
        for k, v in data.items():
            items.append({
                "key": k,
                "source": k,
                "target": str(v),
                "domain": "ui_dict",
            })
    elif isinstance(data, list):
        for i, row in enumerate(data):
            if isinstance(row, dict):
                items.append({
                    "key": str(row.get("key") or i),
                    "source": str(row.get("source") or row.get("en") or ""),
                    "target": str(row.get("target") or row.get("vi") or ""),
                    "domain": "ui_list",
                })

    violations = scan_pairs(items, rules=rules)
    return {
        "schema": SCHEMA,
        "path": str(p),
        "scanned_count": len(items),
        "violation_count": len(violations),
        "canonical_modified": False,
        "violations": violations,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Domestication & Euphemism Detector")
    parser.add_argument("--file", type=Path, required=True, help="Path to CSV or JSON dictionary")
    parser.add_argument("--format", choices=["csv", "json"], default="json")
    parser.add_argument("--rules", type=Path, help="Optional path to custom rules JSON file")
    parser.add_argument("--out-report", type=Path, help="Optional output JSON report path")

    args = parser.parse_args()
    try:
        active_rules = load_rules(args.rules) if args.rules else DEFAULT_RULES
        if args.format == "csv" or args.file.suffix.lower() == ".csv":
            res = scan_canonical_csv(args.file, rules=active_rules)
        else:
            res = scan_localization_dict_json(args.file, rules=active_rules)

        if args.out_report:
            args.out_report.parent.mkdir(parents=True, exist_ok=True)
            args.out_report.write_text(json.dumps(res, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        print(json.dumps({
            "result": "scanned",
            "violation_count": res["violation_count"],
            "canonical_modified": False,
        }, ensure_ascii=False))
        return 0 if res["violation_count"] == 0 else 1
    except Exception as exc:
        print(json.dumps({"result": "error", "error": str(exc)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
