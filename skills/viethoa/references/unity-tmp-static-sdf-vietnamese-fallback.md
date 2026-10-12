# Unity TMP static SDF Vietnamese tofu: renderer-first forensics

## Trigger

Vietnamese strings load correctly in a Unity game but accented characters render as `□` in menus. Do not assume the affected widgets use `UnityEngine.UI.Text`.

## Evidence-first workflow

1. Screenshot the failing menu and retain the exact installed `resources.assets` SHA-256.
2. Scan the **whole Unity data directory** (`resources.assets`, `level*`, `sharedassets*.assets`) for font PPtrs. A raw font-PPtr count alone does not identify the renderer.
3. Resolve `MonoBehaviour.m_Script` against the owning file's external table. For menu widgets, distinguish:
   - `UnityEngine.UI.Text` (`UnityEngine.UI.dll`)
   - `TMPro.TextMeshProUGUI` / `TMP_Text` (`Unity.TextMeshPro.dll`)
4. Map the failing panel's GameObject/RectTransform hierarchy. Inspect descendants rather than every candidate in the asset.
5. For TMP, inspect the active `TMP_FontAsset` **character table and atlas population mode**. A source TTF cmap with Vietnamese coverage is not sufficient: a static SDF atlas without Vietnamese `m_CharacterTable` entries still renders tofu.

## Key pitfall

A successful UnityPy reload proving `m_fontAsset` PPtr changed does **not** prove TMP runtime rendering. A pointer to a dynamic TMP asset can still fail when the asset cannot resolve from the serialized file, when its atlas/character table is incomplete, or when the active static font is defined in another serialized file.

Do not release after structural validation alone. Require a Steam-runtime screenshot of the exact failing menu.

## Static TMP font assets in another asset file

If a menu points to a static SDF `TMP_FontAsset` in `sharedassetsN.assets`:

- The static asset may have `m_SourceFontFile = null`, `m_AtlasPopulationMode = 0`, and an empty fallback list.
- A fallback needs a **resolvable PPtr from that asset file**. A `resources.assets` object cannot be referenced unless the source asset's external table contains that file.
- First make a copy-only serializer proof for the owning `sharedassetsN.assets`: preserve every raw object, modify one known field, save, reload, and require exactly one changed object.
- Then add a valid external reference/fallback or rebuild a static SDF atlas with Vietnamese glyphs. Do not use a dummy or unrelated PPtr as a release patch.

## Reuse a shipped dynamic fallback before baking a new atlas

When the same build already contains a `TMP_FontAsset` with `m_AtlasPopulationMode = 1`, a non-null `m_SourceFontFile`, and a source font whose cmap covers Vietnamese, prefer that native fallback over creating a new asset.

1. Scan every serialized file, not only the dialogue-font owner, for dynamic fallback candidates. Verify source-font bytes and full Vietnamese cmap independently.
2. If the dialogue-font owner lacks an external reference to the fallback's asset file, copy the exact `FileIdentifier` from another serialized file in the **same build** that already resolves that asset. Do not synthesize GUID/type/path fields.
3. Append that external once, use its resulting 1-based `m_FileID`, and add the exact fallback PPtr to every regular/bold/italic TMP font variant that can render localized text.
4. Save a workspace copy, reload the external table and all fallback lists, then load the output beside the referenced asset and require `PPtr.deref()` to resolve the exact fallback object/name/path ID.
5. Require a changed-object whitelist containing only the font assets, unchanged hashes for the referenced asset and `.resS`, and a hash-bound full-file install/rollback rehearsal.

This proves reachability and minimizes the patch, but still remains `offline-validated, pending runtime QA`; dynamic atlas generation and rendering require an in-game screenshot.

## Validation gates

- Object inventory equality, with a narrow changed-object whitelist.
- Exact reload of font/fallback fields.
- For cross-file fallback, exact external `FileIdentifier` reload plus successful `PPtr.deref()` against the staged namespace.
- Installed hash confirms the test patch is actually active.
- Steam-runtime screenshot has no tofu in the originally failing screen.
- Check typography/layout after replacement; fallback fonts can change metrics.

## Practical lesson

Treat `source font cmap`, `TMP character table`, `SDF atlas`, serialized PPtr reachability, and in-game rendering as five separate gates. Passing one does not imply the next.
