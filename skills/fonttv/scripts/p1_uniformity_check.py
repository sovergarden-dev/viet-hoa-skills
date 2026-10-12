#!/usr/bin/env python3
"""Cap height, x-height and baseline uniformity of a built .font.

"Letters at uneven heights" is the defect users actually see, and it is not the
same question as baseline drift alone: a font can sit every glyph on one
baseline yet still have capitals of different ink heights. This measures all
three from the atlas, per font, and compares against the pristine original.

    p1_uniformity_check.py --font BUILT.font [--original PRISTINE.font] [--json OUT]

Reports, for a fixed set of letters with flat tops/bottoms (no round overshoot):
  cap_spread    max-min ink height of uppercase letters
  x_spread      the same for lowercase
  baseline_dev  position of each letter's ink bottom relative to 'H'
  vs_original   the same numbers for the pristine font, so a regression is visible

Exit: 0 within tolerance, 1 outside, 2 input error.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from p1_core import ink_box  # noqa: E402
from p1_telltale_build import TelltaleFont  # noqa: E402

CAPS = "ABDEFHIKLMNPRTUVXZ"
# Flat-topped/flat-bottomed lowercase only. Round letters (a c e o s) overshoot
# the x-height and the baseline by design: including them produced a spread of
# 14-16 px on a font whose capitals agreed within 1 px, which is the instrument
# measuring its own mistake.
LOWER = "mnru"
TOLERANCE = 2


def measure(font: TelltaleFont, char_to_id: dict) -> dict:
    caps, lower, base = {}, {}, {}
    ref = ink_box(font.crop(char_to_id["H"]))
    if ref is None:
        raise ValueError("H has no ink; not a usable font")
    for ch in CAPS + LOWER:
        cid = char_to_id.get(ch)
        box = ink_box(font.crop(cid)) if cid is not None else None
        if box is None:
            continue
        height = box[3] - box[1]
        (caps if ch in CAPS else lower)[ch] = height
        base[ch] = box[3] - ref[3]
    spread = lambda d: (max(d.values()) - min(d.values())) if d else None
    return {"cap_spread": spread(caps), "x_spread": spread(lower),
            "caps": caps, "lower": lower,
            "baseline_min": min(base.values()), "baseline_max": max(base.values()),
            "baseline": base}


def load_map(mapping: Path) -> dict:
    data = json.loads(mapping.read_text(encoding="utf-8"))
    table = {e["char"]: int(e["id"]) for e in data.get("entries") or []}
    for cid in range(0x20, 0x7F):
        table.setdefault(chr(cid), cid)
    return table


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--font", type=Path, required=True)
    ap.add_argument("--original", type=Path)
    ap.add_argument("--mapping", type=Path, required=True)
    ap.add_argument("--json", type=Path)
    args = ap.parse_args(argv)
    try:
        char_to_id = load_map(args.mapping)
        built = measure(TelltaleFont(args.font), char_to_id)
        pristine = measure(TelltaleFont(args.original), char_to_id) if args.original else None
    except (OSError, ValueError, KeyError) as exc:
        print(f"input error: {exc}", file=sys.stderr)
        return 2
    worst = max(v for v in (built["cap_spread"], built["x_spread"]) if v is not None)
    print(f"{args.font.name:34} cap_spread={built['cap_spread']} x_spread={built['x_spread']} "
          f"baseline=[{built['baseline_min']},{built['baseline_max']}]")
    if pristine:
        print(f"{'  (pristine)':34} cap_spread={pristine['cap_spread']} x_spread={pristine['x_spread']} "
              f"baseline=[{pristine['baseline_min']},{pristine['baseline_max']}]")
        # Calibrate on the publisher's own font: a spread the original already has
        # is the design, not a regression.
        allowance = max([TOLERANCE] + [v for v in (pristine["cap_spread"], pristine["x_spread"]) if v is not None])
    else:
        allowance = TOLERANCE
    status = "PASS" if worst <= allowance else "FAIL"
    report = {"schema": "fonttv/p1-uniformity/v1", "font": str(args.font),
              "original": str(args.original) if args.original else None,
              "tolerance": TOLERANCE, "allowance": allowance, "built": built, "pristine": pristine,
              "status": status}
    if args.json:
        args.json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  worst spread {worst} vs allowance {allowance} (pristine + tolerance)")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
