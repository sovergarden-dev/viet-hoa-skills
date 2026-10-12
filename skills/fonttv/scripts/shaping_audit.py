#!/usr/bin/env python3
"""Read-only Vietnamese shaping audit via HarfBuzz (route A, shaper present).

Shapes a Vietnamese corpus in NFC and NFD and reports two separate signals:

- hb_notdef_*: glyph id 0 in HarfBuzz output. HarfBuzz composes base + mark
  into a precomposed glyph when the font has one, so a .notdef in its output
  is a real rendering failure, never a harmless artefact.
- cmap missing (nfc_missing / nfd_missing / nfd_dropped_marks): codepoints the
  cmap lacks. Renderers that map codepoint -> glyph without composing need
  these even when HarfBuzz output looks clean.

Verdict PASS needs both. Passing does not prove mark placement quality, app
rasterizers/layout/cache, or any custom/legacy encoding.

Usage: python shaping_audit.py <font> [--corpus <text>] [--output audit.json]
Exit codes: 0 PASS, 1 FAIL, 2 input error, 3 NOT_SUPPORTED, 4 NOT_RUN.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import unicodedata
from pathlib import Path

try:
    import uharfbuzz
except ImportError:
    uharfbuzz = None

VOWELS = "AaĂăÂâEeÊêIiOoÔôƠơUuƯưYy"
TONES = ("", "\u0300", "\u0301", "\u0309", "\u0303", "\u0323")
WORDS = (
    "Việt Nam Tiếng Việt Nguyễn Trường Tưởng Tượng Phường Quyền "
    "Chuyện Thường Nghiêng Khuỷu Huế Hưởng Phượng"
)
STRESS = (
    "À Á Ả Ã Ạ Ă Ằ Ắ Ẳ Ẵ Ặ Â Ầ Ấ Ẩ Ẫ Ậ "
    "È É Ẻ Ẽ Ẹ Ê Ề Ế Ể Ễ Ệ Ì Í Ỉ Ĩ Ị "
    "Ò Ó Ỏ Õ Ọ Ô Ồ Ố Ổ Ỗ Ộ Ơ Ờ Ớ Ở Ỡ Ợ "
    "Ù Ú Ủ Ũ Ụ Ư Ừ Ứ Ử Ữ Ự Ỳ Ý Ỷ Ỹ Ỵ Đ"
)
SFNT_SIGNATURES = {b"\x00\x01\x00\x00", b"OTTO", b"true", b"wOFF", b"wOF2"}
MAX_LISTED = 40


def build_repertoire() -> str:
    chars = {"Đ", "đ"}
    for base in VOWELS:
        for tone in TONES:
            composed = unicodedata.normalize("NFC", base + tone)
            if len(composed) == 1:
                chars.add(composed)
    return "".join(sorted(chars))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def shape(font, text: str):
    buf = uharfbuzz.Buffer()
    buf.add_str(text)
    buf.guess_segment_properties()
    uharfbuzz.shape(font, buf)
    return buf.glyph_infos, buf.glyph_positions


def glyph_name(font, gid: int) -> str:
    try:
        return font.get_glyph_name(gid) or f"gid{gid}"
    except Exception:
        return f"gid{gid}"


def cmap_missing(font, text: str) -> list[str]:
    missing = []
    for ch in dict.fromkeys(text):
        if not ch.isspace() and not font.get_nominal_glyph(ord(ch)):
            missing.append(f"U+{ord(ch):04X} {unicodedata.name(ch, '<unnamed>')}")
    return missing


def shape_corpus(font, corpus: str) -> dict:
    nfc = unicodedata.normalize("NFC", corpus)
    nfd = unicodedata.normalize("NFD", corpus)
    nfc_infos, _ = shape(font, nfc)
    nfd_infos, _ = shape(font, nfd)
    notdef_chars = {"nfc": [], "nfd": []}
    spacing_marks = []
    for ch in dict.fromkeys(c for c in nfc if not c.isspace()):
        for form in ("nfc", "nfd"):
            sample = unicodedata.normalize(form.upper(), ch)
            infos, positions = shape(font, sample)
            if any(info.codepoint == 0 for info in infos):
                notdef_chars[form].append(f"{ch} ({' '.join(f'U+{ord(c):04X}' for c in sample)})")
            if form == "nfd" and len(infos) > 1:
                if any(pos.x_advance != 0 for pos in positions[1:]):
                    spacing_marks.append(ch)
    nfd_marks = {c for c in nfd if unicodedata.combining(c)}
    return {
        "hb_notdef_nfc": sum(1 for info in nfc_infos if info.codepoint == 0),
        "hb_notdef_nfd": sum(1 for info in nfd_infos if info.codepoint == 0),
        "hb_notdef_chars_nfc": notdef_chars["nfc"][:MAX_LISTED],
        "hb_notdef_chars_nfd": notdef_chars["nfd"][:MAX_LISTED],
        "nfc_missing": cmap_missing(font, nfc),
        "nfd_missing": cmap_missing(font, nfd),
        "nfd_dropped_marks": sorted(f"U+{ord(m):04X}" for m in nfd_marks if not font.get_nominal_glyph(ord(m))),
        "nonzero_advance_marks": spacing_marks[:MAX_LISTED],
        "nfc_glyph_count": len(nfc_infos),
        "nfd_glyph_count": len(nfd_infos),
        "nfc_glyph_sample": [glyph_name(font, i.codepoint) for i in nfc_infos[:12]],
        "nfd_glyph_sample": [glyph_name(font, i.codepoint) for i in nfd_infos[:12]],
    }


def emit(result: dict, output: Path | None) -> int:
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if output:
        output.write_text(text + "\n", encoding="utf-8")
    sys.stdout.buffer.write((text + "\n").encode("utf-8"))
    return result["exit_code"]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Read-only Vietnamese shaping audit (HarfBuzz, NFC + NFD)")
    ap.add_argument("font", type=Path)
    ap.add_argument("--corpus", type=Path)
    ap.add_argument("--output", type=Path)
    a = ap.parse_args(argv)
    base = {"schema": "fonttv/shaping/v2", "tool": "shaping_audit.py", "gate": "shaping", "route": "A_unicode_opentype",
            "applies_if": "runtime text passes through an OpenType shaper; for direct codepoint->glyph renderers the cmap signals decide",
            "font": str(a.font),
            "does_not_prove": ["mark placement quality (needs rendered proof)", "app/engine rasterizer, layout or cache",
                               "custom or legacy encodings"]}
    if not a.font.is_file():
        return emit({**base, "valid": False, "verdict": "INPUT_ERROR", "exit_code": 2, "error": "font_not_found"}, None)
    with a.font.open("rb") as handle:
        signature = handle.read(4)
    base["sha256"] = sha256(a.font)
    if signature not in SFNT_SIGNATURES:
        return emit({**base, "valid": False, "verdict": "NOT_SUPPORTED", "exit_code": 3,
                     "reason": "collection or non-sfnt input; shape one extracted face"}, a.output)
    if uharfbuzz is None:
        return emit({**base, "valid": False, "verdict": "NOT_RUN", "exit_code": 4, "error": "uharfbuzz_missing",
                     "hint": "pip install uharfbuzz"}, a.output)

    font = uharfbuzz.Font(uharfbuzz.Face(a.font.read_bytes()))
    corpus = a.corpus.read_text(encoding="utf-8") if a.corpus else ""
    if not corpus:
        corpus = build_repertoire() + " " + WORDS + " " + STRESS
    result = {**base, "valid": True, "harfbuzz": getattr(uharfbuzz, "__version__", None), "corpus_chars": len(corpus)}
    rep = shape_corpus(font, corpus)
    result.update(rep)
    result["shaping_ok"] = rep["hb_notdef_nfc"] == 0 and rep["hb_notdef_nfd"] == 0
    result["engine_independent_ok"] = not rep["nfc_missing"] and not rep["nfd_missing"]
    warnings = []
    if result["shaping_ok"] and not result["engine_independent_ok"]:
        warnings.append("HarfBuzz composed NFD input into precomposed glyphs; renderers without composition will drop the missing marks")
    if rep["nonzero_advance_marks"]:
        warnings.append("some NFD marks keep a non-zero advance after shaping; check GDEF mark classes / zero-width marks")

    gpos: list[str] = []
    try:
        from fontTools.ttLib import TTFont

        ttf = TTFont(str(a.font), lazy=True, recalcBBoxes=False, recalcTimestamp=False)
        if "GPOS" in ttf and ttf["GPOS"].table.FeatureList is not None:
            gpos = sorted({rec.FeatureTag for rec in ttf["GPOS"].table.FeatureList.FeatureRecord})
        ttf.close()
    except Exception:
        warnings.append("fontTools unavailable or GPOS unreadable; feature list NOT_RUN")
    result["gpos_features"] = gpos
    result["has_mark_feature"] = "mark" in gpos
    result["has_mkmk_feature"] = "mkmk" in gpos
    result["warnings"] = warnings
    passed = result["shaping_ok"] and result["engine_independent_ok"]
    result["verdict"] = "PASS" if passed else "FAIL"
    result["exit_code"] = 0 if passed else 1
    result["proof_level"] = "structurally_verified" if passed else "inventory_only"
    return emit(result, a.output)


if __name__ == "__main__":
    sys.exit(main())
