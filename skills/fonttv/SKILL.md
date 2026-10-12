---
name: fonttv
description: Use when Vietnamese text renders wrong in a font or atlas.
version: 0.21.0
contract_version: "1.0.0"
author: Rurus, Hermes Agent
license: MIT
platforms: [windows, linux, macos]
metadata:
  hermes:
    editorial_name: FontTV
    editorial_description: Forensic, sửa và QA font tiếng Việt cho game/app theo encoding contract và bằng chứng runtime.
    tags: [fonts, vietnamese, glyphs, encoding, atlas, unity, unreal, gamemaker, telltale, typography]
    related_skills: [viethoa, game-localization]
---

# FontTV

Orchestrator cho lỗi font/typography tiếng Việt. File này giữ luồng, bất biến và cửa quyết định; chi tiết nằm trong `references/`.

## When to Use

- Chữ Việt thành tofu `□`/`.notdef`, thành ký hiệu khác (`2`, `©`, `¥`, `§`, `ÿ`), mất chữ, dấu bay/dính, lệch baseline, clipping, fallback lệch phong cách.
- TTF/OTF/UFO/Glyphs, Unity TMP/IMGUI, Unreal, GameMaker, BMFont/MSDF, Telltale `.font`, atlas/bitmap đóng gói trong archive.
- Mở sau khi `viethoa` xác nhận chuỗi đã tới renderer (bậc glyph trong injection ladder). Mojibake ở tầng text không sửa bằng font.

## Bất biến

1. Làm trên bản sao. Khóa root, build ID, engine/version, asset và SHA-256 input; có rollback.
2. **Encoding contract trước glyph.** Xác định text tới font dưới dạng gì (codepoint Unicode, CP1252/Windows-1258, VNI/TCVN3/VISCII/VPS, bảng single-byte do engine/dự án định nghĩa, glyph index, atlas slot) trước khi kết luận font thiếu hay đủ.
3. **Record tồn tại ≠ mapping đúng.** Coverage luôn tách `record_present`, `mapping_correct`, `outline_nonempty`, `metrics_valid`, `runtime_bound`.
4. **Preserve có điều kiện.** Giữ nguyên glyph, record hoặc file gốc chỉ khi identity ngữ nghĩa theo contract đã được chứng minh trên đúng bytes đó. Với custom/legacy encoding, mọi slot sai phải remap, kể cả khi charID đã có record. Thay đổi khác đi qua allowlist và semantic diff.
5. Inventory mọi font consumer (menu phụ, dialog, subtitle, nameplate, fallback); một màn hình đúng không chứng minh font khác.
6. **Chống hiệu ứng "chỗ đậm chỗ nhạt" (Mixed-Weight / Ransom-Note Fallback trong Unity TMP):**
   - Không dùng một fallback font lệch trọng lượng nét (ví dụ fallback `Arial`/`LiberationSans` mảnh 16pt ghép vào font tiêu đề dày đậm như `Orbitron-Black`, hoặc ngược lại) theo kiểu rớt từng chữ cái (per-character fallback), vì các chữ cái ASCII không dấu sẽ giữ nét của font gốc còn chữ có dấu tiếng Việt rơi sang fallback font khác độ đậm và x-height.
   - Khi kiểm tra chuỗi có tiếng Việt ở runtime (`HasVietnameseCharacters`), bắt buộc chuẩn hóa `char.ToLowerInvariant(c)` (hoặc phủ đủ cả chữ HOA lẫn chữ thường có dấu `U+00C0..U+1EF9`, bao gồm `Đ/đ`), tránh lỗi bỏ sót chữ IN HOA có dấu (`NHIỆM VỤ`, `VẬT PHẨM`, `CHỈ SỐ`) khiến chuỗi IN HOA bị rớt từng ký tự sang fallback.
   - Khởi tạo cặp Dynamic TMP_FontAsset tách biệt theo trọng lượng (**Bold** cho Header/Display và **Regular** cho Body/Dialogue) cùng một họ chữ và cùng `samplingPointSize` (ví dụ 48pt SDFAA, atlas 2048×2048), tắt `FontStyles.Bold` nhân tạo (faux-bold) khi đã gán font Bold thật để không bị phình/nhòe nét.
