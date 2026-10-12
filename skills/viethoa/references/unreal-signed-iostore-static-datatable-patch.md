# Unreal signed IoStore — static DataTable patch from community artifacts

Use when a UE5 game stores localization in cooked DataTables inside signed/encrypted IoStore and a community patch proves an override route.

## Architecture priority and stop rules

Prefer this order:

1. Current-build cooked DataTable DLC with a build-guarded Pak + IoStore signing-policy patch.
2. Existing plugin/localization API that loads external structured data.
3. Runtime DataTable mutation only as a diagnostic fallback.
4. Per-widget hooks, polling, hotkeys and persistent `FText` injection are rejected for release.

Stop a route after two controlled failures that produce no new evidence. Never proceed from `retoc verify` alone: structural verification does not prove mount, package priority, header compatibility, font rendering or shutdown safety.

## Community artifact archaeology

Inspect shared patches statically before inventing a loader:

- hash every input;
- unpack archives without running launchers;
- decompile managed launchers and inspect scripts/config;
- inventory proxy DLL/ASI/UE4SS, `.pak/.utoc/.ucas/.sig`, fonts and loose files;
- record container ID, TOC/header versions, flags, mount point, package/chunk IDs and compression;
- compare exact current-build package IDs for representative tables (`MainMenu`, `Settings`, dialogue);
- treat community text as evidence only, never canonical translation;
- audit license/provenance before redistribution; official game `.ucas/.utoc` or community `global` sidecars are runtime evidence, not redistributable defaults;
- if only a discovery companion is needed, generate a minimal project-owned sidecar with a verified open-source tool, include its license, forbid known official/community hashes in candidate/final, and A/B runtime-test only that variable before promotion.

A working community container can prove architecture even when its translation/branding is unacceptable. Use one-variable isolation: keep the known-good container while replacing only the loader/policy layer, then keep the proven loader while replacing only the canonical container.

## Signed Pak + IoStore discovery

Signed IoStore patches can require two independent policy changes:

1. **Pak discovery:** `FPakPlatformFile` may set `bSigned` from `GetPakSigningKeysDelegate().IsBound()`. An unsigned companion `.pak` can be rejected before its `.utoc` is discovered.
2. **IoStore TOC:** `FIoStoreTocResource::Read` may reject an unsigned TOC with `Missing signature` when signing policy is enabled.

Do not use a “universal” bypass that patches the first signature match or replaces an entire function with `mov al,1; ret`. It can patch a lazy initializer, skip side effects and return pointer `0x1`.

For a build-specific policy DLL:

- map source functions from the exact Unreal branch to EXE strings/xrefs/disassembly;
- patch only decision branches, preserving initialization and signed-container validation;
- require exact EXE SHA-256 plus exact original-byte guards for every patch;
- validate all guards before writing any byte;
- read back patched bytes and log each policy independently;
- retain signed validation for original containers;
- package rollback and reject unknown builds.

## Version discipline

Keep these separate:

- reported/asset package version;
- `EIoStoreTocVersion`;
- `EIoContainerHeaderVersion`;
- UAssetAPI parser version.

Never change only a container header tag. A `SoftPackageReferencesOffset` payload mislabeled `NoExportInfo` can pass `verify` yet panic/fail during Zen readback or runtime resolution.

Use the current build as source. Extract it with the serializer matching its real container header. Mixed-version containers in the input directory must be temporarily removed under hash guard and restored in the same transaction.

UAssetAPI load/reload versions must match the extracted legacy header. If UE5.4 extraction is used, a writer hardcoded to UE5.6 can fail before reading custom versions.

## Static DataTable pipeline

1. Lock current game build ID, EXE hash, AES key and container hashes.
2. Extract current-build localization assets to legacy form using the real header-compatible engine version.
3. Reconcile canonical against current `(domain, stable key)` and Japanese source:
   - carry only unchanged Japanese source + protected tokens;
   - remove obsolete keys;
   - keep new blank/debug rows blank;
   - translate new player-facing Japanese rows before release.
4. Write exact stable keys into workspace copies; reload every asset and assert export/row counts.
5. Stage only `.uasset/.uexp`; keep writer reports/JSON outside the cook input.
6. Cook with the native serializer that naturally emits the required header; do not use a header-version override as conversion.
7. Verify container metadata and exact final readback:
   - expected package count;
   - `retoc verify`;
   - Zen → legacy with the matching engine version;
   - exact `.uasset/.uexp` set and SHA-256 equality.
8. Validate fonts by both cmap/codepoint inventory and runtime screenshots.
9. Install under hash guard; user performs runtime QA.

## Diagnostic hierarchy

When the game starts clean but text stays original:

1. Prove policy DLL loaded from its own log.
2. Test a known-good community DLC with the custom policy.
3. If still original, inspect both Pak discovery and IoStore policy; do not rebuild text again.
4. Compare exact package IDs and `_P` priority naming.
5. Only after policy/priority is runtime-proven diagnose canonical container serialization.

When a conversion fails:

- one-package proof first;
- deterministic per-package isolation;
- split-set test;
- inspect non-asset files in cook input;
- distinguish writer panic from reader/readback panic;
- never promote split containers whose package payload cannot be read back exactly.

## Runtime gates

The user runs the game; do not use computer control for gameplay QA. One final session should cover:

- Main Menu and version/branding;
- Settings descriptions/values;
- loading tips;
- item/equipment stats;
- interaction prompts;
- quest/map;
- dialogue/subtitles;
- Vietnamese glyphs, wrap/clipping;
- clean shutdown.

Runtime success must explicitly record startup, visible canonical Vietnamese, branding, representative coverage and shutdown. Only then mark `release_verified`.

## Failure lessons

- Repacking full original IoStore with generic `pack-raw` can lose Oodle/signature/global-shader metadata despite offline `verify`.
- Unsigned `_P` containers can mount yet fail duplicate-package resolution when signing policy/header layout is wrong.
- Lua-created `FText` stored in thousands of DataTable rows can work during play but crash in CRT/static teardown due to ownership/refcount lifetime.
- Delayed Lua widget callbacks can use-after-free destroyed UObjects.
- A community launcher that works is evidence, not automatically the best release architecture.
