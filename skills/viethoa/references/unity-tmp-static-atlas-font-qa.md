# Unity IL2CPP TMP static-atlas Vietnamese QA

## Trigger
Vietnamese localized strings serialize and load, but screenshots show tofu squares (`□`) for diacritics in Unity menus.

## Proven investigation order
1. Verify the installed asset hash against the intended patch. Do not infer installation state from installer output.
2. Identify the renderer used by the affected screen. Inspect instantiated menu hierarchy and component scripts; do not assume `UnityEngine.UI.Text` from appearance.
3. For TMP, identify the actual `TMP_FontAsset` PPtr and whether it is a static atlas (`m_AtlasPopulationMode=0`) or dynamic asset.
4. Audit `m_CharacterTable` against the actual translated corpus, excluding layout controls (`\r`, `\n`, `\t`). Font TTF cmap coverage alone is insufficient.
5. Inspect the font asset's `m_FallbackFontAssetTable` and external-file reachability before attempting a fallback PPtr patch.
6. If the active font is a static SDF atlas with no usable fallback, rebuild its atlas texture, `m_GlyphTable`, and `m_CharacterTable` together. Replace streamed `.resS` texture bytes at the existing texture slot; preserve file layout unless independently validated.
7. Validate changed-object whitelist, reload every modified field, corpus glyph coverage, then capture in-game screenshots of the exact failing menus.

## Key pitfalls
- `UI.Text` font references can be unrelated while visible menu text uses `TextMeshProUGUI`.
- A dynamic TMP source font may have a complete TTF cmap but an empty/prebuilt-incomplete TMP atlas; rerouting to it does not guarantee runtime glyph generation.
- TMP serialized layouts vary. Locate and replace an exact PPtr only after confirming its semantic field for each layout; never assume one byte offset across all components.
- A fallback PPtr is valid only if the owning serialized file can resolve its external reference. A structurally valid but unresolvable fallback silently leaves tofu at runtime.
- Static atlas metadata and texture pixels are one unit: changing only references or only the texture does not fix glyph rendering.

## Release gates
- Installed hashes match manifest for every patched asset and `.resS` companion.
- Localized corpus codepoint set is a subset of active TMP `m_CharacterTable` (excluding controls).
- Structural object whitelist and reload validation pass.
- Steam/runtime screenshots confirm no tofu and acceptable layout in main menu, options, dialogs, and representative dialogue.
