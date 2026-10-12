# Unreal `.locres` full-patch import and QA

## Pre-import gates

1. Run the canonical structural validator, then a **separate corpus QA** over every target string. Structural completeness (`pending == 0`) does not prove language quality.
2. Corpus QA must report, by stable key:
   - forbidden/retired terminology and glossary violations;
   - exact-source English residuals, excluding intentional identifiers, acronyms, proper nouns, code/debug strings and glossary-approved English;
   - known corruption/mojibake and suspicious Vietnamese spelling;
   - protected-token multiset mismatch;
   - unmatched leading/trailing quotes and malformed source fragments;
   - inconsistent translations of repeated source strings;
   - line-break and whitespace anomalies.
3. Do not call the workbook QA-complete while any report remains unreviewed. Community translations and externally supplied rows need the same QA as newly translated rows.

## Import route

1. Export the current-build base `.locres` and use its stable key set as the import authority.
2. Build import CSV from the canonical master using a real CSV writer. Never patch CSV quoting by hand.
3. Import into a workspace copy.
4. Pack the override, unpack the exact final Pak, export its `.locres`, and compare every importable key/value after newline normalization.
5. A tool success count is not proof. Exact readback equality is the gate.

## Malformed source fragments

Some source strings can begin with an unmatched literal quote. A CSV-based importer may report the row as imported while readback retains English or yields an empty target.

When exact readback fails for such a row:

- verify the canonical CSV still parses with the expected header and row count;
- do not mutate canonical quoting merely to satisfy the importer;
- isolate the key into `deferred-import-keys.csv` with reason and desired translation;
- package only the rows that pass exact readback;
- report coverage as `verified/importable`, not `master/master`;
- pursue a native/binary or cooked-asset route separately if the deferred line is player-facing.

## Packaging gates

- Remove or clearly warn about older Paks that override the same locale path.
- Include supported build, mount point, install/uninstall steps, hashes and deferred-key report.
- Run Pak unpack verification and ZIP integrity on the exact final artifact.
- Label the result `offline-validated, pending runtime QA` until screenshots cover menu, quest/task text, dialogue choices, long subtitles, base UI and DLC UI.