7. Sửa đúng representation runtime (font file, FontAsset, atlas, sprite, cache, archive).
8. Bằng chứng cấu trúc không suy ra runtime. Trạng thái gate và proof level theo `references/quality-gates.md`; không có PASS ngầm định.
   **Thước đo phát hành của một bản việt hoá**: mọi font ≥ `archive_verified` và `release_blockers` rỗng — chỉ là font offline/archive readiness, không chứng minh game chạy đúng. Ảnh runtime từng font là bậc cao hơn: chỉ gán được khi biết consumer, nên mặc định **không** đuổi theo; dùng `scripts/release_readiness.py --require-runtime-evidence` khi dự án thật sự muốn hồ sơ đó. Chính sách không nâng proof level: level luôn là mức mà file bằng chứng biện minh được.
9. Phân biệt project release acceptance với proof của từng font; không ép hồ sơ runtime từng font khi dự án không yêu cầu. Không tự nâng lên `release_verified`; mọi claim ghi proof level và build × platform × locale × cache × SHA-256.

## Chọn route

Mỗi font consumer có một route, ghi trong manifest; tiêu chí chọn nằm ở `references/architecture.md`.

- **A. Unicode/OpenType**: renderer tra font bằng codepoint (TTF/OTF/UFO/Glyphs/Designspace; TMP, Unreal, GameMaker dựng từ TTF). Source-first, NFC + NFD, cmap, anchor, `mark`/`mkmk`, GSUB/GPOS, kerning.
- **B. Legacy/custom encoding**: text bị encode thành byte/ID không phải Unicode trước khi tra font. Bảng mapping của encoder là source of truth; đọc `references/custom-and-legacy-encoding.md`.
- **C. Engine-packed bitmap/atlas**: glyph là rect trong atlas, metrics nằm trong binary/container riêng. Giữ bất biến format, readback từ archive live. Thường đi cùng B.

Telltale Tool (`.font`, LANDb, `.ttarch2`): đọc `references/telltale-fonts.md` trước khi đụng file.

## Chọn strategy

Route trả lời *text tới font dưới dạng gì*. Strategy trả lời *glyph Việt lấy từ đâu*. Hai trục độc lập; manifest ghi cả hai cho từng font.

- **P1. Thay trọn glyph (mặc định).** Render toàn bộ bảng chữ (ASCII + Việt) từ một font nguồn đã có tiếng Việt, scale theo metrics font game. Ưu tiên hiển thị đúng; style gần giống. Kiểm bằng identity pixel và baseline đồng nhất, không cần luật đặt dấu. Đọc `references/strategy-p1-replace.md`.
- **P2. Ghép dấu lên chữ gốc.** Giữ style font game. QA dài, lỗi theo từng tổ hợp base × dấu × font. Chỉ dùng khi người dùng yêu cầu rõ giữ style. Đọc `references/strategy-p2-compose.md`.

Chọn theo từng font: hội thoại/phụ đề/menu dùng P1; tiêu đề/logo có thể dùng P2. Đang ở P2 mà hai vòng runtime liên tiếp còn lỗi nhìn thấy, hoặc người dùng phải soi từng chữ, thì đề xuất chuyển font đó sang P1.

Cả hai strategy dùng chung: encoding contract, adapter, readback, và — **khi biết rõ consumer và dự án yêu cầu** — một ảnh coverage page cho mỗi font (`references/runtime-coverage-page.md`). Mặc định không sinh ảnh này: nó chỉ chứng minh thêm khi gán được font ↔ consumer, còn thước đo phát hành đã nằm ở bất biến 7.

## Quy trình

