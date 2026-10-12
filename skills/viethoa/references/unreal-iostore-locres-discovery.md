# Unreal UE5 IoStore localization discovery

Use when an older community localization is a legacy `.pak`, while the installed UE5 game ships `.utoc`/`.ucas` IoStore containers.

## Read-only discovery sequence

1. Record the canonical physical game root, executable, Steam build ID, and hashes of every `.pak`, `.utoc`, and `.ucas` sidecar.
2. Inspect the old patch with `repak info` and `repak list`. Extract it only to the workspace. `.locres` plus `.ufont` in an old patch establishes its scope, not compatibility with the current build.
3. Inspect each live container with `retoc info`; capture container version, header version, mount point, compression, chunk count, and package count. Redirect `retoc list` output to a report: it can be megabytes.
4. Try a narrow `retoc to-legacy --filter '*.locres'` extraction. Zero results means only that `.locres` is not a directly convertible package; do not conclude the game has no localization.
5. If a CUE4Parse scanner is required, invoke it against the physical canonical game root. Do not use a symlink/junction/mirror for the archive root: some providers detect container metadata but mount zero virtual files. Write scanner output to the workspace.
6. If a scanner needs a newer .NET runtime, prefer a workspace-local official runtime archive, verify its published checksum, and set `DOTNET_ROOT` only for that command. Do not modify the system runtime solely for a localization scan.

## Packaging boundary

Do not install the legacy patch, replace live containers, or claim an IoStore patch is compatible until a generated payload passes offline structural verification and the user performs Steam runtime QA.
