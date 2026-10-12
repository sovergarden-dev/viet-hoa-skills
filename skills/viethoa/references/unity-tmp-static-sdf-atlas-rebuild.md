# Unity TMP static SDF Vietnamese atlas rebuild

## Trigger
Vietnamese text shows tofu (`□`) in a Unity TMP menu although localization reloads and a source TTF contains Vietnamese glyphs.

## Evidence-first diagnosis
1. Capture Steam-runtime screenshots and verify the installed hashes; stale/restored assets can mislead.
2. Map the visible menu hierarchy. `UnityEngine.UI.Text` and `TMPro.TextMeshProUGUI` are separate routes.
3. Identify the actual active `TMP_FontAsset`; inspect owner file, `m_AtlasPopulationMode`, `m_CharacterTable`, `m_GlyphTable`, atlas texture, material, stream sidecar, and fallbacks.
4. Verify fallback PPtr reachability through the owning serialized file’s external table. A UnityPy reload only proves serialization.
5. Audit actual translated corpus codepoints excluding `\r`, `\n`, and `\t`.

## Lessons from failed routes
- Swapping legacy UGUI font references does nothing when the visible menu uses TMP.
- Cmap coverage of Roboto/Noto proves source glyph availability, not TMP atlas availability.
- Repointing TMP consumers to a dynamic asset in another file can structurally reload yet fail at runtime when the owner cannot resolve that PPtr.
- A hand-written SDF texture plus `m_GlyphTable`/`m_CharacterTable` can satisfy object/codepoint checks but render fragmented/corrupt menu text. TMP also depends on compatible glyph metrics, face info, material/shader parameters, texture metadata, and streamed `.resS` layout.

## Safe route
Generate a static TMP SDF atlas with the game’s exact Unity Editor/TextMeshPro Font Asset Creator version whenever possible. Bake from a Vietnamese-capable source TTF, then extract the Unity-generated TMP FontAsset and texture artifacts into a copy-only patch.

Before release, require:
- object/file whitelist and reload checks;
- backup/restore for all `.assets` and `.resS` files;
- Steam screenshots of Main Menu, Options, confirmation dialog, small text, and long text;
- no tofu, fragmented glyphs, clipping, or layout break.

Never publish a manual TMP atlas rebuild on structural validation alone.
