## Script P1

P1 thay trọn glyph từ font nguồn. Chi tiết và luật: `references/strategy-p1-replace.md`.

| Script | Việc | Exit |
|---|---|---|
| `scripts/p1_source_select.py FONT… [--license FONT=SPDX:PATH]` | ba cổng chọn font nguồn (coverage, hình dấu, license) | 0 PASS / 1 FAIL / 2 input / 4 thiếu license |
| `scripts/p1_telltale_build.py --fonts-dir --out-dir --mapping --sources` | dựng toàn bộ glyph cho Telltale `.font` | 0 mọi font PASS / 1 FAIL / 2 input |
| `scripts/p1_width_audit.py --font F --source-font G --mapping M --pairs P` | so bề rộng chuỗi nguồn/đích (chỉ để phân loại) | 0 không quá ngưỡng / 1 có / 2 input |
| `scripts/coverage_page.py --font F --mapping M [--max-width px]` | sinh dòng phủ repertoire cho một ảnh mỗi font | 0 / 2 |
| `scripts/p1_core.py` | hàm dùng chung: render, cỡ theo cap height, DXT5, identity, `uv_box` | thư viện |
| `scripts/p1_uniformity_check.py --font F [--original G] --mapping M` | cap height / x-height / baseline của font đã dựng, so bản gốc | 0 PASS / 1 FAIL / 2 input |
| `scripts/telltale_font_diff.py --before A --after B` | diff từng record: page, UV theo pixel, ink, advance | 0 / 2 |
| `scripts/p1_consumer_scan.py --root DIR [--font NAME]` | tìm tên `*.font` được nhắc trong member đã extract (bằng chứng font ↔ consumer) | 0 / 2 |
| `scripts/run_pipeline.py --plan PLAN.json [--dry-run]` | chạy các bước theo thứ tự, dừng ở bước FAIL đầu tiên, ghi receipt | 0 / 1 / 2 |
| `scripts/p1_texture_report.py --fonts-dir A [--original-dir B] [--archive-before X --archive-after Y]` | chi phí texture: bytes, pages, pixel mỗi font và mỗi archive | 0 / 1 page quá cao / 2 |
| `scripts/release_readiness.py --proof P --manifest M [--require-runtime-evidence]` | việc còn thiếu cho thước đo phát hành (mặc định: font ≥ archive_verified + blockers rỗng) | 0 sẵn sàng / 1 còn việc / 2 |
| `scripts/p1_manifest.py --project P --fonts-dir A --original-dir B --audit-dir C --evidence-dir D --readback-dir E --mapping M --adapter AD --container C --container-sha256 H --build-anchor F --out M.json` | dựng manifest từ artefact có thật; thiếu file nào thì từ chối và gọi tên file đó | 0 đã ghi / 2 input |
| `scripts/ttprop_slots.py FILE --list [--lang-key HEX] [--charset DIR]` | liệt kê slot text trong prop Telltale (T3Meta/5VSM), không cần hiểu format | 0 / 2 |
| `scripts/ttprop_slots.py --verify ORIG PATCHED [--plan P.json] [--charset DIR]` | kiểm bất biến bản vá prop | 0 PASS / 1 FAIL / 2 input |
| `scripts/ttprop_slots.py FILE --apply PLAN.json [--out PATCHED]` | vá slot theo plan, **từ chối** nếu đổi độ dài | 0 / 1 từ chối / 2 input |
| `scripts/p1_attach_screenshot.py --image SHOT.png --font F --cite "vì sao ảnh này là bằng chứng cho ĐÚNG font đó" --reviewer T --shots S.json --evidence-dir D` | ghi ảnh làm bằng chứng runtime; **từ chối** nếu thiếu citation, ảnh không đọc được, hay ảnh quá nhỏ | 0 ghi xong / 1 từ chối / 2 input |

`p1_telltale_build.py` độc lập với project TWAU: truyền `--mapping` (schema `fonttv/encoding-map/v1`) và `--sources` (JSON `{"<font stem>": ["a.ttf", "b.ttf"]}`). Nó đã được kiểm bằng cách dựng lại **byte-identical** 12/12 font của bản TWAU đã được người dùng chấp nhận.

