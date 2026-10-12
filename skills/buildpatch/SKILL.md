---
name: buildpatch
description: Build and verify transactional Windows patch installers.
version: 0.5.1
contract_version: "1.0.0"
author: Rurus, Hermes Agent
license: MIT
platforms: [windows]
metadata:
  hermes:
    tags: [windows, installer, rollback, patch-packaging]
    related_skills: [viethoa]
---

# Buildpatch

Build a single-EXE Windows patch installer from runtime-accepted artifacts. This skill owns packaging, transactional install/uninstall, rollback, GUI, sandbox tests, and release promotion. It does not own translation, asset extraction, localization QA, font selection, or game runtime acceptance.

## When to Use

- Build or repair a game/mod patch installer after payload runtime acceptance.
- Package multiple replaced files or sparse patches into one reversible transaction.
- Verify clean install, reinstall, uninstall, refusal, rollback, and final EXE integrity.

Do not use while localization content, runtime hashes, or target build remain unsettled. Keep candidate installation scripts outside the final installer lifecycle.

## Prerequisites

Require an immutable handoff manifest containing:

- supported build ID and executable SHA-256;
- every relative destination path;
- source and target size/SHA-256;
- payload path and format (`full`, `sparse`, or owned addition);
- ownership and uninstall policy;
- runtime acceptance evidence tied to exact target hashes.

Refuse packaging when any payload is labeled preview, near-final, pending runtime QA, or blocked.

## Lazy-load contract

Load only the reference matching the current step. For delta payloads, read `references/compact-self-contained-delta-installers.md` and `references/packaging-pitfalls.md`; for artwork/UI, read `references/installer-ui-anti-slop-and-artwork-safe-zones.md` **and** `references/installer-gui-contrast.md` (colour, label boxes, panel translucency, the screenshot acceptance loop). Do not preload references for a route that is not active. Keep the transaction and rollback rules below in context for every build.

Start GUI work from `templates/installer-DESIGN.md`, `templates/installer-gui-layout.example.json` and `templates/InstallerChassis.cs`. Copy the chassis, then fill project-specific protected/safe rectangles and wire `Engine.Install`/`Uninstall`. Pass `python scripts/verify_installer_gui_layout.py <layout.json> --csharp <Program.cs>` before promotion. Do not rewrite the 1024x576 shell, rainbow `0.045`, adjacent Cài/Gỡ, or Syrin.online cell. Lieflat/Impeccable are token and anti-slop references only: do not copy chart cards, dashboards or web kit chrome into a native installer.

## Fast path

The shortest route that still ships a verified installer. Do these, skip the rest.

1. Freeze the manifest: supported build ID, executable SHA-256, every destination path, source/target size + SHA-256.
2. Pick the payload: full + ZIP by default; consider verified `HDPATCH1` copy/literal delta for either same-size or size-changing files when measured savings justify it. Same-size sparse overwrite is a separate format.
3. Run the project-owned sandbox harness against the packaged EXE (the skill does not ship `run_sandbox_tests.py`): clean install, hash readback, reinstall, uninstall, tampered refusal, unsupported-build refusal, forced-failure rollback, unrelated-file preservation.
4. Screenshot the compiled GUI and pass the layout gate.
5. Promote the exact EXE that passed both.

Rule that must not be skipped: **the shipped EXE is the tested EXE.** Any rebuild — a colour, a
label, one character — voids the previous report; re-run step 3 and regenerate the project release receipt. `finalize_release.py` is not a bundled helper; resolve an existing project command or implement/test the harness before claiming it exists. Never promote a binary whose bytes differ from the one the passing report
names.

Do not spend effort on work the project did not ask for: re-running platform verification the
runtime owner already settled, per-font runtime evidence dossiers, or rebuilding for cosmetics
without re-testing. Each of those costs hours and changes nothing the player sees.

## Procedure

1. **Accept the handoff**
   - Read the manifest and independently hash every artifact.
   - Reject duplicate, absolute, traversal, missing, unlisted, or hash-mismatched paths.
   - Complete when the exact destination set and source/target hashes are frozen.

2. **Choose the smallest safe payload**
   - Measure installer overhead, per-entry ZIP compression, source/target sizes and changed-byte ratio before choosing a format.
   - Equal-size large files: use an old-byte-guarded sparse patch with source and target SHA-256.
   - Size-changing files: use a full payload unless a project-owned, verified delta codec already exists. For the copy/literal `HDPATCH1` route and its safety contract, read `references/compact-self-contained-delta-installers.md`; reuse `scripts/build_hdpatch1.py` and `templates/Hdp.cs` rather than rewriting the codec ad hoc.
   - Compress self-contained single-file runtimes with the platform-supported publisher setting only after payload compaction; verify startup/install time. Keep framework-dependent output optional, never the portable default.
   - Never use UPX, unsafe trimming, obfuscation or a new dependency merely to save a few megabytes.
   - Complete when each target reconstructs byte-for-byte from its supported source and the measured size reduction justifies the added format.

