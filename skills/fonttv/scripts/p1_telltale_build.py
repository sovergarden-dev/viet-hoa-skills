#!/usr/bin/env python3
"""Strategy P1 builder for Telltale Tool ``.font`` (TWAU PC 5VSM profile).

Replaces every glyph the encoder can emit with a glyph rendered whole from a
source TTF. Nothing is composed.

    p1_telltale_build.py --fonts-dir DIR --out-dir DIR --mapping MAP.json
                         --sources SOURCES.json [--manifest OUT.json]

``MAP.json``      fonttv/encoding-map/v1; ids not listed there are printable
                  ASCII 0x21-0x7E mapped to themselves.
``SOURCES.json``  {"<font stem>": ["source.ttf", "source-bold.ttf"], ...}; the
                  candidate whose stem weight is closest to the game font wins.

Container invariants (references/telltale-fonts.md):
* authored page bytes are emitted verbatim; new glyphs pack below the authored
  rows of the last page on a 4-aligned row; last-page records get V rescaled;
* sum(descriptor sizes) == len(payload), checked after writing;
* record ids stay unique and sorted.

Cell conventions are read from the game font:
* proportional: cell tight to ink, rec[10] = line top to cell top, so
  rec[10] + ink_bottom is one baseline for every glyph;
* fixed-cell (every cell same height, rec[10] == 0): glyph drawn inside the
  cell on the authored baseline row; a taller glyph grows the cell upward
  with negative rec[10].

Exit: 0 every font PASS (identity + baseline), 1 any FAIL, 2 input error.
"""
from __future__ import annotations

import argparse
import json
import struct
import sys
from pathlib import Path

import numpy as np
from PIL import ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
from p1_core import (decode_dxt5_alpha, encode_dxt5_alpha, identity_dxt5, ink_box,  # noqa: E402
                     render, sha256, stem_ratio, uv_box)
from telltale_descriptor import read_descriptors, solve_multipage_heights, write_page_geometry  # noqa: E402

WIDTH_LIMIT = 1.08
MIN_SIZE_FACTOR = 0.88
PAGE_HEIGHT_WARN = 2048
MAX_PAGE_HEIGHT = 4096
LETTERS = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
NO_DESCENT = "ABCDEFHIKLMNPRTUVWXZabcdefhiklmnrtuvwxz"
BASELINE_SPREAD = 2


