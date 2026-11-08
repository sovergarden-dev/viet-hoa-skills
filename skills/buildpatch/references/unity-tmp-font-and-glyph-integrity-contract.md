# Quy chuẩn Bảo toàn Mã Glyph & Tính Bất biến Font Nguồn Unity TextMeshPro (TMP)

## 1. Bản chất Lỗi Glyph ID Collision trong Unity TextMeshPro

### Hiện tượng
Ký tự chữ số (ví dụ số `1`) hoặc ký tự thông dụng đột nhiên bị hiển thị thành một ký tự khác hoàn toàn (ví dụ dấu chấm `.`), mặc dù chuỗi văn bản logic gốc hoàn toàn chính xác.

### Cơ chế kỹ thuật gốc rễ
1. **Pre-baked Glyph Table:**
   Các TMP Font Asset SDF (`MonoBehaviour`) được tạo sẵn bởi nhà phát triển game thường chứa bảng glyph (`m_GlyphTable`) đã được render sẵn vào atlas texture. Mỗi glyph mang một chỉ số định danh nội bộ `m_Index`.
2. **Dynamic FreeType Lookup:**
   Khi TMP chạy ở chế độ Dynamic (`m_AtlasPopulationMode = 1`), nếu một ký tự không có sẵn trong `m_CharacterTable`, TMP sẽ gọi thư viện FreeType (`FT_Get_Char_Index`) dựa trên file nhị phân TTF nguồn (`m_SourceFontFile`) để lấy `glyphID` của ký tự đó.
3. **Va chạm chỉ số (Collision):**
   Nếu người làm mod/Việt hóa **thay thế file nhị phân TTF gốc** (`m_FontData`) bằng một font khác (ví dụ Noto Serif, Arial, Roboto...), thì `glyphID` của các ký tự trong font mới sẽ thay đổi.
   - Ví dụ: Trong font mới, số `1` có `glyphID = 18`.
   - Nhưng trong atlas cũ đã bake của game, index `18` lại đang là hình ảnh của **dấu chấm `.`**.
   - TMP tra atlas thấy `index = 18` đã tồn tại, nên tái sử dụng ngay lập tức mà không render lại.
   - **Hậu quả:** Toàn bộ chữ số `1` trên giao diện game bị vẽ thành dấu chấm `.`. Không một gate kiểm tra hash hay compile nào phát hiện được lỗi này!

---

## 2. 5 Quy tắc Bất biến (F1 – F5)

### [F1] Cấm tuyệt đối can thiệp nhị phân TTF gốc của Font Asset đã Bake
- Tuyệt đối KHÔNG thay thế trực tiếp nhị phân TTF (`m_FontData`) của một Font Asset gốc nếu Font Asset đó đang được TextMeshPro tham chiếu bởi một TMP Font Asset SDF đã được bake trước.
- Mở rộng ký tự tiếng Việt CHỈ ĐƯỢC THỰC HIỆN QUA 2 CON ĐƯỜNG:
  1. Thêm TMP Font Asset chứa tiếng Việt vào chuỗi `m_FallbackFontAssetTable`.
  2. Chuyển hướng con trỏ ngôn ngữ runtime (ví dụ `UILanguageFontSettings`).

### [F2] Bắt buộc kiểm định Va chạm Index (Collision Proof)
Trước khi đóng gói phát hành bất kỳ bản vá font nào, bắt buộc phải chạy script kiểm tra va chạm toán học (`verify_tmp_glyph_map.py`):
- Với mọi ký tự ASCII `0-9`, `.`, `,`, `:`, `/`, `%`, `-`, `+`:
  `glyphID(character) ∉ { m_Index của các glyph đã bake cho ký tự khác }`.
- Nếu phát hiện trùng lặp $\rightarrow$ Khóa cổng phát hành (FAIL cứng).

### [F3] Ưu tiên Vá Byte nhị phân tối thiểu (Minimal Binary Patching)
- Đối với container tài nguyên toàn cục (như `resources.assets`), tuyệt đối tránh reserialize toàn bộ file bằng UnityPy (dễ làm lệch offset hàng chục MB và sinh drift không kiểm soát).
- Chỉ vá trực tiếp các byte con trỏ PathID (ví dụ: đổi 2 byte pointer từ 2419 sang 2420). Giữ nguyên 100% dung lượng và cấu trúc file gốc.

### [F4] Thứ tự chuỗi Fallback xác định (Deterministic Fallback Order)
Chuỗi Fallback của TMP Font Asset phải tuân thủ nghiêm ngặt:
1. **Font SDF gốc của game** (giữ nguyên style, số, ký hiệu gốc).
2. **Font SDF tiếng Việt chính** (NotoSerifTC / NotoSans chứa đủ 134 glyphs có dấu).
3. **Font SDF Latin dự phòng**.

### [F5] Kiểm định ngữ nghĩa trước khi Text Fitting
- Khi phát hiện số bị mất hoặc biến thành dấu chấm, **nghiêm cấm** vội vã rút ngắn nhãn UI (Text Fitting).
- Phải phân loại và cô lập nguyên nhân theo đúng thứ tự:
  1. Kiểm tra Glyph Index Collision (số 1 biến thành `.`).
  2. Kiểm tra Fallback Chain (thiếu glyph tiếng Việt).
  3. Kiểm tra Texture/Atlas overflow.
  4. Cuối cùng mới xem xét Bounding Box / Ellipsis clipping.
