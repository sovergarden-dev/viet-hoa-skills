# Luna Abyss v2 culture separation and dialogue lessons

Session learning from Luna Abyss Vietnamese patch QA.

## Corrections that matter

1. **Never patch English culture when using a foreign technical slot.**
   - A patch pak that copies Vietnamese `Game.locres` into `en/Game.locres` makes English mode show Vietnamese.
   - If `Ru` is the Unicode technical slot, package only `ru/`, `ru-RU/`, and optional `vi/`, `vi-VN/`; keep `en/` untouched.
   - Verify patch pak contents with `repak list` before shipping.

2. **Hardcoded ANSI strings are usually global, not culture-specific.**
   - Patching ANSI map/blueprint text directly can make English mode show Vietnamese too.
   - Only patch hardcoded ANSI text if the user accepts that it is global, or if you can prove it is culture-gated.
   - For a culture-selectable release, exclude/revert global ANSI blocks and document them as untranslated until a culture-aware source is found.

3. **Proper names should usually stay English in Luna Abyss.**
   - User rejected literal Vietnamese calques for names/places/items/monsters: examples like `Sai Lầm Mani`, `Lãnh Địa Sụp Đổ`, `Thương Monarch` sound bad.
   - Keep Codex list/title/subcategory proper nouns English or English-ish, shortening only to fit the existing `Ru` slot cap.
   - Keep descriptive body text Vietnamese.
   - If full English name exceeds the existing FString cap, use a conservative English abbreviation (`Monarch Lance`, `Sorrow Canyon`, `Greymont`, `Breaker`) instead of a Vietnamese calque.

4. **Do not call a build final while dialogue/choices are unpatched.**
   - UI/Codex/Tooltip/locres coverage is not dialogue coverage.
   - QA screenshots showed dialogue and choices still in Russian: `АЙЛИН`, `Как тебе новая камера?`, `Ч-ЧТО ТЫ ТАКОЕ?..`, `ПОЖАЛУЙСТА, НЕ ТРОГАЙ МЕНЯ...`.
   - Exact dialogue strings did not appear as raw text in the pak, nor in the recovered Game locres blocks; the dialogue system likely uses another serialized/culture pipeline.
   - Name interim installers honestly, e.g. `*_no_dialogue_final.exe`, until dialogue/choice source is found and patched.

## Validation checklist additions

Before release:

- Select **English** in-game: verify no Vietnamese in UI/Codex/hardcoded prompts.
- Select **Русский**: verify Vietnamese appears only there.
- `repak list pakchunk99-WindowsNoEditor_P.pak` must not include `Localization/Game/en/Game.locres`.
- Scan/revert global ANSI patches unless culture-gated.
- Check Codex list/title names for awkward translated proper nouns.
- Test a live dialogue scene and at least one choice prompt; if still Russian/English, build is not full translation.

## Single-file installer note

A single `.exe` can be built without PyInstaller by compiling a small C#/.NET Framework installer with `csc.exe` and embedding the ZIP payload as a resource:

- Read root from the `.exe` location, not the current working directory.
- Extract `pakchunk99-WindowsNoEditor_P.pak` from embedded ZIP.
- Read `_vi_patch/manifest.tsv` from embedded ZIP.
- Write zlib block payloads into `LunaAbyss-WindowsNoEditor.pak` by offset.
- Verify block length and SHA256 before writing.

This avoids requiring the user to unzip, but unsigned `.exe` may trigger SmartScreen/AV warnings.
