# Unity IL2CPP: decode opaque DialogueSystem and I2 Localization assets with generated type trees

## When this applies

A Unity IL2CPP game has player text in `MonoBehaviour` objects, but UnityPy/AssetStudio only show base fields or fail with an error such as `Expected to read N bytes, but only read 44 bytes`.

## Verified route

1. Fingerprint and retain the live game read-only. Work only in `_viet_work`.
2. Run Il2CppDumper with the game’s `GameAssembly.dll` and `<Game>_Data/il2cpp_data/Metadata/global-metadata.dat`.
3. Use the generated `DummyDll/` as the schema source for UnityPy’s `TypeTreeGenerator`:

```python
from UnityPy.helpers.TypeTreeGenerator import TypeTreeGenerator

gen = TypeTreeGenerator("2020.3.36f1")  # read version from the target asset
# DummyDll is generated from this exact game build:
gen.load_local_dll_folder(".../_viet_work/tools/Il2CppDumper/DummyDll")
node = gen.get_nodes_up("DialogueSystem.dll", "PixelCrushers.DialogueSystem.DialogueDatabase")
data = object_reader.read_typetree(node)
```

4. Pass `node` directly to `read_typetree(node)`. Do not assign a non-existent `object_reader.type_tree` attribute.
5. Resolve a MonoBehaviour’s `m_Script` PPtr before choosing schema. For external file IDs, inspect the owning asset file’s externals; do not search a whole data directory by path ID because many Unity files reuse the same IDs.
6. For PixelCrushers `DialogueDatabase`, extract stable scope as database name + conversation ID + dialogue entry ID + target locale field. Actors and conversation entry order provide speaker/addressee/context.
7. I2 Localization `LanguageSourceAsset` may be present as opaque serialized legacy layouts. Prove its byte layout from a small sample before using it as a release import route. A successful raw string probe is not structural import proof.
8. For legacy I2 sources, extract and count `mTerms` independently before parsing trailing source metadata. In one verified Unity 2020 layout, the `m_Name` string is followed by legacy header bytes and then `mTerms`; each term is `Term`, `TermType`, `Languages` vector, `Flags` vector, and an empty `Languages_Touch` vector. Preserve the untouched trailing bytes and keep this parser extraction-only until a copy-only serialize/reload proof covers the full object.
9. Batch dialogue in source-entry order, but do not require every batch to stay inside one conversation: finish a remaining contextual row, then explicitly record the conversation boundary in the following manifest.

## Important outcomes

- A wrapper MonoScript can inherit a base class from another assembly. If the wrapper schema cannot be generated, generate the base schema (for example `DialogueSystem.dll::PixelCrushers.DialogueSystem.DialogueDatabase`) and validate its complete structured read against the object byte size.
- Il2CppDumper may emit output beside its executable rather than the shell working directory. Verify actual output paths before reporting them.
- Do not treat a successful decode as an import proof. Build a copy-only one-entry write/reload test before modifying any target localization field.

## Windows/MSYS executable paths

When calling a native Windows `.exe` from the MSYS bash terminal, pass native `D:\...` arguments and set `MSYS2_ARG_CONV_EXCL='*'` for that invocation. Otherwise `/d/...` may become `C:\d\...`.
