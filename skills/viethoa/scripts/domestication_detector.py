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
import unicodedata
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

    # --- Category 1: 18+ Adult Euphemisms & Bureaucratic Softening (P2b Expanded) ---
    {
        "rule_id": "creampie_softening",
        "category": "banned_euphemism",
        "source_pattern": re.compile(r"\bcreampie\b", re.IGNORECASE),
        "target_pattern": re.compile(r"\bbánh\s*kem\b|\bbánh\s*ngọt\b", re.IGNORECASE),
        "rationale": "CREAMPIE in adult context must retain sexual act meaning; softening to generic dessert corrupts context.",
    },
    {
        "rule_id": "slut_whore_bureaucratic",
        "category": "bureaucratic_softening",
        "source_pattern": re.compile(r"\bslut\b|\bwhore\b", re.IGNORECASE),
        "target_pattern": re.compile(r"\bngười\s*hành\s*nghề\s*mại\s*dâm\b|\bgái\s*bán\s*hoa\b", re.IGNORECASE),
        "rationale": "SLUT/WHORE in dialogue are colloquial insults; administrative euphemisms destroy character tone.",
    },
    {
        "rule_id": "cum_ejaculation_softening",
        "category": "banned_euphemism",
        "source_pattern": re.compile(r"\bcum(ming)?\b", re.IGNORECASE),
        "target_pattern": re.compile(r"\bra\s*mồ\s*hôi\b|\bđạt\s*khoái\s*cảm\s*nhẹ\b", re.IGNORECASE),
        "rationale": "CUM/CUMMING is explicit orgasm/ejaculation; softening to sweat or mild pleasure is domestic censorship.",
    },
    {
        "rule_id": "dildo_flattening",
        "category": "banned_euphemism",
        "source_pattern": re.compile(r"\bdildo\b", re.IGNORECASE),
        "target_pattern": re.compile(r"\bdụng\s*cụ\s*massage\b|\bmáy\s*mát\s*xa\b", re.IGNORECASE),
        "rationale": "DILDO is a sex toy; flattening to generic massage equipment erases explicit intent.",
    },

    # --- Category 2: Western Proper Nouns & Brands (Anti-Domestication) ---
    {
        "rule_id": "blackdog_brand",
        "category": "proper_noun_domestication",
        "source_pattern": re.compile(r"\bblackdog\b", re.IGNORECASE),
        "target_pattern": re.compile(r"\bchó\s*đen\b", re.IGNORECASE),
        "rationale": "Blackdog is a western Latin proper noun / brand name; literal domestication to 'chó đen' destroys brand identity.",
    },
    {
        "rule_id": "titan_group_brand",
        "category": "proper_noun_domestication",
        "source_pattern": re.compile(r"\btitan\s*group\b", re.IGNORECASE),
        "target_pattern": re.compile(r"\btập\s*đoàn\s*khổng\s*lồ\b", re.IGNORECASE),
        "rationale": "Titan Group is a corporate entity name; translating to 'Tập đoàn khổng lồ' erases proper noun status.",
    },
    {
        "rule_id": "dino_mascot",
        "category": "proper_noun_domestication",
        "source_pattern": re.compile(r"\bdino\b", re.IGNORECASE),
        "target_pattern": re.compile(r"\bkhủng\s*long\b", re.IGNORECASE),
        "rationale": "Dino is a character / mascot proper noun; translating to generic 'khủng long' flattens unique identity.",
    },
    {
        "rule_id": "styx_brew_brand",
        "category": "proper_noun_domestication",
        "source_pattern": re.compile(r"\bstyx\s*brew\b", re.IGNORECASE),
        "target_pattern": re.compile(r"\bbia\s*sông\s*styx\b|\bnước\s*sông\s*styx\b", re.IGNORECASE),
        "rationale": "Styx Brew is a fictional beverage brand; domesticating to literal river water destroys world-building.",
    },
    {
        "rule_id": "silver_bullet_brand",
        "category": "proper_noun_domestication",
        "source_pattern": re.compile(r"\bsilver\s*bullet\b", re.IGNORECASE),
        "target_pattern": re.compile(r"\bviên\s*đạn\s*bạc\b|\bđạn\s*bạc\b", re.IGNORECASE),
        "rationale": "Silver Bullet used as a tavern / brand name must remain Latin or retain brand casing.",
    },
    {
        "rule_id": "night_city_proper_noun",
        "category": "proper_noun_domestication",
        "source_pattern": re.compile(r"\bnight\s*city\b", re.IGNORECASE),
        "target_pattern": re.compile(r"\bthành\s*phố\s*đêm\b", re.IGNORECASE),
        "rationale": "Night City is a canonical proper noun setting; translating to 'thành phố đêm' destroys setting name.",
    },

    # --- Category 3: Japanese Romaji Names (Anti-Sinification / Anti-Literal) ---
    {
        "rule_id": "romaji_suzume",
        "category": "romaji_domestication",
        "source_pattern": re.compile(r"\bsuzume\b", re.IGNORECASE),
        "target_pattern": re.compile(r"\bchim\s*sẻ\b", re.IGNORECASE),
        "rationale": "Suzume as a character name must remain Suzume; literal translation to 'chim sẻ' violates creator naming.",
    },
    {
        "rule_id": "romaji_yukari",
        "category": "romaji_domestication",
        "source_pattern": re.compile(r"\byukari\b", re.IGNORECASE),
        "target_pattern": re.compile(r"\bduyên\s*phận\b", re.IGNORECASE),
        "rationale": "Yukari is a character name; translating literally to 'duyên phận' erases personal identity.",
    },
    {
        "rule_id": "romaji_kazuha",
        "category": "romaji_domestication",
        "source_pattern": re.compile(r"\bkazuha\b", re.IGNORECASE),
        "target_pattern": re.compile(r"\bnhất\s*diệp\b", re.IGNORECASE),
        "rationale": "Kazuha as a character name should preserve Romaji rather than forced Sino-Vietnamese (Hán-Việt) reading.",
    },
    {
        "rule_id": "romaji_shinji",
        "category": "romaji_domestication",
        "source_pattern": re.compile(r"\bshinji\b", re.IGNORECASE),
        "target_pattern": re.compile(r"\bchân\s*nhị\b", re.IGNORECASE),
        "rationale": "Shinji must remain Romaji Shinji; forced Sino-Vietnamese 'Chân Nhị' is domestic pedantry.",
    },
    {
        "rule_id": "romaji_hotaru",
        "category": "romaji_domestication",
        "source_pattern": re.compile(r"\bhotaru\b", re.IGNORECASE),
        "target_pattern": re.compile(r"\bđom\s*đóm\b", re.IGNORECASE),
        "rationale": "Hotaru as a character name must remain Hotaru, not translated to insect name 'đom đóm'.",
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

        src_norm = unicodedata.normalize("NFC", src)
        tgt_norm = unicodedata.normalize("NFC", tgt)

        for rule in active_rules:
            s_pat: re.Pattern = rule["source_pattern"]
            t_pat: re.Pattern = rule["target_pattern"]

            s_match = s_pat.search(src_norm)
            t_match = t_pat.search(tgt_norm)

            if s_match and t_match:
                violations.append({
                    "rule_id": rule["rule_id"],
                    "category": rule["category"],
                    "domain": domain,
                    "key": k,
                    "source": src_norm,
                    "target": tgt_norm,
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
