# Unity StreamingAssets `Lang.json`: Vietnamese technical-slot patch

## Discovery

A Unity IL2CPP Addressables game exposed its primary player-visible text in `*_Data/StreamingAssets/Lang.json`, independently of Addressables bundles. Addressables scans may reveal dialogue IDs and UI prefabs but need not be the translation import route.

The file shape was:

```json
{"Languages":[{"Name":"en-US","Entries":{"stable_key":"English"}}, ...]}
```

Existing locale slots included `zh-CN`; it was selectable and Unicode-capable. Use such a slot only after proving it exists in the live file and preserving English `en-US` intact.

## Build route

1. Copy `Lang.json` into workspace and hash it before any edit.
2. Extract the English `Entries` object to a canonical UTF-8-SIG CSV: `key,source,translation_vi,protected_tokens,status,note`.
3. Validate every row before import:
   - `status == translated`
   - nonempty Vietnamese
   - exact preservation of tokens matching `<[^>]+>`, `\\[A-Za-z]+\\d*`, and `{...}`.
4. Start the target slot from a full copy of English entries, then overwrite all translated values. This covers target-slot omissions; never leave Chinese/Russian fallback mixed into the Vietnamese slot.
5. Change the language-menu display string (e.g. `ui_opt_game_lang_chinese`) to `Tiếng Việt` while retaining the technical locale name (`zh-CN`) unless code-level locale registration is separately proven.
6. Serialize UTF-8 JSON to `patch_files/<Data>/StreamingAssets/Lang.json`; reload it and assert every translated key is present and exact.

## Installer and QA

- Ship only the changed `Lang.json`, plus a manifest containing expected original SHA-256 and payload SHA-256.
- Installer must refuse an unexpected live hash, create `Lang.json.vi-backup`, copy payload, then verify backup/original and target/payload hashes.
- Uninstaller must refuse a post-install modified target, restore exact backup, verify original hash, then remove only the owned backup.
- Test install/uninstall against a sandbox containing the executable and copied target file before touching the live game.
- A running patched process is only smoke evidence. Require in-game screenshots for `Tiếng Việt` selection, diacritics, menu clipping, and dialogue before release-ready status.

## Quality pitfall

Structural CSV/token checks do not detect added dialogue content. Reject translations that expand a short source line into invented plot details or extra sentences; require source-faithful translations before merge.
