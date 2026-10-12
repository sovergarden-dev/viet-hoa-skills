# Luna Abyss final Ru-slot release packaging lessons

Use this when an Unreal game has encrypted pak index, no AES key, and player-facing text is recoverable through zlib blocks.

## Final build pattern

1. Use the UTF-16 culture slot that already exists in the DataTable (`*_Ru` in Luna Abyss) as the Vietnamese slot when English/ANSI rows cannot hold accents.
2. Do not ship while `fallback_english*` rows remain in the final CSV. A dry-run with fallback is a test build only.
3. When async/old batch outputs exist in another folder/schema, never copy by batch number. Salvage only by stable keys such as `source_key + normalized source_en`; keep the active workbook schema as source of truth.
4. Validate before writing:
   - all target rows filled
   - no Cyrillic in Vietnamese slot
   - no English fallback statuses
   - placeholders/tags/newlines preserved, normalizing CRLF/LF semantics rather than byte-exact line endings
   - each replacement length <= target slot cap
   - recompressed zlib block fits original compressed length
5. Apply direct compressed-block patch only after dry-run is clean. Then read back from the real pak and verify SHA256 + zlib decompression + sample strings.

## Hardcoded ANSI side pass

Some player-facing toast/tutorial strings may be ANSI FStrings in map/blueprint assets rather than locres/DataTable.

Rules:
- Do not put accented Vietnamese into ANSI rows.
- Use short ASCII Vietnamese only if it fits the original FString capacity.
- After each candidate replacement, recompress the whole zlib block. If it no longer fits, skip/report that row instead of failing the build.
- Treat this as a secondary coverage pass; it must not block the core UTF-16 DataTable release.

## Portable installer package

Do not ship the full 8GB pak. Build a ZIP that mirrors game root and contains:

```text
INSTALL_VI.bat
INSTALL_VI.ps1
README_VI.txt
LunaAbyss/Content/Paks/pakchunk99-WindowsNoEditor_P.pak
_vi_patch/manifest.json
_vi_patch/blocks/block_<n>_<offset>_<length>.bin
_vi_patch/reports/*.json
```

Installer duties:
- Open `LunaAbyss/Content/Paks/LunaAbyss-WindowsNoEditor.pak` read/write.
- For each manifest block, verify file length and SHA256 before writing.
- Seek to manifest offset and write patched compressed bytes.
- Tell user to choose `Русский` if the label cannot be safely renamed; document that it is a technical Vietnamese slot.
- Recovery: delete patch pak, then Steam Verify Integrity.

## Release validation summary

Report exact numbers:
- rows patched by asset/table
- blocks written
- hash/zlib readback errors
- Cyrillic rows
- English fallback rows
- representative sample strings found after readback
- ZIP path, SHA256, `zipfile.testzip()` result
