# Unity TextAsset HTML localization: autonomous batch and patch validation

## Proven route

A Unity game stored its active dialogue in `resources.assets` → `TextAsset` named `Script-EN`. The payload was HTML with `li` rows using CSS classes such as `character`, `id`, `dialogue`, `action`, and `sceneheader`.

1. Parse with an HTML parser, not regex.
2. Retain stable `path_id:sequential_row` key, asset name, CSS class, source, and current speaker inherited from the preceding `character` row.
3. Multiple large script assets may be alternatives/legacy copies. Identify the active runtime TextAsset before translating duplicates.
4. Use canonical CSV for dialogue rows and batch CSVs of 60–80 rows with speaker/order context.

## Batch integrity

- Write every CSV with Python `csv.DictWriter`; never hand-compose comma-delimited rows.
- Read worker output using `utf-8-sig`, because a valid CSV may contain a UTF-8 BOM. Otherwise `key` becomes `\ufeffkey` and merge fails.
- Merge only when `key` and `source_en` exactly match the canonical workbook.
- Validate status against an explicit allowed set. A shifted comma can put Vietnamese text in the status field; repair only when the intended state is independently recoverable from another field, otherwise reject.
- After each merge, recount `reviewed`, `needs_context`, and `pending` from the canonical merged CSV, not batch manifests.

## Final import proof

For UnityPy TextAsset edits:

```python
data.m_Script = changed_text
data.save()
output_path.write_bytes(env.file.save())
```

Then reload the generated asset and prove every reviewed Vietnamese string is present in the active TextAsset. Do not only sample strings. Keep explicit `skipped_debug` rows outside player-visible import scope.

## Reversible install proof

- Hash the live original before installation.
- Installer must refuse unexpected source hash, copy `resources.assets` to `resources.assets.vi-backup`, then install the patch.
- After install, hash both installed target and backup; target must equal patch hash and backup must equal original hash.
- Launch the game only after installation verification and require runtime screenshot/font QA before calling it release-ready.
- `zipfile.testzip()` validates archive integrity only, not game rendering.

## Autonomous pacing

When asked to finish autonomously and fast, schedule continuation at a short cadence (for example two minutes) and stage enough pending batches ahead. Local-only TUI cron jobs preserve work but do not message the chat; say this explicitly. Pause the job after all translation, validation, package generation, and runtime QA conditions are satisfied.
