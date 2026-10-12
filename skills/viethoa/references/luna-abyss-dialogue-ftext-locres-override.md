# Luna Abyss dialogue/choices: FText keys and culture-safe locres override

Session lesson: dialogue/choices may live in cooked DataTables as `FText` with stable GUID keys, not in the same `.locres` or Codex/Tooltip tables already patched.

## Symptoms

- UI/Codex/Tooltip translate correctly in a technical culture slot (`Ru`).
- English culture must stay fully English.
- Dialogue/choice UI still shows Russian or untranslated text.
- Exact Russian strings from screenshots may not appear in raw pak/zlib searches.

## Correct search path

1. Stop broad scans for names like `AYLIN`; they match FMOD paths, asset names, camera/sequencer assets, and metadata.
2. Search high-signal phrases first, but do not block on exact OCR text:
   - Russian: `Как тебе`, `новая камера`, `Ч-ЧТО`, `ТРОГАЙ МЕНЯ`.
   - English: `How do you like`, `new cell`, `WHAT ARE YOU`, `touch me`.
3. Inspect dialogue system assets and DataTables:
   - `/Game/LunaAbyssPrototye/AnonsDialogSystem/Data/DT_Dialog`
   - `/Game/LunaAbyssPrototye/AnonsDialogSystem/Data/Dialog_Struct`
   - UI/dialogue widgets such as `W_DialogBox`, `W_DialogEntry`, `BP_DialogSystem`.
4. For Luna Abyss, `DT_Dialog` exposed fields:
   - `DialogText`
   - `DialogName`
   - `Response1..4`
   - `Answer1..4`
   - `DialogAudio`, `ResponseAudio`, `DialogEventID`.
5. Extract dialogue-like English source rows and the adjacent FText GUID keys. Cooked FText in this project appeared as an ASCII source string immediately preceded by a 32-hex GUID key FString; locres exporter represents keys as `/GUID`.

## Culture-safe patch rule

Do **not** patch `DT_Dialog` source strings directly if English must remain clean. Direct DataTable edits are culture-agnostic and will Vietnamese-leak into English.

Preferred approach:

1. Build a dialogue workbook from FText keys:
   - `key` like `/75FC8AF94708619E689D73B97E024ECF`
   - `source_en`
   - `translation_vi`
   - `speaker` / `addressee` if recoverable
2. Add those key/source/target rows to the `ru` locres used by the patch pak.
3. Pack only `ru/Game.locres` and `ru-RU/Game.locres` (plus optional `vi/vi-VN`), not `en`.
4. Verify English mode stays English before calling the package final.

## Tool caveat

`UnrealLocres import` updates existing keys but does not add new keys to an existing locres. A fake-key test exported no added key after import.

Implication: if dialogue FText keys are not already present in the locres you are modifying, either:

- find the locres target that already contains those keys and edit it; or
- use/implement a locres writer/merge path that can add new keys, then merge into the target culture locres.

`UnrealLocres merge` may help if you can generate a source locres containing the extra dialogue keys. Otherwise read the tool/source format or write a small locres builder.

## Minimal locres add-key writer pattern

For Luna Abyss, a compact-version locres writer was enough to add new dialogue keys while staying culture-specific:

1. Parse the existing translated `Game.locres`.
   - Magic: `0e147475674a03fc4a15909dc3377f1b`.
   - Version byte `3` = optimized/cityhash form in the shipped locres.
   - Read string-table offset, namespace count, namespace/key strings, `sourceStringHash`, and string table entries.
2. Add dialogue rows under the empty namespace for keys exported as `/GUID`.
3. Compute `sourceStringHash` with UE `FCrc::StrCrc32`, not Python `zlib.crc32`.
   - UE hashes each UTF-16/TCHAR code unit as four 8-bit CRC steps.
   - Sanity check: `zlib.crc32()` will not match existing locres source hashes.
4. Save as compact locres version `1` to avoid key-hash/cityhash requirements.
   - Write magic, version byte `1`, string-table offset placeholder, namespace count.
   - For each namespace: UnrealString namespace, key count, UnrealString key, `uint32 sourceStringHash`, `int32 stringTableIndex`.
   - Then write string table count and UnrealString localized values; patch the string-table offset.
5. Export the result with `UnrealLocres export` to verify the added keys survive.
   - Expected proof: row count increases, e.g. `473 -> 600`, and sample keys like `/45FE...` export with Vietnamese target text.

This avoids direct DataTable edits, so English culture remains clean. Treat it as a test build until in-game dialogue confirms the runtime looks up those FText keys from the patched `ru/Game.locres`.

## Verification

- Scan current patch pak: no `en/Game.locres`.
- English culture: no Vietnamese in UI/dialogue.
- `Ru` culture: dialogue lines and choices show Vietnamese.
- No Cyrillic remains in player-facing `Ru` dialogue.
- Do not ship as final if dialogue/choices remain untranslated, even if Codex/UI are complete.
