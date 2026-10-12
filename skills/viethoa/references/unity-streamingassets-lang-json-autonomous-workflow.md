# Unity StreamingAssets `Lang.json` localization route

## Discovery order for Unity games

Before deep-scanning Addressables bundles or recovering IL2CPP type trees, inventory `*_Data/StreamingAssets/` for small structured files, especially `Lang.json`, `Languages.json`, `Localization*.json`, `.csv`, `.tsv`, and custom named language files.

If a readable file contains locale objects such as:

```json
{"Languages":[{"Name":"en-US","Entries":{"key":"source text"}}]}
```

then treat it as the primary localization source. Extract the English locale to a canonical CSV keyed by `Entries` keys. Preserve original bytes and SHA-256 in a workspace. Do not patch Addressables unless runtime evidence shows the JSON is not read.

## Safe autonomous batch translation

- Use a canonical CSV with `key,source,translation_vi,protected_tokens,status,note`.
- Batch stable ranges (for example 75 rows) and merge by exact key/order only.
- Validate every returned batch through Python's `csv` parser before merging.
- Require exact equality for `key`, `source`, and `protected_tokens`; require non-empty `translation_vi` and `status=translated`.
- Independently compare all protected markup/control tokens extracted from source and translation: HTML/TMP tags, button placeholders, escaped control sequences, and `{variables}`.
- A structurally valid translation can still invent text. In delegation prompts explicitly require source-faithful translation with no added sentences, plot details, speaker text, or inferred context. Reject/retranslate any batch where manual spot checks reveal expansion.
- Rebuild the master workbook from validated `batch_*_translated.csv` files so disk state, not agent counters, determines progress after interruptions.
- When all rows are complete, rerun the whole-workbook validation: total rows, translated count, empty translations, and token mismatches must all be zero.

## Import boundary

Completing a CSV/workbook is not permission to modify the game. First create `Lang.json` only in the patch workspace, reload JSON structurally, verify locale selection/import route and visual font/UI behavior on a copy of the game, then package reversible changes.
