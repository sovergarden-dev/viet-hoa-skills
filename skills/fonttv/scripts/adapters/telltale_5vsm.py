#!/usr/bin/env python3
"""Read-only fonttv adapter for Telltale Tool 5VSM `.font` files.

Supported profile: the TRectNew/BC3 layout used by The Wolf Among Us PC
(5VSM, 48-byte ``<III4f5f`` records, 512-pixel-wide DXT5 pages). Unknown
magic/layouts fail closed. The adapter derives records and alpha ink directly
from the input bytes; it never assigns semantic glyph identities.

Protocol: python telltale_5vsm.py --input FONT --output JSON
          --invocation-id ID --protocol fonttv-adapter/v1
Exit 0 = inventory written; 3 = unsupported variant; 1 = corrupt supported
input or protocol misuse.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import struct
import sys
from pathlib import Path

PROTOCOL = "fonttv-adapter/v1"
EXIT_UNSUPPORTED = 3
RECORD = struct.Struct("<III4f5f")
ATLAS_WIDTH = 512
PAGE0_BYTES = ATLAS_WIDTH * 512  # BC3 is one byte/pixel at 4x4 block granularity.
MAX_ELEMENTS = 4096
MAX_RECORDS = 65536


class Unsupported(Exception):
    pass


class Corrupt(Exception):
    pass


def fail(code: int, message: str) -> int:
    sys.stderr.write(message + "\n")
    return code


def u32(data: bytes, offset: int, where: str) -> int:
    if offset < 0 or offset + 4 > len(data):
        raise Corrupt(f"truncated at {where}")
    return struct.unpack_from("<I", data, offset)[0]


def f32(data: bytes, offset: int, where: str) -> float:
    if offset < 0 or offset + 4 > len(data):
        raise Corrupt(f"truncated at {where}")
    value = struct.unpack_from("<f", data, offset)[0]
    if not math.isfinite(value):
        raise Corrupt(f"non-finite float at {where}")
    return value


def descriptor_starts(blob: bytes, pages: int) -> list[int]:
    """Locate page descriptors by their Telltale type-header prefix."""
    prefix = b"\x04\x00\x00\x00\x08\x00\x00\x00"
    starts, pos = [], 8  # blob begins with total-size and page count
    while len(starts) < pages:
        hit = blob.find(prefix, pos)
        if hit < 0:
            break
        starts.append(hit)
        pos = hit + len(prefix)
    if len(starts) != pages or starts[0] != 8:
        raise Unsupported("unrecognised Telltale texture descriptor layout")
    return starts


def parse(data: bytes) -> tuple[list[dict], list[bytes], list[int], dict]:
    if len(data) < 24:
        raise Corrupt("truncated 5VSM stream")
    if data[:4] != b"5VSM":
        if data[:4] == b"6VSM":
            raise Unsupported("6VSM TRectNew profile is not verified")
        raise Unsupported("not a Telltale 5VSM font (magic mismatch)")

    header_size, _unknown, declared_tex_size = struct.unpack_from("<III", data, 4)
    elements = u32(data, 16, "element count")
    if not 0 < elements <= MAX_ELEMENTS:
        raise Corrupt(f"invalid element count {elements}")
    pos = 20 + elements * 12
    if pos + 8 > len(data):
        raise Corrupt("truncated property table")

    name_len = u32(data, pos, "font name length")
    pos += 4
    next_len = u32(data, pos, "alternate font name length")
    if name_len >= next_len and name_len - next_len == 8:
        name_len = next_len
        pos += 4
    if name_len > 4096 or pos + name_len + 5 > len(data):
        raise Corrupt(f"invalid font name length {name_len}")
    pos += name_len + 1 + 4
    if f32(data, pos, "optional scale") in (0.5, 1.0):
        pos += 4
    if f32(data, pos, "optional flag") == 1.0:
        pos += 4

    if pos + 8 > len(data):
        raise Corrupt("missing block-coordinate header")
    block_size, count = struct.unpack_from("<ii", data, pos)
    pos += 8
    if count < 0 or count > MAX_RECORDS:
        raise Corrupt(f"invalid record count {count}")
    if block_size != count * RECORD.size + 8:
        raise Unsupported(f"unsupported TRectNew stride/block: block={block_size}, count={count}")
    records_end = pos + count * RECORD.size
    texture_offset = header_size + 16 + elements * 12 + 4
    if records_end > texture_offset or texture_offset > len(data):
        raise Corrupt("record/header boundaries are outside the file")
    raw = data[texture_offset:]
    if declared_tex_size != len(raw):
        raise Corrupt(f"declared texture size {declared_tex_size} != payload {len(raw)}")
    if len(raw) % 16:
        raise Corrupt("DXT5 payload is not block aligned")

    tex_header = data[records_end:texture_offset]
    if len(tex_header) < 9:
        raise Corrupt("missing texture descriptors")
    pages = u32(tex_header, 4, "texture page count")
    if not 0 < pages <= 64:
        raise Corrupt(f"invalid texture page count {pages}")
    starts = descriptor_starts(tex_header, pages)

    unpacked = []
    for index in range(count):
        values = RECORD.unpack_from(data, pos + index * RECORD.size)
        if not all(math.isfinite(v) for v in values[3:]):
            raise Corrupt(f"record {index} has non-finite geometry")
        unpacked.append(values)
    page_ids = [int(r[1]) for r in unpacked]
    if any(pg < 0 or pg >= pages for pg in page_ids):
        raise Corrupt("record references a texture page outside the descriptor table")

    # Read descriptor width/height and payload-size fields. Original assets use
    # exact per-page sizes. Some historical patchers left stale first-page
    # descriptors; those layouts are only safe when every record was collapsed
    # to the one expanded payload.
    descriptor_sizes, descriptor_heights, descriptor_widths = [], [], []
    for index, start in enumerate(starts):
        end = starts[index + 1] if index + 1 < len(starts) else len(tex_header)
        desc = tex_header[start:end]
        if len(desc) < 92:
            raise Unsupported("Telltale texture descriptor is too short")
        width = u32(desc, len(desc) - 92, f"page {index} width")
        height = u32(desc, len(desc) - 88, f"page {index} height")
        size20 = u32(desc, len(desc) - 20, f"page {index} payload size")
        size8 = u32(desc, len(desc) - 8, f"page {index} payload size mirror")
        if width <= 0 or width % 4 or height <= 0 or height % 4 or size20 != size8 or size20 != width * height:
            raise Unsupported(f"unverified page descriptor {index}: {width}x{height}, sizes {size20}/{size8}")
        descriptor_sizes.append(size20)
        descriptor_heights.append(height)
        descriptor_widths.append(width)

    # Some v3 outputs collapse all records onto page 0 while retaining two
    # descriptors and a single expanded payload. Treat that as one logical
    # page; splitting by stale descriptors would assign UVs to the wrong bytes.
    referenced_pages = sorted(set(page_ids))
    collapsed = pages > 1 and referenced_pages == [0]
    exact_descriptors = sum(descriptor_sizes) == len(raw)
    ink_supported = True
    if pages == 1:
        chunks = [raw]
        record_page_map = {0: 0}
        texture_layout = "descriptor_sized_pages"
    elif collapsed:
        chunks = [raw]
        record_page_map = {0: 0}
        texture_layout = "collapsed_to_referenced_page"
    elif exact_descriptors:
        chunks, cursor = [], 0
        for size in descriptor_sizes:
            chunks.append(raw[cursor:cursor + size])
            cursor += size
        record_page_map = {index: index for index in range(pages)}
        texture_layout = "descriptor_sized_pages"
    else:
        # Records/UV/metrics are still parseable, but page boundaries are not.
        # Omit ink capability rather than manufacture pixels from a guessed split.
        chunks = []
        record_page_map = {index: index for index in range(pages)}
        texture_layout = "ambiguous_multipage_no_ink"
        ink_supported = False
    widths = []
    heights = []
    if ink_supported:
        for index, chunk in enumerate(chunks):
            width = descriptor_widths[0] if collapsed else descriptor_widths[index]
            if len(chunk) % width or len(chunk) == 0:
                raise Corrupt(f"page {index} BC3 byte size is not a {width}-wide image")
            height = len(chunk) // width
            if height % 4:
                raise Corrupt(f"page {index} height {height} is not block aligned")
            widths.append(width)
            heights.append(height)
    else:
        widths = descriptor_widths
        heights = descriptor_heights

    meta = {"header_size": header_size, "element_count": elements, "record_count": count,
            "texture_pages": pages, "texture_offset": texture_offset,
            "descriptor_offsets": starts, "descriptor_sizes": descriptor_sizes,
            "descriptor_widths": descriptor_widths, "descriptor_heights": descriptor_heights,
            "page_widths": widths, "page_heights": heights,
            "texture_layout": texture_layout, "record_page_map": record_page_map,
            "ink_supported": ink_supported}
    return unpacked, chunks, heights, meta


def alpha_palette(a0: int, a1: int) -> list[int]:
    if a0 > a1:
        return [a0, a1] + [((7 - i) * a0 + i * a1) // 7 for i in range(1, 7)]
    return [a0, a1] + [((5 - i) * a0 + i * a1) // 5 for i in range(1, 5)] + [0, 255]


def count_ink(raw: bytes, width: int, height: int, box: tuple[int, int, int, int], threshold: int = 16) -> int:
    x0, y0, x1, y1 = box
    if x1 <= x0 or y1 <= y0:
        return 0
    blocks_w = width // 4
    count = 0
    for by in range(y0 // 4, (y1 - 1) // 4 + 1):
        for bx in range(x0 // 4, (x1 - 1) // 4 + 1):
            off = (by * blocks_w + bx) * 16
            if off + 8 > len(raw):
                raise Corrupt("glyph UV points beyond DXT5 page")
            a0, a1 = raw[off], raw[off + 1]
            palette = alpha_palette(a0, a1)
            bits = int.from_bytes(raw[off + 2:off + 8], "little")
            for py in range(4):
                y = by * 4 + py
                if y < y0 or y >= y1 or y >= height:
                    continue
                for px in range(4):
                    x = bx * 4 + px
                    if x < x0 or x >= x1 or x >= width:
                        continue
                    idx = (bits >> (3 * (py * 4 + px))) & 7
                    if palette[idx] > threshold:
                        count += 1
    return count


def uv_box(record, width: int, height: int) -> tuple[int, int, int, int]:
    u0, u1, v0, v1 = record[3:7]
    if not (0.0 <= u0 <= 1.0 and 0.0 <= u1 <= 1.0 and 0.0 <= v0 <= 1.0 and 0.0 <= v1 <= 1.0):
        raise Corrupt(f"record {record[0]} has UV outside [0,1]")
    x0 = max(0, min(width, int(round(u0 * width))))
    x1 = max(0, min(width, int(round(u1 * width))))
    y0 = max(0, min(height, int(round(v0 * height))))
    y1 = max(0, min(height, int(round(v1 * height))))
    return x0, y0, x1, y1


def inventory(path: Path, data: bytes, invocation_id: str) -> dict:
    records, chunks, heights, meta = parse(data)
    out = []
    for rec in records:
        cid, declared_page, channel = int(rec[0]), int(rec[1]), int(rec[2])
        logical_page = meta["record_page_map"][declared_page]
        box = uv_box(rec, meta["page_widths"][logical_page], heights[logical_page])
        row = {
            "id": cid, "page": declared_page, "channel": channel,
            "uv": [float(rec[3]), float(rec[5]), float(rec[4]), float(rec[6])],
            "ink_bbox": list(box),
            "width": float(rec[7]), "height": float(rec[8]),
            "x_offset": float(rec[9]), "y_offset": float(rec[10]), "x_advance": float(rec[11]),
        }
        if meta["ink_supported"]:
            row["ink_pixels"] = count_ink(chunks[logical_page], meta["page_widths"][logical_page], heights[logical_page], box)
        out.append(row)
    digest = hashlib.sha256(data).hexdigest()
    return {
        "schema": "fonttv/font-inventory/v1", "font": path.name, "sha256": digest,
        "adapter": {
            "name": "telltale-5vsm", "version": "1.0.0", "supported": True,
            "capabilities": ["records", "uv", "metrics"] + (["ink"] if meta["ink_supported"] else []),
            "input_sha256": digest,
            "inventory_method": "parsed TWAU PC 5VSM TRectNew records and decoded DXT5 alpha blocks",
            "profile": "twau-pc-5vsm-trectnew-v1", "metadata": meta,
        },
        "invocation": {"id": invocation_id, "protocol": PROTOCOL},
        "lookup": "binary_search", "records": out,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--input", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--invocation-id", required=True)
    ap.add_argument("--protocol", required=True)
    a = ap.parse_args(argv)
    if a.protocol != PROTOCOL:
        return fail(1, f"unsupported protocol {a.protocol!r}")
    try:
        data = a.input.read_bytes()
        result = inventory(a.input, data, a.invocation_id)
        a.output.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
        return 0
    except Unsupported as exc:
        return fail(EXIT_UNSUPPORTED, str(exc))
    except (Corrupt, OSError, struct.error, ValueError) as exc:
        return fail(1, f"corrupt/invalid Telltale font: {exc}")


if __name__ == "__main__":
    sys.exit(main())
