# Unity IL2CPP localization: fast semantic batches without duplicate scope

## Problem

Accelerating contextual translation by raising batch size or scheduling workers can accidentally create overlapping manifests when a prior manifest still has pending rows. Later workers then translate the same stable keys in multiple batches, producing conflicting audit state even when the workbook itself remains correct.

## Safe fast path

1. Treat the canonical workbook as the only source of truth for row status.
2. Before creating a batch, reconcile every existing numeric `manifest_NNN.json` against workbook rows by `stable_key`:
   - all rows `reviewed` with nonblank target: mark manifest reconciled/reviewed;
   - any pending rows: resume this **lowest-numbered incomplete** manifest;
   - never create a new batch while an earlier manifest has pending rows.
3. Put `row_count`, stable keys, source hashes, conversation IDs, and context file in each manifest.
4. Apply translations only if the current source hash matches the manifest source hash.
5. Validate the complete manifest after merge: target nonblank, placeholders/tags/control codes preserved, no unintended fallback language.
6. Update checkpoint counters from the actual CSV only after validation passes.

## Throughput guidance

- 20 rows suits sensitive dialogue or uncertain relationships.
- 60–80 rows can be used when each row retains speaker and neighboring context and a semantic review pass processes the whole packet.
- Do not use rule-only translation as completion: it may safely fill repeated UI/action forms, but all remaining semantic rows still require reviewed Vietnamese.
- A scheduler should run one complete batch at a time, not pre-create multiple pending batches.

## Full-object UnityPy writes

When emitting a modified Unity asset, source and output whole-file byte sizes may differ because target UTF-8 strings differ in length. Validate by fresh reload plus object inventory: all object IDs/types remain, only intended DialogueDatabase objects differ, and every intended target value reloads exactly.
