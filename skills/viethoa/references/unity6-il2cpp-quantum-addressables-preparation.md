# Unity 6 IL2CPP + Quantum Addressables preparation

Use when a Unity 6 IL2CPP game ships a binary Addressables catalog, very large local bundles, and Quantum database payloads such as `.qpure`.

## Proven preparation route

1. Bind the scan to the canonical executable, `*_Data`, and workspace paths. Record Unity version from `globalgamemanagers`, Addressables version from `StreamingAssets/aa/settings.json`, and hashes for the executable, `UnityPlayer.dll`, `GameAssembly.dll`, `globalgamemanagers*`, `resources.assets`, and catalog files.
2. Index bundle path, size, and SHA-256 before structural scanning. Very large scene/prefab bundles can exceed tens of GB; use a resumable progress report and prioritize likely data bundles before broad scene scans.
3. With current UnityPy, `str(obj.type)` may render as the numeric class ID rather than `ClassIDType.TextAsset`. Detect `TextAsset` with `int(obj.type) == 49`.
4. UnityPy may expose binary `TextAsset.m_Script` as a Python `str` containing surrogate-escaped bytes. Recover exact bytes with `script.encode("utf-8", "surrogateescape")` when `m_Script` is a string; use `bytes(script)` otherwise.
5. A successfully recovered `.qpure` payload that is not UTF-8 is binary Quantum data, not a directly editable localization source. Record object name, path ID, byte count, and decode status; do not raw-patch it.
6. Search IL2CPP metadata only as routing evidence for localization types. Resolve the exact localization service/type and owning serialized assets with DummyDll/type-tree discovery before exporting player-visible text.
7. If all useful candidates are opaque `MonoBehaviour` or Quantum payloads, defer expensive world-scene scans until type ownership narrows the route. This is evidence-based prioritization, not proof that scenes contain no text.

## Verification gates

- The inventory reports zero per-object extraction errors.
- Recomputed hashes for critical installed files still match the preparation manifest.
- No canonical translation workbook is created until stable keys and player-visible source text are structurally proven.
- Preparation status reports `translated_rows=0`; discovery and staging are not translation progress.
- Never launch the game during offline preparation.
