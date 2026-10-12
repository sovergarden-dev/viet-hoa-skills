# Unity IL2CPP community VPK: extraction, QA, and update baseline

Use when a Unity IL2CPP community patch ships as a BepInEx plugin plus an encrypted `translation.vpk`, and the goal is to improve translation quality without editing installed game files during review.

## Proven discovery route

1. Fingerprint the installed plugin and VPK with size and SHA-256. Confirm runtime provenance from the exact game root and plugin path.
2. Inspect the managed plugin rather than guessing the container. Useful evidence includes VPK signature/version, table layout, passphrase derivation, IV derivation, cipher mode/padding, verification record, line-break escaping, and fallback plaintext filename.
3. For the NRFTW-style VPK v3 container:
   - Header signature: `VPK\x03`.
   - Read `count`, encrypted payload offset/size, and verification value from the header.
   - Key: `SHA256(passphrase UTF-8)`.
   - IV: first 16 bytes of `SHA256(key + iv_suffix UTF-8)`.
   - Cipher: AES-CBC with PKCS#7 padding.
   - Entry table starts at byte 32; each record is four little-endian `uint32` values: source offset/size and target offset/size.
   - Entry zero can be an internal sentinel/integrity record rather than a translation. Validate later records first and skip the sentinel only after proving its malformed/internal nature from plugin logic and neighboring valid records.
   - String offsets are relative to the decrypted payload. Decode UTF-8, strip terminal NUL only, and restore the plugin’s escaped line-break marker exactly.
4. Export a canonical review CSV with stable IDs and columns such as `id, source_en, community_vi, qa_vi, status, category, note`. Never treat the community Vietnamese as authority; English remains the source of truth.

## Cross-engine community baseline routing

Dù container là VPK, `.locres`, StringTable, JSON hay cooked DataTable, luôn extract current-build authoritative source riêng rồi align theo exact `(domain,key)`/table identity. Cấm positional, suffix, normalized-source hoặc source-only merge. Community target chỉ vào `community_vi_reference` với artifact/build hash và alignment evidence.

Classify exact current keys:

- `review_existing`: exact key + unchanged source + structurally clean tokens;
- `retranslate`: changed source, token mismatch, wrong-row/branding/semantic suspicion;
- `translate_missing`: current key không có community target;
- `exclude`: obsolete hoặc non-player-facing.

External Phase 1 xử lý `retranslate/translate_missing`; `review_existing` đi thẳng Phase 2 để editorial accept/rewrite. Không auto-promote community Vietnamese thành reviewed. Re-apply current English semantic policy: item/skill/location đã bị legacy dịch trái policy phải khôi phục identity English khi exact key evidence xác nhận.

## Corpus QA discipline

- Preserve row count, order, stable IDs, English source, and community-reference column.
- Statuses must distinguish `pending`, `reviewed`, `needs_context`, and `locked_english`.
- The canonical validator must compare exact multisets of markup, placeholders, input tokens, escapes, and control codes between English and final QA text.
- A community patch may already have deleted tokens while translating prose. High-confidence terminology replacement must not mark such rows reviewed until missing tokens are restored and validation passes.
- Screenshot QA is useful for discovering terminology problems, but apply fixes corpus-wide by English key and semantic context, not by blind Vietnamese substring replacement alone.
- Use Vietnamese sentence case for ordinary UI labels. Keep English for item, weapon, armor, Rune, Spell, NPC, boss, faction, place, update/area names, and other proper nouns unless a natural established Vietnamese rendering is explicitly approved.
- Examples of semantic corrections: camera-like `lấy nét` is wrong for RPG `Focus`; use `Tập trung` / `Điểm tập trung`. Boxing-like `Hạng cân` is awkward for equipment burden `Weight Class`; a concise mechanics label such as `Mức tải` is clearer.

## Future-update readiness

Create a baseline manifest alongside the canonical CSV containing:

- installed VPK SHA-256,
- entry count,
- stable row ID,
- full English source,
- SHA-256 of English source,
- optional SHA-256 of the old community target.

When a major update arrives, extract the new patch/source independently and reconcile by exact English source hash first, then normalized/stable source key if available. Classify unchanged, changed-source, added, and removed rows. Carry reviewed Vietnamese only for exact source matches; changed English must return to review.

## Safety gates

- Extraction and QA are read-only against the game directory.
- Do not overwrite `translation.vpk` during review.
- Build/re-encrypt only after `pending == 0`, validator errors are zero, and the reviewed workbook is accepted.
- Preserve the original VPK and plugin for rollback.
- Runtime screenshots are still required after packaging; offline decrypt/re-encrypt and token validation do not prove UI fit or hook coverage.
