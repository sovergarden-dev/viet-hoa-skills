# Unity TMP Vietnamese glyph forensic workflow

## Trigger
A Vietnamese localization loads in game but characters with diacritics render as tofu squares (`□`), even though a legacy `Font` asset has Vietnamese cmap coverage.

## Critical distinction
Do not assume every menu label is `UnityEngine.UI.Text`.

Unity games can combine:
- legacy `UnityEngine.UI.Text` using a `Font` object;
- TextMeshPro (`TMP_FontAsset`) using a serialized SDF glyph atlas and `m_CharacterTable`;
- I2/Dialogues stored text that is rendered by either path.

A full TrueType/OpenType cmap is **not sufficient** for TMP. TMP renders only glyphs already present in its SDF atlas / character table unless a compatible runtime dynamic atlas population route actually works.

## Evidence-first procedure
1. Capture an in-game screenshot and record which strings show tofu. This proves text import is working but font QA failed.
2. Verify the installed asset hash and backup hash before blaming a patch. Confirm the patch is truly active.
3. Inventory all legacy `Font` assets and audit their cmap with `fontTools`; record available Vietnamese characters.
4. Inventory actual `UnityEngine.UI.Text` objects through a recovered type tree and read `m_FontData.m_Font`, not only raw PPtr byte patterns. A pointer swap may serialize/reload correctly yet be irrelevant to the active menu.
5. Inventory `TMP_FontAsset` objects with the `TMPro.TMP_FontAsset` type tree. For each candidate, inspect:
   - `m_SourceFontFile`
   - `m_AtlasPopulationMode`
   - `m_CharacterTable` Unicode values
   - `m_GlyphTable`, `m_AtlasTextures`, and material
6. Test required Vietnamese Unicode codepoints against the TMP `m_CharacterTable`. Missing entries are a release blocker even if the source font file’s cmap is complete.
7. Find TMP consumers and settings/fallback assets. Inspect `TMP_Settings` / serialized lists and scan all asset/scene files; account for external `PPtr` file IDs, not only local `fileID=0` PPtrs.
8. Only modify a font route after proving the *actual renderer and asset file*. For TMP, build or regenerate a compatible SDF atlas and character/glyph tables from a Vietnamese-capable font, preserve material/atlas bindings, then test in Steam runtime.

## Do not do
- Do not declare a font fix successful from cmap coverage alone.
- Do not ship after only a `UnityPy` reload/object-inventory result.
- Do not mass raw-replace `Font` PPtrs. It can touch unrelated serialized fields and may not affect TMP at all.
- Do not substitute unaccented Vietnamese as the final solution.

## Release gate
Require screenshots from the actual Steam runtime showing Vietnamese on:
- main menu;
- Options labels and values;
- confirmation dialogs;
- at least one dialogue/subtitle or I2 string;
- no tofu characters and no clipping/overlap.

If a clone launch lacks Steam API initialization, it can prove asset loading but cannot replace Steam-runtime font QA.
