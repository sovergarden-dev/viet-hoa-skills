# Unreal community patch versus current DLC gap audit

Use when a community `.pak` override may predate a DLC or game update.

## Read-only procedure

1. Locate mod overrides under `Content/Paks/~mods/`; record the exact patch hash and preserve the live install.
2. Use `repak info` and `repak list` on the override. Its mount point and file list define scope. A patch that contains one `.../Localization/<target>/en/<target>.locres` only covers that localization target.
3. Extract the current English counterpart from the installed readable companion `.pak` into the workspace. Do not infer localization coverage from IoStore `retoc list` output alone: games can retain authoritative `.locres` files in a companion legacy `.pak`.
4. Export both `.locres` files to CSV and reconcile by stable `key`, not text order. Report:
   - current source key count;
   - override key count;
   - intersection/coverage;
   - source keys missing from override;
   - override-only stale keys;
   - common keys still equal to English.
5. Create one canonical missing workbook with source, Vietnamese target, protected-token column, `reviewed`, and `needs_context`.
6. DLC keyword filtering is triage only. It can produce a short priority workbook, but retain the full missing-key workbook for a complete later phase.

## Two-phase delivery

- Phase 1: translate and package only verified DLC-related keys. Keep it as an additive override payload, with a separate manifest/readme and no replacement of the existing community patch.
- Phase 2: reconcile every remaining current key plus unchanged-English keys; then create the complete replacement/additive patch.
- Never claim a DLC filter is exhaustive without source-key reconciliation and user runtime screenshots.

## Autonomous cron guard

A translation cron that must pause itself on `pending == 0` needs the `cronjob` toolset enabled. Otherwise it cannot honor the completion-stop rule. Use one sequential writer, run the canonical validator after every merge, and synchronize derived views only after the validator passes.
