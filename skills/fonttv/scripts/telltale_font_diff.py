#!/usr/bin/env python3
"""Per-record diff between two Telltale ``.font`` files.

Written because the same ad-hoc comparison was needed on every build round: what
changed between the pristine font and the built one, record by record, on page,
pixel-space UV, ink box and advance. Pixel-space UV matters: comparing raw UV
floats across a page whose height changed reports everything as different.

    telltale_font_diff.py --before PRISTINE.font --after BUILT.font [--json OUT] [--context 10]

Exit: 0 ran, 2 input error.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from p1_core import ink_box, uv_box  # noqa: E402
from p1_telltale_build import TelltaleFont  # noqa: E402

FIELDS = ("page", "x_advance", "cell_w", "cell_h", "x_offset", "y_offset")


def rows(font: TelltaleFont) -> dict:
    out = {}
    for cid, rec in font.records.items():
        page = int(rec[1])
        desc = font.descs[page] if page < len(font.descs) else None
        box = None
        if desc is not None:
            box = uv_box(rec[3], rec[4], rec[5], rec[6], desc["width"], desc["height"])
        ink = ink_box(font.crop(cid))
        out[cid] = {
            "page": page, "x_advance": round(float(rec[11]), 2),
            "cell_w": round(float(rec[7]), 1), "cell_h": round(float(rec[8]), 1),
            "x_offset": round(float(rec[9]), 1), "y_offset": round(float(rec[10]), 1),
            "uv_px": box, "ink": ink,
            "ink_px": 0 if ink is None else (ink[2] - ink[0]) * (ink[3] - ink[1]),
        }
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--before", type=Path, required=True)
    ap.add_argument("--after", type=Path, required=True)
    ap.add_argument("--context", type=int, default=10)
    ap.add_argument("--json", type=Path)
    args = ap.parse_args(argv)
    try:
        b, a = rows(TelltaleFont(args.before)), rows(TelltaleFont(args.after))
    except (OSError, ValueError) as exc:
        print(f"input error: {exc}", file=sys.stderr)
        return 2
    added = sorted(set(a) - set(b))
    removed = sorted(set(b) - set(a))
    changed = {}
    for cid in sorted(set(a) & set(b)):
        fields = [f for f in FIELDS if b[cid][f] != a[cid][f]]
        if b[cid]["ink_px"] != a[cid]["ink_px"]:
            fields.append("ink_px")
        if fields:
            changed[cid] = fields
    print(f"{args.before.name} -> {args.after.name}")
    print(f"  records {len(b)} -> {len(a)}   added {len(added)}  removed {len(removed)}  changed {len(changed)}")
    if added:
        print(f"  added ids: {added[:args.context]}{' ...' if len(added) > args.context else ''}")
    if removed:
        print(f"  removed ids: {removed[:args.context]}{' ...' if len(removed) > args.context else ''}")
    tally: dict[tuple, int] = {}
    for fields in changed.values():
        tally[tuple(fields)] = tally.get(tuple(fields), 0) + 1
    for fields, count in sorted(tally.items(), key=lambda kv: -kv[1]):
        print(f"  {count:4d} records differ in {', '.join(fields)}")
    report = {"schema": "fonttv/telltale-font-diff/v1",
              "before": str(args.before), "after": str(args.after),
              "counts": {"records_before": len(b), "records_after": len(a),
                         "added": len(added), "removed": len(removed), "changed": len(changed)},
              "added": added, "removed": removed, "changed": {str(k): v for k, v in changed.items()}}
    if args.json:
        args.json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
