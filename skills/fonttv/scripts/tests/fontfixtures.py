"""Synthetic TrueType fixtures for fonttv tests (no real fonts, no network)."""
from __future__ import annotations

import importlib.util
import unicodedata
from pathlib import Path

HAS_FONTTOOLS = importlib.util.find_spec("fontTools") is not None
HAS_HARFBUZZ = importlib.util.find_spec("uharfbuzz") is not None

VOWELS = "AaĂăÂâEeÊêIiOoÔôƠơUuƯưYy"
TONES = ("", "\u0300", "\u0301", "\u0309", "\u0303", "\u0323")
MARKS = "".join(chr(c) for c in (0x0300, 0x0301, 0x0302, 0x0303, 0x0306, 0x0309, 0x031B, 0x0323))
WORDS = ("Việt Nam Tiếng Việt Nguyễn Trường Tưởng Tượng Phường Quyền "
         "Chuyện Thường Nghiêng Khuỷu Huế Hưởng Phượng")


def repertoire() -> str:
    chars = {"Đ", "đ"}
    for base in VOWELS:
        for tone in TONES:
            composed = unicodedata.normalize("NFC", base + tone)
            if len(composed) == 1:
                chars.add(composed)
    return "".join(sorted(chars))


def word_ascii() -> str:
    return "".join(sorted({c for c in unicodedata.normalize("NFD", WORDS) if c.isascii() and c.isalpha()}))


def full_chars() -> str:
    return repertoire() + MARKS + word_ascii()


def build_font(path: Path, chars: str, *, empty: str = "", gpos: bool = True, unicode_bits: tuple[int, ...] | None = None) -> Path:
    from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
    from fontTools.fontBuilder import FontBuilder
    from fontTools.pens.ttGlyphPen import TTGlyphPen

    real = sorted({c for c in chars if not c.isspace()})
    names = {c: f"g{ord(c):04X}" for c in real}
    order = [".notdef", "space"] + [names[c] for c in real]
    fb = FontBuilder(1000, isTTF=True)
    fb.setupGlyphOrder(order)
    fb.setupCharacterMap({0x20: "space", **{ord(c): names[c] for c in real}})
    empty_names = {names[c] for c in empty if c in names} | {"space"}
    glyphs = {}
    for name in order:
        pen = TTGlyphPen(None)
        if name not in empty_names:
            pen.moveTo((100, 0))
            pen.lineTo((100, 500))
            pen.lineTo((400, 500))
            pen.lineTo((400, 0))
            pen.closePath()
        glyphs[name] = pen.glyph()
    fb.setupGlyf(glyphs)
    metrics = {name: (500, 100) for name in order}
    metrics["space"] = (250, 0)
    for c in real:
        if unicodedata.combining(c):
            metrics[names[c]] = (0, 0)
    fb.setupHorizontalMetrics(metrics)
    fb.setupHorizontalHeader(ascent=800, descent=-200)
    fb.setupNameTable({"familyName": "FonttvFixture", "styleName": "Regular"})
    fb.setupOS2()
    fb.setupPost(formatType=3.0)
    if gpos and "a" in names and "\u0301" in names:
        acute, a = names["\u0301"], names["a"]
        addOpenTypeFeaturesFromString(fb.font, (
            f"markClass {acute} <anchor 0 500> @TOP;\n"
            f"feature mark {{ pos base {a} <anchor 250 700> mark @TOP; }} mark;\n"
            f"feature mkmk {{ pos mark {acute} <anchor 0 600> mark @TOP; }} mkmk;\n"
            f"feature kern {{ pos {a} {a} -50; }} kern;\n"))
    if unicode_bits is not None:
        os2 = fb.font["OS/2"]
        os2.ulUnicodeRange1 = os2.ulUnicodeRange2 = os2.ulUnicodeRange3 = os2.ulUnicodeRange4 = 0
        for bit in unicode_bits:
            setattr(os2, f"ulUnicodeRange{bit // 32 + 1}", getattr(os2, f"ulUnicodeRange{bit // 32 + 1}") | (1 << (bit % 32)))
    fb.save(str(path))
    return path
