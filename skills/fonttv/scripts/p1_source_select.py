#!/usr/bin/env python3
"""Gate candidate source fonts for strategy P1: coverage, glyph ink, dot shape, license.

Every font given on the command line is checked; nothing is read from a
built-in list. Exit codes: 0 every candidate PASS, 1 at least one FAIL,
2 input error, 4 no license evidence given (PLANNING_ONLY).

    p1_source_select.py FONT [FONT ...] [--license FONT=SPDX:PATH ...] [--output JSON]

Coverage is the 134 Vietnamese letters plus printable ASCII. A glyph that is
mapped but renders no ink counts as missing. The dot-below gate fails when the
dot below does not match the font's own period (|fill - period| > 0.15): a
foreign mark. A square dot that matches a square period (Roboto Slab, Arial)
is the design and only warns. Square dots were a runtime defect in P2 because
Arial's mark was composed onto round-dot game fonts.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from p1_core import dot_shapes, render, sha256, vn_repertoire  # noqa: E402

ASCII = "".join(chr(c) for c in range(0x21, 0x7F))
SQUARE_FILL = 0.95
DOT_MISMATCH = 0.15
OPEN_LICENSES = {"OFL-1.1", "Apache-2.0", "MIT", "UFL-1.0"}
LICENSE_MARKERS = {"OFL-1.1": "SIL Open Font License", "Apache-2.0": "Apache License",
                   "MIT": "Permission is hereby granted", "UFL-1.0": "Ubuntu Font Licence"}


def audit(path: Path, license_spec: tuple[str, Path] | None) -> dict:
    from fontTools.ttLib import TTFont
    from PIL import ImageFont

    row = {"font": str(path), "sha256": sha256(path), "problems": []}
    try:
        cmap = TTFont(str(path), fontNumber=0).getBestCmap() or {}
    except Exception as exc:  # fontTools raises many types on corrupt input
        row["problems"].append(f"unreadable: {type(exc).__name__}")
        row["verdict"] = "FAIL"
        return row
    ft = ImageFont.truetype(str(path), 64)
    vn, missing, no_ink = vn_repertoire(), [], []
    for ch in vn + ASCII:
        if ord(ch) not in cmap:
            missing.append(ch)
        elif render(ft, ch)[0] is None:
            no_ink.append(ch)
    row.update({"repertoire": len(vn), "missing": "".join(missing), "no_ink": "".join(no_ink)})
    if missing:
        row["problems"].append(f"{len(missing)} characters not in cmap")
    if no_ink:
        row["problems"].append(f"{len(no_ink)} characters render no ink")
    shapes = dot_shapes(path) if ord("\u1ecd") in cmap else {"dot_below": None, "period": None}
    fill, period = shapes["dot_below"], shapes["period"]
    row["dot_below_fill"], row["period_fill"] = fill, period
    row["warnings"] = []
    if fill is None:
        row["problems"].append("dot below not measurable")
    elif period is not None and abs(fill - period) > DOT_MISMATCH:
        # A dot below that does not match the font's own period is a foreign
        # mark: the failure the user saw when Arial's square dot was composed
        # onto round-dot fonts.
        row["problems"].append(f"dot below fill {fill} does not match period fill {period}")
    elif fill > SQUARE_FILL:
        # Square but consistent with the design (Roboto Slab, Arial): allowed.
        row["warnings"].append(f"square dot below by design (fill {fill}, period {period})")
    if license_spec is None:
        row["license"] = None
    else:
        spdx, lic_path = license_spec
        text = lic_path.read_text(encoding="utf-8", errors="replace") if lic_path.is_file() else ""
        marker = LICENSE_MARKERS.get(spdx)
        row["license"] = {"spdx": spdx, "file": str(lic_path),
                          "sha256": sha256(lic_path) if lic_path.is_file() else None}
        if spdx not in OPEN_LICENSES:
            row["problems"].append(f"license {spdx} does not allow redistribution in a patch")
        elif not text or (marker and marker not in text):
            row["problems"].append(f"license file does not contain {marker!r}")
    row["verdict"] = "FAIL" if row["problems"] else "PASS"
    return row


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("fonts", nargs="+", type=Path)
    ap.add_argument("--license", action="append", default=[], metavar="FONT=SPDX:PATH")
    ap.add_argument("--output", type=Path)
    args = ap.parse_args(argv)
    licenses = {}
    for item in args.license:
        try:
            font, rest = item.split("=", 1)
            spdx, lic = rest.split(":", 1)
        except ValueError:
            print(f"bad --license {item!r}; expected FONT=SPDX:PATH", file=sys.stderr)
            return 2
        licenses[Path(font).name] = (spdx, Path(lic))
    rows = []
    for font in args.fonts:
        if not font.is_file():
            print(f"missing font {font}", file=sys.stderr)
            return 2
        rows.append(audit(font, licenses.get(font.name)))
    for r in rows:
        print(f"{Path(r['font']).name:34} {r['verdict']:5} fill={r.get('dot_below_fill')} period={r.get('period_fill')} "
              f"missing={len(r.get('missing', ''))} no_ink={len(r.get('no_ink', ''))} "
              f"license={(r['license'] or {}).get('spdx')} {'; '.join(r['problems'])}")
    failed = any(r["verdict"] != "PASS" for r in rows)
    planning = not failed and any(r["license"] is None for r in rows)
    verdict = "FAIL" if failed else ("PLANNING_ONLY" if planning else "PASS")
    report = {"schema": "fonttv/p1-source-select/v1", "verdict": verdict, "fonts": rows}
    if args.output:
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"verdict {verdict}")
    return 1 if failed else (4 if planning else 0)


if __name__ == "__main__":
    raise SystemExit(main())