1. **Intake**: rights/license, hash baseline, manifest từ `templates/manifest.template.json`.
2. **Inventory**: consumer → representation → container; ghi route từng font.
3. **Contract**: khóa bảng encoder thật (file + hash), normalization, passthrough.
4. **Audit chỉ đọc** theo route (bảng dưới). Font gốc cũng phải qua audit semantic.
5. **Plan**: chọn strategy từng font; danh sách preserve (kèm audit PASS), remap, add, allowlist; font nguồn (P1) hoặc donor (P2) chỉ sau rights/coverage/hình dấu/style/metrics gate.
6. **Build** vào staging, không ghi live.
7. **Re-audit** trên bytes output và semantic diff trước/sau.
8. **Package + readback**: đóng gói, extract lại từ container mà game thực sự load, so SHA-256 với output.
9. **Runtime**: ưu tiên buộc test hẹp nhất chứng minh đúng điều còn nghi ngờ — chạy game thật trên đúng build và chụp màn hình chỗ đang nghi. Coverage page một-ảnh-mỗi-font (`references/runtime-coverage-page.md`) chỉ làm khi biết rõ consumer và khi dự án yêu cầu; mặc định bỏ qua. Trả text về bản chính trước release.
10. **Release**: clean install, rollback, sign-off trên SHA-256 cuối; chạy `scripts/proof_level_check.py`.

## Helper chỉ đọc

| Script | Route | Chứng minh | Không chứng minh |
|---|---|---|---|
| `scripts/fonttv_audit.py FONT --corpus TXT` | A | cmap precomposed + 8 combining, outline nonempty, advance, GPOS/GSUB tags, OS/2 bit 29/57 | custom encoding, identity glyph, runtime |
| `scripts/shaping_audit.py FONT` | A có shaper | HarfBuzz NFC/NFD không `.notdef`; cmap đủ cho renderer không compose | chất lượng đặt dấu, app/rasterizer |
| `scripts/custom_encoding_audit.py --mapping MAP --adapter-script A --adapter-sha256 H --font-file FONT [--identity-evidence TYPE=PATH --text TXT --encoded BIN]` | B/C | record/UV/ink/metrics do adapter đã pin parse lại từ `FONT` trong chính lần chạy; semantic tuple từng slot, identity có evidence được re-hash, trùng/thứ tự ID, round-trip Unicode → byte → glyph | adapter đúng tuyệt đối, archive live, runtime |
| `scripts/custom_encoding_audit.py … --inventory INV` | B/C | kế hoạch/baseline từ inventory external (lời khai); tối đa `inventory_only` | mapping |
| `scripts/adapters/ftvf_reference.py`, `scripts/adapters/telltale_5vsm.py` | B/C | adapter `fonttv-adapter/v1`: FTVF là tham chiếu tổng hợp; Telltale parse read-only profile TWAU PC 5VSM/TRecordNew, UV/metrics và DXT5 ink khi ranh giới page được chứng minh | biến thể 6VSM/5VSM khác profile; multipage descriptor mâu thuẫn sẽ bỏ capability ink |
| `scripts/proof_level_check.py MANIFEST --verify-files ROOT` | mọi | proof level tối đa mà các file bằng chứng có thật và đúng hash cho phép; chặn overclaim. Thiếu `--verify-files` thì chỉ ra `inventory_only` | thẩm mỹ |
| `scripts/tmpro_audit.py`, `tmpro_atlas_audit.py`, `tmpro_atlas_pixels_audit.py`, `tmpro_binding_audit.py`, `addressables_font_audit.py` | A/C Unity | characterTable, atlas rect/pixel, material binding, dependency graph (từ JSON export) | identity glyph, runtime |

Exit code: `0` chỉ khi verdict `PASS`, `1` FAIL, `2` lỗi input, `3` NOT_SUPPORTED, `4` INCOMPLETE/NOT_RUN/`PLANNING_ONLY`. Chỉ `0` được ghi PASS. External inventory là lời khai; `--accept-external-inventory-for-planning` đổi nhãn thành `PLANNING_ONLY` nhưng vẫn exit 4. Trên route B/C, cả `structurally_verified` lẫn `mapping_verified` đều đòi adapter đã pin chạy lại trên font đích; thiếu hoặc không chạy được adapter thì trần là `inventory_only`. `proof_level_check.py --verify-files` phải tự chạy lại audit đó (`semantic_reexecution`); hash file report không phải lần chạy adapter (protocol ở `references/custom-and-legacy-encoding.md` §8).

