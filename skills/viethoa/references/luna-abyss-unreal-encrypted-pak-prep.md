# Luna Abyss / Unreal encrypted pak localization prep

## Durable lesson

Some Unreal games expose enough plaintext fragments inside `.pak` payloads to tempt blind string extraction, but their pak index may still be encrypted. Do not translate from raw binary scans when the goal is high-quality Việt hóa: scans mix real UI/dialogue with FMOD events, asset paths, class names, metadata, and string-table internals, and they destroy speaker/addressee context needed for Vietnamese pronouns.

## Observed workflow

1. Fingerprint top-level install before assuming Unity/RPG Maker.
   - `Engine/` + project folder + `Content/Paks/*.pak` usually means Unreal packaged build.
2. Use a real pak tool for confirmation.
   - `repak info <pak>` reports pak version and whether AES is required.
   - Example blocker: `trying version V11 failed: pak is encrypted but no key was provided` and `Fnv64BugFix`.
3. Probe payload only to identify likely text systems, not to produce release translations.
   - Useful probes: `.locres`, `StringTable`, `/Game/Localization`, `Game.locres`, known character/lore names.
   - Treat hits near `FMOD`, `Buses`, `Events`, `Texture2D`, `AnimSequence`, `BlueprintGeneratedClass` as non-translation metadata unless proven player-visible.
4. Prepare glossary/pronoun rules before extraction is solved.
   - Store research, glossary, pronoun rules, and style guide in the workspace.
   - Mark xưng hô as tentative until speaker/addressee can be derived from real dialogue tables.
5. Block honestly when the pak index is encrypted.
   - Need AES key, FModel/UnrealPak export, or developer-provided `.locres/.po/.archive/StringTable/DataTable` files.
   - Do not claim the patch is possible from scan-only data.

## Pronoun/style baseline pattern for dark sci-fi prison games

- Authority / AI warden -> prisoner: start with `ta/ngươi` only when the source voice is cold, superior, and carceral; validate against real dialogue.
- Prisoner -> named AI: start neutral (`tôi/cô` or `tôi/anh-chị`) until gender/personality is confirmed.
- Cosmic collective voice -> protagonist: `bọn ta/ngươi`; preserve eerie address forms like “little wanderer” with a poetic but not cổ trang rendering.
- UI/system: avoid pronouns when possible.

## Tool note

`repak` is useful as a lightweight Unreal pak validator/list/extract tool. Verify release checksum when downloading. Missing AES is a blocker for structured extraction, not a reason to fall back to release-grade raw string patching.