class TelltaleFont:
    def __init__(self, path: Path):
        self.path = path
        data = bytearray(path.read_bytes())
        # A short or empty file is a bad input, not a crash: struct.error escaping
        # from here makes callers report a traceback instead of naming the file.
        if len(data) < 20:
            raise ValueError(f"{path.name}: truncated .font header ({len(data)} bytes)")
        self.data = data
        self.header_size, _unk, _tex = struct.unpack_from("<III", data, 4)
        self.count_elements, = struct.unpack_from("<I", data, 16)
        poz = 20 + self.count_elements * 12
        name_len, = struct.unpack_from("<I", data, poz)
        poz += 4
        nxt, = struct.unpack_from("<I", data, poz)
        if name_len - nxt == 8:
            name_len = nxt
            poz += 4
        poz += name_len + 1 + 4
        val, = struct.unpack_from("<f", data, poz)
        if val in (0.5, 1.0):
            poz += 4
        val, = struct.unpack_from("<f", data, poz)
        if val == 1.0:
            poz += 4
        self.block_offset = poz
        _bcs, count = struct.unpack_from("<ii", data, poz)
        poz += 8
        self.records = {}
        for i in range(count):
            rec = list(struct.unpack_from("<III4f5f", data, poz + i * 48))
            self.records[rec[0]] = rec
        self.tex_pos = self.header_size + 16 + self.count_elements * 12 + 4
        self.tex_header = bytearray(data[poz + count * 48:self.tex_pos])
        self.page_count, = struct.unpack_from("<I", self.tex_header, 4)
        if self.page_count not in (1, 2):
            raise ValueError(f"{path.name}: unsupported page count {self.page_count}")
        for desc in read_descriptors(self.tex_header, self.page_count):
            if desc["consistent"]:
                continue
            if desc["width"] % 4 or desc["size20"] != desc["size8"] or desc["size20"] % desc["width"]:
                raise ValueError(f"{path.name}: page {desc['index']} cannot be normalised: {desc}")
            fixed_h = desc["size20"] // desc["width"]
            if fixed_h % 4:
                raise ValueError(f"{path.name}: page {desc['index']} height {fixed_h} not block aligned")
            write_page_geometry(self.tex_header, desc, desc["width"], fixed_h)
        self.descs = read_descriptors(self.tex_header, self.page_count)
        self.width = self.descs[0]["width"]
        self.raw_pages, self.pages = [], []
        cursor = self.tex_pos
        for desc in self.descs:
            if not desc["consistent"] or desc["width"] != self.width or desc["height"] % 4:
                raise ValueError(f"{path.name}: inconsistent page {desc}")
            raw = bytes(data[cursor:cursor + desc["size20"]])
            if len(raw) != desc["size20"]:
                raise ValueError(f"{path.name}: page {desc['index']} payload truncated")
            self.raw_pages.append(raw)
            self.pages.append(decode_dxt5_alpha(raw, self.width, desc["height"]))
            cursor += desc["size20"]
        if cursor != len(data):
            raise ValueError(f"{path.name}: {len(data) - cursor} trailing bytes after payload")

    def crop(self, cid: int):
        rec = self.records.get(cid)
        if rec is None or int(rec[1]) >= len(self.pages):
            return None
        desc = self.descs[int(rec[1])]
        x0, y0, x1, y1 = uv_box(rec[3], rec[4], rec[5], rec[6], desc["width"], desc["height"])
        if x1 <= x0 or y1 <= y0:
            return None
        return self.pages[int(rec[1])][y0:y1, x0:x1]


def analyse(font: TelltaleFont) -> dict:
    printable = [r for cid, r in font.records.items() if cid >= 33]
    fixed = len({r[8] for r in printable}) == 1 and all(r[10] == 0 for r in printable)
    h_box = ink_box(font.crop(ord("H")))
    if h_box is None:
        raise ValueError(f"{font.path.name}: 'H' has no ink")
    h_rec = font.records[ord("H")]
    cap = h_box[3] - h_box[1]
    x_box = ink_box(font.crop(ord("x")))
    x_h = None if x_box is None else x_box[3] - x_box[1]
    return {
        "fixed_cell": fixed, "cell_h": int(h_rec[8]), "cap": cap,
        "baseline": int(h_rec[10]) + h_box[3],
        "caps_only": x_h is not None and x_h >= 0.9 * cap,
        "stem": stem_ratio(font.crop(ord("I"))),
        "orig_adv_sum": sum(font.records[ord(c)][11] for c in LETTERS if ord(c) in font.records),
        "f2": int(h_rec[2]),
    }


def choose_source(info: dict, candidates: list[Path]) -> dict:
    best = None
    for path in candidates:
        probe = ImageFont.truetype(str(path), 200)
        hb = probe.getbbox("H", anchor="ls")
        size = 200.0 * info["cap"] / (hb[3] - hb[1])
        alpha, *_ = render(ImageFont.truetype(str(path), size), "I")
        stem = stem_ratio(alpha) if alpha is not None else None
        score = abs((stem or 0) - (info["stem"] or 0))
        if best is None or score < best[0]:
            best = (score, path, size, stem)
    _score, path, size, stem = best

    def adv_sum(sz, sx=1.0):
        ft = ImageFont.truetype(str(path), sz)
        return sum(ft.getlength(c.upper() if info["caps_only"] else c) * sx for c in LETTERS)

    ratio = adv_sum(size) / max(1.0, info["orig_adv_sum"])
    factor, sx = 1.0, 1.0
    if ratio > WIDTH_LIMIT:
        factor = max(MIN_SIZE_FACTOR, WIDTH_LIMIT / ratio)
        if ratio * factor > WIDTH_LIMIT:
            sx = WIDTH_LIMIT / (ratio * factor)
    size *= factor
    return {"path": path, "size": size, "sx": sx, "size_factor": factor, "width_ratio_raw": ratio,
            "width_ratio": adv_sum(size, sx) / max(1.0, info["orig_adv_sum"]), "stem_src": stem}


