#!/usr/bin/env python3
"""Read-only Vietnamese audit for Unicode/OpenType fonts (route A only).

Proves what a Unicode cmap can prove: which codepoints map to a glyph, whether
those glyphs have outlines and advances, and which OpenType features exist.
It does NOT prove a custom/legacy encoding (bytes -> glyph slots), the identity
of the glyph drawn for a codepoint, atlas/archive binding or runtime rendering.
Use custom_encoding_audit.py for route B/C.

Exit codes: 0 PASS, 1 FAIL, 2 input error, 3 NOT_SUPPORTED, 4 NOT_RUN.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import unicodedata
from pathlib import Path

VN = "ăâđêôơưĂÂĐÊÔƠƯàáảãạằắẳẵặầấẩẫậèéẻẽẹềếểễệìíỉĩịòóỏõọồốổỗộờớởỡợùúủũụừứửữựỳýỷỹỵ"
VOWELS = "AaĂăÂâEeÊêIiOoÔôƠơUuƯưYy"
TONES = ("", "\u0300", "\u0301", "\u0309", "\u0303", "\u0323")
COMBINING = {0x0300, 0x0301, 0x0302, 0x0303, 0x0306, 0x0309, 0x031B, 0x0323}
SFNT_SIGNATURES = {b"\x00\x01\x00\x00", b"OTTO", b"true", b"wOFF", b"wOF2"}
COLOR_TABLES = ("COLR", "CPAL", "SVG ", "CBDT", "CBLC", "sbix")
DOES_NOT_PROVE = [
    "custom or legacy byte encodings (use custom_encoding_audit.py)",
    "identity of the glyph drawn for a codepoint (needs rendered proof)",
    "atlas, archive or renderer binding",
    "runtime rendering or visual quality",
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def scalars(text: str) -> set[int]:
    return {ord(c) for c in text if not c.isspace()}


def build_vietnamese_repertoire(corpus_codepoints: set[int]) -> tuple[set[int], set[int], list[str]]:
    """Repertoire from vowel bases x tone marks (NFC) plus the combining marks
    the corpus uses in NFD; not a hardcoded U+1EA0-U+1EF9 list."""
    precomposed = {ord("Đ"), ord("đ")}
    non_composing = []
    for base in VOWELS:
        for tone in TONES:
            composed = unicodedata.normalize("NFC", base + tone)
            if len(composed) == 1:
                precomposed.add(ord(composed))
            elif tone:
                non_composing.append(f"U+{ord(base):04X}+U+{ord(tone):04X}")
    combining = set(COMBINING)
    for cp in corpus_codepoints:
        for part in unicodedata.normalize("NFD", chr(cp)):
            if unicodedata.combining(part):
                combining.add(ord(part))
    return precomposed, combining, non_composing


def feature_tags(font, tag: str) -> list[str]:
    if tag not in font:
        return []
    feature_list = getattr(font[tag].table, "FeatureList", None)
    if not feature_list:
        return []
    return sorted({record.FeatureTag for record in feature_list.FeatureRecord})


def outline_flavor(tables) -> str:
    if "glyf" in tables:
        return "TrueType glyf"
    if "CFF2" in tables:
        return "CFF2"
    if "CFF " in tables:
        return "CFF"
    return "unknown"


def fmt(cps) -> list[str]:
    return [f"U+{cp:04X}" for cp in sorted(cps)]


def emit(result: dict, output: Path | None) -> int:
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if output:
        output.write_text(text + "\n", encoding="utf-8")
    sys.stdout.buffer.write((text + "\n").encode("utf-8"))
    return result["exit_code"]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Read-only Vietnamese audit for Unicode/OpenType fonts. "
                                                 "Does not prove custom/legacy encodings or runtime.")
    parser.add_argument("font", type=Path)
    parser.add_argument("--corpus", type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--output", type=Path)
    a = parser.parse_args(argv)
    base = {"schema": "fonttv/audit/v2", "tool": "fonttv_audit.py", "route": "A_unicode_opentype",
            "encoding_contract": "unicode_cmap", "font": str(a.font), "does_not_prove": DOES_NOT_PROVE}
    if not a.font.is_file():
        return emit({**base, "valid": False, "verdict": "INPUT_ERROR", "exit_code": 2, "error": "font_not_found"}, None)
    if a.output and a.output.resolve() == a.font.resolve():
        parser.error("refusing to overwrite the input font")
    with a.font.open("rb") as handle:
        signature = handle.read(4)
    base.update({"sha256": sha256(a.font), "size": a.font.stat().st_size})
    if signature == b"ttcf":
        return emit({**base, "valid": False, "verdict": "NOT_SUPPORTED", "exit_code": 3,
                     "reason": "TTC/OTC collection: extract and audit one face at a time"}, a.output)
    if signature not in SFNT_SIGNATURES:
        return emit({**base, "valid": False, "verdict": "NOT_SUPPORTED", "exit_code": 3,
                     "reason": "not an sfnt/WOFF font; engine formats need an adapter and custom_encoding_audit.py"}, a.output)
    try:
        from fontTools.pens.boundsPen import ControlBoundsPen
        from fontTools.ttLib import TTFont
    except ImportError:
        return emit({**base, "valid": False, "verdict": "NOT_RUN", "exit_code": 4, "error": "fontTools_missing"}, a.output)

    corpus = a.corpus.read_text(encoding="utf-8") if a.corpus else VN
    required = scalars(corpus)
    try:
        font = TTFont(str(a.font), lazy=False, recalcBBoxes=False, recalcTimestamp=False)
        cmap: dict[int, str] = {}
        for table in font["cmap"].tables:
            cmap.update(table.cmap)
        glyph_set = font.getGlyphSet()
    except Exception as exc:
        return emit({**base, "valid": False, "verdict": "FAIL", "exit_code": 1,
                     "error": f"font_parse_error:{type(exc).__name__}:{exc}"}, a.output)

    vn_pre, vn_comb, non_composing = build_vietnamese_repertoire(required)
    missing_pre = (required | vn_pre) - set(cmap)
    missing_comb = vn_comb - set(cmap)
    nfd_missing = {ord(p) for cp in required for p in unicodedata.normalize("NFD", chr(cp))
                   if unicodedata.combining(p) and ord(p) not in cmap}
    checked = sorted(cp for cp in (required | vn_pre | vn_comb) if cp in cmap
                     and unicodedata.category(chr(cp)) not in ("Zs", "Cc", "Cf"))
    hmtx = font["hmtx"].metrics if "hmtx" in font else {}
    empty, zero_advance, spacing_marks = [], [], []
    for cp in checked:
        name = cmap[cp]
        pen = ControlBoundsPen(glyph_set)
        try:
            glyph_set[name].draw(pen)
        except Exception:
            pen.bounds = None
        if pen.bounds is None:
            empty.append(cp)
        advance = hmtx.get(name, (None, None))[0]
        if unicodedata.combining(chr(cp)):
            if advance not in (0, None):
                spacing_marks.append(cp)
        elif advance is not None and advance <= 0:
            zero_advance.append(cp)

    tables = sorted(font.keys())
    gpos, gsub = feature_tags(font, "GPOS"), feature_tags(font, "GSUB")
    warnings = []
    os2 = font["OS/2"] if "OS/2" in font else None
    bit29 = bool(os2 and os2.ulUnicodeRange1 & (1 << 29))
    bit57 = bool(os2 and os2.ulUnicodeRange2 & (1 << (57 - 32)))
    if any(0x1E00 <= cp <= 0x1EFF for cp in cmap) and not bit29:
        warnings.append("OS/2 ulUnicodeRange bit 29 (Latin Extended Additional) is unset although U+1E00-U+1EFF is mapped")
    if bit57 and not any(cp > 0xFFFF for cp in cmap):
        warnings.append("OS/2 ulUnicodeRange bit 57 (Non-Plane 0) is set without non-BMP codepoints; likely a misplaced bit 29")
    if "fvar" in tables:
        warnings.append("variable font: only the default instance was audited; masters/instances are NOT_RUN")
    if "CFF2" in tables:
        warnings.append("CFF2 outlines: binary patch backends in this skill do not support CFF2")
    color = [t for t in COLOR_TABLES if t in tables]
    if color:
        warnings.append(f"color/bitmap tables {color}: only base outlines were checked")
    if spacing_marks:
        warnings.append("combining marks with non-zero advance; they will not overlay unless GPOS/renderer zeroes them")

    record_present = "PASS" if not missing_pre and not missing_comb else "FAIL"
    outline_nonempty = "PASS" if not empty else "FAIL"
    metrics_valid = "PASS" if not zero_advance else "FAIL"
    verdict = "PASS" if record_present == outline_nonempty == metrics_valid == "PASS" else "FAIL"
    result = {
        **base,
        "valid": True,
        "corpus_codepoints": len(required),
        "required_codepoints": fmt(required),
        "tables": tables,
        "glyph_count": len(font.getGlyphOrder()),
        "units_per_em": int(font["head"].unitsPerEm) if "head" in font else None,
        "cmap_codepoints": len(cmap),
        "missing_codepoints": fmt(missing_pre),
        "missing_combining_marks": fmt(missing_comb),
        "nfd_missing_marks": fmt(nfd_missing),
        "empty_outline_codepoints": fmt(empty),
        "zero_advance_codepoints": fmt(zero_advance),
        "spacing_combining_marks": fmt(spacing_marks),
        "coverage": {
            "record_present": record_present,
            "mapping_correct": "NOT_RUN",
            "outline_nonempty": outline_nonempty,
            "metrics_valid": metrics_valid,
            "runtime_bound": "NOT_RUN",
        },
        "gpos_features": gpos,
        "gsub_features": gsub,
        "has_mark_feature": "mark" in gpos,
        "has_mkmk_feature": "mkmk" in gpos,
        "has_kern_feature": "kern" in gpos,
        "outline_flavor": outline_flavor(tables),
        "is_variable": "fvar" in tables,
        "os2_unicode_range": {"bit29_latin_extended_additional": bit29, "bit57_non_plane0": bit57},
        "coverage_ok": record_present == "PASS",
        "warnings": warnings,
        "verdict": verdict,
        "exit_code": 0 if verdict == "PASS" else 1,
        "proof_level": "structurally_verified" if verdict == "PASS" else "inventory_only",
    }
    if non_composing:
        result["non_composing_pairs"] = non_composing
    if a.manifest:
        try:
            result["manifest"] = json.loads(a.manifest.read_text(encoding="utf-8"))
        except Exception as exc:
            result["manifest_error"] = f"{type(exc).__name__}:{exc}"
    return emit(result, a.output)


if __name__ == "__main__":
    sys.exit(main())
