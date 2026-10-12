#!/usr/bin/env python3
"""Build a coverage page: one line that exercises the whole Vietnamese repertoire.

Renders nothing. It measures the font's own advances (through the encoding
mapping) and splits the repertoire into lines that fit an optional pixel width,
so the same text can be dropped into an engine's localisation table and one
screenshot per font covers every glyph the game can draw.

    coverage_page.py --font FONT --mapping MAP [--max-width px] [--output JSON]

``--max-width`` is the usable text width in game pixels. Omit it for one line
per group (baseline check), which is what a test screen wants: each line starts
with ``Hx`` so a baseline drift is visible without measuring anything.

Exit: 0 emitted, 2 input error.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from p1_width_audit import load_mapping, read_advances, width  # noqa: E402

GROUPS = ["aàáảãạăằắẳẵặâầấẩẫậ", "eèéẻẽẹêềếểễệ", "iìíỉĩị", "oòóỏõọôồốổỗộơờớởỡợ",
          "uùúủũụưừứửữự", "yỳýỷỹỵ", "đ",
          "AÀÁẢÃẠĂẰẮẲẴẶÂẦẤẨẪẬ", "EÈÉẺẼẸÊỀẾỂỄỆ", "IÌÍỈĨỊ", "OÒÓỎÕỌÔỒỐỔỖỘƠỜỚỞỠỢ",
          "UÙÚỦŨỤƯỪỨỬỮỰ", "YỲÝỶỸỴ", "Đ"]
WORDS = ["CHƠI", "DỮ LIỆU", "ĐẤT", "BẬT", "PHỤ", "chuột", "người", "ƯT", "thuế"]


def emit(char_to_id: dict, advances: dict, max_width: float | None) -> list[str]:
    lines = []
    for group in GROUPS:
        line = "Hx " + " ".join(group)
        if max_width:
            line = "Hx " + " ".join(group) if width(line, char_to_id, advances)[0] <= max_width else "Hx " + group
        lines.append(line)
    lines.append("Hx " + " ".join(WORDS))
    return lines


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--font", type=Path, required=True)
    ap.add_argument("--mapping", type=Path, required=True)
    ap.add_argument("--max-width", type=float, default=None)
    ap.add_argument("--output", type=Path)
    args = ap.parse_args(argv)
    try:
        advances = read_advances(args.font)
        char_to_id = load_mapping(args.mapping)
    except (OSError, ValueError) as exc:
        print(f"input error: {exc}", file=sys.stderr)
        return 2
    lines = emit(char_to_id, advances, args.max_width)
    missing = sorted({c for line in lines for c in line
                      if not (c.isspace() or (char_to_id.get(c) in advances))})
    for line in lines:
        print(f"{width(line, char_to_id, advances)[0]:7.1f}  {line}")
    if args.output:
        args.output.write_text(json.dumps(
            {"schema": "fonttv/coverage-page/v1", "font": str(args.font),
             "max_width": args.max_width, "lines": lines, "missing_glyphs": missing},
            ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nlines {len(lines)}  unresolved glyphs {len(missing)} {''.join(missing)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
