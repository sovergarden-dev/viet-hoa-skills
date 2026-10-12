# Mortal Shell II Demo — UE5 `.locres` via RU culture slot

Session pattern worth reusing for Unreal demo/full-release prep.

## Findings

- Game root: `<SteamLibrary>\steamapps\common\Mortal Shell II Demo`.
- Project: `MortalShell2`.
- Main pak: `MortalShell2\Content\Paks\pakchunk0-Windows.pak`.
- Pak info from `repak`: mount point `../../../`, version `V11`, index not encrypted, compression `Oodle`, path hash seed `05D06DBE`.
- Primary localization path inside pak: `MortalShell2/Content/Localization/Game/*/Game.locres`.
- No loose `.locres`; extract from pak.
- `Game.locres` exported with `UnrealLocres` contains 7,429 rows per culture.
- Dialogue is included in `Game.locres` (`Dialogue_*` keys). Many cooked `ST_Core_*` StringTable assets exist, but first pass can treat compiled `.locres` as source of truth unless QA finds missing strings.
- In this demo, loose patch paks placed beside the originals (`pakchunk99-Windows_VietHoa_P.pak`, then `pakchunk0-Windows_P.pak`) existed in Explorer and were readable with `repak`, but the game still showed Russian. Direct original-pak replacement was required for the test build.

## Workflow

1. Create `_viet_work` under the game root; do not edit originals.
2. Use local tools:
   - `repak.exe info/list/unpack`
   - `UnrealLocres.exe export/import`
3. Extract only localization first:
   ```bat
   repak.exe unpack "...\pakchunk0-Windows.pak" --output "...\_viet_work\extracted\pakchunk0" --include "MortalShell2/Content/Localization/Game/*"
   ```
4. Export `en` and chosen technical culture (`ru`) to CSV:
   ```bat
   UnrealLocres.exe export -f csv -o Game_en_locres.csv "...\en\Game.locres"
   UnrealLocres.exe export -f csv -o Game_ru_locres.csv "...\ru\Game.locres"
   ```
5. Build workbook keyed by `key`, with columns: `source_en`, `reference_ru`, `vietnamese`, `status`, `category`, `note`.
6. Use `ru` as Vietnamese slot; keep `en` clean.
7. Preserve all rich tags/placeholders/newline counts. Mask before MT:
   - `<Bold>`, `</>`, `<img id="R1"/>`
   - `{ShellID}` style placeholders
   - locked lore terms/proper nouns (`Shell`, `Beacon`, `Gloom`, `Tarstone`, `Mether`, `Undermether`, `Passenger`, names)
8. Import Vietnamese CSV into the original `ru/Game.locres`:
   ```bat
   UnrealLocres.exe import -f csv -o "patch\root\MortalShell2\Content\Localization\Game\ru\Game.locres" "...\ru\Game.locres" "Game_ru_vi_import.csv"
   ```
   Important: `UnrealLocres import` matches by `key + current source`. For a `ru` slot import CSV, keep the original Russian text in `source` and put Vietnamese in `target`. If you put Vietnamese in `source` and leave `target` blank, the tool can report `Imported 0 translations` while still writing an unchanged locres.
9. Pack a loose patch first with matching pak settings. `repak info` prints the path hash seed as hex (`05D06DBE`), but `repak pack --path-hash-seed` expects decimal (`97545662`):
   ```bat
   repak.exe pack --version V11 --path-hash-seed 97545662 "patch\root" "package\pakchunk0-Windows_P.pak"
   ```
   Prefer uncompressed (`compression: None`) for tiny locres-only patch paks unless a matching compressed build has been proven in-game.
10. Verify the patch pak contains `MortalShell2/Content/Localization/Game/ru/Game.locres` and export it back with `UnrealLocres` to confirm sample strings (`New Game = Chơi mới`, `Language = Ngôn ngữ`, Cyrillic leftovers `0`).
11. Install the loose patch by copying `pakchunk0-Windows_P.pak` into `MortalShell2\Content\Paks`; uninstall by deleting it. If a nonstandard name like `pakchunk99-Windows_VietHoa_P.pak` appears in Explorer but the game still shows Russian, rename/repack to `pakchunk0-Windows_P.pak` before considering direct original-pak edits.
12. If `pakchunk0-Windows_P.pak` still does not affect in-game Russian after a full restart, treat loose-pak mounting/priority as failed for that build. With user approval, create a backup and replace the original pak content:
   ```bat
   copy "MortalShell2\Content\Paks\pakchunk0-Windows.pak" "_viet_work\backups\pakchunk0-Windows.pak.original"
   repak.exe unpack "_viet_work\backups\pakchunk0-Windows.pak.original" --output "_viet_work\patch\pakchunk0_full_unpack"
   copy "_viet_work\patch\root\MortalShell2\Content\Localization\Game\ru\Game.locres" "_viet_work\patch\pakchunk0_full_unpack\MortalShell2\Content\Localization\Game\ru\Game.locres"
   repak.exe pack --version V11 --path-hash-seed 97545662 --compression Oodle "_viet_work\patch\pakchunk0_full_unpack" "_viet_work\patch\pakchunk0-Windows.pak"
   copy "_viet_work\patch\pakchunk0-Windows.pak" "MortalShell2\Content\Paks\pakchunk0-Windows.pak"
   ```
   Remove any loose patch paks during this test to avoid confusion. Verify by unpacking only `ru/Game.locres` from the installed `pakchunk0-Windows.pak` and exporting it back.
13. For testing on another computer, package a portable direct-pak test folder rather than assuming a patch pak will mount. Include:
   - patched `pakchunk0-Windows.pak`
   - `Cai_VietHoa_Test.bat` that asks for the game root, backs up `MortalShell2\Content\Paks\pakchunk0-Windows.pak` to `pakchunk0-Windows.pak.viethoa_backup_original`, then copies the patched pak
   - `Go_VietHoa_Test.bat` that restores that backup
   - README with SHA256, install path, Russian-slot instruction, and Steam Verify warning

## Pitfalls

- A minimal handwritten UE4 pak parser is not worth it for UE5 V11 pak with path hash/full directory/encoded entries. Use `repak` once the pak is readable.
- `UnrealLocres export` CSV uses columns `key,source,target`; exported localized text may be in `source`, not `target`.
- `UnrealLocres import` requires the CSV `source` to match the current locres culture source; for RU-slot replacement, `source=original Russian`, `target=Vietnamese`.
- Do not classify short visible UI like `Yes`, `No`, `Language`, `Continue` as non-text just because it is short or generic.
- Google translate endpoint is useful for large first-pass MT, but use cache/resume and mask terms/tags. Do not paste large dictionaries into shell commands; write scripts.
- A loose patch pak can be structurally valid yet not load/override in-game. Screenshot QA wins over file-level QA. If the screenshot still shows Russian, either find logs proving mount failure or switch to direct-pak test with a backup.
- Direct-pak test builds are not clean release patches. Document that Steam Verify will restore the original and remove the localization.
- If a later QA screenshot shows English/Russian outside `.locres`, inspect cooked DataTable/StringTable/widget defaults next rather than expanding raw binary scans into release source.

## Reusable outputs

- `translation_cache_google_en_vi.json` for resumable MT cache.
- `translation_report.json` with status counts and validation issue counts.
- `build_patch_report.json` with pak path, install target, pak size, import/pack outputs.
- `direct_pak_patch_report.json` with backup path/hash and installed patched pak hash.
- Portable direct-pak test ZIP for external machines when loose patch paks do not mount.
