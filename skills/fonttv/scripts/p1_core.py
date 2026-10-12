"""Engine-neutral helpers for strategy P1 (replace every glyph from a source TTF).

Nothing here knows a container format. Engine adapters (``p1_telltale_build.py``)
supply pages/records; this module renders, sizes, packs-checks and verifies.

Rules encoded here were each learned from a false result (see
references/strategy-p1-replace.md):

* ``uv_box`` rounds. UVs are float32; ``516 / th`` reads back as 515.99999 and
  ``int()`` drops a row, which made 131 glyphs look like the wrong shape.
* ``identity_dxt5`` does not use binary IoU. DXT5 keeps 8 alpha levels per 4x4
  block, so fringe alpha below ~18 legitimately becomes 0. Identity means: no
  ink where the source had none, no strong pixel (>= 32) lost, and no pixel
  off by more than 19 alpha steps.
"""
from __future__ import annotations

import hashlib
import io
import struct
import unicodedata
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

DXT5_MAX_ERR = 19
STRONG_ALPHA = 32


def sha256(path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


# ---------------------------------------------------------------- geometry

def uv_box(u0: float, u1: float, v0: float, v1: float, width: int, height: int):
    """Pixel box of a float32 UV rect. Rounds; never truncates."""
    return round(u0 * width), round(v0 * height), round(u1 * width), round(v1 * height)


def ink_box(alpha, thr: int = 0):
    if alpha is None:
        return None
    ys, xs = np.nonzero(alpha > thr)
    if len(ys) == 0:
        return None
    return int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1


def stem_ratio(alpha):
    """Stroke width of the middle row of 'I' relative to its height (weight proxy)."""
    box = ink_box(alpha, 127)
    if box is None:
        return None
    row = alpha[(box[1] + box[3]) // 2, box[0]:box[2]] > 127
    return int(row.sum()) / max(1, box[3] - box[1])


# ---------------------------------------------------------------- rendering

def render(ft: ImageFont.FreeTypeFont, ch: str, sx: float = 1.0):
    """Render ``ch`` on the baseline.

    Returns ``(alpha, ink_left, ink_top, advance)``; ink_left/ink_top are
    relative to the pen origin on the baseline (``anchor="ls"``), so every
    glyph of one font shares one baseline by construction.
    """
    bb = ft.getbbox(ch, anchor="ls")
    adv = ft.getlength(ch) * sx
    if bb[2] <= bb[0] or bb[3] <= bb[1]:
        return None, 0, 0, adv
    pad = 4
    img = Image.new("L", (bb[2] - bb[0] + 2 * pad, bb[3] - bb[1] + 2 * pad), 0)
    ox, oy = pad - bb[0], pad - bb[1]
    ImageDraw.Draw(img).text((ox, oy), ch, font=ft, fill=255, anchor="ls")
    box = img.getbbox()
    if box is None:
        return None, 0, 0, adv
    img = img.crop(box)
    left, top = box[0] - ox, box[1] - oy
    if sx != 1.0:
        img = img.resize((max(1, round(img.width * sx)), img.height), Image.LANCZOS)
        left *= sx
    return np.array(img, dtype=np.uint8), left, top, adv


def size_for_cap(path, cap_px: float, probe: int = 200) -> float:
    """Pixel size at which the ink height of 'H' equals ``cap_px``."""
    ft = ImageFont.truetype(str(path), probe)
    bb = ft.getbbox("H", anchor="ls")
    return probe * cap_px / (bb[3] - bb[1])


def _fill(mask) -> float | None:
    box = ink_box(mask.astype(np.uint8))
    if box is None:
        return None
    w, h = box[2] - box[0], box[3] - box[1]
    return round(int(mask.sum()) / max(1, w * h), 3)


def dot_shapes(path, size: int = 200) -> dict:
    """Fill ratio of the dot below and of the font's own period. ~0.79 round, 1.0 square.

    The dot is taken from the rows of ``ọ`` below the lowest ink row of ``o``.
    Subtracting whole images is wrong: in NotoSerif the ``o`` inside ``ọ`` is
    not pixel-identical to a standalone ``o`` (87 px differ), and the outline
    sliver drags the fill to 0.044.
    """
    ft = ImageFont.truetype(str(path), size)
    canvas = (size * 3, size * 3)
    base = size * 2

    def draw(ch):
        img = Image.new("L", canvas, 0)
        ImageDraw.Draw(img).text((size // 2, base), ch, font=ft, fill=255, anchor="ls")
        return np.array(img) > 127

    o_box = ink_box(draw("o").astype(np.uint8))
    dot = draw("\u1ecd")
    if o_box is None:
        return {"dot_below": None, "period": _fill(draw("."))}
    dot[:o_box[3] + 1] = False
    return {"dot_below": _fill(dot), "period": _fill(draw("."))}


def dot_below_fill(path, size: int = 200):
    return dot_shapes(path, size)["dot_below"]


# ---------------------------------------------------------------- coverage

def vn_repertoire() -> str:
    """134 precomposed Vietnamese letters, derived (never hard-coded)."""
    vowels = "AaĂăÂâEeÊêIiOoÔôƠơUuƯưYy"
    tones = ("", "\u0300", "\u0301", "\u0309", "\u0303", "\u0323")
    chars = {"Đ", "đ"}
    for v in vowels:
        for t in tones:
            c = unicodedata.normalize("NFC", v + t)
            if len(c) == 1 and not c.isascii():
                chars.add(c)
    return "".join(sorted(chars))


# ---------------------------------------------------------------- DXT5

def encode_dxt5_alpha(alpha: np.ndarray, color_part: bytes = b"\xff\xff\xff\xff\xaa\xaa\xaa\xaa") -> bytes:
    """Encode an alpha plane as DXT5 blocks with constant white colour."""
    h, w = alpha.shape
    if h % 4 or w % 4:
        raise ValueError(f"DXT5 plane {w}x{h} is not block aligned")
    blocks = alpha.reshape(h // 4, 4, w // 4, 4).swapaxes(1, 2).reshape(-1, 16)
    a_max, a_min = blocks.max(axis=1), blocks.min(axis=1)
    a0, a1 = a_max.astype(np.int32), a_min.astype(np.int32)
    levels = np.stack([a0, a1] + [((7 - k) * a0 + k * a1) // 7 for k in range(1, 7)], axis=1)
    idx = np.argmin(np.abs(blocks[:, :, None].astype(np.int32) - levels[:, None, :]), axis=2).astype(np.uint64)
    packed = np.bitwise_or.reduce(idx << (np.arange(16, dtype=np.uint64) * 3)[None, :], axis=1)
    out = bytearray(len(blocks) * 16)
    for i in range(len(blocks)):
        if a_max[i] == 0:
            out[i * 16:i * 16 + 16] = b"\x00" * 8 + color_part
        elif a_min[i] == a_max[i]:
            out[i * 16:i * 16 + 16] = bytes([a_max[i], a_max[i], 0, 0, 0, 0, 0, 0]) + color_part
        else:
            out[i * 16:i * 16 + 16] = bytes([a_max[i], a_min[i]]) + int(packed[i]).to_bytes(6, "little") + color_part
    return bytes(out)


def decode_dxt5_alpha(raw: bytes, width: int, height: int) -> np.ndarray:
    """Decode the alpha plane of a raw DXT5 surface through Pillow's DDS reader."""
    header = bytearray(128)
    header[0:4] = b"DDS "
    for off, val in ((4, 124), (8, 0x81007), (12, height), (16, width), (20, len(raw)),
                     (28, 1), (76, 32), (80, 0x4), (108, 0x1000)):
        struct.pack_into("<I", header, off, val)
    header[84:88] = b"DXT5"
    img = Image.open(io.BytesIO(bytes(header) + raw)).convert("RGBA")
    return np.array(img.split()[-1], dtype=np.uint8)


# ---------------------------------------------------------------- verification

def identity_dxt5(got, want) -> dict:
    """Glyph identity after a DXT5 round trip. See module docstring."""
    if got is None or want is None or got.shape != want.shape:
        return {"ok": False, "reason": "shape", "added": None, "strong_lost": None, "max_err": None}
    added = int(((got > 0) & (want == 0)).sum())
    strong_lost = int(((want >= STRONG_ALPHA) & (got == 0)).sum())
    max_err = int(np.abs(got.astype(np.int16) - want.astype(np.int16)).max()) if got.size else 0
    ok = not added and not strong_lost and max_err <= DXT5_MAX_ERR
    return {"ok": ok, "reason": None if ok else "pixels", "added": added,
            "strong_lost": strong_lost, "max_err": max_err}
