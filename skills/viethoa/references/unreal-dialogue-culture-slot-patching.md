# Unreal dialogue tables: culture-slot patching notes

Use when a game has UI/Codex translated but dialogue/choices stay in another language.

## Lessons from Luna Abyss

- Do not assume dialogue is in `.locres`. Luna Abyss stored many lines in cooked DataTables under paths like `/Game/LunaAbyssGame/UI/Dialog/CSV/*_Dialog`.
- These tables can contain per-language columns such as `enDialogText`, `ruDialogText`, `frDialogText`, etc. Patch the target culture column only. Do not patch source/global text if English must remain clean.
- For a technical Vietnamese slot (`Ru`/`Русский`), patch only `ruDialogText` or `Ru` fields. Keep `enDialogText` and `en/Game.locres` untouched.
- Dialogue choices may duplicate each language value in adjacent FStrings. Patch both duplicate `ruDialogText` values when the UI uses one for label and one for selected/answer state.
- Row data may include link row IDs between metadata and localized text. Do not treat every row-ID-looking FString as a new row; a true row start is usually: `RowID`, `Speaker`, numeric metadata, numeric metadata, `TRUE/FALSE`.
- Some language strings are UTF-16 while English may be ANSI. Preserve the storage encoding/slot size. For UTF-16 FString replacement: update length to `-(len(text)+1)`, write UTF-16LE text plus null, pad remaining bytes with zeroes.
- Recompress each zlib block and require compressed size <= original consumed/target length. If it does not fit, shorten the Vietnamese text; do not expand cooked asset structures.

## QA rules

- English culture must stay untouched: no `en/Game.locres`, no hardcoded ANSI/global Vietnamese patches if they appear in all cultures.
- Final builds must not be labelled final while dialogue/choices remain Russian or English fallback.
- For user-facing proper nouns in game localization, prefer keeping English names for places/characters/factions/items/monsters unless a Vietnamese rendering is natural and requested.
- For installer packaging, include dialogue patch blocks in the manifest along with DataTable/Codex blocks; verify readback by searching old Russian and new Vietnamese in the patched decompressed block.
