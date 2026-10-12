# The Alters — UE5 IoStore DLC coverage audit

## Scope

Use for an installed The Alters community Vietnamese override when a newer Steam build/DLC may add untranslated text. This is a read-only preparation/audit route. Do not launch the game and do not write any live game file.

## Proven layout (Steam build 24262921)

- Canonical root: `G:\SteamLibrary\steamapps\common\The Alters`
- Base IoStore: `TheAlters\Content\Paks\TheAlters-Windows.utoc` + `.ucas`
- Readable companion archive: `TheAlters\Content\Paks\TheAlters-Windows.pak`
- Community mod location: `TheAlters\Content\Paks\~mods\*.pak`
- Authoritative player-facing locale domain: `TheAlters/Content/Localization/P9Playable/en/P9Playable.locres`

The companion `.pak` can carry the directly extractable English `P9Playable.locres` even though the installation also uses IoStore. Prefer this source before attempting broad IoStore extraction.

## Audit sequence

1. Fingerprint the current root and record Steam build ID from `appmanifest_1601570.acf`.
2. Find mod Paks under `Content/Paks/~mods/`; inspect each using `repak info` and `repak list`.
3. Extract mod Paks only to the workspace. A mod rooted at `Localization/P9Playable/en/` establishes it overrides English locale resource data.
4. List/extract the base `P9Playable/en/P9Playable.locres` from the companion base Pak with `repak`.
5. Export both locres files with UnrealLocres to CSV. Its rows are `key,source,target`; for this workflow the active localized text appears in `source`. Confirm this from sample output rather than assuming a generic target column convention.
6. Compare stable `key` values, not line count or string text. Produce:
   - all base keys absent from the override;
   - common keys whose override `source` still equals current English;
   - override-only keys, retained for compatibility review.
7. Export missing rows to canonical CSV with `key`, `source`, `translation_vi`, `protected_tokens`, `reviewed`, `needs_context`.
8. Make a separate **keyword triage** CSV for likely DLC rows. Label it heuristic, never claim it represents the complete DLC scope. Reconcile every missing base key before release.

## Last Variable triage vocabulary

Useful initial routing terms include `Last Variable`, `cryosleep`, `Cryochamber`, `Old Scientist`, `Gamer's Den`, `Card Game`, `Hot Phase`, `Underground Base`, `Oasis`, and `Terraformer`. These terms route likely expansion rows but can match shared/base-game material.

## Reporting boundaries

State both counts: all missing current keys and heuristic DLC-candidate keys. Do not call all missing rows DLC-only. Current base updates can also add/rekey base-game text. Do not infer runtime behavior from an offline Pak structure; runtime screenshots remain required after a future import.

## Tool notes

- `retoc list` may output chunk IDs without package paths for this title. Preserve its report, then use the readable companion Pak for `P9Playable.locres` extraction.
- `repak info` shows Pak format/mount point and `repak list` identifies override scope.
- Verify downloaded workspace-local tools against publisher checksums when available. Keep tools outside the game directory.
