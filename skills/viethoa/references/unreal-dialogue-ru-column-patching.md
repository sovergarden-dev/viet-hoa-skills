# Unreal dialogue tables: patch culture column, not source text

Session lesson from Luna Abyss.

## When it applies

Use this when UI/Codex/Tooltip are localized but in-game dialogue and choices still show a foreign language after selecting the technical Unicode slot.

## Key finding

Some Unreal games store dialogue outside `.locres` and outside Codex/Tooltip DataTables. Luna Abyss used cooked dialogue CSV/DataTable assets under paths like:

- `/Game/.../UI/Dialog/CSV/CELL_Dialog`
- `/Game/.../UI/Dialog/CSV/AETHER_Dialog`
- `/Game/.../UI/Dialog/CSV/CANYON_Dialog`
- `/Game/.../UI/Dialog/CSV/CITY_Dialog`
- `/Game/.../UI/Dialog/CSV/DRIFT_Dialog`
- `/Game/.../UI/Dialog/CSV/FREYA_Dialog`
- `/Game/.../UI/Dialog/CSV/HUB_Dialog`
- `/Game/.../UI/Dialog/CSV/MEADOWS_Dialog`
- `/Game/.../UI/Dialog/CSV/SKY_Dialog`
- `/Game/.../UI/Dialog/CSV/WOMB_Dialog`

The row structure had per-language columns such as:

- `enDialogText`
- `frDialogText`
- `deDialogText`
- `esDialogText`
- `ruDialogText`
- `ptDialogText`
- `plDialogText`

Patch only the target culture column (`ruDialogText` here). Do **not** patch `enDialogText` or the source text, or English culture will be polluted.

## Workflow

1. Confirm the visible foreign dialogue with exact strings from screenshots.
2. Search for dialogue asset paths, not only exact text:
   - `UI/Dialog/CSV`
   - `*_Dialog`
   - `ruDialogText`
   - `enDialogText`
   - `DialogText`, `Response`, `Choice`
3. Extract/decompress nearby zlib blocks and parse Unreal FStrings.
4. Detect row starts as `RowID, Speaker, ..., TRUE/FALSE`, then collect per-language text fields.
5. Because CJK/Korean/Japanese may be filtered out during English/Russian extraction, the retained order may be `en, fr, de, es, ru, pt, pl`; Russian is still index `4` in that filtered set.
6. For player choices, each language text may appear twice. Detect `k=2` when the first two English strings are identical; patch both Russian slots.
7. Translate from `enDialogText`, fit into the existing `ruDialogText` FString cap, and patch the UTF-16 slot in place.
8. Recompress each zlib block and require the new compressed stream to fit the original consumed/allocated block size.
9. Read back every patched `ruDialogText` and fail QA if any target slot still contains Cyrillic.
10. Patch `ru[name]...` speaker labels separately. Keep proper names in English where possible; shorten only when the old Russian FString cap forces it.

## Pitfalls

- Do not keep searching `.locres` after you have confirmed dialogue columns exist. Dialogue may not use locres at all.
- Do not patch hardcoded ANSI/global strings unless you are willing to affect every culture. If English must stay clean, avoid global ANSI patches.
- Do not infer repeated-language count from `len(texts)//language_count`; unrelated row-link strings can inflate the count. Detect duplicated English values instead.
- Do not call a build “final” while dialogue/choice rows still show foreign text. Ship a clearly named test build if only priority rows are patched.

## QA checklist

- English culture has no Vietnamese in UI/dialogue.
- Technical Unicode slot (`Ru` in Luna Abyss) has:
  - `ruDialogText`: all translated, no Cyrillic.
  - `ru[name]`: no Cyrillic speaker tags.
  - Screenshot probes no longer find old strings such as `Как тебе новая камера?`.
- Exact readback validates every patched FString equals `translation_vi`.
- Installer/package includes all dialogue block reports, not just Codex/Tooltip blocks.
