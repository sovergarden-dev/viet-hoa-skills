# Unity IL2CPP legacy I2 Localization: safe manual term rewrite and proof

## When this applies

`I2.Loc.LanguageSourceAsset` can be present as an opaque legacy `MonoBehaviour`. Generated Dummy DLL type trees may decode enough to identify it but fail strict reads because trailing source metadata differs from the generated schema.

## Verified extraction layout

For the observed Unity 2020 build:

- `resources.assets:path_id=6343` = `I2Dialogues`.
- `resources.assets:path_id=6344` = `I2Languages`.
- `m_Name` begins at the normal MonoBehaviour body; `mTerms` begins at byte offset 56.
- Each term is serialized as `Term` string, `TermType` int32, `Languages` vector<string>, `Flags` vector<byte>, 4-byte alignment, then `Languages_Touch` vector<string>.
- Everything after the `mTerms` vector is version-specific legacy metadata and must be retained byte-for-byte until fully modeled.

## Copy-only write proof

1. Load `resources.assets` and cache raw bytes for **every** Unity object.
2. Reapply every payload with `set_raw_data` before saving. Without this, UnityPy can emit zero-byte payloads for untouched objects.
3. Parse only `mTerms`; replace target locale index `1` (`Russian` / `ru`) values by stable I2 term key.
4. Re-emit the terms with correct UTF-8 string length and 4-byte alignment.
5. Append the original trailing metadata untouched.
6. Save under `_viet_work/patch/proof_*`, reload with a fresh UnityPy environment, parse again, and verify exact target strings.
7. Inventory `(path_id, type, raw length, SHA-256(raw))` source versus copy. Pass only if object count matches and only intended I2 object(s) differ.

## Observed proof

Changing `I2Languages:6344` target text to `Axit giả kim` yielded:

- source/copy object count: 8,243 / 8,243;
- only `path_id=6344` changed;
- target string reloaded exactly;
- trailing metadata length and bytes matched;
- whole asset size changed slightly, which is valid because UTF-8 text length changes.

## Release boundary

This proves structural serialization, not runtime locale selection. Keep the technical `Russian` slot until an in-game smoke test proves the locale picker and content load. Do not rename the displayed locale to `Tiếng Việt` before that test.
