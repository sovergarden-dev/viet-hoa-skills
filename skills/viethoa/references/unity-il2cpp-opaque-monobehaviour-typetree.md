# Unity IL2CPP opaque MonoBehaviour: structural recovery without native picker

Use this when UnityPy/AssetStudio finds player text inside a `MonoBehaviour` but reports a short base payload such as `read N bytes but expected M bytes`. This commonly means the asset's custom IL2CPP type tree is absent, not that the text is raw/unstructured.

## Safe discovery sequence

1. Create a canonical native game-root value and verify the executable plus data file exist beneath it before every external-tool launch.
2. If invoking a Windows `.exe` from MSYS/Git Bash, pass native `D:\...` arguments and use `MSYS2_ARG_CONV_EXCL='*'`; otherwise `/d/...` can be rewritten to `C:\d\...`.
3. For a `MonoBehaviour`, inspect `m_Script` as `(m_FileID, m_PathID)`. Resolve `m_FileID` against the owning asset file's external table before searching for the `m_PathID`; IDs are only unique within an asset file.
4. Inventory `MonoScript` assets structurally (`m_ClassName`, `m_Namespace`, `m_AssemblyName`) to prove the runtime type. Do not infer class from raw dialogue strings.
5. Generate IL2CPP metadata from the game's own `GameAssembly.dll` and `il2cpp_data/Metadata/global-metadata.dat` (e.g. Il2CppDumper) and inspect the generated schema for fields, stable IDs, language lists, and dialogue entries.
6. Prefer `UnityPy.helpers.TypeTreeGenerator(unity_version)`, `load_local_game(game_root)`, then `get_nodes_up(assembly, fullname)` to apply a generated type tree to a workspace-loaded object. Decode first; modify only after a copy-only round-trip/reload proof.

## Tool-output rule

Asset tools may write output beside their executable, not the caller's working directory. Check output paths immediately after the first successful run. Configure no-interaction mode before background use when possible.

## Verification gate

Before reporting an extractor as scanning the intended game, require a tool log line that contains the exact canonical game root. A launched process, visible localhost server, or picker click is not proof of correct input.

## Scope

This is discovery/recovery only. It does not authorize direct editing of live assets or raw-byte replacement. Preserve English and prove the target-locale runtime route before patching.
