# Adobe AIR / Flash `.xlg` localization route

## Fingerprint

Typical AIR package markers:

- `META-INF/AIR/application.xml` identifies the AIR namespace, game ID, build, entry SWF, and declared `supportedLanguages`.
- A root `*.swf` is the Flash payload; localization may instead live in ordinary sidecar files.
- `assets/config/dialogs/<locale>.xlg` can be zlib-compressed UTF-8 XML despite the custom extension.

Record the hashes of the source locale, reference locale, `application.xml`, and entry SWF before any write. Read the original-language locale when present; it is essential for Vietnamese register and pronouns.

## Safe preparation

1. Probe each `.xlg` with `zlib.decompress(raw)`; parse the result as XML.
2. Export nonblank element text to a canonical CSV using a stable XML path plus ordinal as the key.
3. Preserve literal `\\n`, leading/trailing whitespace, XML text layout, tags, and placeholders. Use Python `csv` parsing, never physical-line counting.
4. Include columns: `key`, `ordinal`, `section`, `attributes`, `source_en`, `reference_<original locale>`, `translation_vi`, `protected_tokens`, `status`, `notes`.
5. Keep immutable compressed source snapshots in the workspace. Never run a preparation script after work begins if it resets target translations.

## Autonomous translation cadence

Hermes cron runs have a 3-minute hard interrupt and a tick lock. Use one sequential writer at `every 3m`, normally 40 rows per tick for this XML route. Do not run concurrent writers against the canonical CSV.

Per tick:

1. Validate the canonical workbook.
2. Stage the next pending batch only.
3. Translate English with original-language reference and neighboring context where needed.
4. Save a batch JSON mapping exact `key -> translation_vi`.
5. Merge through a single guarded updater that rejects unknown/nonpending keys, blank text, and token mismatches.
6. Re-run the workbook validator and persist translated/pending counts.
7. When pending reaches zero and validation is clean, pause the verified current cron ID. Do not import into the game automatically.

Cron delivery to a local desktop/TUI session may be stored locally instead of appearing as a live chat message. State this accurately; users should inspect the workbook or cron status when no gateway destination is configured.

## Import later

Do not modify the installed game during preparation or autonomous translation. After review is complete, create `vi.xlg` from a copy of the English source and update a copied `application.xml` to declare `vi` only after proving the AIR language-selection route. Require user-run runtime screenshots before release, including menus, long dialog text, small UI labels, and Vietnamese diacritics.
