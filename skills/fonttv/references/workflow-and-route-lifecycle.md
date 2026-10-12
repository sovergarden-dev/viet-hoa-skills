# FontTV Workflow Lifecycle, Route Architecture & Release Proof Acceptance

Tài liệu này lưu trữ đặc tả chi tiết về 10 bước quy trình xử lý font, tiêu chí phân loại Route A/B/C và thang đo nghiệm thu phát hành (Release Acceptance vs Proof Level) của kỹ năng `fonttv`.

---

## 1. Chi Tiết Chọn Route Cho Font Consumer

Mỗi font consumer trong game có một route duy nhất được ghi nhận vào manifest:

### Route A: Unicode / OpenType
- **Đặc trưng:** Renderer tra font trực tiếp bằng codepoint Unicode (áp dụng cho TTF/OTF/UFO/Glyphs/Designspace; Unity TMP, Unreal Engine, GameMaker dựng từ TTF).
- **Trọng tâm kiểm toán:** Source-first, NFC + NFD, bảng `cmap`, định vị anchor, tính năng OpenType `mark`/`mkmk`, `GSUB`/`GPOS`, và khoảng cách kerning.

### Route B: Legacy / Custom Encoding
- **Đặc trưng:** Text bị encode thành mã byte hoặc ID không phải Unicode trước khi tra font.
- **Trọng tâm kiểm toán:** Bảng mapping của encoder là nguồn chân lý duy nhất (source of truth). Kiểm toán bắt buộc đối chiếu round-trip Unicode → byte → glyph record và semantic tuple (xem chi tiết tại `references/custom-and-legacy-encoding.md`).

### Route C: Engine-Packed Bitmap / Atlas
- **Đặc trưng:** Glyph là các tọa độ chữ nhật (rect/UV) trong atlas hình ảnh, metrics nằm trong asset đi kèm (áp dụng cho BMFont, AngelCode, TextMeshPro Sprite Asset, atlas nhị phân đóng gói trong archive).
- **Trọng tâm kiểm toán:** Tính toàn vẹn của tọa độ UV, độ phân giải atlas, ink coverage, và liên kết shader material.

---

## 2. Đặc Tả 10 Bước Quy Trình Xử Lý Font (Workflow Lifecycle)

1. **Intake (Tiếp nhận):** Xác minh bản quyền/giấy phép sử dụng font, tính mã băm SHA-256 baseline của font gốc, khởi tạo manifest từ `templates/manifest.template.json`.
2. **Inventory (Kiểm kê):** Phân loại theo chuỗi `consumer → representation → container`; gán nhãn route A/B/C cho từng font.
3. **Contract (Khóa hợp đồng):** Khóa bảng encoder thực tế (tệp + mã băm), quy tắc chuẩn hóa Unicode (NFC/NFD), và các ký tự passthrough.
4. **Audit Chỉ Đọc (Read-only Audit):** Thực hiện kiểm toán ngữ nghĩa theo từng route. Font gốc cũng bắt buộc phải vượt qua audit ngữ nghĩa để làm mốc đối chiếu.
5. **Plan (Lập kế hoạch):** Chọn chiến lược (P1 Replace trọn bộ hoặc P2 Compose ghép dấu) cho từng font; lập danh sách preserve (kèm kết quả audit PASS), remap, add, allowlist. Font nguồn (P1) hoặc donor (P2) chỉ được phê duyệt sau khi vượt qua các gate: rights, coverage, hình dấu, style và metrics.
6. **Build (Dựng font):** Thực thi build vào thư mục staging; tuyệt đối không ghi đè trực tiếp lên asset game đang hoạt động.
7. **Re-audit (Kiểm toán lại):** Chạy lại toàn bộ kiểm toán trên bytes output và tạo semantic diff so sánh trước/sau khi can thiệp.
8. **Package + Readback (Đóng gói & Đọc ngược):** Đóng gói font vào container/archive mà game thực tế load, sau đó extract ngược lại từ container để so sánh mã băm SHA-256 với output của bước build.
9. **Runtime (Kiểm định Runtime):** Ưu tiên bài test phạm vi hẹp nhất chứng minh đúng điều còn nghi ngờ — khởi chạy game thực tế trên đúng build đó và chụp màn hình vị trí nghi vấn. Trang kiểm tra toàn diện một-ảnh-mỗi-font (`references/runtime-coverage-page.md`) chỉ thực hiện khi biết rõ consumer và dự án yêu cầu; mặc định bỏ qua. Trả lại tệp text về bản chính trước khi phát hành.
10. **Release (Phát hành):** Kiểm tra cài đặt sạch (clean install), kịch bản rollback, ký duyệt sign-off trên SHA-256 cuối cùng, và chạy `scripts/proof_level_check.py`.

---

## 3. Thước Đo Nghiệm Thu Phát Hành (Release Acceptance vs Proof Level)

- **Nguyên tắc phân định:** Trạng thái font offline chỉ chứng minh font được đóng gói đúng theo đặc tả kỹ thuật nội bộ; nghiệm thu phát hành dự án (`project release acceptance`) mới là bằng chứng game vận hành chuẩn xác ngoài đời thực. Không dùng trạng thái offline để tuyên bố dự án hoàn tất.
- **Thước đo tối thiểu cho bản vá:** Mọi font phải đạt cấp độ tối thiểu `archive_verified` và danh sách `release_blockers` rỗng. Bằng chứng ảnh runtime (`runtime_bound`) là bậc cao hơn, chỉ gán được khi biết rõ consumer.
- **Chính sách không nâng khống Proof Level:** Cấp độ proof level luôn là mức tối đa mà tệp bằng chứng thực tế biện minh được. Mọi công bố phát hành phải ghi rõ bộ 5 thông số: `build × platform × locale × cache × SHA-256`.
