# Unity TMP Vietnamese font debugging

## Trigger
Vietnamese localization strings reload correctly but runtime renders `□` for accented characters.

## Required split: UI.Text vs TextMeshPro
Do not infer renderer from a screenshot or only inspect `Font.m_FontData` cmap.

1. Inventory font pointers across all serialized files, including `resources.assets`, `level*`, and `sharedassets*.assets`.
2. Resolve the actual screen prefab hierarchy from its named `GameObject` (for example `Options Panel`) to descendants.
3. Identify renderer by MonoScript:
   - `UnityEngine.UI.Text`: update `m_FontData.m_Font` with a type-tree write.
   - `TMPro.TextMeshProUGUI`: inspect the TMP component's `m_fontAsset` pointer and the referenced `TMP_FontAsset` atlas.
4. For TMP, distinguish a source TTF's Unicode cmap from the prebuilt TMP `m_CharacterTable`: the latter is what determines whether a static atlas can render a glyph.
5. If menu text uses a static TMP SDF atlas, replacing unrelated legacy `UI.Text` font references cannot fix it.

## Proven diagnostic evidence in this Unity 2020 IL2CPP layout
- `resources.assets` had 82 `UnityEngine.UI.Text` references to legacy `Perfect DOS VGA 437`; replacing them with Roboto was structurally valid but did not change the menu screenshot.
- The actual Options hierarchy used `TextMeshProUGUI` components.
- Its TMP text field pointed externally to `sharedassets0.assets:path_id=7`, a static `CormorantGaramond-Light SDF` asset. That static atlas lacked Vietnamese glyphs.
- Existing `NotoSans-Light SDF` in `resources.assets` was dynamic and its source TTF had Vietnamese cmap coverage, but its prebuilt character table was almost empty. It must be runtime-tested before declaring a fix.

## Validation gates
- Preserve every untouched raw object before serializing modified assets.
- Inventory source/output `(path_id, type, raw-size, hash)` and whitelist only intended objects.
- Reload exact font pointers and target localization fields.
- Run an in-game Steam-runtime screenshot test. Structural pointer reload and font cmap coverage alone do not prove TMP glyph rendering or layout.
- Keep a reversible installer with hash guards and do not mark release-ready until screenshot QA has no `□` glyphs.

## Common false positives
- A full TTF cmap says a font *can* contain Vietnamese; it does not prove a TMP static atlas contains those characters.
- A successful installer message does not prove the game ran that asset. Verify the installed asset hash and backup state after installation.
- Whole `.assets` file size may change legitimately after UTF-8 localization; use object inventory and changed-object whitelist instead.
