# Compact self-contained patch installers

## Trigger

Use when a verified single-file Windows installer is too large because it embeds full game assets and a self-contained .NET runtime.

## Optimization order

Measure before changing format:

1. Installer size.
2. Embedded payload ZIP size and per-entry compressed sizes.
3. Self-contained runtime overhead: `installer_size - embedded_payload_size`.
4. Source/target sizes and changed-byte ratio for each large destination.

Stop at the first safe rung that materially helps:

1. Deflate the payload at maximum standard ZIP compression.
2. Replace large source-derived targets with a guarded delta.
3. Set `.NET` `EnableCompressionInSingleFile=true` while remaining self-contained.
4. Only offer framework-dependent output as an explicitly optional lite build. Never make it the default because the user may lack the matching Desktop Runtime.

Do not use UPX, unsafe trimming, obfuscation or a new native codec merely to chase a smaller number. They increase antivirus false positives, startup failure and support burden.

## HDPATCH1 copy/literal delta

Use a project-owned copy/literal delta when both source and target are immutable and a full compressed payload remains meaningfully larger.

Binary layout, little-endian:

```text
8 bytes   magic = HDPATCH1
uint32    version = 1
uint64    source_size
uint64    target_size
32 bytes  source_sha256
32 bytes  target_sha256
uint32    command_count
commands...
```

Commands:

```text
0 + uint64 source_offset + uint64 length
1 + uint64 length + literal bytes
```

Required guards:

- Manifest hashes and sizes the delta file itself.
- Header repeats source size/hash and target size/hash.
- Decoder verifies source SHA-256 before reconstruction.
- Every copy range must satisfy `offset + length <= source_size` without overflow.
- Every command must keep total output `<= target_size`.
- Command count has a defensive upper bound.
- Decoder rejects unknown commands, truncation and trailing bytes.
- Output is written only to staging and must match exact target size/SHA-256.
- All targets are reconstructed and validated before the first game-file write.

Global source SHA-256 is the old-byte guard. Per-run byte guards are redundant once the complete immutable source is hashed.

## Manifest fields

Each file records:

```json
{
  "path": "relative/game/path",
  "format": "full | delta",
  "payload": "relative/archive/path",
  "source_size": 0,
  "source_sha256": "...",
  "size": 0,
  "sha256": "...",
  "payload_size": 0,
  "payload_sha256": "...",
  "ownership": "created | replaced"
}
```

For `full`, payload size/hash equal target size/hash. For `delta`, payload fields guard the delta while `size`/`sha256` guard reconstructed output.

## Transaction integration

1. Validate executable/build.
2. Extract archive to a random temp directory.
3. Validate every full payload and delta payload.
4. Validate every live source hash.
5. Reconstruct every delta target under `_ready/<destination>`.
6. Validate every staged target size/SHA-256.
7. Only then snapshot backups and commit game files.
8. Keep existing reverse-order rollback and atomic state write.

If a live file already equals the target but installer state is absent, copy that target into staging and classify the commit as `same`; never feed target bytes to a source-only delta decoder.

## Generator policy

A deterministic stdlib generator may index fixed-size source blocks, scan target bytes for matches, emit longest copy runs and literal gaps, then immediately apply its own output and compare exact target SHA-256. The block matcher affects compression only; correctness comes from decoder bounds and final hash verification.

Keep the delta only when:

- Python and production decoder both reconstruct exact target bytes;
- compressed delta is materially smaller than compressed full payload;
- clean install remains acceptably fast;
- source mismatch refuses before any destination write.

## Verification matrix

- Generator self-readback: exact target hash.
- Production decoder clean install: exact target hash.
- Idempotent reinstall.
- Clean uninstall and exact original hash restore.
- Wrong executable refusal.
- Wrong delta source refusal before write.
- Corrupt/missing payload refusal.
- Modified installed file refusal.
- Missing/corrupt backup refusal before uninstall mutation.
- No empty owned directories after clean uninstall.
- Record old/new installer bytes, percentage reduction and install time.

## Proven ceiling

A self-contained WinForms runtime remains the largest fixed cost after payload compaction. A framework-dependent build can be much smaller but is not portable. Keep self-contained as the release standard unless the user explicitly accepts an external `.NET Desktop Runtime` prerequisite.

## Manifest serialization & diagnostic verification

- **System.Text.Json naming policy:** Khi `manifest.json` dùng snake_case (`patch_sha256`, `orig_sha256`, `game_name`) và C# class dùng PascalCase (`PatchSha256`, `OrigSha256`), cấu hình mặc định `PropertyNameCaseInsensitive = true` **KHÔNG TỰ ĐỘNG BỎ DẤU GẠCH DƯỚI `_`**! Khiến trường hash bị deserialize thành `""` hoặc `null`. Bắt buộc phải thêm `[JsonPropertyName("patch_sha256")]` vào từng trường trong model, hoặc thiết lập `PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower` trong `JsonSerializerOptions`.
- **Diagnostic hash messages:** Trong câu thông báo ngoại lệ kiểm tra SHA-256 sau khi giải nén tệp tạm, luôn luôn in cả hai giá trị: `Thực tế: '{actualHash}', Kỳ vọng: '{expectedHash}'`. Điều này giúp phát hiện tức thì lỗi rỗng hash do deserialize thay vì đoán mò lỗi do tệp ZIP bị hỏng.
