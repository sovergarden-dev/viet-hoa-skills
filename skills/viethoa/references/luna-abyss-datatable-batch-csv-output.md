# Luna Abyss DataTable batch CSV output

Use this when asked to translate a Luna Abyss DataTable batch CSV such as `translate/datatable_vi_slot/batch_02.csv`.

## Pattern

1. Locate the batch under `LunaAbyss_viethoa_work/translate/datatable_vi_slot/`.
2. Reuse the existing per-batch fill-script pattern when present, e.g. `tools/fill_datatable_vi_batch03.py`:
   - dictionary keyed by row `id`
   - `textwrap.dedent(...).strip('\n')` for long multiline quotes
   - preserve `ImageName` / `Imagename` asset slots exactly
   - write `translation_vi`
   - set `status = done_ascii_slot` for `target_type == ansi`, else `manual_reviewed`
3. If there is no fill script yet, create a real temporary/project script file and run it. Do **not** paste a huge translation dictionary into `terminal(command=...)` on Windows; long inline commands can fail with `WinError 206` before Python runs.
4. If the user asks for a CSV output, write an explicit sibling output file such as `batch_02_output.csv` even if the in-place batch file is also updated.
5. Validate with Python stdlib `csv`:
   - output parses with `csv.DictReader`
   - row count matches expected batch count
   - header/fieldnames unchanged
   - every `translation_vi` is non-empty
   - every `len(translation_vi) <= int(target_max_chars)`
   - status counts match the actual data

## Pitfall

Do not hardcode expected ANSI-slot counts from another batch. Batch 03 had 13 `done_ascii_slot` rows; batch 02 had 11. Compute expected count from `target_type == 'ansi'` in the current batch.

## Reporting

Report only paths and validation numbers:

```text
Output: <path>
Validation: rows=<n>, blank_translation_vi=0, over_cap=0, status={<counts>}
```
