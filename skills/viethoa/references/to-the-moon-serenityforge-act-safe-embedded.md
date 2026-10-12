# To the Moon SerenityForge: safe Act title-card localization

Date: 2026-07-05

## Problem

The Act title cards (`Act 1`, `Act 2`, `Act 3`, and quotes) looked like image text. A previous raw `.resS` patch corrupted the Act screen. The safe solution was to patch only the English `Texture2D` objects through Unity serialization, not raw stream bytes.

## Key lesson

For Unity streamed textures, do **not** write bytes directly into `resources.assets.resS`. Use a serializer-aware path (`Texture2D.set_image()` via UnityPy or an equivalent Unity texture importer) so image data and metadata remain coherent.

## Discovery pattern

1. Decode original `Texture2D` assets with UnityPy and save previews.
2. Build contact sheets for same-name localized textures.
3. Identify only the English texture `path_id`s by visual inspection/OCR.
4. Patch only those IDs.
5. Prefer embedding patched image data back into `resources.assets`; leave `.resS` untouched unless a real round-trip importer proves safe.

## English path IDs found in this project

- `Act1`: `1352`, `1365`
- `Act1 - quote`: `634`
- `Act2`: `642`, `719`
- `Act2 - quote`: `730`
- `Act3`: `1458`, `852`
- `Act3 - quote`: `833`
- `Act3 - Finale - quote`: `699`

## Vietnamese wording used

```text
Act 1 -> Hồi 1
“I never told anyone, but… I’ve always thought they were lighthouses.”
-> “Tôi chưa từng nói với ai, nhưng…
   tôi luôn nghĩ chúng là những ngọn hải đăng.”

Act 2 -> Hồi 2
“Billions of lighthouses. . . stuck at the far end of the sky.”
-> “Hàng tỷ ngọn hải đăng…
   mắc kẹt nơi tận cùng bầu trời.”

Act 3 -> Hồi 3
“They shine their lights at the other lighthouses, and at me.”
-> “Chúng rọi ánh sáng tới những ngọn hải đăng khác,
   và tới cả tôi.”

Finale quote:
“Because one day . . . I’m going to befriend one of them.”
-> “Vì một ngày nào đó…
   tôi sẽ kết bạn với một trong số chúng.”
```

## Validation rule

A valid zip test is not enough for image patches. For title cards, require in-game visual QA of at least Act 1 immediately after install; if possible also Act 2/3 or targeted save access.