Tự kiểm helper từ skill_dir: `python -m unittest discover -s scripts/tests -v`. Full suite cần fontTools, uharfbuzz, numpy, Pillow trong cùng interpreter; có thể dùng môi trường tách biệt `uv run --with-requirements scripts/tests/requirements.txt python -B -m unittest discover -s scripts/tests -v`. Fixture project thiếu phải skip rõ; không tính skip là pass. Test lỗi input phải tự dựng bytes trong TemporaryDirectory, không phụ thuộc game. Báo cáo texture phải từ chối font parse lỗi hoặc thư mục archive explicit bị thiếu; không bỏ qua input lỗi rồi exit 0.

## Script P1

Khi chọn P1, đọc `references/p1-command-reference.md` cho CLI build/manifest/release. Không preload lệnh Telltale cho Unicode/TMP.

## References

- `references/architecture.md`: ba route, chuỗi representation, route theo engine, thứ tự nguồn dấu, capability matrix.
- `references/quality-gates.md`: trạng thái, 13 gate, proof level, semantic diff, lỗi chặn phát hành.
- `references/custom-and-legacy-encoding.md`: encoding contract, semantic tuple, remap, round-trip, JSON adapter.
- `references/strategy-p1-replace.md`: thay trọn glyph từ font Việt ngoài; chọn font nguồn, scale, baseline, kiểm identity, công cụ P1, recipe cho Unity/Unreal/GameMaker.
- `references/strategy-p2-compose.md`: **toàn bộ luật P2** — nguồn dấu và C12, dựng base và bẫy fontTools, đọc bố cục từ donor, đặt dấu (móc, chấm `i`, dạng sừng, bầu chữ), cỡ/độ dày/méo hình, và bộ audit C1–C13 kèm hiệu chuẩn sabotage, cỡ nhỏ, lỗi giữa hai ký tự, phân loại phủ corpus, glyph gốc nguyên vẹn.
- `references/screenshot-font-measurement.md`: đo cỡ chữ thật và nhận diện mặt chữ từ ảnh chụp màn hình; ba mask tìm dải, ghép theo thứ tự đọc, tương phản WCAG, và phân công "model đọc chữ — pixel đo".
- `references/case-twau-history.md`: lịch sử 14 vòng P2 trên TWAU, từng lỗi lọt audit và cách phát hiện.
- `references/runtime-coverage-page.md`: chuỗi test phủ bảng chữ, cách đặt vào game, cách đọc ảnh; và cửa sổ duyệt font ngoài game.
- `references/telltale-fonts.md`: Telltale `.font`/LANDb và case study TWAU V3/V7/V9.
- `references/telltale-prop-text.md`: chữ nằm ngoài font — prop trong `.ttarch2` và **tầng cache tải từ server** trong `Documents\Telltale Games\...` (choice/feed/caboose); cách game tự ghi đè và cách chặn.
- `references/telltale-crash-isolation.md`: thang tách nguyên nhân crash trên game đã mod (log 1000 → gỡ từng lớp → so offset); ma trận đã đo với TWAU + tay cầm.
- `references/screenshot-attribution-attempts.md`: hai lần đo ảnh → font đều thất bại; vì sao chỉ gán được ảnh khi có bằng chứng consumer.
- `references/font-engineering-research.md`: Unicode/OpenType, thiết kế dấu Việt, renderer notes, failure mode đã tái lập, công cụ.
- `references/unity-adventure-creator-monofont-vietnamese-compose.md`: áp dụng P2 lên Unity legacy `Font` + Adventure Creator — fallback theo từng ký tự, kiểm kê consumer, `CustomLanguageSettings`, slot ngôn ngữ 0, và vì sao gán font theo element không đọc được tĩnh.
- `references/cinzel-fantasy-fonts-dcroat-floating-crossbar-repair.md`: recipe sửa Đ/đ họ Cinzel.

## Phạm vi kiểm lại

Docs-only: kiểm contract/link và test helper bị ảnh hưởng; không rebuild/reinstall dự án. Tái dùng evidence chỉ khi input/output hashes, tool/config, build, scope và loại proof khớp. Không gọi skip là PASS. Thay artifact thì kiểm lại gate phụ thuộc; riêng installer EXE đổi byte phải chạy lại exact-EXE suite.
