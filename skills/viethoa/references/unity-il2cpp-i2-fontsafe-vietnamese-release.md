# The Bookwalker Unity IL2CPP: full I2 import and Vietnamese font fallback

## Proven I2 legacy source write route

For legacy `I2Dialogues` / `I2Languages` source objects whose typetree cannot decode trailing metadata:

1. Prove the `mTerms` byte layout from raw data. In this Unity 2020 build: start terms at offset 56; term = aligned UTF-8 `Term`, `TermType`, `Languages` vector, `Flags` byte vector + alignment, `Languages_Touch` string vector.
2. Rebuild only the `mTerms` block and append `raw[old_terms_end:]` byte-for-byte. Do not parse/rewrite trailing legacy metadata.
3. Before save, preserve raw payloads for every Unity object via `set_raw_data(bytes(get_raw_data()))`; otherwise UnityPy may emit empty payloads for unrelated objects.
4. Copy-only proof requirements: reload exact edited string; same object count; only target I2 object differs; trailing metadata is identical after recalculated term end.
5. Full import proof: all reviewed I2 rows reload exactly; only I2 source objects may change.

Observed full import: 962 `I2Dialogues` + 1,510 `I2Languages` rows, exact reload, only `path_id=6343` and `6344` changed.

## Combined localization proof

A combined full-scope build must reload every dialogue and I2 value, and inventory changes must be limited to localization objects. Overall `.assets` byte size may change legitimately because target UTF-8 strings vary in length; compare object inventory and exact field values instead.

## Font QA and safe fallback repair

A successfully loaded Vietnamese menu can still show `□` for accented characters. Treat this as a font glyph coverage failure, not a translation or serialization failure.

1. Extract embedded Unity `Font.m_FontData` and inspect cmap coverage for the full Vietnamese alphabet.
2. Inventory raw `PPtr<Font>` references in `MonoBehaviour` objects, resolve the `MonoScript`, and distinguish `UnityEngine.UI.Text` from TMP font assets.
3. Replace only bindings of a known incomplete UI font with a verified complete embedded font, on a copy-only asset.
4. Preserve all other raw objects before save; reload and require only intended UI text objects to change.
5. Smoke-test menu labels with diacritics before release.

Observed case: `Perfect DOS VGA 437` lacked 102 Vietnamese glyphs and was referenced by 82 `UnityEngine.UI.Text` objects. Embedded `Roboto-Regular` had full Vietnamese cmap coverage. TMP font assets were not modified.

## Smoke-test caveat

Launching a hardlinked clone directly may initialize Unity but fail SteamAPI outside normal Steam runtime. That confirms startup/asset loading only; it does not replace a Steam-context visual smoke test. Keep the original install hash verified before and after clone creation.
