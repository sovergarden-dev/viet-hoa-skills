# To the Moon SerenityForge: Act title card corruption lesson

Date: 2026-07-05

## Symptom

Patching `resources.assets.resS` for `Act1/Act2/Act3` title card textures caused the Act screen to render as black with scattered colored pixel fragments.

## Root cause

The Act title cards are Unity `Texture2D` entries named like:

- `Act1`
- `Act2`
- `Act3`
- `Act1 - quote`
- `Act2 - quote`
- `Act3 - quote`
- `Act3 - Finale - quote`

They point into `resources.assets.resS` with `TextureFormat` value `25` and external stream data. A naive raw alpha-byte rewrite of `resS` is unsafe. It can corrupt runtime texture interpretation even when byte count matches `width * height`.

## Rule

Do not patch Unity `.resS` title-card/image text by raw byte writes. Treat external streamed texture data as unsafe unless the exact Unity texture format, mipmaps, compression, stream alignment, and serialized metadata are round-trip validated in-game.

## Safe fallback

Ship text patch without Act texture patch:

- keep translated dialogue/UI TextAssets
- leave Act title cards in English
- document known limitation

For To the Moon SerenityForge this fallback zip was:

`To_the_Moon_SerenityForge_VietHoa_v1.1-hotfix-no-act.zip`

## Upgrade path

To localize Act title cards safely:

1. Work on a clean verified game copy.
2. Use a proper Unity texture exporter/importer that updates serialized texture metadata and external stream data together.
3. Patch only one known `Act1 - quote` texture first.
4. Compare original/modified texture metadata: format, mip count, dimensions, stream path, offset, size.
5. Launch the game and inspect the exact Act scene before patching all duplicate textures.
6. Only include `.resS` in release after in-game visual QA passes.

Alternative safer route: locate the UI/text source that generates the Act card, if any, and patch text there instead of image data.
