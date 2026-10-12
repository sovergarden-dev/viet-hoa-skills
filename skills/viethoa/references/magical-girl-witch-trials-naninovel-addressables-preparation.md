# Magical Girl Witch Trials: Unity IL2CPP Addressables + Naninovel preparation

## Proven discovery shape

- Canonical root: `G:\SteamLibrary\steamapps\common\manosaba_game`
- Executable/data pair: `manosaba.exe` + `manosaba_Data`
- Runtime: Unity IL2CPP (`GameAssembly.dll`) with Addressables 2.4.6 (`StreamingAssets/aa/settings.json`).
- `StreamingAssets/config.json` advertised text locales: `ja`, `zh-Hans`; fallback is Japanese.
- Addressables contained paired assets:
  - Japanese routes: `naninovel-scripts_assets_naninovelscripts-*.bundle`
  - Simplified Chinese localized routes: `general-localization-zhhans-scripts-*.bundle`
- The zh-Hans localization `TextAsset` holds a Naninovel document: Japanese source is preserved in semicolon-prefixed comment lines and active zh-Hans text follows. The header `# <id>` gives an entry identifier but is only unique within a TextAsset. Canonical CSV key must be `<TextAsset name>::<id>`.

## Extraction recipe

1. Never write under game root during preparation. Record hashes for executable, UnityPlayer, GameAssembly, globalgamemanagers and catalog before any extraction.
2. Extract each zh-Hans `TextAsset` to a workspace source copy. Build a CSV containing canonical key, speaker, `source_ja`, `source_zh_hans`, empty `translation_vi`, protected tokens, asset, bundle, source hash, status, and review note.
3. Consider a dialogue block translatable only when it has both Japanese source and active zh-Hans text. Skip command-only lines such as speaker declarations and directives.
4. Treat Japanese as translation source and zh-Hans as contextual reference; do not inherit zh-Hans wording as authoritative.
5. Preserve `m_Script` formatting and tags. Block comments, blank lines, `<br>`, ruby, and `|#...|` IDs must survive reconstruction.
6. Validate unique canonical keys, CSV readback row count, protected-token equality for translated rows, and blank Vietnamese cells before translation starts.

## UnityPy Windows note

On current UnityPy Windows builds, call `UnityPy.load(str(path))`, not with a `pathlib.Path`. `TextAsset` content is exposed as `m_Script`, not `script`. Use `obj.type.name` (for example `TextAsset`) rather than matching the string representation of the enum.

## Preparation result from this game build

- 24 zh-Hans script bundles.
- 440 localized TextAssets.
- 34,367 extracted translatable rows.
- The pre-translation workbook was intentionally left with all Vietnamese cells blank and validated at zero errors.

## Remaining safety gate

Before bulk import, make one controlled workspace-copy edit to a bundle, reload it with UnityPy, and assert exact `m_Script` content. Only then design the Vietnamese Addressables/locale route. Runtime and visual QA remain user-driven: do not launch Steam/game automatically.
