#!/usr/bin/env python3
"""Texture cost of a replacement: what the patch does to page sizes and bytes.

Replacing every glyph grows the atlas, and the growth is invisible in every other
check — the descriptor stays consistent, the audit passes, and the game still
loads. TWAU's Project archive went from 1.32 MB to 17.5 MB and one page reached
1956 px, which is worth seeing before a release rather than after.

    p1_texture_report.py --fonts-dir AFTER_DIR [--original-dir BEFORE_DIR]
                         [--archive-before DIR] [--archive-after DIR] [--json OUT]

Exit: 0 reported, 1 a page exceeds --warn-height, 2 input error.
"""
from __future__ import annotations

import argparse
import json
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from p1_telltale_build import TelltaleFont  # noqa: E402


def font_row(path: Path) -> dict:
    font = TelltaleFont(path)
    pages = [{"index": d["index"], "width": d["width"], "height": d["height"],
              "bytes": d["size20"], "inconsistent": not d["consistent"]} for d in font.descs]
    return {"font": path.name, "bytes": path.stat().st_size, "records": len(font.records),
            "pages": pages, "pixels": sum(p["width"] * p["height"] for p in pages),
            "max_height": max(p["height"] for p in pages)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--fonts-dir", type=Path, required=True)
    ap.add_argument("--original-dir", type=Path)
    ap.add_argument("--archive-before", type=Path)
    ap.add_argument("--archive-after", type=Path)
    ap.add_argument("--warn-height", type=int, default=2048)
    ap.add_argument("--json", type=Path)
    args = ap.parse_args(argv)
    for label, directory in (("fonts", args.fonts_dir), ("original", args.original_dir),
                             ("archive-before", args.archive_before), ("archive-after", args.archive_after)):
        if directory is not None and not directory.is_dir():
            print(f"input error: {label} directory missing: {directory}", file=sys.stderr)
            return 2
    if bool(args.archive_before) != bool(args.archive_after):
        print("input error: archive-before and archive-after must be paired", file=sys.stderr)
        return 2
    fonts = sorted(args.fonts_dir.glob("*.font"))
    if not fonts:
        print(f"input error: no .font in {args.fonts_dir}", file=sys.stderr)
        return 2
    before = {p.name: p for p in (args.original_dir.glob("*.font") if args.original_dir else [])}
    rows, over = [], False
    for path in fonts:
        try:
            row = font_row(path)
        except (ValueError, OSError, IndexError, KeyError, struct.error) as exc:
            print(f"input error: {path.name}: {exc}", file=sys.stderr)
            return 2
        orig = before.get(path.name)
        if orig is not None:
            try:
                old = font_row(orig)
            except (ValueError, OSError, IndexError, KeyError, struct.error) as exc:
                print(f"input error: original {orig.name}: {exc}", file=sys.stderr)
                return 2
            if old:
                row["original_bytes"] = old["bytes"]
                row["byte_growth"] = round(row["bytes"] / max(1, old["bytes"]), 2)
                row["height_before"] = [p["height"] for p in old["pages"]]
        over = over or row["max_height"] > args.warn_height
        rows.append(row)
        flag = "WARN" if row["max_height"] > args.warn_height else "    "
        growth = f"{row.get('byte_growth', 0):.2f}x" if "byte_growth" in row else "   -"
        print(f"{flag} {row['font']:34} bytes={row['bytes']:>10,} {growth:>7} "
              f"pages={[p['height'] for p in row['pages']]} max={row['max_height']}")
    archives = {}
    if args.archive_before and args.archive_after:
        for after in sorted(args.archive_after.glob("*.ttarch2")):
            b = args.archive_before / after.name
            archives[after.name] = {"before": b.stat().st_size if b.is_file() else None,
                                    "after": after.stat().st_size}
            if b.is_file():
                archives[after.name]["growth"] = round(after.stat().st_size / b.stat().st_size, 2)
        print()
        for name, row in archives.items():
            print(f"      {name:70} {row.get('before')} -> {row['after']} ({row.get('growth')}x)")
    report = {"schema": "fonttv/texture-report/v1", "fonts": rows, "archives": archives,
              "warn_height": args.warn_height,
              "total_bytes": sum(r["bytes"] for r in rows),
              "total_pixels": sum(r["pixels"] for r in rows)}
    if args.json:
        args.json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nfonts {len(rows)} total_bytes {report['total_bytes']:,} total_pixels {report['total_pixels']:,}")
    if over:
        print(f"WARNING: at least one page exceeds {args.warn_height} px")
    return 1 if over else 0


if __name__ == "__main__":
    raise SystemExit(main())
