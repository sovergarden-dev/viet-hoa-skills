# The Bookwalker: Unity IL2CPP runtime localization and installer lessons

Use for Unity 2020 IL2CPP games that combine Pixel Crushers DialogueSystem, I2 Localization, TextMeshPro, localized sprite terms, and a BepInEx runtime font fix.

## Proven release architecture

- Structured rewrite of DialogueDatabase and I2 MonoBehaviours from a reviewed CSV source of truth.
- Strict changed-object whitelist and exact field reload.
- Runtime TMP font AssetBundle loaded by a BepInEx IL2CPP plugin.
- Conditional font replacement only for strings containing Vietnamese-specific Unicode.
- Dedicated optional image-button AssetBundle with narrow sprite-name mappings.
- One portable hash-guarded WinForms installer with embedded payload and artwork.

## Runtime font timing

A one-second component poll can produce visible tofu when new dialogue renders before the next scan. Prefer:

1. Discover all live `TMP_Text` periodically.
2. In `LateUpdate`, inspect already known objects every frame.
3. If localized text contains Vietnamese-specific codepoints, assign the Vietnamese font before the frame renders.
4. Keep English/Russian/ASCII-only strings on their original fonts.
5. Use a setter/Harmony hook only if runtime ordering proves `LateUpdate` insufficient.

## Failure-domain isolation

Critical font behavior must start before optional artwork loading. Wrap optional image bundle work in its own `try/catch`:

- A missing or malformed sprite logs a warning and disables only artwork replacement.
- Font rendering continues.
- Never let an optional visual enhancement abort `Plugin.Load()` before the core behavior is registered.

## Localized images are asset references

I2 `TermType=5` / `Image/*` values are asset names, not translated labels. A fabricated target such as `_ui bag vi` yields a blank/white control if the asset does not exist.

Required audit:

1. Parse all I2 sources and every `TermType=5` plus `Image/*` term.
2. Inventory all `Sprite` and `Texture2D` names.
3. Verify each target-locale reference exists.
4. Until target artwork passes runtime QA, point target locale to an existing English asset.
5. Rebuild from the verified original backup and re-audit output.

Unity-imported PNGs expose a `Texture2D` main asset and a `Sprite` sub-asset. Use the full Unity path with `LoadAssetWithSubAssets()` and select the `Sprite`; casting `LoadAsset(path)` can fail.

## Alpha-mask artwork

Some UI lettering is encoded entirely in alpha over flat RGB. Inspect alpha separately before deciding an image is blank. For reconstructed Vietnamese lettering:

- preserve exact dimensions;
- preserve flat RGB and alpha-mask convention;
- render Vietnamese accents explicitly;
- validate final-size alpha bounding boxes and safe margins;
- use `Sprite (2D and UI)`, alpha from input, no mipmaps, clamp, bilinear, uncompressed, no NPOT scaling;
- keep English textures untouched and use a dedicated AssetBundle.

User preference wins after QA. If the user chooses English for some persistent artwork and Vietnamese for another, narrow runtime mappings accordingly. Remove unused mappings rather than carrying speculative options.

## Rebuild pitfalls

- Never build a new patch from the currently installed patch. Use the one verified original backup as source.
- UnityPy may preserve a backup filename such as `resources.assets.viet_runtime_backup`; normalize generated output to `resources.assets`.
- Delete stale generated output before rebuild.
- For CSV rewrites, use `DictReader.fieldnames`, validate exact stable keys, write a sibling temp file, then atomically replace.
- Do not overwrite or stack the sole original backup during upgrades.

## Locale-label restraint

Changing the displayed locale name (`Russian` to `Tiếng Việt`) is optional presentation, not localization correctness. Keep the internal slot stable. If the user prefers lower risk, remove the runtime label rewrite entirely and keep the documented selection as `Russian`. Avoid cosmetic hooks that add failure surface without improving translated content.

## Canonical release workspace

Use one release root, for example:

```text
C:\Users\<user>\viethoa\<GameName>\
```

Keep final EXE, source, build script, payload/manifest, artwork, reports, and README there. Remove duplicate deliverables from the home directory, game directory, and obsolete release folders only after the canonical final binary passes tests.

## Installer requirements

- Embed verified patch, official BepInEx distribution ZIP, runtime artifacts, manifest, and background.
- Never package live BepInEx cache/interop/logs.
- Auto-detect the game root but allow a folder picker.
- Exclude the installer PID from process-name checks.
- Accept only verified original and exact supported patched hashes.
- Stage, hash, replace, and rollback transactionally.
- Preserve pre-existing loader files and third-party plugins.
- Track only newly created files in an ownership state file.
- Restore only a backup matching the original hash.
- Include `/install <root>` and `/uninstall <root>` modes for clone tests.

Required final-binary tests:

1. Clean install and installed hashes.
2. Clean uninstall and original hash.
3. Upgrade from supported patched state.
4. Preserve pre-existing loader and unrelated plugin.
5. Reject unsupported hash before any write.
6. Verify rollback on failure.
7. Run the exact deliverable from the canonical workspace after the last rebuild.
8. Inspect the final GUI, not an earlier binary.

## Release decision propagation

After any late user decision, search and update every layer:

- workbook/source of truth;
- runtime mapping/plugin source;
- plugin version;
- payload manifest/version;
- installer success text;
- README;
- final EXE;
- checksum report.

Then rebuild from source and repeat the final-deliverable smoke install/uninstall. Never report final based on a previous binary.
