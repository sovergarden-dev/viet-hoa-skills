#!/usr/bin/env python3
"""Find which extracted game members reference which ``.font`` files.

Font↔consumer binding is normally claimed from documentation, and that has been
wrong: an image of the Settings menu was attributed to a slab font because a
reference file said so, while the lettering in the screenshot was a thin sans.
This scan gives byte evidence instead of a claim.

    p1_consumer_scan.py --root EXTRACTED_DIR [--root ...] [--font NAME ...] [--json OUT]

A hit means the member mentions the font name. It does **not** prove that the
member's screen is the one that draws it: a style table can be shared between
screens. Report it as evidence of reference, keep runtime screenshots for the
gate.

Exit: 0 ran (hits or not), 2 input error.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

SKIP_SUFFIXES = {".ttarch2", ".dds", ".png", ".jpg", ".bmp", ".wav", ".fsb", ".ogg", ".mp3", ".zip"}
NAME_RE = re.compile(rb"([A-Za-z0-9_\-]{2,64}\.font)")
CONTEXT = 60


def discover(root: Path) -> set[str]:
    """Collect every ``*.font`` name mentioned anywhere under root."""
    names = set()
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix.lower() in SKIP_SUFFIXES:
            continue
        try:
            data = path.read_bytes()
        except OSError:
            continue
        names |= {m.group(1).decode("latin1") for m in NAME_RE.finditer(data)}
    return names


def scan(root: Path, wanted: list[str]) -> list[dict]:
    hits = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix.lower() in SKIP_SUFFIXES:
            continue
        try:
            data = path.read_bytes()
        except OSError:
            continue
        if b".font" not in data:
            continue
        for name in wanted:
            needle = name.encode()
            for match in re.finditer(re.escape(needle), data):
                start = max(0, match.start() - CONTEXT)
                window = data[start:match.end() + CONTEXT]
                clean = re.sub(rb"[^ -~]", b".", window).decode("latin1")
                hits.append({"font": name, "member": path.relative_to(root).as_posix(),
                             "offset": match.start(), "context": clean})
    return hits


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", type=Path, action="append", required=True)
    ap.add_argument("--font", action="append", default=[])
    ap.add_argument("--json", type=Path)
    args = ap.parse_args(argv)
    roots = [r for r in args.root if r.is_dir()]
    if not roots:
        print("input error: no readable --root", file=sys.stderr)
        return 2
    scanned = 0
    if args.font:
        wanted = args.font
    else:
        # Deriving names from .font files that exist in the tree does not work:
        # a game tree references fonts it does not contain, so nothing is found
        # and the tool exits 2 on a perfectly valid question.
        wanted = sorted({n for root in roots for n in discover(root)})
    if not wanted:
        print("input error: no .font name found to look for (pass --font)", file=sys.stderr)
        return 2
    all_hits = {name: [] for name in wanted}
    for root in roots:
        scanned += sum(1 for _ in root.rglob("*"))
        for hit in scan(root, wanted):
            all_hits[hit["font"]].append(hit)
    for name, hits in all_hits.items():
        members = sorted({h["member"] for h in hits})
        print(f"{name:34} {len(hits):3d} mentions in {len(members)} member(s)")
        for member in members[:6]:
            example = next(h for h in hits if h["member"] == member)
            print(f"     {member}")
            print(f"        ...{example['context'].strip()}...")
    report = {"schema": "fonttv/consumer-scan/v1", "roots": [str(r) for r in roots],
              "files_walked": scanned, "fonts": all_hits,
              "note": "a mention is evidence of reference, not proof of which screen renders it"}
    if args.json:
        args.json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nfonts with hits: {sum(1 for v in all_hits.values() if v)}/{len(wanted)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
