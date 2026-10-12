# Unity IL2CPP PixelCrushers + legacy I2: full Vietnamese patch, smoke boundary, and font QA

## Applies when

A Unity IL2CPP game stores dialogue in PixelCrushers `DialogueDatabase` MonoBehaviours and UI/system text in legacy `I2Localization` `LanguageSource`/`LanguageSourceAsset` records. A foreign technical locale slot, such as `Russian`, is reused for Vietnamese.

## Proven structured import route

1. Create a full source manifest; retain the original game asset untouched.
2. Decode `DialogueDatabase` using a type tree generated from the exact build's Il2CppDumper `DummyDll/`.
3. For each modified Unity asset save, first retain and reapply raw bytes for **every** object:

```python
objects = list(env.objects)
for obj in objects:
    obj.set_raw_data(bytes(obj.get_raw_data()))
```

Then serialize only the intended dialogue objects through `save_typetree`.

4. Legacy I2 extraction/import may require a manual parser. In the verified layout:
   - leave MonoBehaviour base bytes alone;
   - `mTerms` begins at byte offset 56;
   - a term is `Term`, `TermType`, `Languages[]`, `Flags[]`, aligned, then `Languages_Touch[]`;
   - preserve the trailing version-specific metadata after `mTerms` byte-for-byte.
5. Rebuild `mTerms` from reviewed target strings, preserving language order. The target technical index was `1` (`Russian`).
6. Save only into workspace test output, then reload all edited rows using a fresh `UnityPy` environment.

## Required structural assertions

For a combined patch, require all of these before any runtime attempt:

- every reviewed DialogueDatabase row reloads exact;
- every reviewed I2 term reloads exact;
- object inventory count matches source;
- changed object IDs equal the known localization objects only;
- untouched raw object hashes remain identical;
- original asset SHA-256 is unchanged.

Overall `.assets` byte size may legitimately change due to UTF-8 Vietnamese length. Do not use file-size equality as an invariant.

## Smoke-test protocol

- A hardlink clone can save disk space, but unlink the patched files before copying replacements so the original install is never modified.
- A game launched from a clone may fail `SteamAPI_Init`; this proves only engine startup, not a valid Steam runtime smoke test.
- A screenshot showing Vietnamese while the locale selector still says `Russian` proves the target locale slot loads. Do not rename the locale label to `Tiếng Việt` until the I2 trailing language metadata has its own copy-only write/reload proof.

## Font gate

If screenshots show square boxes (`□`) in Vietnamese words, translation and serialization are working; the UI font/atlas lacks required glyphs. This is a release blocker.

Before shipping:

1. identify the active UI font asset(s) for menu, buttons, subtitles, and small labels;
2. rebuild/replace the font atlas with full Vietnamese Unicode coverage, including `Ă Â Đ Ê Ô Ơ Ư` and all lower-case accented forms;
3. smoke-test labels that exercise missing glyphs, e.g. `TÙY CHỌN`, `Ngôn ngữ`, `Độ phân giải`, `Đồng bộ dọc`, `Quay lại`;
4. verify Vietnamese diacritics in normal, small, uppercase, and button styles.

Do not replace Vietnamese with unaccented ASCII as a final workaround.
