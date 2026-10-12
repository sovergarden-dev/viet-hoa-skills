# Unity 2020 TMP Font Asset Creator bake workflow

## Trigger
A Unity TMP menu renders Vietnamese as tofu (`□`), and static-atlas/pointer-swap experiments are unsafe or ineffective.

## Safe bake route
1. Restore every previous test patch and hash-check the original `.assets` and `.resS` sidecars before opening Unity.
2. Install/use the exact game editor version when feasible. TMP output is version-sensitive.
3. Create a separate empty Unity project under the work directory. Never open the game directory as a Unity project.
4. Import TMP Essentials only; Examples & Extras are unnecessary.
5. Copy the audited source TTF into that project’s `Assets/` directory. A file outside `Assets/` cannot be selected as `Source Font File`.
6. Build a character-file corpus from the reviewed Vietnamese text, excluding `\r`, `\n`, and `\t`; include normal ASCII/UI punctuation. In Font Asset Creator choose `Characters from File`.
7. Start with `Auto Sizing`, `Padding 5`, `Fast`, `2048x2048`, `SDFAA`, and kerning enabled. If the only missing character is LF (`ID 10`), it is benign because line breaks need no glyph.
8. Save the generated TMP asset under `Assets/`. Unity 2020 may embed the generated `Material`, `Texture2D`, and `TMP_FontAsset` as sub-assets in one `.asset` file; do not assume separate `.png`/`.mat` files.
9. Inspect/export Unity-baked serialized artifacts and build a copy-only game patch. Validate owner-file external PPtrs, object/file whitelist, streamed sidecars, reload, installer rollback, then Steam screenshots.

## Critical pitfalls
- Source cmap coverage is not baked-atlas coverage.
- Do not hand-author a TMP SDF atlas based on glyph-table checks. It can structurally pass yet fragment/corrupt runtime text due to metrics, material/shader state, texture metadata, or `.resS` layout.
- A fallback/PPtr can serialize and reload but still be unreachable at runtime if the owner asset has no resolvable external reference.
- Do not claim completion or prescribe expected output filenames before checking what the Unity version actually generated.
- Font tests that worsen rendering must be uninstalled immediately and all modified `.assets` and `.resS` restored from verified backups.
