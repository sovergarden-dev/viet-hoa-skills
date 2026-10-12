#!/usr/bin/env python3
"""Register a screenshot as runtime evidence for one named font.

Gate 12 wants pixels from a real session, but pixels alone cannot say *which*
font drew them: two earlier attempts measured this and failed (see
``references/screenshot-attribution-attempts.md``). So attribution comes from the
one thing that does identify a font — its consumer: a member name in a script, or
a design no other font in the build shares. This tool refuses to record a
screenshot for a font until that citation is written down.

It does not decide anything about the image's content. It checks that the file is
a real image of usable size, copies it into the evidence directory, hashes it, and
appends the entry the manifest tool reads.

    p1_attach_screenshot.py --image SHOT.png --font ITC_Kabel_Book.font \
        --cite "uiz_ConsoleButtons.lua names ITC_Kabel_Book.font" \
        --reviewer Rurus --shots shots.json --evidence-dir DIR [--replace]

Exit: 0 recorded, 1 refused (missing/placeholder image, no citation, duplicate),
2 input error.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

from PIL import Image

MIN_WIDTH, MIN_HEIGHT = 200, 100


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical(name: str) -> str:
    """One key per font, whether it is written ``X`` or ``X.font``.

    Without this the duplicate check misses: a manifest with ``Cantoria_MT`` and a
    new attachment for ``Cantoria_MT.font`` looked like two different fonts, so the
    same screenshot got recorded twice against one font.
    """
    return name[:-5].lower() if name.lower().endswith(".font") else name.lower()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--image", type=Path, required=True)
    ap.add_argument("--font", required=True, help="output font name, e.g. ITC_Kabel_Book.font")
    ap.add_argument("--cite", required=True,
                    help="why this screenshot is evidence for THAT font: the consumer reference "
                         "(file that names the font) or the unique design that eliminates others")
    ap.add_argument("--reviewer", required=True)
    ap.add_argument("--shots", type=Path, required=True)
    ap.add_argument("--evidence-dir", type=Path, required=True)
    ap.add_argument("--replace", action="store_true",
                    help="replace an existing entry for this font instead of refusing")
    args = ap.parse_args(argv)

    if not args.cite.strip():
        print("refused: --cite is empty; a screenshot without a citation proves nothing", file=sys.stderr)
        return 1
    if not args.image.is_file():
        print(f"refused: image not found at {args.image}", file=sys.stderr)
        return 1
    try:
        with Image.open(args.image) as image:
            size, fmt = image.size, image.format
    except OSError as exc:
        print(f"refused: not a readable image ({exc})", file=sys.stderr)
        return 1
    if size[0] < MIN_WIDTH or size[1] < MIN_HEIGHT:
        print(f"refused: {size[0]}x{size[1]} is too small to be a session screenshot "
              f"(minimum {MIN_WIDTH}x{MIN_HEIGHT}); a placeholder proves nothing", file=sys.stderr)
        return 1

    shots = {"schema": "fonttv/screenshots/v1", "shots": []}
    if args.shots.is_file():
        try:
            shots = json.loads(args.shots.read_text(encoding="utf-8"))
        except ValueError as exc:
            print(f"input error: {args.shots} is not valid JSON ({exc})", file=sys.stderr)
            return 2
    # Compare case-insensitively but store the caller's spelling: the member name
    # is ITC_Kabel_Book.font, and evidence that renames it is not evidence.
    key = canonical(args.font)
    member = args.font if args.font.lower().endswith(".font") else f"{args.font}.font"
    entries = shots.setdefault("shots", [])
    existing = [e for e in entries if canonical(str(e.get("font") or "")) == key]
    if existing and not args.replace:
        print(f"refused: {member} already has {len(existing)} screenshot(s); pass --replace to "
              f"supersede, or attach to a different font", file=sys.stderr)
        return 1

    digest = sha256(args.image)
    args.evidence_dir.mkdir(parents=True, exist_ok=True)
    archived = args.evidence_dir / f"{member[:-5]}__{digest[:8]}{args.image.suffix}"
    shutil.copy2(args.image, archived)
    entry = {"path": str(archived), "sha256": sha256(archived), "font": member,
             "why": args.cite.strip(), "reviewer": args.reviewer, "format": fmt, "size": list(size)}
    if args.replace:
        entries = [e for e in entries if canonical(str(e.get("font") or "")) != key] + [entry]
    else:
        entries.append(entry)
    shots["shots"] = entries
    args.shots.write_text(json.dumps(shots, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"recorded {args.font} <- {archived.name} ({size[0]}x{size[1]}, {fmt})")
    print(f"  cited: {entry['why']}")
    print(f"  sha256: {entry['sha256']}")
    print(f"  next: regenerate the manifest so the gate can read it")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