3. **Implement one transaction**
   - Validate executable/build and refuse while the game runs.
   - Verify all live source hashes before the first write.
   - Extract/reconstruct every target into staging and verify all target hashes.
   - Snapshot every destination, backup, state file, and owned addition.
   - Stage sibling files, commit via same-volume atomic replace, and verify each live readback.
   - Persist atomic per-file state with `created`, `same`, or `replaced` ownership.
   - On failure, rollback committed files in reverse order and verify restored hashes.
   - Never permit partial install or partial uninstall.

4. **Implement safe uninstall/reinstall**
   - Reinstall only when every live file matches supported original or installer-owned state.
   - Uninstall only when every live installed hash still matches state.
   - Restore only `replaced`, delete only `created`, preserve `same` and unrelated files.
   - If Steam replaced a live file with the current official original, preserve it and clean only installer-owned residuals.
   - Stop without mutation on unknown or user-modified state.

5. **Build the GUI**
   - Đọc `references/native-gui-implementation.md`: chassis 1024×576, Cài/Gỡ cạnh nhau, minimize, Syrin.online rainbow 0.045, safe art, icon, contrast, PathMap và screenshot gate vẫn bắt buộc.
   - Screenshot từ exact compiled candidate; JSON layout không chứng minh visual PASS.

6. **Exercise the exact packaged EXE**
   - Run a GUI pre-flight: one theme and accent, one radius rule, no repeated title/logo, no AI-purple/glow, no unnecessary cards/pills/labels, no wrapped CTA, no duplicate action intent, visible focus, correct tab order, normal cursors over every interactive control, taskbar minimize/restore, and no protected-artwork intersection.
   - Clean install and 100% target hash readback.
   - Idempotent reinstall.
   - Clean uninstall and zero owned residuals.
   - Unsupported build and tampered payload refusal before write.
   - Forced failures after each commit checkpoint with exact rollback.
   - Modified-live and modified-owned-file refusal.
   - Preserve unrelated files/mods.
   - Verify GUI screenshot, `installer-gui-layout.json` gate, link target, icon, PE architecture, EXE hash, size, measured reduction versus the previous release, and clean install time.

7. **Promote**
   - Keep builds under `candidates/<RC>` until every gate passes.
   - Promote only the exact EXE tested against the exact runtime-accepted target hashes.
   - Re-run final validators after copy/rename and leave one current final deliverable plus any explicitly locked previous final.

## Pitfalls

- A successful copy is not a successful transaction; require live readback and rollback proof.
- Do not build final EXEs before localization/runtime hashes freeze.
- Do not embed multi-gigabyte full files when a verified sparse patch reproduces an equal-size target.
- Do not compile single-file executables without `<PathMap>$(MSBuildProjectDirectory)=/_</PathMap>` and `<DebugType>none</DebugType>`; otherwise internal workspace paths and usernames will leak into the compiled PE metadata.
- Do not rely solely on `<ApplicationIcon>` in `.csproj` for the Taskbar icon; `FormBorderStyle.None` borderless windows require explicit `Form.Icon` and `WM_SETICON` on handle creation.
- Do not call `Console.OutputEncoding = Encoding.UTF8` in `<OutputType>WinExe</OutputType>` without a `try/catch` guard (throws `IOException: The handle is invalid` when launched in background pipes or non-console sessions).
- Do not treat community binaries or opaque payloads as trusted. Inspect source/format, use exact byte guards, and document provenance/license.
- Do not restore a previous-build backup over a newer Steam original.
- Do not use ordinary copy-overwrite as atomic replacement; stage a sibling and rename/replace on the same volume.
- Do not promote a binary that differs by even one byte from the one the passing report names; a cosmetic rebuild voids the suite.
- Do not let a control keep its default colours: on a dark system theme a WinForms button is dark-on-dark, and the user reports unreadable text.
- Do not measure translucency by eye: compare the artwork's and the render's standard deviations in a strip that holds no control — the ratio must equal `(255 - alpha) / 255`.

## Verification

Release is complete only when:

- all source/target/payload hashes match the frozen manifest;
- exact packaged-EXE sandbox install/reinstall/uninstall/refusal/rollback tests pass;
- final EXE contains no local/debug/community-reference paths;
- the installer target hashes equal the game-runtime-accepted hashes;
- final EXE SHA-256 and size are recorded.

## Phạm vi kiểm lại

Docs-only: kiểm contract/link và test helper bị ảnh hưởng; không rebuild/reinstall dự án. Tái dùng evidence chỉ khi input/output hashes, tool/config, build, scope và loại proof khớp. Không gọi skip là PASS. Thay artifact thì kiểm lại gate phụ thuộc; riêng installer EXE đổi byte phải chạy lại exact-EXE suite.
