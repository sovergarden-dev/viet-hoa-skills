# Luna Abyss: Unreal DataTable/TooltipTable patching without AES

Session lesson: after `.locres` patch pak worked, Bách Khoa/Codex and Options help text remained English because they were cooked DataTable text assets, not `Game.locres`.

## Findings

- `Game.locres` recovered from zlib payload covered many UI labels/dropdowns, but not Codex article bodies or help panels.
- Codex archive text lived in cooked DataTable namespace `CODEX_Codex` near final pak zlib blocks.
- Difficulty help text lived in `/Game/LunaAbyssGame/Text/Tables/TooltipTable`, keys such as:
  - `TT_DIFFICULTYMODES_En1/En2`
  - `TT_DIFFICULTYMODES_STORY_En1/En2`
  - `TT_DIFFICULTYMODES_SCOUT_En1/En2`
  - `TT_DIFFICULTYMODES_WARDEN_En1/En2`
  - `TT_DIFFICULTYMODES_SCOURGE_En1/En2`
- The correct decompressed `TooltipTable` payload size was `119162`; crash reporter showed `Expected 119162`, confirming the expected serial payload size.

## Pitfall: do not override a carved/compressed block as `.uasset`

A bad patch placed raw carved/compressed bytes as:

```text
LunaAbyss/Content/LunaAbyssGame/Text/Tables/TooltipTable.uasset
```

Game crashed:

```text
DataTable /Game/LunaAbyssGame/Text/Tables/TooltipTable.TooltipTable: Serial size mismatch: Got ..., Expected 119162
```

Reason: the bytes were not a complete cooked `.uasset`; the useful tooltip data was the decompressed export payload (`.uexp`-like serial data), and pak compression blocks had to be concatenated/decompressed first.

## Safer recovery workflow

1. Keep the last known-good locres-only patch as rollback.
2. Scan final pak zlib blocks for structural markers: `CODEX_Codex`, `TooltipTable`, `TT_`, `Archive Entry Title`, `Archive Description`.
3. For adjacent zlib streams belonging to one asset, concatenate **decompressed** data in order, not compressed bytes.
4. Validate asset shape:
   - Codex merged stream began with UE package magic `c1 83 2a 9e`, so it can be tried as a `.uasset` override.
   - Tooltip merged stream ended with UE package magic for next file and its first `119162` bytes matched crash `Expected 119162`, so treat it as `.uexp`/export payload, not `.uasset`.
5. Patch FString values structurally:
   - Read 4-byte signed FString length.
   - Positive length = ANSI bytes including null terminator.
   - Negative length = UTF-16LE chars including null terminator.
   - Preserve the original serialized length; pad with spaces/null terminator. Do not shift following bytes unless a full Unreal asset writer is used.
6. For Vietnamese with diacritics, prefer an existing UTF-16 localized slot (`_Fr`, `_Ru`, `_Pl`, etc.) rather than overwriting `_En` ANSI strings. Also copy Vietnamese `.locres` into that culture folder (`fr`, `fr-FR`, etc.) and instruct the user to select that language for DataTable-driven text.
7. Smoke-test only a few screenshot-proven entries first:
   - `Cell_Title/Cell_Quote`
   - `LastStand_Title/LastStand_Quote`
   - `TT_DIFFICULTYMODES_*`
8. If the smoke patch starts and displays accented Vietnamese, expand to the full workbook.

## Context-management lesson

For large localization sessions, do not paste raw CSV/logs/workbooks into chat. Process them from disk and report only paths/counts. If the session nears context limit, branch/compact and continue full-scope work from disk artifacts rather than reducing task scope.