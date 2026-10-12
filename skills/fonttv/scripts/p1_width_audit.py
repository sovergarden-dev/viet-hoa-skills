#!/usr/bin/env python3
"""Strategy P1 width audit: which translated strings are wider than the source?

A replacement font is not the original one, so a string that fitted its box in
the source language can overflow in the translation. This measures the advance
sum of the source and target strings through the font's own record table and
reports every pair above ``--limit``. Reader is read-only.

    p1_width_audit.py --font FONT --mapping MAP --pairs PAIRS.json [--limit 1.05]

PAIRS.json: ``[{"id": "...", "source": "...", "target": "..."}]`` where target
uses the same characters the game text uses (precomposed, after normalisation).

Exit: 0 nothing over the limit, 1 at least one pair over, 2 input error.
"""
from __future__ import annotations

import argparse
import json
import sys
import struct
from pathlib import Path

SKILL = Path(__file__).resolve().parent
sys.path.insert(0, str(SKILL))


def read_advances(font: Path) -> dict:
    """charID -> x_advance for every record of a Telltale .font (read-only)."""
    d = font.read_bytes()
    elems, = struct.unpack_from("<I", d, 16)
    pos = 20 + elems * 12
    n, = struct.unpack_from("<I", d, pos); pos += 4
    nxt, = struct.unpack_from("<I", d, pos)
    if n - nxt == 8:
        n = nxt; pos += 4
    pos += n + 1 + 4
    v, = struct.unpack_from("<f", d, pos)
    if v in (0.5, 1.0): pos += 4
    v, = struct.unpack_from("<f", d, pos)
    if v == 1.0: pos += 4
    _b, cnt = struct.unpack_from("<ii", d, pos); pos += 8
    out = {}
    for i in range(cnt):
        rec = struct.unpack_from("<III4f5f", d, pos + i * 48)
        out[rec[0]] = float(rec[11])
    return out


def load_mapping(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema") != "fonttv/encoding-map/v1":
        raise ValueError(f"{path}: schema must be fonttv/encoding-map/v1")
    table = {int(e["id"]): e["char"] for e in data.get("entries") or []}
    for cid in range(0x21, 0x7F):
        table.setdefault(cid, chr(cid))
    return {c: i for i, c in table.items()}


def width(text: str, char_to_id: dict, advances: dict) -> tuple[float, list[str]]:
    total, missing = 0.0, []
    for ch in text:
        cid = char_to_id.get(ch, ord(ch) if ord(ch) < 128 else None)
        if cid is None or cid not in advances:
            missing.append(ch)
            continue
        total += advances[cid]
    return total, missing


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--font", type=Path, required=True)
    ap.add_argument("--source-font", type=Path,
                    help="font the source text was rendered with (defaults to --font)")
    ap.add_argument("--mapping", type=Path, required=True)
    ap.add_argument("--pairs", type=Path, required=True)
    ap.add_argument("--limit", type=float, default=1.05)
    ap.add_argument("--output", type=Path)
    ap.add_argument("--top", type=int, default=25)
    args = ap.parse_args(argv)
    try:
        advances = read_advances(args.font)
        src_advances = read_advances(args.source_font) if args.source_font else advances
        char_to_id = load_mapping(args.mapping)
        pairs = json.loads(args.pairs.read_text(encoding="utf-8"))
    except (OSError, ValueError, KeyError) as exc:
        print(f"input error: {exc}", file=sys.stderr)
        return 2
    rows, missing_total = [], 0
    for item in pairs:
        src, tgt = item.get("source") or "", item.get("target") or ""
        if not src or not tgt:
            continue
        w_src, m_src = width(src, char_to_id, src_advances)
        w_tgt, m_tgt = width(tgt, char_to_id, advances)
        missing_total += len(m_src) + len(m_tgt)
        if w_src <= 0:
            continue
        rows.append({"id": item.get("id"), "ratio": round(w_tgt / w_src, 3),
                     "source": src, "target": tgt, "source_px": round(w_src, 1), "target_px": round(w_tgt, 1),
                     "missing": "".join(sorted(set(m_src + m_tgt)))})
    rows.sort(key=lambda r: -r["ratio"])
    over = [r for r in rows if r["ratio"] > args.limit]
    for r in rows[:args.top]:
        flag = "OVER" if r["ratio"] > args.limit else "    "
        print(f"{flag} {r['ratio']:.3f} {r['source_px']:7.1f}->{r['target_px']:7.1f}  {r['target'][:64]}")
    report = {"schema": "fonttv/p1-width-audit/v1", "font": str(args.font), "pairs": len(rows),
              "limit": args.limit, "over_limit": len(over), "missing_glyphs": missing_total, "rows": rows}
    if args.output:
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\npairs {len(rows)}  over {args.limit}: {len(over)}  chars without a record: {missing_total}")
    return 1 if over else 0


if __name__ == "__main__":
    raise SystemExit(main())
