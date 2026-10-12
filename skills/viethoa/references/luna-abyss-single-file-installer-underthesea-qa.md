# Luna Abyss: Underthesea QA and single-file installer packaging

Session learning: after a full Luna Abyss Vietnamese build appeared complete, an optional underthesea QA pass found a real leftover English vertical-layout locres row (`Archive Entry List`). The fix was to preserve the exact CRLF layout while replacing visible letters with Vietnamese.

## Underthesea QA pattern

Use underthesea only after structural extraction/import validation has passed.

Recommended scope:
- DataTable final CSV (`ru_slot_final_translation.csv`).
- Locres final workbook (`LunaAbyss_translation_workbook_final_vi.csv`).
- Report-only CSV/JSON output.

Hard failures remain structural/stdlib checks:
- blank translated target;
- placeholder/tag/control-code mismatch;
- Cyrillic left in the Vietnamese target;
- fallback English in release-scope rows;
- decompressed block/hash/readback failure.

Underthesea warnings need review, not automatic failure:
- `lang_detect_*` is noisy on short uppercase Vietnamese UI, names, vendor terms, and glitch typography.
- `text_normalize` produces many diffs for uppercase/glitch/control-text rows; do not auto-apply if the row has placeholders, tags, backslashes, `%` tokens, or deliberate layout.
- Still inspect `lang_detect_en`/`maybe_english_leftover`; in this session it caught a true leftover vertical English row.

## Vertical text fix pattern

If a locres row is vertical text (`A\r\nr\r\nc...`) and must preserve layout:
1. Count source `\r` and `\n` separately.
2. Build Vietnamese vertical text with the same counts.
3. Update workbook status to a manual vertical-layout status.
4. Rebuild locres and confirm `Translated N / N (100%)`.

Example replacement used:

```text
D\r\nA\r\nN\r\nH\r\nS\r\nÁ\r\nC\r\nH\r\n\r\nB\r\nÁ\r\nC\r\nH\r\n\r\nK\r\nH\r\nO\r\nA
```

This preserved the original `Archive Entry List` vertical layout while making the visible text Vietnamese (`DANH SÁCH BÁCH KHOA`).

## Release completeness check

Do not rely on subagent success messages when API quota/errors happened mid-translation. Verify from disk:
- all batch files expected by the active workbook exist;
- final DataTable CSV has all `translation_vi` filled;
- locres workbook/import reaches 100%;
- no `fallback_english*` statuses remain in final release CSV;
- QA report has zero hard issues;
- zlib block hashes/decompression read back from the target pak.

## Single-file installer pattern

A ZIP with `INSTALL_VI.bat` is acceptable, but a one-file installer is easier for users: copy one file into the game root and run it.

For Windows without a .NET SDK, use the built-in .NET Framework compiler if present:

```bat
C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe ^
  /nologo /optimize+ /platform:x64 /target:exe ^
  /out:LunaAbyss_VietHoa_Installer.exe ^
  /resource:LunaAbyss_VietHoa_Final_extract_to_game_then_INSTALL_VI.zip,payload.zip ^
  /r:System.IO.Compression.dll /r:System.IO.Compression.FileSystem.dll ^
  LunaAbyssVietHoaInstaller.cs
```

Installer design:
- Determine game root from the `.exe` location, not current working directory.
- Require `LunaAbyss/Content/Paks/LunaAbyss-WindowsNoEditor.pak` relative to that root.
- Embed the final payload ZIP as a managed resource (`payload.zip`).
- Include `_vi_patch/manifest.tsv` in the payload to avoid JSON parsing dependencies in .NET Framework.
- Extract only `pakchunk99-WindowsNoEditor_P.pak`; stream block `.bin` entries from the embedded ZIP directly into the original pak offsets.
- Verify every embedded block length and SHA256 before writing.
- Write a small install report beside the `.exe`.
- Do not copy/back up the full 8GB pak by default; tell users to restore with Steam Verify Integrity.

Pitfall: IExpress can build a single EXE but is awkward for this class because the payload extracts to temp and the installer may lose the original launch/game-root directory. A tiny C# self-extractor that uses `Assembly.GetExecutingAssembly().Location` is more reliable.

## Expected final user instructions

```text
1. Copy LunaAbyss_VietHoa_Installer.exe into the Luna Abyss game root, where LunaAbyss\Content\Paks exists.
2. Run the EXE.
3. In game, choose Русский. This is the technical Vietnamese Unicode slot.
4. If recovery is needed: delete pakchunk99-WindowsNoEditor_P.pak and Steam > Verify integrity.
```
