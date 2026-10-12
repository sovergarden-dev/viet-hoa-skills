---
name: fonttv
description: Use when Vietnamese text renders wrong in a font or atlas.
version: 0.22.0
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

Orchestrator cho lỗi font và typography tiếng Việt trong game/app. File này giữ luồng điều phối, bất biến kỹ thuật và tiêu chí nghiệm thu; chi tiết thao tác nằm trong `references/`.

## When to Use

- Chữ Việt thành tofu `□`/`.notdef`, thành ký hiệu lạ (`2`, `©`, `¥`, `§`, `ÿ`), mất chữ, dấu bay/dính, lệch baseline, clipping, hoặc fallback lệch phong cách.
- Định dạng TTF/OTF/UFO/Glyphs, Unity TMP/IMGUI, Unreal Engine, GameMaker, BMFont/MSDF, Telltale `.font`, và atlas/bitmap đóng gói trong archive.
- Mở sau khi `viethoa` xác nhận chuỗi đã tới renderer (bậc glyph trong injection ladder). Mojibake ở tầng text không sửa bằng font.

## Bất biến

1. **Bản sao độc lập:** Thao tác trên bản sao staging; khóa root, build ID, engine/version, asset và SHA-256 input; có cơ chế rollback.
2. **Encoding contract trước glyph:** Xác định dạng text tới font (Unicode codepoint, CP1252, VNI/TCVN3, single-byte custom, glyph index, atlas slot) trước khi kết luận font thiếu hay đủ.
3. **Record tồn tại ≠ mapping đúng:** Coverage luôn bóc tách 5 cấp độ: `record_present`, `mapping_correct`, `outline_nonempty`, `metrics_valid`, `runtime_bound`.
4. **Preserve có điều kiện:** Giữ nguyên glyph/record gốc chỉ khi identity ngữ nghĩa theo contract đã được chứng minh trên đúng bytes đó. Mọi slot sai trong custom encoding phải remap có kiểm soát.
5. **Inventory consumer:** Kiểm kê mọi font consumer (menu, dialog, subtitle, nameplate, fallback); một màn hình hiển thị đúng không chứng minh font khác hoạt động đúng.
6. **Chống lỗi lệch nét trong Unity TMP:** Tuyệt đối không dùng fallback font lệch trọng lượng nét gây lỗi rơi từng chữ có dấu (ransom-note fallback). Khởi tạo cặp Dynamic FontAsset tách biệt (Bold/Regular); đọc chi tiết tại `references/unity-tmp-fallback-and-weight-policy.md`.
7. **Sửa đúng representation:** Sửa đúng tầng runtime thực tế (font file, FontAsset, atlas rect, sprite, cache, hoặc archive).
8. **Bằng chứng cấu trúc không suy ra runtime:** Proof level tuân thủ `references/quality-gates.md`. Thước đo phát hành offline tối thiểu là mọi font ≥ `archive_verified` và `release_blockers` rỗng.
9. **Minh bạch thông số:** Phân biệt phát hành game với trạng thái font offline. Mọi chứng nhận phát hành phải ghi rõ `build × platform × locale × cache × SHA-256`.

## Chọn Route

Mỗi font consumer gắn liền với một route duy nhất (chi tiết tại `references/workflow-and-route-lifecycle.md`):
- **Route A (Unicode / OpenType):** Renderer tra bằng codepoint Unicode. Trọng tâm: NFC/NFD, cmap, anchor, GSUB/GPOS, kerning.
- **Route B (Legacy / Custom Encoding):** Text bị mã hóa thành byte/ID trước khi tra font. Trọng tâm: Bảng mapping encoder, semantic tuple (`references/custom-and-legacy-encoding.md`).
- **Route C (Engine-Packed Bitmap / Atlas):** Glyph là rect/UV trong atlas ảnh. Trọng tâm: Tọa độ rect, pixel ink, material binding.

## Quy Trình 10 Bước

Quy trình chuẩn hóa từ tiếp nhận đến phát hành (đặc tả tại `references/workflow-and-route-lifecycle.md`):
1. **Intake:** Kiểm tra bản quyền, tính SHA-256 baseline, lập manifest.
2. **Inventory:** Phân loại `consumer → representation → container` và gán route.
3. **Contract:** Khóa bảng encoder thực tế, normalization và passthrough.
4. **Audit chỉ đọc:** Kiểm toán ngữ nghĩa font gốc theo route.
5. **Plan:** Chọn P1 Replace hoặc P2 Compose; lập danh sách preserve, remap, allowlist.
6. **Build:** Xuất bản vào thư mục staging; không ghi đè live.
7. **Re-audit:** Kiểm toán lại bytes output và so sánh semantic diff.
8. **Package + Readback:** Đóng gói và extract ngược từ container để so khớp SHA-256.
9. **Runtime:** Kiểm thử trực tiếp trong game trên build thực tế khi cần bằng chứng consumer.
10. **Release:** Kiểm tra clean install, rollback, chạy `scripts/proof_level_check.py`.

