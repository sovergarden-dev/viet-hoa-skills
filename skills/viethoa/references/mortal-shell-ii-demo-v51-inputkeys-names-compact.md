# Mortal Shell II Demo v5.1: Engine InputKeys, English names, compact installer

Session lesson from a UE5 `.locres` Vietnamese patch using Russian as the technical culture slot.

## Problems observed after Vietnamese loaded

1. **Russian key names remained in keybindings** even though `Game.locres` was fully Vietnamese.
   - Cause: visible key names like `Левая клавиша "Alt"`, `Правая кнопка мыши`, `Пробел` came from `Engine/Content/Localization/Engine/ru/Engine.locres`, not project `Game.locres`.
   - Fix: export `Engine/en/Engine.locres` and `Engine/ru/Engine.locres`; for Russian slot, copy all `InputKeys/*` and `EnhancedInput/*` rows from English into the Russian target locres.
   - Verify by exporting patched Engine ru locres and checking `InputKeys/*|EnhancedInput/*` for Cyrillic count `0`.

2. **Item/boss/location/Shell/Tarstone names were machine-translated** into awkward Vietnamese (`Common Moonshine` -> `Ánh trăng chung`, `Weltcap` -> `mũ lưỡi trai`, `The Acolyte` -> `Người giúp việc`).
   - User preference: keep name-like game terms in English; translate descriptions/dialogue/UI instructions.
   - Rule: revert name-like keys (`ItemName`, `*Name`, boss/location/groupfight/shell/tarstone/seal title/filter/title rows) to `source_en`, but keep `Desc`, `FlavorText`, `GameplayDesc`, dialogue, prompts, and tutorial text Vietnamese.
   - Validate samples: `Common Moonshine`, `Weltcap`, `The Acolyte`, `Untarnished Seal`, while descriptions like `Nghỉ ngơi tại Beacon` / `Sử dụng Gloom Siphon` remain Vietnamese.

3. **Full direct-pak distribution was too large** (~921 MB).
   - Better sharing package: compact installer zip containing only changed files plus `repak.exe`.
   - Changed files used here:
     - `MortalShell2/Content/Localization/Game/ru/Game.locres`
     - `Engine/Content/Localization/Engine/ru/Engine.locres`
     - patched font assets, e.g. `PTSerif-Regular/Bold/Italic.ufont`, `Trajan_Pro_Regular.ufont`
   - Installer flow on target PC:
     1. Ask for game root.
     2. Backup `MortalShell2/Content/Paks/pakchunk0-Windows.pak` once as `.viethoa_backup_original`.
     3. `repak unpack` backup to temp.
     4. `xcopy` changed files over unpack tree.
     5. `repak pack --version V11 --path-hash-seed <decimal seed> --compression Oodle` into a new `pakchunk0-Windows.pak`.
     6. Copy over original; uninstall restores backup.
   - Size dropped to ~6.5 MB while preserving a full-pak fallback for emergencies.

## Verification pattern

After build, unpack only these paths from installed pak and export locres:

- `MortalShell2/Content/Localization/Game/ru/Game.locres`
- `Engine/Content/Localization/Engine/ru/Engine.locres`

Check:

```text
Game ru Cyrillic count: 0
Engine InputKeys/EnhancedInput Cyrillic count: 0
Sample keys:
InputKeys/LeftAlt = Left Alt
InputKeys/RightMouseButton = Right Mouse Button
InputKeys/SpaceBar = Space Bar
/CommonMoonshine key = Common Moonshine
/Weltcap key = Weltcap
ST_Core_Shells/TielSubname = The Acolyte
tra/BeaconInteractText = Nghỉ ngơi tại Beacon
ST_Core_Interactions/UseSiphon = Sử dụng Gloom Siphon
```

## Pitfalls

- Do not assume residual Russian visible in UI belongs to project `Game.locres`; key names and engine labels can live in `Engine/Content/Localization/Engine/<culture>/Engine.locres`.
- Do not use Vietnamese no-diacritic text as a final fix for font loss; patch font assets first. No-diacritic text is only a diagnostic fallback.
- Do not ship a huge full pak when changed files are small and a local repack installer can rebuild from the user's own pak.
- Do not translate name/title rows indiscriminately; keep proper nouns and item/title-like game terms English when the user says Vietnamese calques sound wrong.
