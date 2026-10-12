# Unity Adventure Creator IMGUI font and locale-table localization

## Trigger

Use when Adventure Creator dialogue strings localize correctly, but subtitles keep an unattractive/mixed font, and item names/descriptions or other UI remain in English.

## Renderer proof before any font patch

1. Do not infer the live renderer from a serialized prefab hierarchy. A project can contain `TextMeshProUGUI` and `UnityEngine.UI.Text` components while Adventure Creator renders the visible menu through IMGUI.
2. Trace `AC.PlayerMenus.SetStyles(MenuElement)` and `AC.MenuLabel.Display(...)` in `AC.dll`:
   - IMGUI path sets `GUIStyle.font = MenuElement.font` and `GUIStyle.fontSize = MenuElement.GetFontSize()`.
   - `MenuLabel.Display` ultimately calls `GUI.Label(...)`.
3. A safe read-only runtime probe may use BepInEx + Harmony postfix on `PlayerMenus.SetStyles`. Match the original argument name exactly (`element`); HarmonyX rejects a mismatched patch parameter name.
4. Log only the target `MenuLabel` identity (`title`, `labelType`), font name/instance ID, size and scale. Do not mutate `PreDisplay`, input or dialogue state while discovering the route.
5. If runtime reports `TMP=0` and `UGUI=0`, do not keep patching TMP assets. Confirm the IMGUI path instead.

## Exact font-fix pattern

For a proven Adventure Creator IMGUI subtitle element:

1. Build a Vietnamese-capable font artifact in the matching Unity LTS line. Audit requested glyph coverage and missing glyph count.
2. An AssetBundle built around a `TMP_FontAsset` may not return its source font through `LoadAllAssets<Font>()`. Load the TMP asset, then resolve the legacy font through `TMP_FontAsset.sourceFontFile`.
3. Patch only the exact `MenuLabel` used for dialogue (for example `title == "Line"`) at `PlayerMenus.SetStyles`, before the style copies `MenuElement.font`.
4. Keep `AC.dll` unchanged. Removing the plugin and bundle must fully roll back the font fix.
5. Runtime gates: dialogue/input still advance, ASCII and Vietnamese use one face/baseline/weight, no tofu, diacritic collision, clipping or bad wrapping.

## Dangerous anti-patterns

- Do not patch `AC.MenuLabel.PreDisplay` to test font size/style. Exceptions there can leave Adventure Creator waiting forever, remove dialogue and block input.
- Do not accept serialized pointer/style/material changes as live proof. If screenshots are pixel-identical, rollback immediately.
- Do not repeatedly edit unrelated TMP font assets, materials or prefab consumers after the live renderer is proven as IMGUI.
- Do not use rich-text `<font>` tags unless the exact renderer parses them; Adventure Creator IMGUI can display the tags literally.

## Separate locale tables

Adventure Creator speech and non-dialogue UI can have different owners:

- Speech may live in `SpeechManager.lines[].translationText[languageIndex]`.
- Item names/descriptions, documents, settings and prompts may live in a separate structured localization table.

When a screenshot shows untranslated item/UI text after dialogue is complete:

1. Search the exact visible string to identify its serialized owner.
2. Decode all language-table objects and a key registry. Require exact key/count alignment between authoritative Chinese and English reference tables.
3. Inventory the entire table; do not patch only the screenshot string. Classify item, document and UI rows, excluding only proven empty/non-player-facing placeholders.
4. Import into the runtime language slot on a copy, reload every target, preserve source-language objects, and require a changed-object whitelist.
5. Runtime QA at least one item name/description, a different item, a long document and representative system UI.

## External-return integrity lessons

- External claims such as “all line breaks preserved” are not evidence. Compare exact newline sequences, including CRLF versus LF, in both immutable fields and targets.
- Restore every immutable field from canonical input during merge; never carry an external copy merely because it looks equivalent.
- Partial acceptance is valid: accept independently clean rows and requeue only exact failing keys in a separately named immutable rework input.
- An empty target marked `translated` is invalid unless the canonical Chinese and English fields are both empty and the row is a proven placeholder; mark it excluded instead.

## Verification receipt

Record:

- exact build and original hashes;
- live renderer/font evidence;
- plugin and font-bundle SHA-256;
- localization table owner/path ID;
- row count, ordered key-set hash and accepted/excluded counts;
- changed-object whitelist and patched hashes;
- runtime screenshots for subtitle, item and long-document checkpoints.
