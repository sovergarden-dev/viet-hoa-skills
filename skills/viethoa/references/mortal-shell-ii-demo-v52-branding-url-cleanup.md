# Mortal Shell II Demo v5.2 branding/link + beta cleanup lessons

## Context

Mortal Shell II Demo is UE5 with `.pak` plus IoStore `.ucas/.utoc`. The working Vietnamese build uses the `ru` culture slot and direct `pakchunk0-Windows.pak` rebuild because loose patch paks did not override in-game.

## Branding menu label

The main menu `Feedback` label is in `Game.locres`:

- key: `ST_Core_Misc/FeedbackForm`
- English source: `Feedback`
- Vietnamese/branding target: `Syrin.online`

Patch this through the normal workbook -> `UnrealLocres import` -> direct pak rebuild path.

## Branding click URL

The click action URL was not in `Game.locres` and not in `.pak` asset list. It was an ASCII string inside `pakchunk0-Windows.ucas`:

```text
old: https://forms.gle/vbozJVDF2imowiJg9
new: https://note.syrin.online/#m-shell2
```

Both strings are exactly 35 bytes, so a fixed-length in-place patch is safe for this demo build.

Observed offset in this beta build:

```text
pakchunk0-Windows.ucas offset 477547557
```

Rules:

1. Search `.ucas` streaming for URLs instead of reading the entire 19GB file into memory.
2. Only patch in place when `len(old) == len(new)` and bytes at offset match `old`.
3. Store a tiny backup record of old bytes/offset for uninstall.
4. Do not ship the `.ucas`; compact installers should patch the URL bytes on the user's installed file.
5. If a future official build changes the offset, re-scan for the old URL before patching.

## Compact beta installer strategy

For this project, the best shareable beta package is not a full pak:

- Changed files inside rebuilt pak:
  - `MortalShell2/Content/Localization/Game/ru/Game.locres`
  - `Engine/Content/Localization/Engine/ru/Engine.locres`
  - patched UI font assets with Vietnamese glyph coverage
- Additional direct byte patch:
  - `pakchunk0-Windows.ucas` feedback URL, fixed-length replacement
- Include `repak.exe` locally.
- Installer flow:
  1. Ask for game root.
  2. Backup `pakchunk0-Windows.pak` and the 35 URL bytes from `pakchunk0-Windows.ucas`.
  3. Unpack original pak backup.
  4. Copy changed locres/font files.
  5. Repack `pakchunk0-Windows.pak` using the recorded UE5 settings.
  6. Patch URL bytes in `.ucas` only if old bytes match.
- Uninstaller restores pak backup and URL bytes backup.

## Beta cleanup strategy

Keep for future official release:

- `_viet_work/scripts/`
- `_viet_work/tools/repak.exe`, `UnrealLocres.exe`, Python deps needed for font QA
- `_viet_work/workbook/` final workbook, source exports, glossary/style guide
- `_viet_work/reports/` final reports and QA reports
- `_viet_work/portable/*latest compact installer*`
- `_viet_work/backups/README` and tiny byte-offset backups
- original full pak backup only if disk space allows; otherwise rely on Steam Verify and keep scripts/manifests/checksums

Safe to delete/regenerate:

- full unpack directories (`patch/pakchunk0_full_unpack`, large extracted trees)
- old portable full-pak zips
- old v3/v4/v5 package folders/zips after v5.2 validates
- temporary verification folders and exports

Never delete the final workbook/scripts/reports. They are the source of truth when the beta updates or official build releases.
