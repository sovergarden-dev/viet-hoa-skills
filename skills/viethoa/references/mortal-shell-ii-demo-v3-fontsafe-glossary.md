# Mortal Shell II Demo — UE5 locres, direct pak, font-safe UI v3

Session lesson for Unreal Việt hóa builds where `.locres` patching works structurally but loose patch paks do not visibly override in-game.

## Durable workflow notes

- Keep Vietnamese in a non-English culture slot when possible (e.g. `ru/Game.locres`) so English remains clean for fallback/comparison. Only make an English-override convenience build as a separate explicit artifact.
- For `UnrealLocres import`, the CSV `source` column must contain the current target-culture text and `target` must contain the new Vietnamese. If `source` is the English text while importing over `ru`, the tool can import `0` rows.
- A valid loose pak in `Content/Paks` can still fail to mount or override. Try normal Unreal patch names first (`pakchunk0-Windows_P.pak`), then if screenshots still show old text after restart, build a backed-up direct-pak test.
- Direct-pak test pattern:
  1. Back up original `pakchunk0-Windows.pak` with checksum.
  2. Unpack original pak structurally with `repak`.
  3. Replace only target culture `Game.locres`.
  4. Repack using matching UE pak version/settings/path hash seed.
  5. Copy modified pak over original.
  6. Provide a restore BAT that copies the backup back.
- For other machines, package the full modified pak only for test builds when loose patching fails. Include installer/restorer BATs that backup the target machine's original pak before overwrite.

## Glossary and QA lessons

- Machine translation will translate game terms too literally. Lock protected terms early: `Disciple`, `Sidearm`, `Sester`, `Tarstone`, `Mether`, `Beacon`, `Gloom`, `Resolve`, `Harbinger`, `Shell`, NPC names, place names, item/monster names.
- Screenshot QA matters after file-level `Cyrillic leftover = 0`; file-level validation does not catch bad Vietnamese term choices or font glyph loss.
- Some UI fonts render subtitles with Vietnamese accents correctly but drop glyphs in uppercased/small-menu widgets. Do not strip accents globally. Convert only affected UI/menu/prompt key groups to ASCII Vietnamese.
- Example font-safe UI fixes that avoided missing glyphs:
  - `Liên kết Shell` -> `Lien ket Shell`
  - `Khả năng Shell` -> `Ky nang Shell`
  - `Nói chuyện với Genessa` -> `Noi chuyen voi Genessa`
  - `Rời đi` -> `Roi di`
  - `Bắn (Sidearm)` -> `Ban (Sidearm)`
  - `Né tránh` -> `Ne tranh`
  - keep `Parry`, `Harden`, `Sidearm` as terms.
- Treat dialogue/subtitles separately from UI. If screenshots show subtitle accents working, keep accented Vietnamese for dialogue/lore and only make UI no-diacritic where needed.

## QA targets after rebuild

- NPC/Shellkeeper menus: Shell bonding/abilities/leave/talk labels.
- Genessa training menu: seal/weapon/training labels.
- Keybindings: action labels and key names.
- Dialogue subtitles: accents, pronouns, protected terms.
- Language/settings screen: target culture label and no residual Russian.
