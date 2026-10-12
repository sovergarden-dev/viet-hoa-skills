# UE4 residual Russian QA: settings panels, key names, and installer signature

Use this after a culture-slot UE4 localization looks mostly correct but screenshots still show Russian in options, keybinds, or help panels.

## Screenshot-driven residual scan
- Treat every screenshot with leftover Russian as a precise probe source.
- Extract exact visible strings and near-exact fragments, then scan both raw pak bytes and zlib-decompressed blocks.
- Do not rely on broad markers like `OLED`, `Aylin`, or `INTERFACE` alone; they create shader/asset-path false positives.
- Once a hit is found, classify the storage type before patching: locres namespace, DataTable FString, StringTable, or engine-generated key display name.

## Settings description panels
- A translated left-side setting label does not prove the right-side help panel is translated.
- Luna Abyss stored some settings help text in `TooltipTable` UTF-16 rows rather than `Game.locres`.
- Patch these as fixed-length UTF-16 FStrings: keep the original serialized length field, write the Vietnamese text, and pad the remaining slot.
- Example residual fix:
  - `Повысить интенсивность чёрного цвета` -> `Bật mức đen điện ảnh`
  - `Повысить интенсивность чёрного цвета экрана... OLED-экране.` -> `Tăng mức đen của màn hình... OLED.`

## Keybind display names
- Russian key labels such as `Пробел`, `Ctrl (левая)`, `Левая кнопка мыши` can come from UE `InputKeys` localization, not the project UI table.
- Add/override locres entries in namespace `InputKeys` inside the technical target culture locres:
  - `InputKeys/SpaceBarShort` -> `Space`
  - `InputKeys/SpaceBar` -> `Space`
  - `InputKeys/LeftControl` -> `Ctrl (trái)`
  - `InputKeys/LeftShift` -> `Shift (trái)`
  - `InputKeys/LeftAlt` -> `Alt (trái)`
  - `InputKeys/LeftMouseButton` -> `Nút chuột trái`
  - `InputKeys/RightMouseButton` -> `Nút chuột phải`
- Repack the patch pak and reinstall it; do not patch English culture.

## GUI installer polish
- If the user asks for author branding, put it in the GUI installer, not in translated game strings.
- A small WinForms/C# self-extractor can embed:
  - payload zip;
  - original blocks for uninstall;
  - background image;
  - author signature such as `Syrin.online`.
- Keep buttons simple and localized: `Cài Việt hóa` and `Gỡ Việt hóa`.

## QA gates
- Re-run readback QA after residual patches:
  - target field equality with `rstrip()` for fixed-length padding;
  - no Cyrillic in patched target fields;
  - exact screenshot old strings absent;
  - patch pak contains no `en/Game.locres` when English must remain clean.
- Update the final payload and uninstall original-block archive after every residual block or locres change; otherwise the GUI installer can lag behind the currently patched game.
