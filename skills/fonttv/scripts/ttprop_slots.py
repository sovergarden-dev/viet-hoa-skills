#!/usr/bin/env python3
"""Read and patch Telltale property files whose strings sit in fixed-length slots.

Not every user-visible string lives in a LANDb. In TWAU the choice-statistics
screen, the community popups and the rating prompt are drawn from ``.prop`` files,
and the text inside them is stored as length-prefixed slots:

    [8-byte key][uint32 length][length bytes]        key = language or property id

The same file also carries nested size fields (T3Meta nodes, 5VSM blocks) that
describe the byte range of every section. Changing a slot's length means rewriting
those fields; a missed one corrupts the file. So the supported edit is
**length-preserving**: the new text is encoded with the project's vn128 single-byte
charset and padded to the exact byte length of the text it replaces. Every size
field then stays valid and the file stays byte-length identical.

    ttprop_slots.py --list FILE [--lang-key HEX] [--min 2]
    ttprop_slots.py --verify ORIGINAL PATCHED
    ttprop_slots.py --apply FILE PLAN.json [--out PATCHED]

PLAN.json is ``[{"len_off": <offset of the length field>, "old": "<english>",
"new": "<vietnamese>"}]``; ``--verify`` re-checks the invariants after an edit.

Exit: 0 clean, 1 a check failed, 2 input error.
"""
from __future__ import annotations

import argparse
import json
import re
import struct
import sys
from pathlib import Path

MIN_LEN, MAX_LEN = 2, 900
PRINTABLE = set(range(32, 127)) | {9, 10, 13}


TEXTY = re.compile(rb"^[A-Za-z0-9][A-Za-z0-9 _.'%:!?,\(\)&/+-]{1,}$")


def looks_like_text(chunk: bytes) -> bool:
    """A slot payload is text, not binary.

    Two rules earn their place here, both from real misses:

    * requiring a space hid every short label ('EPISODE' was not a slot before the
      patch but was afterwards, because padding adds spaces), so a space is only
      one of two ways to qualify;
    * a bare printable-ratio let a whole T3Meta *node* count as one slot, which
      made the scanner skip the real slots inside it and leave their English text
      in place. Real text has no NULs, so that is now fatal.
    """
    if not chunk or len(chunk) > MAX_LEN:
        return False
    if any(b == 0 or b < 9 or 13 < b < 32 for b in chunk):
        return False
    rank = sum(1 for b in chunk if b in PRINTABLE or b >= 128) / len(chunk)
    if rank < 0.9:
        return False
    return b" " in chunk or bool(TEXTY.match(chunk))


def slots(data: bytes, min_len: int = MIN_LEN) -> list[dict]:
    """Every length-prefixed text slot, with the offset of its length field.

    Bytes >= 128 count as text: that is where the vn128 charset lives, and a
    scanner that only accepts ASCII stops seeing slots as soon as a file has been
    translated.
    """
    out, i, n = [], 0, len(data)
    while i < n - 12:
        length = struct.unpack_from("<I", data, i + 8)[0]
        if min_len <= length <= MAX_LEN and i + 12 + length <= n:
            chunk = data[i + 12:i + 12 + length]
            if looks_like_text(chunk):
                out.append({"key": data[i:i + 8].hex(), "len_off": i + 8,
                            "len": length, "raw": chunk})
                i += 12 + length
                continue
        i += 1
    return out


def decode(raw: bytes, charset: Path | None) -> str:
    if charset is not None:
        sys.path.insert(0, str(charset))
        from vn_charset import decode_vn  # noqa: PLC0415
        return decode_vn(raw)
    return raw.decode("latin-1")


def encode(text: str, charset: Path | None) -> bytes:
    if charset is not None:
        sys.path.insert(0, str(charset))
        from vn_charset import encode_vn  # noqa: PLC0415
        return encode_vn(text)
    return text.encode("latin-1")


def apply_plan(data: bytes, plan: list[dict], charset: Path | None) -> bytes:
    out = bytearray(data)
    for row in sorted(plan, key=lambda r: -int(r["len_off"])):
        off = int(row["len_off"]) + 4
        old, new = row["old"].encode("latin-1"), encode(row["new"], charset)
        if len(old) != len(new):
            raise ValueError(f"not length-preserving: {row['old']!r} -> {row['new']!r} "
                             f"({len(new)} vs {len(old)} bytes)")
        if bytes(out[off:off + len(old)]) != old:
            raise ValueError(f"slot at {off} does not hold {row['old']!r}")
        out[off:off + len(old)] = new
    return bytes(out)


