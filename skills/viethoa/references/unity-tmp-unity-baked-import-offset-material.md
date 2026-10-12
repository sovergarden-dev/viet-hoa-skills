# Unity-baked TMP import into an existing static atlas

## Trigger
A Unity 2020.3.x-compatible TMP Font Asset was baked from a Vietnamese-capable TTF, but a copy-only import still shows tofu (`□`) or the old atlas at runtime.

## Proven diagnostics
- Verify the runtime screen's active `TMP_FontAsset`, its material PPtr, atlas texture PPtr, and `StreamingInfo.offset`.
- Verify the installed file hashes before interpreting screenshots.
- Check the baked `m_CharacterTable` against the actual localized corpus, excluding CR/LF/TAB. Include UI symbols used by source strings (for this case `£`, `®`, `™`).
- A generated TMP atlas may report one missing LF (`U+000A`); that is not a glyph requirement.

## Critical import rules
1. **Write streamed atlas bytes at `Texture2D.m_StreamData.offset`, not at byte 0 of `.resS`.** In this Unity 2020 static atlas case the offset was `524288` and the Alpha8 payload length was `524288` for a `1024×512` atlas. Writing at zero leaves the actual runtime atlas unchanged.
2. Preserve the original `.resS` bytes outside the texture stream range.
3. Keep all PPtrs internal to the target owner file: baked font `material -> existing game Material`, `m_AtlasTextures -> existing game Texture2D`.
4. Do not treat matching dimensions, glyph tables, and a reload as runtime proof.
5. If the baked font still displays tofu after correct stream-offset injection, test a copy-only variant that imports the **Unity-baked material properties** while preserving the game's shader PPtr and remapping `_MainTex` to the existing game texture. TMP material scale ratios and shader properties can matter.
6. Every material/atlas change must be Steam screenshot-tested on Main Menu, Options, confirmation dialogs, small labels, and long text. Immediately uninstall/revert a test that worsens rendering.

## Structural proof checklist
- Build proof from preserved original sidecar/asset backups, never from whichever test patch is currently installed.
- Whitelist serialized changes separately from streamed-sidecar changes: an unchanged `Texture2D` object plus a changed `.resS` payload is expected.
- Reload `TMP_FontAsset`, verify font/material/atlas PPtrs, all corpus codepoints, texture dimensions/format, correct stream offset, payload length, and backup/original hashes.
- Do not package as release-ready until visual QA passes.