def build_font(src: Path, out: Path, byte_to_char: dict, candidates: list[Path]) -> dict:
    font = TelltaleFont(src)
    info = analyse(font)
    choice = choose_source(info, candidates)
    ft = ImageFont.truetype(str(choice["path"]), choice["size"])
    sx = choice["sx"]
    last = font.page_count - 1
    tw = font.width
    orig_h = font.descs[last]["height"]

    items, cells = [], {}
    for b in sorted(byte_to_char):
        ch = byte_to_char[b]
        glyph = ch.upper() if info["caps_only"] and ch.islower() else ch
        alpha, left, top, adv = render(ft, glyph, sx)
        if alpha is None:
            # Whitespace has an advance and no ink. It must be in the map so layout
            # and string matching can measure it, but it contributes no glyph.
            if ch.isspace() and b in font.records:
                font.records[b][11] = float(round(adv))
                continue
            raise ValueError(f"{src.stem}: source rendered no ink for {ch!r}")
        gh, gw = alpha.shape
        if info["fixed_cell"]:
            y_in_cell = info["baseline"] + top
            ext_up = max(0, -y_in_cell)
            y_in_cell += ext_up
            cell_h = max(info["cell_h"] + ext_up, y_in_cell + gh)
            shift = max(0, -round(left))
            x_in_cell = round(left) + shift
            cell_w = max(round(adv) + shift, x_in_cell + gw)
            cell = np.zeros((cell_h, cell_w), dtype=np.uint8)
            cell[y_in_cell:y_in_cell + gh, x_in_cell:x_in_cell + gw] = alpha
            f9, f10 = float(-shift), float(-ext_up)
        else:
            cell = alpha
            f9, f10 = float(round(left)), float(info["baseline"] + top)
        rec = [b, last, info["f2"], 0.0, 0.0, 0.0, 0.0,
               float(cell.shape[1]), float(cell.shape[0]), f9, f10, float(round(adv))]
        items.append((b, cell, rec))
        cells[b] = cell

    start_y = ((orig_h + 2 + 3) // 4) * 4
    positions, cur_x, cur_y, row_h = [], 2, start_y, 0
    for _b, cell, _rec in items:
        h, w = cell.shape
        if w + 4 > tw:
            raise ValueError(f"{src.stem}: glyph {w}px wider than page {tw}")
        if cur_x != 2 and cur_x + w + 2 > tw:
            cur_x, cur_y, row_h = 2, cur_y + row_h + 2, 0
        positions.append((cur_x, cur_y))
        cur_x += w + 2
        row_h = max(row_h, h)
    if len(positions) != len(items):
        raise ValueError(f"{src.stem}: packed {len(positions)} of {len(items)} glyphs")
    th = ((cur_y + row_h + 2 + 3) // 4) * 4
    tail = np.zeros((th - orig_h, tw), dtype=np.uint8)
    records = {cid: list(r) for cid, r in font.records.items()}
    scale = orig_h / th
    for rec in records.values():
        if int(rec[1]) == last:
            rec[5] *= scale
            rec[6] *= scale
    for (b, cell, rec), (x, y) in zip(items, positions):
        h, w = cell.shape
        tail[y - orig_h:y - orig_h + h, x:x + w] = cell
        rec[3], rec[4] = x / tw, (x + w) / tw
        rec[5], rec[6] = y / th, (y + h) / th
        records[b] = rec
    if 32 in records:
        records[32][11] = float(round(ft.getlength(" ") * sx))

    raw_pages = font.raw_pages[:last] + [font.raw_pages[last] + encode_dxt5_alpha(tail)]
    payload = b"".join(raw_pages)
    tex_header = bytearray(font.tex_header)
    write_page_geometry(tex_header, read_descriptors(tex_header, font.page_count)[last], tw, th)
    check = read_descriptors(tex_header, font.page_count)
    if [d["size20"] for d in check] != [len(p) for p in raw_pages]:
        raise ValueError(f"{src.stem}: descriptor sizes do not match payload {check}")
    if font.page_count == 2:
        heights = solve_multipage_heights(tex_header, 2, len(raw_pages[0]), len(payload), tw)
        if heights != [font.descs[0]["height"], th]:
            raise ValueError(f"{src.stem}: solver {heights} disagrees with pages")

    # An atlas that grows past what the engine accepts is a silent failure mode:
    # the descriptor stays consistent and the audit passes. Warn at the largest
    # page observed working (TWAU: 1956 px) and refuse well beyond it.
    if th > MAX_PAGE_HEIGHT:
        raise ValueError(f"{src.stem}: page height {th} exceeds the {MAX_PAGE_HEIGHT} px guard")
    if th > PAGE_HEIGHT_WARN:
        print(f"  WARNING {src.stem}: page height {th} px is above the {PAGE_HEIGHT_WARN} px "
              f"working maximum; texture memory grows with it")
    ordered = sorted(records.values(), key=lambda r: r[0])
    ids = [r[0] for r in ordered]
    if len(ids) != len(set(ids)):
        raise ValueError(f"{src.stem}: duplicate record ids")
    blob = b"".join(struct.pack("<III4f5f", *r) for r in ordered)
    head = bytes(font.data[:font.block_offset]) + struct.pack("<ii", len(ordered) * 48 + 8, len(ordered)) \
        + blob + bytes(tex_header)
    out_bytes = bytearray(head + payload)
    struct.pack_into("<I", out_bytes, 4, len(head) - (16 + font.count_elements * 12 + 4))
    struct.pack_into("<I", out_bytes, 12, len(payload))
    out.write_bytes(out_bytes)
    return {
        "font": src.name, "input_sha256": sha256(src), "output_sha256": sha256(out), "bytes": len(out_bytes),
        "source": str(choice["path"]), "source_sha256": sha256(choice["path"]),
        "size": round(choice["size"], 3), "size_factor": round(choice["size_factor"], 3),
        "h_scale": round(sx, 3), "width_ratio_raw": round(choice["width_ratio_raw"], 3),
        "width_ratio": round(choice["width_ratio"], 3),
        "mode": "fixed_cell" if info["fixed_cell"] else "proportional",
        "caps_only": info["caps_only"], "cap": info["cap"], "baseline": info["baseline"],
        "glyphs_replaced": len(items), "page_heights": [d["height"] for d in check], "_cells": cells,
    }


def baseline_devs(font: TelltaleFont, baseline: int, char_to_byte) -> list[int]:
    dev = []
    for ch in NO_DESCENT:
        cid = char_to_byte(ch)
        rec, box = font.records.get(cid), ink_box(font.crop(cid))
        if rec is not None and box is not None:
            dev.append(int(rec[10]) + box[3] - baseline)
    return dev


def verify(out: Path, built: dict, byte_to_char: dict) -> dict:
    font = TelltaleFont(out)
    bad, max_err = [], 0
    for b, cell in built["_cells"].items():
        res = identity_dxt5(font.crop(b), cell)
        max_err = max(max_err, res["max_err"] or 0)
        if not res["ok"]:
            bad.append(byte_to_char[b])
    char_to_byte = {c: b for b, c in byte_to_char.items()}
    dev = baseline_devs(font, built["baseline"], lambda c: char_to_byte.get(c, ord(c)))
    return {"identity_bad": bad, "identity_max_alpha_err": max_err,
            "baseline_dev_min": min(dev), "baseline_dev_max": max(dev), "baseline_checked": len(dev)}


def load_byte_map(mapping: Path) -> dict:
    data = json.loads(mapping.read_text(encoding="utf-8"))
    if data.get("schema") != "fonttv/encoding-map/v1":
        raise ValueError(f"{mapping}: schema must be fonttv/encoding-map/v1")
    table = {}
    for entry in data.get("entries") or []:
        cid, ch = int(entry["id"]), entry["char"]
        if cid in table:
            raise ValueError(f"{mapping}: duplicate id {cid}")
        table[cid] = ch
    for cid in range(0x20, 0x7F):
        table.setdefault(cid, chr(cid))
    return table


def load_char_map(mapping: Path) -> dict:
    """char -> charID. The inverse of :func:`load_byte_map`.

    The build walks byte ids, so it wants id -> char; layout and string-matching
    tooling walks text, so it wants the other direction. Using the build's map in
    a text walker makes every lookup miss: a screenshot matcher then reports
    "no candidate could render the string" for a string that renders fine.
    """
    return {ch: cid for cid, ch in load_byte_map(mapping).items()}


def load_sources(path: Path) -> dict:
    """Accept a bare mapping or {"schema": "fonttv/p1-sources/v1", "fonts": {...}}.

    Fails closed with a readable reason: a plan that silently drops a font makes
    the build look complete while one font keeps its old glyphs.
    """
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and "fonts" in data:
        if data.get("schema") not in (None, "fonttv/p1-sources/v1"):
            raise ValueError(f"{path}: schema must be fonttv/p1-sources/v1")
        data = data["fonts"]
    if not isinstance(data, dict) or not data:
        raise ValueError(f"{path}: expected a non-empty object of font stem -> [source fonts]")
    out = {}
    for stem, value in data.items():
        files = [value] if isinstance(value, str) else value
        if not isinstance(files, list) or not files:
            raise ValueError(f"{path}: '{stem}' must map to a font path or a non-empty list")
        paths = []
        for item in files:
            candidate = Path(item)
            if candidate.suffix.lower() not in (".ttf", ".otf"):
                raise ValueError(f"{path}: '{stem}' -> {item!r} is not a .ttf/.otf")
            if not candidate.is_file():
                raise ValueError(f"{path}: '{stem}' -> {item!r} does not exist")
            paths.append(candidate)
        out[stem] = paths
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--fonts-dir", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--mapping", type=Path, required=True)
    ap.add_argument("--sources", type=Path, required=True)
    ap.add_argument("--manifest", type=Path)
    args = ap.parse_args(argv)
    try:
        byte_to_char = load_byte_map(args.mapping)
        sources = load_sources(args.sources)
    except (OSError, ValueError, KeyError) as exc:
        print(f"input error: {exc}", file=sys.stderr)
        return 2
    fonts = sorted(args.fonts_dir.glob("*.font"))
    missing = sorted(f.stem for f in fonts if f.stem not in sources)
    if not fonts:
        print(f"input error: no .font in {args.fonts_dir}", file=sys.stderr)
        return 2
    if missing:
        print(f"input error: no source font given for {missing}", file=sys.stderr)
        return 2
    args.out_dir.mkdir(parents=True, exist_ok=True)
    report, ok = [], True
    for src in fonts:
        out = args.out_dir / src.name
        built = build_font(src, out, byte_to_char, sources[src.stem])
        check = verify(out, built, byte_to_char)
        orig = baseline_devs(TelltaleFont(src), built["baseline"], ord)
        built.pop("_cells")
        built.update(check)
        built["orig_baseline_dev"] = [min(orig), max(orig)]
        allowed = max(BASELINE_SPREAD, built["orig_baseline_dev"][1] - built["orig_baseline_dev"][0])
        built["pass"] = not check["identity_bad"] and \
            check["baseline_dev_max"] - check["baseline_dev_min"] <= allowed
        ok = ok and built["pass"]
        report.append(built)
        print(f"{src.stem:32} {built['mode']:12} src={Path(built['source']).name:24} size={built['size']:7.2f} "
              f"wr={built['width_ratio']:.2f} n={built['glyphs_replaced']} bad={len(check['identity_bad'])} "
              f"maxerr={check['identity_max_alpha_err']} base=[{check['baseline_dev_min']},{check['baseline_dev_max']}] "
              f"orig={built['orig_baseline_dev']} {'PASS' if built['pass'] else 'FAIL'}")
    if args.manifest:
        args.manifest.write_text(json.dumps({"schema": "fonttv/p1-build/v1", "fonts": report},
                                            ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"P1_BUILD_ALL_PASS = {ok} ({sum(r['pass'] for r in report)}/{len(report)})")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
