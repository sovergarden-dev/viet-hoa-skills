# Unity IL2CPP Addressables: pre-translation discovery for large bundle sets

## Use case

A Unity IL2CPP game has `GameAssembly.dll`, Addressables `catalog.json`, and a large `StreamingAssets/aa/<platform>` bundle directory. The user asks to prepare first, then explicitly authorizes translation.

## Safe preparation sequence

1. Confirm the canonical executable and matching `*_Data` directory.
2. Create `C:\Users\<user>\viethoa\<GameName>\` outside the game. Create at least `reports/`, `source/`, `patch_files/`, `backups/`, `scripts/`, `qa/`, and `release/`.
3. Do not copy or edit game files during preparation. Hash the executable, `UnityPlayer.dll`, `GameAssembly.dll`, `globalgamemanagers`, and Addressables `catalog.json`; then index all bundles with relative path, byte size, and SHA-256.
4. Parse `catalog.json` as metadata, but do not use simple substring hits as localization proof: Addressables stores compact/binary-encoded entry data and base64-like content.
5. Scan bundles structurally with UnityPy. Inventory object types for every bundle. For `TextAsset`, collect `m_Name`, byte count, and a bounded UTF-8 preview only as discovery evidence. Write a durable JSON report.
6. After discovery identifies candidate serialized StringTables, inspect their `MonoBehaviour` fields, locale code, table name, and stable entry IDs. Extract English source plus the chosen runtime locale. Compare both directions because target-only tables can exist.
7. Before any bulk import, make one workspace-copy edit, serialize, reload the emitted file, and assert the exact target value. Never write to the live game path before this proof and runtime QA.

## Scale rule

For thousands of bundles, run the structural scan as a tracked background process and persist progress every fixed batch. The final report must include scan count and per-bundle errors, so an interrupted run can resume from evidence instead of assuming completion.

## Common mistake

A catalog keyword search may produce many false positives from encoded internal data. It is a routing hint only; UnityPy object-level evidence determines whether a bundle contains localizable content.
