# Tormentum - Dark Sorrow (Adobe AIR) preparation

## Confirmed target

- Canonical game root: `G:\SteamLibrary\steamapps\common\Tormentum`
- Engine: Adobe AIR / ActionScript; `META-INF/AIR/application.xml` declares AIR application 19.0 and game version `1.4.2`.
- Main content: `Tormentum.swf`; scene assets are external SWFs.
- Direct localization route: `assets/config/dialogs/*.xlg`.
- Each `.xlg` is a zlib stream beginning at byte 0 and inflates to UTF-8 XML.
- English source: `en.xlg`; Polish (`pl.xlg`) is the original-language context source. The installed set also includes `br`, `cs`, `de`, `es`, `fr`, `hu`, `it`, `pt`, `ru`, `tr`.

## Safe preparation route

1. Create a separate workspace; do not create files under the game root during preparation.
2. Hash and copy `en.xlg` and `pl.xlg` into `source/`.
3. Inflate both with `zlib.decompress`; parse with Python stdlib `xml.etree.ElementTree`.
4. Export one CSV row per non-empty XML text node with a stable structural key, English source, Polish reference, Vietnamese target, protected-token column, status, and notes.
5. Preserve XML/CDATA semantics, explicit backslash escapes (`\\n`, `\\r`, `\\t`), placeholders, tags, square-bracket controls, and percent tokens. Parse CSV through `csv.DictReader`; do not use physical line counts.
6. Do not enable/import Vietnamese yet when the user asks for preparation only. Wait for an explicit start-translation command.
7. Once translation is reviewed, build `vi.xlg` only in a copy/package staging directory and update a copied `application.xml` locale declaration. Do not modify the installed game while developing.

## Verified preparation baseline

The English table contained 883 non-empty text rows in the inspected build. This is a build-specific diagnostic, not a universal expectation: derive the count afresh whenever source hashes differ.

## Font and runtime boundary

Vietnamese glyph coverage is not proven by XML extraction. AIR/Flash fonts may be embedded in the main or external SWFs. Do not launch the game automatically; request user-run screenshots later for menus, dialogue, small labels, wrapping, and missing glyphs.

## Minimal dependency route

For this file format, Python stdlib is sufficient: `zlib`, `xml.etree.ElementTree`, `csv`, `hashlib`, and `json`. Avoid adding extraction dependencies unless an SWF/font investigation later requires them.
