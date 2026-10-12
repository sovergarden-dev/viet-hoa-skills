# Unity 6 IL2CPP I2: preparation, payload parsing, and cron recovery

## Trigger

Use when a Unity 6 IL2CPP game stores its main corpus in an opaque I2 `LanguageSourceAsset`, UnityPy lacks a typetree, or an autonomous cron reports `ok` while canonical progress stalls.

## Route proven on Unity 6000 + metadata v31

1. Lock executable, `globalgamemanagers.assets`, `GameAssembly.dll`, `global-metadata.dat`, build ID and hashes from the same install.
2. Locate the opaque `MonoBehaviour` by object payload/name and resolve its `MonoScript`; do not mistake small Unity Localization Addressables tables for the main I2 corpus.
3. Use AssetRipper/Il2CppDumper on the same build to recover `LanguageSourceAsset`, `LanguageSourceData`, `TermData` and `LanguageData` schema. Direct TypeTreeGenerator IL2CPP lookup may fail on metadata v31; same-build dummy assemblies can still document fields.
4. If generated typetree reads fail (`read_str out of bounds`), parse only the evidenced serialized prefix and `mTerms` layout. For the observed I2 layout: MonoBehaviour base, `m_Name`, a version-specific control block, term count, then each term as `Term`, `TermType`, `Languages[]`, `Flags[]`, `Languages_Touch[]`, all with Unity 4-byte alignment. Require parser position to equal exact payload length; preserve trailing metadata byte-for-byte when rewriting.
5. Treat I2 specialization tags such as `[i2s_XBox]`, `[i2s_PS5]`, `[i2s_Switch]`, `[i2s_PC]` as protected tokens in the single canonical matcher.
6. Before saying preparation is complete, populate canonical, assert full-key uniqueness/hash, run token vectors, audit fonts, build validator/stager/merger/importer and pass one-row copy-only roundtrip where only the intended I2 object changes after reload.

## Cron stall recovery

Symptoms: cron creates translated 40-row batches repeatedly with the same key-set hash, project-state counts advance, but canonical hash/mtime and validator counts do not.

1. Pause verified cron job before inspection.
2. Validator counts from canonical are truth. Compare canonical hash/mtime against project-state and recent batch manifests.
3. Identify newest batch whose exact full-key set remains all `pending`; require valid envelope, source/protected-token equality, allowed states and nonblank translated targets.
4. If project-state is stale while canonical is clean and no writer is active, atomically sync state from canonical.
5. Merge exactly one valid batch with the canonical merger; checkpoint, reload and validate. Quarantine malformed batches and archive committed ones.
6. Resume only after cron prompt/script requires post-commit proof: canonical hash/mtime changed, processed count increased by batch size, pending decreased by batch size, validator clean, project-state matches canonical.

## Pitfalls

- AssetRipper `ok`/loaded server is not proof it exported opaque fields.
- Candidate generation is not progress.
- Updating project-state before canonical commit creates false progress and blocks later merges.
- Repeated batches with identical key-set hash indicate stalled canonical, not higher throughput.
- Static font cmap coverage is necessary but not runtime TMP/atlas/material proof.
