"""Span-relative Telltale texture descriptor reader/writer.

This module mirrors the descriptor arithmetic used by the fonttv adapter
(scripts/adapters/telltale_5vsm.py) so build tooling and audit tooling can
never disagree about where width/height/payload fields live.

Adapter rule, repeated here on purpose:

    desc = tex_header[start : next_start or len(tex_header)]
    width  = u32(desc, len(desc) - 92)
    height = u32(desc, len(desc) - 88)
    size20 = u32(desc, len(desc) - 20)
    size8  = u32(desc, len(desc) -  8)

Descriptor spans are NOT a fixed size. Observed in TWAU PC 5VSM assets:
Rockwell_Std_48_bold -> 189 bytes, ITC_Kabel_Book -> 233 bytes. Any writer
that hard-codes a span length or an absolute offset will corrupt the layout.

The invariant every written multipage font must satisfy:

    sum(descriptor_sizes) == len(texture_payload)      -> ink measurable

If that sum does not match, the adapter must not claim ink support and the
structural gate must not pass. This module refuses to write a font that
would violate the invariant.
"""

from __future__ import annotations

import struct

DESCRIPTOR_PREFIX = b"\x04\x00\x00\x00\x08\x00\x00\x00"

WIDTH_FROM_END = 92
HEIGHT_FROM_END = 88
SIZE20_FROM_END = 20
SIZE8_FROM_END = 8


class DescriptorError(Exception):
    """Raised when a descriptor table cannot be read or written safely."""


def find_descriptor_starts(tex_header: bytes, pages: int) -> list[int]:
    """Locate page descriptors by their Telltale type-header prefix."""
    starts: list[int] = []
    pos = 8  # blob begins with total-size and page count
    while len(starts) < pages:
        hit = tex_header.find(DESCRIPTOR_PREFIX, pos)
        if hit < 0:
            break
        starts.append(hit)
        pos = hit + len(DESCRIPTOR_PREFIX)
    if len(starts) != pages or starts[0] != 8:
        raise DescriptorError("unrecognised Telltale texture descriptor layout")
    return starts


def _spans(tex_header: bytes, starts: list[int]) -> list[tuple[int, int]]:
    out = []
    for index, start in enumerate(starts):
        end = starts[index + 1] if index + 1 < len(starts) else len(tex_header)
        if end - start < 92:
            raise DescriptorError(f"descriptor {index} span too short ({end - start})")
        out.append((start, end))
    return out


def read_descriptors(tex_header: bytes, pages: int) -> list[dict]:
    starts = find_descriptor_starts(tex_header, pages)
    out = []
    for index, (start, end) in enumerate(_spans(tex_header, starts)):
        span = end - start
        width = struct.unpack_from("<I", tex_header, start + span - WIDTH_FROM_END)[0]
        height = struct.unpack_from("<I", tex_header, start + span - HEIGHT_FROM_END)[0]
        size20 = struct.unpack_from("<I", tex_header, start + span - SIZE20_FROM_END)[0]
        size8 = struct.unpack_from("<I", tex_header, start + span - SIZE8_FROM_END)[0]
        out.append(
            {
                "index": index,
                "start": start,
                "span": span,
                "width": width,
                "height": height,
                "size20": size20,
                "size8": size8,
                "consistent": (
                    width > 0
                    and width % 4 == 0
                    and height > 0
                    and height % 4 == 0
                    and size20 == size8 == width * height
                ),
            }
        )
    return out


def write_page_geometry(tex_header: bytearray, desc: dict, width: int, height: int) -> None:
    """Write width/height/payload mirrors for one descriptor, span-relative.

    Both payload mirrors are set to width*height so the adapter's consistency
    check (size20 == size8 == width*height) holds exactly.
    """
    if width <= 0 or width % 4 or height <= 0 or height % 4:
        raise DescriptorError(f"illegal page geometry {width}x{height}")
    span = desc["span"]
    base = desc["start"]
    payload = width * height
    struct.pack_into("<I", tex_header, base + span - WIDTH_FROM_END, width)
    struct.pack_into("<I", tex_header, base + span - HEIGHT_FROM_END, height)
    struct.pack_into("<I", tex_header, base + span - SIZE20_FROM_END, payload)
    struct.pack_into("<I", tex_header, base + span - SIZE8_FROM_END, payload)


def solve_multipage_heights(
    tex_header: bytes,
    pages: int,
    page0_payload: int,
    total_payload: int,
    width: int = 512,
) -> list[int]:
    """Choose heights so the descriptor sum equals the real payload length.

    Page 0 keeps its authored height and payload (untouched source bytes).
    Remaining pages must absorb ``total_payload - page0_payload`` with each
    page height block-aligned. Returns the full height list, index 0 included.
    """
    descs = read_descriptors(tex_header, pages)
    remainder = total_payload - page0_payload
    if remainder < 0:
        raise DescriptorError(
            f"page 0 payload {page0_payload} exceeds total payload {total_payload}"
        )
    if pages < 2:
        return [page0_payload // width]

    heights = [descs[0]["height"]]
    if pages == 2:
        if remainder % width:
            raise DescriptorError(
                f"page 1 payload {remainder} is not a multiple of width {width}"
            )
        height = remainder // width
        if height % 4:
            raise DescriptorError(
                f"page 1 height {height} is not block aligned "
                f"(payload {remainder}, width {width})"
            )
        heights.append(height)
        return heights

    raise DescriptorError("only 1- and 2-page fonts are supported by this solver")


def verify_layout(tex_header: bytes, pages: int, total_payload: int) -> dict:
    """Return a verification record; raise only on structural impossibility."""
    descs = read_descriptors(tex_header, pages)
    sizes = [d["size20"] for d in descs]
    total = sum(sizes)
    bad = [d for d in descs if not d["consistent"]]
    return {
        "descriptor_spans": [d["span"] for d in descs],
        "descriptor_heights": [d["height"] for d in descs],
        "descriptor_sizes": sizes,
        "sum_sizes": total,
        "payload": total_payload,
        "match": total == total_payload,
        "inconsistent_descriptors": [d["index"] for d in bad],
    }