## Helper Chỉ Đọc

| Script | Route | Chứng minh | Con trỏ chi tiết |
|---|---|---|---|
| `scripts/fonttv_audit.py FONT --corpus TXT` | A | cmap precomposed + 8 combining, outline nonempty, advance | `references/architecture.md` |
| `scripts/shaping_audit.py FONT` | A | HarfBuzz NFC/NFD không `.notdef`, cmap đủ cho renderer | `references/architecture.md` |
| `scripts/custom_encoding_audit.py` | B/C | record/UV/ink/metrics do adapter parse lại từ FONT đích | `references/custom-and-legacy-encoding.md` |
| `scripts/proof_level_check.py` | mọi | proof level tối đa mà bằng chứng cho phép, chặn overclaim | `references/quality-gates.md` |
| `scripts/tmpro_audit.py` | A/C | characterTable, atlas rect/pixel, material binding, graph | `references/unity-tmp-fallback-and-weight-policy.md` |

Chi tiết bảng audit toàn diện, thang exit code `0..4`, cơ chế `semantic_reexecution` và ma trận test: đọc `references/tool-inventory-and-verdicts.md`.

## Script P1

Khi chọn P1, đọc `references/p1-command-reference.md` cho CLI build/manifest/release. Không preload lệnh Telltale cho Unicode/TMP.

## References

- `references/architecture.md`: Ba route representation, pipeline engine và capability matrix.
- `references/quality-gates.md`: 13 gate kiểm định, thang proof level và semantic diff.
- `references/custom-and-legacy-encoding.md`: Encoding contract, semantic tuple, remap và JSON adapter.
- `references/strategy-p1-replace.md`: Thay thế toàn bộ glyph từ font nguồn bên ngoài cho Unity/Unreal/GameMaker.
- `references/strategy-p2-compose.md`: Dựng glyph và dấu tiếng Việt (móc, nón, sừng, râu) kèm bộ audit C1–C13.
- `references/unity-tmp-fallback-and-weight-policy.md`: Phòng chống lỗi lệch trọng lượng nét (ransom-note fallback) trong Unity TMP.
- `references/tool-inventory-and-verdicts.md`: Bảng audit toàn diện, thang exit code 0-4 và môi trường test độc lập.
- `references/workflow-and-route-lifecycle.md`: Đặc tả 10 bước quy trình, phân loại route A/B/C và nghiệm thu phát hành.
- `references/screenshot-font-measurement.md`: Đo đạc cỡ chữ và nhận diện font từ ảnh chụp màn hình.
- `references/case-twau-history.md`: Lịch sử kiểm toán và phân lập lỗi font qua các vòng P2.
- `references/runtime-coverage-page.md`: Chuỗi test phủ bảng chữ và đối chiếu ảnh runtime.
- `references/telltale-fonts.md`: Cấu trúc font Telltale (.font/LANDb) và case studies.
- `references/telltale-prop-text.md`: Xử lý chuỗi nằm ngoài font (prop trong .ttarch2 và cache server).
- `references/telltale-crash-isolation.md`: Thang phân lập nguyên nhân crash do font trên game đã mod.
- `references/screenshot-attribution-attempts.md`: Giới hạn gán ảnh khi thiếu bằng chứng consumer.
- `references/font-engineering-research.md`: Nghiên cứu thiết kế dấu tiếng Việt và failure modes đã tái lập.
- `references/unity-adventure-creator-monofont-vietnamese-compose.md`: Áp dụng P2 lên Unity legacy Font và Adventure Creator.
- `references/cinzel-fantasy-fonts-dcroat-floating-crossbar-repair.md`: Recipe sửa lỗi ký tự Đ/đ họ Cinzel.

## Phạm vi kiểm lại

Docs-only: kiểm contract/link và test helper bị ảnh hưởng. Tái dùng evidence chỉ khi hashes, tool/config, build và scope khớp 100%. Không gọi skip là PASS. Thay artifact thì kiểm lại gate phụ thuộc.
