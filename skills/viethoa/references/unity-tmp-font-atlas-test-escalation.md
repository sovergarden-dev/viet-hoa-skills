# Unity TMP font atlas test escalation

## Trigger
Vietnamese localization loads but TMP screens show tofu (`□`).

## Durable findings
- The visible menu may use a static `TMP_FontAsset` in `sharedassets*.assets`, while localization and TMP settings live in `resources.assets`.
- Identify the owner of the active font PPtr before changing consumers. A PPtr to a dynamic asset in another serialized file can reload structurally yet be unreachable at runtime.
- Source TTF cmap coverage is not glyph-atlas coverage. Audit the actual `m_CharacterTable`, `m_GlyphTable`, atlas texture, material, and `.resS` stream.
- Do not hand-author SDF texture bytes and TMP tables for release. Even complete codepoints can render fragmented text because TMP requires Unity-generated metrics/material/texture metadata compatibility.
- Use the game-matched Unity Editor and TMP Font Asset Creator to bake a static atlas. Export only Unity-created artifacts into a copy-only patch.

## Installer discipline for iterative font tests
1. Back up every replaced file on the first install only, including `.assets` and `.resS` sidecars.
2. Upgrades may accept only explicit known prior test hashes; never replace an existing `.viet_backup`.
3. Uninstall restores all first-install backups and verifies hashes after restore.
4. A visual regression requires immediate restore before the next experiment.

## Runtime QA minimum
Capture through Steam: Main Menu, Options, confirmation dialog, small labels, and a long text view. Reject tofu, fragmented glyphs, clipping, or changed menu structure.
