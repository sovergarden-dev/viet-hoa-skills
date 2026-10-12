# Unity IL2CPP MonoBehaviour text: type-aware recovery before localization

## Trigger

Use when a Unity IL2CPP game stores apparent player text inside `MonoBehaviour` assets, but UnityPy cannot deserialize the object because the serialized type tree/script definition is unavailable.

## Evidence pattern

A raw scan can locate readable strings and a Unity asset parser can map each offset to a containing `path_id`, yet this is still **not** an editable localization route. Typical UnityPy evidence:

```text
ValueError: Expected to read <object size> bytes, but only read <small prefix>
```

This indicates that reading the managed MonoBehaviour needs recovered type information; it does not authorize raw byte patching.

## Safe workflow

1. Keep the raw scan only as discovery metadata.
2. Map each candidate to `file + object path_id + relative object offset` to prove scope and identify high-value containers.
3. Inventory object types. If most candidates are `MonoBehaviour`, inspect a representative dialogue object before building a translation workbook.
4. Use a type-aware exporter such as AssetRipper against a workspace copy or the read-only game folder. Load the full game root so it can resolve Unity version, IL2CPP metadata, and referenced assets.
5. Export/dump the recovered MonoBehaviour schema and data. Identify the actual dialogue/UI fields, ordering, speaker/name fields, branching links, and any external references.
6. Create canonical CSV only from structurally exported fields. Stable keys must include at least source file, object `path_id`, field/array path, and source hash.
7. Before bulk translation, prove a one-entry round trip in `patch/`: patch a workspace copy through the same structural writer, reload with the exporter/parser, assert exact target text, then launch the game.
8. Never treat object-relative raw offsets as release patch instructions. They are useful as audit metadata only.

## Notes

- A headless GUI server can expose AssetRipper in a browser, but native `Open Folder` pickers may require an interactive desktop route. This is an operational detail, not a reason to fall back to binary replacement.
- Do not publish or translate based on raw strings mixed with object names, font licenses, input paths, editor labels, and player text.
