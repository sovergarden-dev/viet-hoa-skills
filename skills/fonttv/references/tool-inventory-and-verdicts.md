# FontTV Tool Inventory, Verification Verdicts & Test Execution Matrix

Tài liệu này lưu trữ toàn bộ đặc tả chi tiết về danh mục script kiểm toán, phân công nhiệm vụ, bằng chứng chứng minh/không chứng minh, thang mã thoát (Exit Codes) và môi trường kiểm thử tự động của kỹ năng `fonttv`.

---

## 1. Bảng Phân Tích Script Kiểm Toán Toàn Diện (Full Audit Inventory)

| Script | Route | Chứng minh (Verified Capabilities) | Không chứng minh (Out of Scope) |
|---|---|---|---|
| `scripts/fonttv_audit.py FONT --corpus TXT` | A | cmap precomposed + 8 combining, outline nonempty, advance, GPOS/GSUB tags, OS/2 bit 29/57 | custom encoding, identity glyph, runtime |
| `scripts/shaping_audit.py FONT` | A có shaper | HarfBuzz NFC/NFD không `.notdef`; cmap đủ cho renderer không compose | chất lượng đặt dấu, app/rasterizer |
| `scripts/custom_encoding_audit.py --mapping MAP --adapter-script A --adapter-sha256 H --font-file FONT [--identity-evidence TYPE=PATH --text TXT --encoded BIN]` | B/C | record/UV/ink/metrics do adapter đã pin parse lại từ `FONT` trong chính lần chạy; semantic tuple từng slot, identity có evidence được re-hash, trùng/thứ tự ID, round-trip Unicode → byte → glyph | adapter đúng tuyệt đối, archive live, runtime |
| `scripts/custom_encoding_audit.py … --inventory INV` | B/C | kế hoạch/baseline từ inventory external (lời khai); tối đa `inventory_only` | mapping |
| `scripts/adapters/ftvf_reference.py`, `scripts/adapters/telltale_5vsm.py` | B/C | adapter `fonttv-adapter/v1`: FTVF là tham chiếu tổng hợp; Telltale parse read-only profile TWAU PC 5VSM/TRecordNew, UV/metrics và DXT5 ink khi ranh giới page được chứng minh | biến thể 6VSM/5VSM khác profile; multipage descriptor mâu thuẫn sẽ bỏ capability ink |
| `scripts/proof_level_check.py MANIFEST --verify-files ROOT` | mọi | proof level tối đa mà các file bằng chứng có thật và đúng hash cho phép; chặn overclaim. Thiếu `--verify-files` thì chỉ ra `inventory_only` | thẩm mỹ |
| `scripts/tmpro_audit.py`, `tmpro_atlas_audit.py`, `tmpro_atlas_pixels_audit.py`, `tmpro_binding_audit.py`, `addressables_font_audit.py` | A/C Unity | characterTable, atlas rect/pixel, material binding, dependency graph (từ JSON export) | identity glyph, runtime |

---

## 2. Quy Chuẩn Exit Codes & Giao Thức Tái Thực Thi (Protocol & Verdicts)

Exit code:
- **`0`**: Chỉ khi verdict `PASS`.
- **`1`**: `FAIL` (phát hiện lỗi cấu trúc, mojibake, tràn glyph, gãy outline, hoặc mất ký tự).
- **`2`**: Lỗi input (đầu vào bị hỏng, sai định dạng hoặc thiếu tệp bắt buộc).
- **`3`**: `NOT_SUPPORTED`.
- **`4`**: `INCOMPLETE` / `NOT_RUN` / `PLANNING_ONLY`.

### Quy tắc Đánh giá Bằng chứng (Evidence Integrity):
- **Chỉ `0` được ghi PASS.**
- **External inventory là lời khai:** Cờ `--accept-external-inventory-for-planning` đổi nhãn thành `PLANNING_ONLY` nhưng script bắt buộc vẫn phải exit `4`.
- **Yêu cầu Adapter Thực thi trên Route B/C:** Cả hai trạng thái `structurally_verified` lẫn `mapping_verified` đều đòi hỏi adapter đã pin phải được chạy lại trực tiếp trên font đích. Nếu thiếu hoặc không thể chạy lại adapter, trần proof level tối đa chỉ là `inventory_only`.
- **Giao thức Semantic Re-execution:** Lệnh `proof_level_check.py --verify-files` bắt buộc phải tự động thực thi lại audit ngữ nghĩa (`semantic_reexecution`); việc chỉ kiểm tra hash của file report kết quả không thay thế được lần chạy thực tế của adapter (xem chi tiết giao thức tại `references/custom-and-legacy-encoding.md` §8).

---

## 3. Môi Trường Kiểm Thử Tự Động & Cách Ly Fixture (Test Execution Matrix)

- **Lệnh tự kiểm helper từ `skill_dir`:**
  ```bash
  python -m unittest discover -s scripts/tests -v
  ```
- **Thư viện yêu cầu:** Full suite cần `fontTools`, `uharfbuzz`, `numpy`, `Pillow` trong cùng interpreter. Có thể dùng môi trường tách biệt:
  ```bash
  uv run --with-requirements scripts/tests/requirements.txt python -B -m unittest discover -s scripts/tests -v
  ```
- **Nguyên tắc Fixture & Báo cáo Lỗi:**
  * Fixture project thiếu phải skip rõ ràng (`skipTest`); tuyệt đối không tính `skip` là `PASS`.
  * Các bài test kiểm tra xử lý lỗi đầu vào bắt buộc phải tự dựng bytes thử nghiệm bên trong `tempfile.TemporaryDirectory()`, không được phụ thuộc vào tệp game thương mại thực tế.
  * Báo cáo phân tích texture phải từ chối font parse lỗi hoặc thư mục archive explicit bị thiếu; cấm nuốt lỗi rồi thoát exit `0`.
