# Unity TMP Font Asset Creator → bundle import proof

## Trigger
A Unity TMP static SDF menu shows Vietnamese tofu. Existing game atlases lack the reviewed corpus. Direct hand-authored SDF texture/table rewrites are visually unsafe.

## Proven preparation
1. Use the exact Unity Editor version recorded by the game (`ProjectVersion.txt` / build revision) and activate its GUI license.
2. Create a separate font-bake project beside the workspace; never open or import the game directory into Unity.
3. Import TMP Essentials only. Do not need TMP Examples.
4. Copy the vetted TTF into the Unity project's `Assets/` before opening Font Asset Creator.
5. Generate with `Window → TextMeshPro → Font Asset Creator` using:
   - source: vetted Vietnamese-capable TTF;
   - `Characters from File` from a corpus excluding CR/LF/TAB;
   - `SDFAA`, static atlas, kerning enabled;
   - atlas dimensions matching the target runtime texture exactly.
6. A reported missing `ID 10` / LF is expected if the text file includes a line ending; it is not a missing Vietnamese glyph. Prefer corpus files without CR/LF/TAB.
7. Save the TMP FontAsset. Unity stores Material, Texture2D, and TMP FontAsset as sub-assets in the generated `.asset`.

## Bundle extraction route
- Assign only the new saved asset to an AssetBundle in the Unity GUI, then build for `StandaloneWindows64`.
- Confirm the bundle manifest lists only the intended font asset. Previously assigned test assets can remain in a bundle unless their AssetBundle name is cleared first.
- Inventory the resulting bundle: require `MonoBehaviour` TMP_FontAsset, Material, Texture2D, and compatible shader objects.
- Read the baked TMP typetree and map its PPtrs to target-local IDs. Preserve the target asset's external-file reachability.
- For streamed target textures, retain existing stream metadata/format/offset and replace only the exact `.resS` texture payload after proving the Unity-baked texture dimensions and format match.
- Copy-only proof must reload and whitelist exactly the runtime font asset, its material, and its atlas texture; validate full reviewed corpus against `m_CharacterTable`.

## Important pitfall
A structurally valid raw SDF atlas/table rewrite can fragment or corrupt runtime text. Do not release it. Unity-baked artifacts still require Steam-runtime screenshots of Main Menu, Options, confirmation dialogs, small labels, and long text before release.

## License nuance
The Editor GUI license may not authorize Unity `-batchmode`. If batch build is rejected for licensing while GUI works, expose a `Tools/…` build menu and invoke it in the licensed GUI; do not repeatedly retry batch activation.