def verify(original: bytes, patched: bytes, charset: Path | None,
           plan: list[dict] | None = None) -> list[str]:
    """Invariants that make a length-preserving edit safe to ship.

    A size/slot comparison alone passed a file with a corrupted byte outside every
    slot, so the check that matters is added: every byte that differs must sit
    inside a slot payload. Nothing else in the file is allowed to move.
    """
    problems = []
    if len(original) != len(patched):
        problems.append(f"file size changed: {len(original)} -> {len(patched)}")
    before, after = slots(original), slots(patched)
    if len(before) != len(after):
        problems.append(f"slot count changed: {len(before)} -> {len(after)}")
    if [s["len_off"] for s in before] != [s["len_off"] for s in after]:
        problems.append("slot offsets moved; the edit was not in place")
    if [s["len"] for s in before] != [s["len"] for s in after]:
        problems.append("a slot length changed")
    payload = set()
    for s in after:
        payload.update(range(s["len_off"] + 4, s["len_off"] + 4 + s["len"]))
    outside = [i for i in range(len(patched)) if patched[i] != original[i] and i not in payload]
    if outside:
        problems.append(f"{len(outside)} byte(s) changed outside any slot, first at {outside[0]:#x}")
    if plan:
        by_offset = {int(r["len_off"]): r for r in plan}
        for s in after:
            row = by_offset.get(s["len_off"])
            if row is None:
                continue
            want = encode(row["new"], charset)
            if bytes(s["raw"]) != want:
                problems.append(f"slot at {s['len_off']:#x} does not hold the planned text")
    # the doubled-percent rule is text level, so it runs with or without a charset:
    # every substitution template must keep exactly one % next to the number
    for a in after:
        try:
            text = decode(a["raw"], charset)
        except Exception as exc:                      # noqa: BLE001
            problems.append(f"slot at {a['len_off']} no longer decodes: {exc}")
            continue
        if "%%" in text:
            problems.append(f"slot at {a['len_off']} contains a doubled percent: {text!r}")
    return problems


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("file", type=Path, nargs="?")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--verify", nargs=2, metavar=("ORIGINAL", "PATCHED"), type=Path)
    ap.add_argument("--plan", type=Path, help="with --verify: also require the planned text per slot")
    ap.add_argument("--apply", type=Path, metavar="PLAN.json")
    ap.add_argument("--lang-key")
    ap.add_argument("--charset", type=Path, help="directory holding vn_charset.py")
    ap.add_argument("--min", type=int, default=MIN_LEN)
    ap.add_argument("--out", type=Path)
    args = ap.parse_args(argv)
    if args.verify:
        original, patched = (p.read_bytes() for p in args.verify)
        plan = json.loads(args.plan.read_text(encoding="utf-8")) if args.plan else None
        problems = verify(original, patched, args.charset, plan)
        for line in problems:
            print(f"  FAIL {line}")
        print(f"verify: {'PASS' if not problems else 'FAIL'} "
              f"({len(slots(original))} slots, {len(original)} bytes)")
        return 0 if not problems else 1
    if not args.file or not args.file.is_file():
        print("input error: give a file", file=sys.stderr)
        return 2
    data = args.file.read_bytes()
    if args.apply:
        plan = json.loads(args.apply.read_text(encoding="utf-8"))
        try:
            out = apply_plan(data, plan, args.charset)
        except ValueError as exc:
            print(f"refused: {exc}", file=sys.stderr)
            return 1
        dest = args.out or args.file.with_suffix(args.file.suffix + ".patched")
        dest.write_bytes(out)
        problems = verify(data, out, args.charset)
        print(f"wrote {dest} ({len(plan)} replacements, {len(out)} bytes)")
        for line in problems:
            print(f"  FAIL {line}")
        return 0 if not problems else 1
    found = slots(data, args.min)
    if args.lang_key:
        found = [s for s in found if s["key"] == args.lang_key]
    for s in found:
        print(f"  @{s['len_off']:#08x} key={s['key']} len={s['len']:>4} {decode(s['raw'], args.charset)!r}")
    print(f"{len(found)} slot(s) in {args.file.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
