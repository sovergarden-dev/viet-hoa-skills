# Canonical validation and merge protocol

Load when creating or repairing a validator, merging any batch, accepting manual `bientaptay` edits, receiving external output, or reconciling a new game build.

## One validator per project

Each project has exactly one canonical validator. Cron, manual repair, `bientaptay` save readback, handoff receipt and release gates call it. The protected-token matcher is one shared module imported by every writer/QA helper; ad-hoc competing regexes are forbidden.

Per row, validate:

- CSV parses with unchanged required header;
- `(domain, key)` is unique and the canonical key set is unchanged;
- `state` is one of `pending`, `translated`, `reviewed`, `needs_context`, `rejected`;
- `translation_vi` is nonblank for `translated`/`reviewed`;
- protected tokens match under the declared format profile;
- source association and release-scope counts are consistent.

Project-specific detail belongs in `status_detail`; it must map to one canonical state. `fallback_english*` remains `pending` for release scope.

## An audit must be calibrated against a known-bad build, and be differential

A validator that has never failed anything is not evidence. Before trusting a new audit:

1. Copy the builder and sabotage it on purpose — reintroduce the exact defect class the
   audit is meant to guard against (a buried diacritic, a shrunk mark, a wrong scale).
2. Build the sabotaged variant to a separate output path so the good artefacts survive.
3. Audit it and confirm the expected checks fire, in the expected number.
4. Only then audit the real build — a clean result now means something.

Prefer **differential** checks wherever a reference exists. "Is this mark 12 units above
its base?" has no answer without a target; "is it in the same relation to its base as the
reference font's own mark?" is answerable and stable across faces with different
proportions. Where no reference exists, derive the bound from the artefact's OWN native
glyphs (e.g. what that font already draws past `hhea`), never from a generic constant.

Apply only the rule each item is actually governed by — checking a horn's overhang rule
against a hook reports failures on every hook. And never slice an upstream report's data
list twice: pairing item N's geometry with item N-1's label manufactures phantom failures
by the dozen.

Related: sibling skill `fonttv`, file_path="references/unity-adventure-creator-monofont-vietnamese-compose.md" (not a viethoa-local reference).
carries the concrete implementation and the full check list (C1..C9).

## Token profiles

Declare profiles per source format. A project may use multiple profiles only when every row/domain explicitly selects one. Profiles may add format rules; they may not weaken base equality checks.

- `generic_tags`: placeholders, actual printf directives, rich-text tags, variables, escapes/control codes and explicit line-break counts.
- `rpgmaker_escaped`: compare on-disk escaped controls such as `\\c[n]`, `\\w[n]`, `\\oi[n]`, `\\t3`, `\\.`; wrapping must not move `\\.` to line start.
- `unreal_macro`: preserve macro invocation count, name, balance and syntax. Translatable macro arguments may change; macro structure may not.
- `xml_air`: require XML well-formedness, correct entity escaping and tag-structure equality.

Do not treat prose such as `50% of max HP` as printf. Do not treat bracketed UI states, labels, or subtitle cues such as `[LOCKED]`, `[NEW]`, `[mumbling]`, `[screaming]` as format tokens; over-broad bracket regexes (e.g. `\[[A-Za-z0-9_]+\]`) falsely reject valid translations like `[ĐÃ KHÓA]`, `[lẩm bẩm]`. Whitespace-only source rows (e.g. `' '`, `'  '`) must be preserved as-is into translation and marked done, never dropped or stripped into empty strings that stall completion. Add every discovered false pass/fail to project test vectors before changing the matcher.

## Writer exclusivity and project lock

Only one canonical writer may operate: cron worker, manual `bientaptay` edit, build reconciliation or external merge. Before writing:

1. pause cron using its verified job ID;
2. confirm no incomplete stage/candidate transaction;
3. verify canonical hash against project state/manifest;
4. record the active operation and exact key set;
5. checkpoint canonical CSV.

An `external_handoff_in_flight` lock contains batch ID and key-set hash and blocks Plan 1 staging over the same key range.

## Atomic write and checkpoint

Before every merge, copy canonical CSV to `checkpoints/<UTC-timestamp>.csv` and record row count, key-set hash, translated/pending counts and source hash. Retain at least the latest 10 plus release-tagged checkpoints.

Write a sibling temp file in the same directory, flush and fsync, then `os.replace(temp, canonical)`. Never edit canonical in place or replace across filesystems. Recovery restores a verified checkpoint; never reconstruct rows manually.

## Stable-key merge guard

- Merge by `(domain, stable key)`, never by row position.
- Do not change canonical key set/header or reorder source data.
- Do not overwrite canonical source/context from untrusted output.
- Do not overwrite nonblank translations outside the exact transaction key set.
- Do not downgrade `reviewed` without explicit reviewed-change workflow.
- On envelope/key mismatch or malformed input, leave canonical untouched and emit a mismatch report.

For external output, envelope validity and per-row validity are separate. If the envelope/exact key set is valid, independently proven clean rows may be accepted atomically while rejected rows are emitted as a stable-key remainder. If envelope identity is invalid, reject the entire submitted subset.

## Commit sequence

`lock → checkpoint → parse → envelope validate → per-row validate/QA → write temp → reload canonical → canonical validator → persist hashes/counts → clear transaction files/lock → allow bientaptay watcher reload → resume one writer if needed`

A transaction is successful only after canonical reload and validator pass. Staging, dispatch or candidate creation is not progress.

## Reference lifecycle

New lessons may begin as game case studies. When the same lesson appears in a third case, promote it into a topic route/protocol and mark competing advice `Superseded:`. Empty/dangling references block skill release. Never delete or merge case files until the target has been diff-checked for every unique technical lesson.