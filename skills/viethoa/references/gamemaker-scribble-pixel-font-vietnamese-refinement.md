# GameMaker Scribble Pixel Font Vietnamese Refinement

## 1. Scribble External .yy Synchronization Protocol
In GameMaker games utilizing the Scribble text engine (e.g. `initate_scribble`, `scribble_add_font`):
- Scribble parses the `.yy` JSON file located in the game directory (`font_normal.yy`, `font_dialog.yy`, `font_header.yy`) to retrieve glyph layout coordinates `(SourceX, SourceY, SourceWidth, SourceHeight, Shift, Offset)`.
- If `data.win` embedded font texture atlas is modified (new dimensions, re-packed glyph positions), the external `.yy` files on disk MUST be strictly bit-for-bit synchronized with the exact texture coordinates.
- Failure to synchronize `.yy` files causes severe character offset mapping mismatches, turning dialogue into mojibake or random shifted characters (e.g. 'T' mapping to 'Ẹ̈').

## 2. Pixel Art Vietnamese Diacritic Rules for 12-16px Retro Fonts
On low-resolution bitmap fonts (x-height 5-8px, bounding box 12-16px):
1. **Circumflex + Acute (`ế, ấ, ố`)**:
   - Never place circumflex and acute side-by-side at equal heights; it forms an undulating horizontal wave reading as tilde `~` (e.g. `chiến` -> `chiễn`, `tiến` -> `tiễn`).
   - Draw a symmetrical circumflex roof at rows 2-3 (`..###....` / `.##..##..`) and place a bold 2-pixel acute slash at row 1 on the right slope (`.....##..`). Keep row 0 empty.
2. **Breve + Acute (`ắ`)**:
   - Never connect the right wing of the breve cup to the acute slash; it forms a continuous checkmark `✓` (Nike swoosh).
   - Draw a symmetrical breve cup at rows 2-3 (`.##..##.` / `..####...`) and float the acute slash at row 0-1 above the right wing with 1px clearance.
3. **Breve + Grave (`ằ`)**:
   - Do not merge the grave mark into the left wing of the breve (resembles a plain `ă` or `đăng`). Float the grave at row 0-1 above the left wing with 1px clearance.
4. **Standalone Tilde (`ã, ẽ, ĩ, õ, ũ, ỹ`)**:
   - Never draw a symmetrical curve with both ends high and center low; this forms a U-shape/bowl identical to breve `ă`, causing `quãng` to be read as `quăng`.
   - Use a clean 2-row stepped wave descending from left to right: row 2 left 4px (`.####....`), row 3 right 4px (`....####.`).
5. **Circumflex + Hook (`ể, ẩ, ổ`)**:
   - Circumflex apex at row 2 col 2, wings at row 3 cols 1 & 3; hook top loop at row 1 cols 5-6, spine at row 2 col 6.
   - Maintain 3px of negative space between apex and hook to prevent clumping.
6. **Horn Vowels (`ơ, ư`) Kerning**:
   - Keep within standard glyph width (w=9). Integrate the horn directly into the right shoulder/stem (cols 7-8, rows 3-4) rather than widening to col 10-11, leaving 4px of negative space to prevent clashing with the dot on an adjacent `i` (as in `thời`).
7. **Dot Below (`ạ, ẹ, ị, ọ, ụ`)**:
   - Lowercase baseline ends at row 12. Row 13 MUST be 100% empty negative space, and the dot placed at row 14 (cols 4-5) to prevent fusing with the bottom of `o` into a `q` shape.

## 3. GameMaker C++ YYC Locale / Case-conversion Pitfall
- GameMaker YYC uses standard CRT `towupper` in "C" locale. For non-ASCII Unicode characters outside Latin-1, `towupper` fails to convert lowercase Vietnamese letters (`ắ, ầ, ặ, ộ, ũ, ơ`).
- In UI and Menu strings that game code displays via `string_upper()`, strings in `lang.json` MUST be stored in pre-uppercased form (ALL CAPS, e.g. `BẮT ĐẦU TRÒ CHƠI`, `CÀI ĐẶT`, `ĐỘI NGŨ SẢN XUẤT`, `THOÁT TRÒ CHƠI`) to avoid ANSI fallback to German umlauts (`Ä, Ó, Ô, Ü`).
