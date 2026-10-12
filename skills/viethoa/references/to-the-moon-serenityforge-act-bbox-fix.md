# To the Moon SerenityForge: safe Act title-card localization

Date: 2026-07-05

## Problem

Act title cards look like a full black screen with two centered text lines, but the visible text is assembled from Unity `Texture2D` alpha-mask sprites. The game crops/renders each sprite based on the original alpha bounds/sprite mesh, not the full 640x480 canvas.

Naive approaches failed:

- Raw `.resS` patch: corrupted the screen.
- Full-card texture: title got cropped and quote disappeared.
- Two-line quote texture: line got clipped because quote layer is a narrow one-line region.

## Working solution

For each Act texture:

1. Decode the original `Texture2D` with UnityPy.
2. Read the alpha channel bbox with `img.getchannel("A").getbbox()`.
3. Draw the Vietnamese replacement strictly inside that original bbox.
4. Use `Texture2D.set_image()` and save into `resources.assets`.
5. Do not raw-edit `resources.assets.resS`.

This preserves Unity's original sprite crop/mesh behavior.

## Verified result

v1.4 Act 1 in-game screenshot showed:

```text
Hồi 1
“Tôi chưa từng nói với ai, nhưng... tôi luôn nghĩ chúng là những ngọn hải đăng.”
```

No cropping, no missing quote, no corrupted black screen.

## Release package

`To_the_Moon_SerenityForge_VietHoa_v1.4-act-bbox.zip`

SHA256:

`c5da540e7e4bdca3ce557fd690d7cb1b5b851b0771228478e10ce75add4ada3c`
