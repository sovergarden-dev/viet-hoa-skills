# Luna Abyss / Unreal encrypted pak zlib locres recovery

## Durable lesson

An encrypted Unreal `.pak` index blocks normal listing/extraction, but some payload blocks may still be individually zlib-compressed and readable. For localization, this can recover valid `.locres` data without AES when the localization resource itself is in an unencrypted compressed block.

Use this as a recovery path after confirming the pak index is encrypted. It is not a DRM bypass; it only reads plaintext/compressed payload bytes already present in the pak.

## Workflow

1. Confirm Unreal and pak state.
   - Engine markers: `Engine/`, project folder, `Content/Paks/*.pak`.
   - `repak info/list <pak>` confirms pak version and whether encrypted index blocks structured extraction.
2. Probe for localization needles.
   - Search payload for `.locres`, `/Game/Localization`, `Default__StringTable`, `StringTable\0`, `GameText\0`, and lore/UI terms.
   - If hits cluster near localization resources, scan nearby bytes for zlib headers: `78 01`, `78 5e`, `78 9c`, `78 da`.
3. Decompress candidate zlib blocks.
   - Try `zlib.decompress(data[offset:offset+~1MB])` from each header.
   - Keep blocks containing UI/lore markers like `BackButton`, `DifficultyScourge`, `ALL-FATHER`, `Fawkes`, `Aylin`, `Greymont`, `Return to Cell`.
   - Reject FMOD/event/bank blocks as metadata unless they contain actual localized subtitle text.
4. Detect valid `.locres`.
   - UE locres magic may start with bytes `0e 14 74 75` (`0x7574140E` little-endian).
   - Do not hand-parse the whole format if a tool exists.
5. Export with an existing locres tool.
   - `akintos/UnrealLocres` can export/import CSV/POT from a recovered `.locres` block.
   - Example:

```bat
UnrealLocres.exe export -f csv -o Game_en_from_zlib_locres.csv recovered_game_en.locres
```

6. Build a clean workbook.
   - Keep `key`, `source`, `target` from locres export as source-of-truth.
   - Add review columns in a separate workbook: `source_type`, `namespace_or_table`, `source_en`, `translation_vi`, `category`, `status`, `notes`.
   - Category flags that helped: `lore_pronoun_check`, `format_check`, `long_text`, `ui_text`, `ui_short`.
7. Validate and rebuild `.locres`.
   - Preserve placeholders `{minutes}`, `{PG}`, tags `<...>`, and newline counts unless intentionally changed.
   - Run an identity import/export smoke test before translating.
   - Example:

```bat
UnrealLocres.exe import -f csv -o Game_vi.locres recovered_game_en.locres Game_vi_import.csv
UnrealLocres.exe export -f csv -o Game_vi_check.csv Game_vi.locres
```

## Packaging caveat

Recovering and rebuilding `Game_vi.locres` is only the text-file step. Delivery still needs a game-accepted path:

- First try a loose localization override if the Unreal build accepts loose files.
- If loose files are ignored, create a patch pak with the correct internal path if it can be inferred and the game accepts unencrypted patch paks.
- If neither works, ask for FModel/UnrealPak export, AES key, or developer-provided localization assets.

## Pitfalls

- Raw string scan is still not release-grade. Use it to locate/decompress blocks, then switch to `UnrealLocres` or another structural parser.
- Some zlib blocks are other languages or engine input-key resources. Score blocks by English markers and reject obvious non-English UI strings.
- StringTable-like payloads may be parseable separately, but without asset path/import path they are lower confidence than valid `.locres` export.
- Do not treat `EncryptionKey` strings from Epic Online Services config as pak AES keys.
