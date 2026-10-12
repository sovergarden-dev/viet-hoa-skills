# Pitfalls when packaging a real release [V]

Lessons from the TWAU Vietnamese release (24.6 MB payload, 27 MB EXE, 18 archives incl. four 136–402 MB containers).

## Payload / manifest

- **Snake_case manifest + C# reader = silent zeros.** A Python generator wrote `payload_size`, `target_sha256`, `source_size`; the C# model had `PayloadSize`, `TargetSha256`, `SourceSize`. `PropertyNameCaseInsensitive` does **not** bridge underscores, so every length/hash defaulted to 0/null and the first symptom was a *hash mismatch*, not a parse error. Fix: `JsonSerializerOptions { PropertyNameCaseInsensitive = true, PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower }`. If a manifest field "looks ignored", print the deserialized object before touching the payload.
- **Embed one blob, not N resources.** Concatenate all payload files into `payload.bin` and keep `(offset, size)` in the manifest; embedding dozens of resources makes the csproj generated and fragile.
- **`<EnableCompressionInSingleFile>` requires self-contained.** With `--self-contained false` the publish fails with NETSDK1176; drop the flag instead of switching to self-contained.

## Delta encoding

- **Header command count must be the TOTAL of every command** (copies *and* literals). Counting only copies produces "Delta length/trailing-data mismatch" at apply time on a correct payload.
- **Aligned-block matching alone cannot handle a rebuilt container.** Changing one member's size shifts everything after it, so every 256-byte block is misaligned and the patch degrades to a full copy. Add a *shift-following* probe: remember the end of the last copy and search `source[estimate ± SPAN]` for the current target window with a SIMD/`Span.IndexOf`/`bytes.find` search. Measured: 136 MB → 360 KB, 402 MB → 664 KB (0.1–0.3%).
- **Bound the fallback.** When nothing matches, advance by `STRIDE` (≥ MINRUN guarantees no long run is skipped) instead of 1 byte, and keep SPAN small (2^18). Without this, a mostly-different pair runs for tens of minutes; with it, 21 MB finishes in ~6 s and simply falls back to a full payload.
- **Decide delta vs full by measurement, and expect rebuilds to lose.** Story archives rebuilt by the packer are structurally different from the originals: their delta is ~100% of the target, so ship them zlib-compressed instead (≈22% of target). Only delta files whose container is *close* to the original.
- **Verify a delta by applying it.** Before packing, re-apply each patch in a second implementation and compare to the target byte-for-byte. This caught the header bug and proves the payload without running the installer.

## Transaction / guards

- **Full-payload entries still need a source guard.** Verifying the source only for delta entries means a user who modded that archive gets their file silently overwritten. Check the live source hash for every archive entry that has one; skip only installer-owned additions (no source hash).
- **Idempotent reinstall = read the state file first.** If every recorded target already matches, return "already installed" instead of re-running the guard chain (which fails because the live files are now targets, not sources). Mixed state must refuse, not repair.
- **The layout gate wants the signature inside a safe rectangle at the bottom-right** (`x >= 744`, `y >= 496`, inside 1016×568), not merely "somewhere bottom-right". If you move the dock to the artwork's other side, add a second small safe rect for the signature and shrink the protected art rect so the two do not overlap.
- **`%` in an argparse help string breaks the script** (`badly formed help string` when help formatting runs): escape it as `%%`.

## Sandbox testing

- **Hardlinks only work on one volume.** Put the sandbox on the same drive as the game; otherwise `os.link` fails with WinError 17 and copies of a 1.2 GB install become expensive.
- **`shutil.rmtree` does not clear read-only files**, so a forced-failure test (read-only destination) leaves a sandbox that the next run cannot rebuild. Chmod everything writable first, then rmtree, then assert the path is gone.
- Test list that actually earns `status: PASS`: clean install + live hash readback, idempotent reinstall, clean uninstall with byte-identical originals, tampered source refusal (with no writes before the refusal), unsupported build refusal, forced failure mid-commit with full rollback, and preservation of unrelated files.
