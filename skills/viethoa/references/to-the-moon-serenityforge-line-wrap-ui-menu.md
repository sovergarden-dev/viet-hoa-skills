# To the Moon SerenityForge: dialogue line wrapping and menu UI localization

Date: 2026-07-05

## Dialogue line wrapping lesson

Long Vietnamese lines can trigger Unity/RPG-style dialogue auto-fit, shrinking the font into a single hard-to-read line. Actual newline characters inside the TextAsset CSV cell worked in-game for normal dialogue boxes.

Tested line:

```text
Đến lúc này ông ấy không còn phản ứng, nhưng nhìn tình hình thì,
ý thức của ông ấy vẫn đang bám trụ.
```

Result: two lines, normal font size, no visible `\n`.

## Pitfall: pause code at line start

Do not place `\.` / `\\.` at the beginning of a wrapped line. In this game it can render as a visible dot before the next word, e.g. `.ý`.

Safe rule:

- Wrap with actual newline.
- Strip leading pause tokens from the new line.
- Do not auto-wrap lines that are dense with control codes/tags.

## Safe long-line workflow

1. Create `long_line_audit.csv` with line length, source text, proposed wrapped text, and changed flag.
2. Skip NameBox, DialogueChoice/menu rows, Act title textures, and dev notes.
3. Wrap only lines above a threshold, e.g. visible length > 82.
4. Use actual newline inside the CSV field.
5. Avoid breaking inside tokens: `\.`, `\|`, `\c[]`, `\w[]`, `\oi[]`, `<i>`, `<b>`.
6. Rebuild and test a known easy-to-trigger save point first.

## Menu/UI localization lesson

The pause menu tabs and item/character descriptions were not fully covered by dialogue extraction. They lived in:

- `Terms_Loc`: tabs, buttons, option labels, description headers, character descriptions.
- `Items_Loc`: item names and item descriptions.

Patch the English column in these TextAsset tables for every part: main, Minisode 1, Minisode 2.

Examples:

```text
Characters -> Nhân vật
Notes -> Ghi chú
Items -> Vật phẩm
Description: -> Mô tả:
Equipment -> Thiết bị
With a box this heavy, what's inside has got to be important.
-> Chiếc hộp nặng thế này thì bên trong hẳn phải là thứ quan trọng.
Senior memory traversal agent, Sigmund Corp.
-> Đặc vụ cấp cao chuyên du hành ký ức, Sigmund Corp.
Technician specialist, Sigmund Corp.
-> Chuyên viên kỹ thuật, Sigmund Corp.
Save -> Lưu
Load -> Tải
Options -> Tùy chọn
Exit Game -> Thoát game
```

## Release artifacts from this session

- `long_line_audit_v19.csv`: 300 long lines audited, 201 wrapped.
- `To_the_Moon_SerenityForge_VietHoa_v1.9-longline-wrap.zip`: line wrap release.
- `To_the_Moon_SerenityForge_VietHoa_v2.0-ui-menu.zip`: UI/menu localization patch.
