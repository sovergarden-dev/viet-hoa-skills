# Unity IL2CPP DialogueSystem database extraction with Dummy DLL type trees

## Use case

A Unity IL2CPP game stores player text in opaque serialized `MonoBehaviour` objects. UnityPy/AssetStudio may report a short base-object read (for example, 44 bytes) while the serialized object is much larger because the game ships no custom type tree.

## Verified route

1. Inventory `MonoScript` objects structurally. For a target `MonoBehaviour`, inspect its raw base header and resolve `m_Script` through the owning asset's external file table; do not search all asset files by path ID because Unity path IDs repeat per file.
2. Run Il2CppDumper on the game's `GameAssembly.dll` and `*_Data/il2cpp_data/Metadata/global-metadata.dat` to produce `DummyDll/`.
3. Install `TypeTreeGeneratorAPI` if UnityPy reports it missing.
4. Build a UnityPy `TypeTreeGenerator` from the dumped `DummyDll/`, not necessarily its direct IL2CPP loader. Use the actual base class when a wrapper class has no independent serializable fields.
5. Pass the generated node directly to UnityPy:
   ```python
   data = obj.read_typetree(node)
   ```
   Do not assign `obj.type_tree`; current UnityPy `ObjectReader` has no such property.
6. Persist decoded JSON, then construct canonical CSV keys from asset path ID plus domain IDs such as database/conversation/entry/target-field. Treat a foreign locale field as the technical Vietnamese slot only after proving its runtime selection and keeping English source unchanged.

## Pixel Crushers Dialogue System

`DialogueDatabase` has stable structures: actors, conversations, `DialogueEntry` IDs, and field lists. The localized entry field (e.g. `English`, `Russian`) is preferable to raw `Dialogue Text`; derive speaker/addressee from entry fields with conversation-level fields as fallback, and provide neighboring entries as translation context.

## Checks

- Record object path ID, script assembly/class, decoded root keys, actor and conversation counts.
- Verify every extracted row points to a localized target field, not an arbitrary raw string occurrence.
- Never write/import until a workspace-copy round-trip reload succeeds.
