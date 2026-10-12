# Unity Editor-baked TMP Vietnamese atlas: practical workflow

## Trigger
A Unity TMP static SDF menu renders Vietnamese as tofu after localization data reloads correctly. Do not hand-author an atlas texture or merely repoint TMP consumers.

## Proven approach
1. Restore all previous font experiments before proceeding; verify original `.assets` and `.resS` hashes.
2. Identify the runtime TMP FontAsset and its owning asset/sidecar. In the Bookwalker-style layout, the active static font was in `sharedassets0.assets`, with the atlas streamed in `sharedassets0.assets.resS`.
3. Install and run the editor version matching the game build. Unity GUI activation may be valid while `-batchmode` is rejected; use the activated GUI editor for editor-only build commands if batch mode reports an invalid license.
4. Create a separate Unity project beside the game; never open the game directory as a Unity project.
5. Import TMP Essentials only. Copy a Vietnamese-capable TTF into the isolated project's `Assets/` directory and verify its hash against the source.
6. In `Window → TextMeshPro → Font Asset Creator`, choose:
   - source font: imported TTF
   - character set: `Characters from File`
   - text file: corpus excluding CR/LF/TAB
   - static atlas, `SDFAA`, `Fast` packing
   - begin at `2048 × 2048` for a full Vietnamese UI corpus
   - enable kerning pairs
7. A reported missing U+000A/LF is normal if the source character file retained a newline; it is not a missing Vietnamese glyph. Prefer excluding CR/LF/TAB from the requested corpus.
8. Save the generated font asset. A Unity 2020 TMP save can embed the TMP FontAsset, Material, and Texture2D subassets in one `.asset` YAML file. Verify it contains all three subasset classes before extraction/import work.
9. Build/export artifacts through the activated GUI Editor if batch mode has license restrictions. Give build scripts a `Tools/...` menu item so the user can invoke it without a shell.
10. Extract/import only Unity-baked artifacts into a copy patch. Preserve exact material, glyph metrics, face info, texture object metadata, and `.resS` stream offsets. Structural validation alone is insufficient; require Steam runtime screenshots.

## Pitfalls
- A source TTF cmap only proves source glyph availability, not runtime TMP atlas availability.
- A font fallback PPtr can serialize and reload but still be unreachable across serialized-file external tables.
- Replacing a static TMP atlas with a hand-made SDF/table set can render fragmented or corrupt text even when every codepoint table check passes.
- Legacy `UnityEngine.UI.Text` font swaps do not affect TMP menus.
- Do not package a font test until Main Menu, Options, confirmation dialog, small labels, and long text show no tofu, fragmentation, clipping, or broken layout.
