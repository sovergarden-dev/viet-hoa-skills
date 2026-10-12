# Unity IL2CPP: PixelCrushers DialogueSystem + legacy I2 Localization extraction

## When this applies

A Unity IL2CPP game has `GameAssembly.dll`, `global-metadata.dat`, PixelCrushers `DialogueSystem.dll`, and I2 Localization classes, but UnityPy/AssetStudio reports an unreadable custom `MonoBehaviour` due to missing type trees.

## Verified extraction route

1. Fingerprint the game and work only from `*_viet_work`.
2. Run Il2CppDumper on `GameAssembly.dll` + `*_Data/il2cpp_data/Metadata/global-metadata.dat`; retain `DummyDll/`.
3. Install `TypeTreeGeneratorAPI` if UnityPy requests it.
4. Load the Dummy DLL directory with `UnityPy.helpers.TypeTreeGenerator`, then create the base schema:
   ```python
   gen.get_nodes_up('DialogueSystem.dll',
                    'PixelCrushers.DialogueSystem.DialogueDatabase')
   ```
5. Identify candidate databases by reading the `MonoBehaviour` base script PPtr. Resolve its external file reference and require that it maps to the `DialogueDatabase` MonoScript in `globalgamemanagers.assets`; do not rely on a globally duplicated `path_id` alone.
6. Decode each database with `obj.read_typetree(node)`. Key dialogue rows as database + conversation ID + entry ID + target localized field. Read `English` as source, use `Russian` and other locales only for context, and retain actor/conversant IDs plus adjacent entries.

## I2 localization

For legacy I2 `LanguageSourceAsset` objects, generated Dummy-DLL schemas can differ from the serialized legacy layout. If strict typetree decode fails, do not import or patch based on it.

A safe extraction-only fallback is a bounded manual parser validated against raw offsets and term counts. In one verified 2020.3 build:

- MonoBehaviour base ends at offset 28; `m_Name` begins there.
- I2 term vector began at offset 56.
- Each term was `Term` UTF-8 string, `TermType` int32, `Languages` vector of strings, `Flags` byte vector, alignment, then an empty `Languages_Touch` vector.
- `I2Dialogues` and `I2Languages` were separate LanguageSourceAsset objects.

Before accepting a manual parse, verify: expected term count, first/last term keys, English/Russian lane alignment, no parser bounds error, and consumed-byte count. Treat unparsed trailing source metadata as out of scope for extraction; it must be structurally understood before any import route is implemented.

## Pitfalls

- Asset path IDs collide across scene files. Resolve `m_Script` with the owning asset file's external table.
- A wrapper MonoScript may inherit `DialogueDatabase`; generate/read the base `DialogueSystem.dll` schema.
- `ObjectReader` does not accept `obj.type_tree = ...`; pass the node: `obj.read_typetree(node)`.
- A successful extraction is not import proof. Do not modify a Unity asset until workspace-copy write, reload, exact cell equality, and in-game smoke test pass.
