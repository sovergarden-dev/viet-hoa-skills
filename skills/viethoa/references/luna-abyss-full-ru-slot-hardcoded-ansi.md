# Luna Abyss — full Ru-slot pass + hardcoded ANSI text

Use this when an encrypted-index Unreal pak can be patched only by recompressing known zlib blocks and the chosen target culture is a UTF-16 slot such as `Ru`.

## Lessons captured

1. **Do not ship a “full” patch while lore batches are still English fallback.**
   - A dry-run can pass structurally with English fallback, but final quality requires waiting for translated batch outputs.
   - Track stats separately: `manual`, `translated_*`, `fallback_label_vi`, `fallback_english`, `fallback_english_shortened`.
   - Treat `fallback_english*` as acceptable for safety builds, not for final “full Vietnamese” builds.

2. **Merge translations into one final CSV before patching.**
   - Input: source workbook such as `ru_slot_full_translation_workbook.csv`.
   - Overlay `translated_batch_XX.csv` files.
   - Overlay manual smoke-test translations for rows intentionally excluded from batches.
   - Validate: no blank target, no target over `target_max_chars`, no Cyrillic, placeholders/tags/newlines preserved.

3. **Patch only UTF-16 target slots for Vietnamese with diacritics.**
   - If DataTable target FString is UTF-16, write Vietnamese normally and pad with UTF-16 spaces to preserve original serialized length.
   - If a player-visible hardcoded FString is ANSI, do not insert Vietnamese diacritics. Use ASCII Vietnamese fallback (e.g. `Da them "..." vao Bach Khoa`) or leave it if the zlib block cannot fit.

4. **Hardcoded ANSI player-facing text is a separate pass.**
   - Examples found outside `CODEX_Codex`/`TooltipTable`: Codex unlock toasts and tutorial prompts embedded in map/blueprint assets.
   - These are often ANSI FStrings with fixed length. Translate only if:
     - source string matches exactly,
     - replacement length <= capacity,
     - recompressed zlib block fits the original compressed length.
   - Use a greedy per-row patch attempt: if one replacement makes the block too large, skip that row rather than failing the entire patch.

5. **Report skipped ANSI rows honestly.**
   - Common skip reasons: `skip_no_zlib_fit`, `skip_no_fstring`, `skip_source_mismatch`, non-ANSI/handled elsewhere.
   - These skips are not fatal to the main DataTable/locres patch; document them in QA notes.

6. **Portable installer should store exact compressed block bytes.**
   - Extraction-only cannot write inside an 8GB pak.
   - Package `_vi_patch/blocks/*.bin` plus a manifest of `{offset, length, sha256}` and a PowerShell/BAT installer that writes bytes to `LunaAbyss-WindowsNoEditor.pak`.
   - Build those block bytes from the final computed chunks, not from a stale pak state, unless the pak has already been patched and read back.

## Minimal validation gates

- Dry-run patcher: all DataTable rows patchable, 0 missing keys, 0 cap/Cyrillic/token errors.
- `fallback_english* == 0` for release-quality full Vietnamese build; otherwise call it a safety/test build.
- `zlib.decompress(compressed_block) == patched_decompressed_block` for every chunk.
- Readback from pak after apply finds representative Vietnamese strings in each modified block group.
- `zipfile.testzip() is None` and SHA256 reported for the portable ZIP.
