# To the Moon SerenityForge: UI tables, line wrapping, and crash lessons

Date: 2026-07-06

## User QA signals

Screenshots revealed three late-stage release issues:

1. Long Vietnamese dialogue was auto-shrunk into a single tiny line instead of wrapping.
2. Items/Notes/Characters menu text was still English beyond the first visible screenshot.
3. UI patch zips v2.0/v2.1 crashed because asset files were accidentally saved as tiny truncated/corrupt files.

## Dialogue line wrapping

The game accepts actual newline characters inside TextAsset CSV cells.

Working pattern:

```text
Đến lúc này ông ấy không còn phản ứng, nhưng nhìn tình hình thì,
ý thức của ông ấy vẫn đang bám trụ.
```

Pitfall:

Do not put pause codes at the beginning of a wrapped line. A line like this can show a stray dot:

```text
...
\.ý thức...
```

Rule:

- Create `long_line_audit.csv` for long lines.
- Wrap only dialogue rows, not NameBox/menu/Act title rows.
- Do not wrap lines dense with control codes/tags unless manually reviewed.
- After a newline, strip leading pause controls: `\.`, `\\.`.
- Test one save-accessible line before batch wrapping.

## UI / Items / Notes / Characters

Do not translate only what the user screenshot shows. Menus unlock new rows over time.

Scan and patch all relevant TextAsset tables:

- `Terms_Loc`: tabs, buttons, labels, options, character descriptions, credits terms.
- `Items_Loc`: item names, item descriptions, note names, note descriptions.
- `Actors_Loc`: character names if localized; often names remain unchanged.

For To the Moon SerenityForge, full UI mapping was stored in:

`ui_items_notes_full_mapping_v21.csv`

Examples:

```text
Characters -> Nhân vật
Notes -> Ghi chú
Items -> Vật phẩm
Description: -> Mô tả:
Equipment -> Thiết bị
Note: Moon -> Ghi chú: Mặt trăng
Toy Platypus -> Thú mỏ vịt đồ chơi
Paper Rabbit -> Thỏ giấy
Beta Blocker -> Thuốc chẹn beta
```

## Crash lesson: check asset sizes

v2.0/v2.1 crashed because the UI patch was built from a bad save path that shrank Unity asset files:

```text
bad main resources.assets: ~0.49 MB
expected main resources.assets: ~145 MB
```

Rule:

After every Unity asset save, compare patched file sizes against the last known good patch or original asset. Reject any patch whose `.assets` files are suspiciously tiny.

Expected safe sizes for the To the Moon SerenityForge v1.9/v2.3 line:

```text
main resources.assets:      ~145 MB
minisode1 resources.assets: ~63 MB
minisode2 sharedassets2:    ~66 MB
```

## Safe rebuild pattern after a corrupt UI patch

1. Start from the last known good full-size patch or clean original, not the corrupt output.
2. Add UI rows to the same workbook/pipeline used for dialogue TextAssets.
3. Rebuild TextAssets through the proven structured importer.
4. Reapply Act bbox texture patch after TextAsset rebuild.
5. Verify zip and asset file sizes.
6. Only then ask for in-game QA.

## Release safety checklist

- `zipfile.testzip() == None`
- asset file sizes are plausible, not tiny
- game starts past Unity loading screen
- menu tabs are translated
- later Notes/Items entries are translated
- long dialogue wraps without stray dot before the next line
