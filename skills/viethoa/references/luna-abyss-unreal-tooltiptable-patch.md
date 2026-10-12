# Luna Abyss Unreal `TooltipTable` patch without AES

Session lesson: a patch pak can successfully override `Game.locres` while some settings/help text remains English because it is not in the localization target. In Luna Abyss the right-side Options description panel came from a cooked DataTable asset:

```text
/Game/LunaAbyssGame/Text/Tables/TooltipTable
```

Relevant rows found in zlib-compressed asset payload:

```text
TT_DIFFICULTYMODES_En1
TT_DIFFICULTYMODES_En2
TT_DIFFICULTYMODES_STORY_En1 / En2
TT_DIFFICULTYMODES_SCOUT_En1 / En2
TT_DIFFICULTYMODES_WARDEN_En1 / En2
TT_DIFFICULTYMODES_SCOURGE_En1 / En2
```

## Detection pattern

If in-game screenshot shows:
- labels/tabs/dropdowns translated from `Game.locres`, but
- the right-side help/tooltip panel remains English,

then do not keep changing `Game.locres`. Search for `TooltipTable`, `TT_*`, or exact help strings in zlib-compressed UI asset regions.

Useful scan targets:

```text
DIFFICULTY MODES
Adjusts difficulty mode
STORY MODE:
SCOUT MODE:
WARDEN MODE:
SCOURGE MODE:
associated accessibility
TooltipTable
/Game/LunaAbyssGame/Text/Tables/TooltipTable
```

The source asset path was found by scanning printable context around `TooltipTable` and `TT_DIFFICULTYMODES` hits. In this session, the important zlib streams were inside `TooltipTable.uasset`; decompressed blocks exposed cooked DataTable rows.

## Patch strategy

Best path: use FModel/UE tooling to export/edit/reimport `TooltipTable.uasset` cleanly.

Fallback path when there is no AES/index but the payload is readable:
1. Carve the cooked asset range around `/Game/LunaAbyssGame/Text/Tables/TooltipTable`.
2. Locate zlib streams inside the asset.
3. Decompress streams.
4. Patch only `FString` values for `_En` keys used by the current game language.
5. Keep replacement strings no longer than the original FString capacity.
6. Recompress each zlib stream so it fits in the original compressed byte span; pad with zeros if smaller.
7. Reinsert streams into the carved `.uasset` without changing asset byte length.
8. Pack the overridden asset in a patch pak using the exact cooked path:

```text
LunaAbyss/Content/LunaAbyssGame/Text/Tables/TooltipTable.uasset
```

Pair it with the working `Game.locres` override in the same patch pak.

## Important constraints

- Direct cooked-asset patching is layout-sensitive. Do not change serialized sizes unless you are rebuilding the asset with proper Unreal tooling.
- For byte-stable fallback patches, prefer ASCII/no-accent Vietnamese in `TooltipTable` if needed to stay under the original byte length and avoid UTF-8/font/layout surprises. Keep normal accented Vietnamese in `.locres` where supported.
- Validate after patch by decompressing the modified stream and checking patched keys still exist and no replacement spills into the next row.
- `repak list` should show both localization files and the DataTable override, e.g.:

```text
LunaAbyss/Content/Localization/Game/en/Game.locres
LunaAbyss/Content/Localization/Game/vi/Game.locres
LunaAbyss/Content/Localization/Game/vi-VN/Game.locres
LunaAbyss/Content/LunaAbyssGame/Text/Tables/TooltipTable.uasset
```

## Pitfall

Do not conclude patch pak failed just because one panel remains English. If other UI is translated, the patch path works; the missing text likely comes from a separate DataTable/StringTable/Widget asset rather than the locres target.
