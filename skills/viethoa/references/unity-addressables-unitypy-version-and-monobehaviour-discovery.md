# Unity Addressables: UnityPy version fallback and MonoBehaviour discovery

## When bundles have no embedded Unity version

Some Addressables bundles omit a usable Unity version. UnityPy then fails every bundle with `UnityVersionFallbackError` unless a fallback is configured.

1. Read the canonical game's `*_Data/globalgamemanagers` bytes.
2. Extract the Unity version (for example, `2022.3.17f1`).
3. Set it **before** every `UnityPy.load()` call:

```python
import UnityPy
UnityPy.config.FALLBACK_UNITY_VERSION = "2022.3.17f1"
```

Treat the fallback warning as expected only after the version is evidenced from the same game root. Do not guess a version or reuse one from another Unity game.

## Serialized MonoBehaviour discovery

For Unity Localization or custom dialogue systems with no `TextAsset` strings:

1. Scan `MonoScript` assets across candidate bundles first. Record `m_Name`, `m_ClassName`, `m_Namespace`, and `m_AssemblyName`.
2. Resolve the owning `MonoBehaviour.m_Script` pointer against the owning serialized file/external table.
3. Only then read matching MonoBehaviour type trees and identify stable keys/fields.
4. `read_typetree(wrap=False)` returns a plain Python mapping in current UnityPy. Serialize with `json.dumps(..., default=str)` for inspection; do not call `.to_json()` on the returned mapping.
5. Do not select candidate objects merely because their serialized tree contains generic terms such as `text` or `dialogue`; built-in components and unrelated scene objects create false positives.

Use a one-entry workspace-copy roundtrip and exact reload assertion before any batch extraction or write.
