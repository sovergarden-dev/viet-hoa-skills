# Abyssus (Steam 1721110) — Unreal pak preparation

## Verified baseline (2026-07)

- Install root: `<SteamLibrary>\steamapps\common\Abyssus`
- Steam app ID: `1721110`
- Observed build ID: `23987091`; treat it as a version lock, not a durable current value.
- Main payload: `RGame/Content/Paks/RGame-Windows.pak`.
- `repak info` reported:
  - mount point: `../../../`
  - version: `V11` / `Fnv64BugFix`
  - encrypted index: `false`
  - compression: `Oodle`
  - path hash seed: `0x42EB5A28`
  - 51,683 file entries

## Safe start

1. Record the installed Steam build ID plus pak size/mtime before every extraction.
2. Use `repak info` first. It is read-only and establishes the precise pack settings.
3. Only after the user authorizes work, list/extract to a separate `_viet_work` workspace and locate `.locres`, StringTable/DataTable assets, font assets, and image-text candidates.
4. Preserve English. Prefer a pre-existing Unicode foreign language slot for Vietnamese if the game supports one; populate all rows with English fallback first, then overwrite reviewed Vietnamese. Do not write Vietnamese into `en` unless explicitly requested.
5. Build a reversible installer/uninstaller that validates build ID and hashes before applying anything. Do not distribute the 5+ GB base pak.

## Community launcher evidence boundary

RevoltVH 1.0.6 is a Tauri/WebView2 launcher. Its manifest at `https://vh.revolt.vn/games.json` exposes only Abyssus game metadata, while its binary indicates a generic ZIP download, backup, extract, and restore flow (`.revolt_backupmanifest.txt`). This establishes installer behavior only. Do not infer whether its old patch modified `.locres`, DataTables, or the pak without the actual patch archive.

When the archive is unavailable, record it as unavailable and continue from the current game structure; do not fabricate an old-patch comparison.
