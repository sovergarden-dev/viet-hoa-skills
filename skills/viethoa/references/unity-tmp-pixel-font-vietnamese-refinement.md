# Unity TMP & GameMaker Pixel Font Vietnamese Refinement

## 1. Unity TextMeshPro Pixel Font & Dynamic Fallback Pitfall

### Trigger & Symptoms
Game đồ họa Pixel Art sử dụng TextMeshPro (TMP) gặp 2 hiện tượng lỗi font song song:
1. **Chữ đậm chữ mỏng không đồng bộ:** Ký tự không dấu hoặc ký tự có sẵn trong Latin-1 (như *C, à, i, t, r, ò, c, h, ơ, i*) hiển thị đúng nét pixel đậm, vuông vức. Nhưng các ký tự có dấu phức tạp (như *ả, ạ, ắ, ầ, ế, ộ*) lại hiển thị nét mảnh, mượt (vector antialiased).
2. **Ký tự ô vuông (Tofu `□`):** Một số ký tự như `ự` (`\u1ef1`) hiển thị thành ô vuông rỗng.

### Root Cause
- Font pixel chính (ví dụ `Pixellari SDF`, `Glasstown SDF`) có `m_AtlasPopulationMode = 1` (Dynamic) liên kết tới `Font.m_FontData` (TrueType font trong asset).
- Khi TrueType font gốc thiếu ký tự tiếng Việt, TMP Dynamic không thể rasterize trực tiếp được, nên nó kích hoạt cơ chế fallback sang `LiberationSans SDF` (được cấu hình trong `TMP Settings`).
- `LiberationSans SDF` là font vector mượt, nên khi nó gánh các ký tự thiếu, dòng chữ bị pha trộn giữa font pixel đậm và font vector mảnh. Đồng thời `LiberationSans SDF` được nướng atlas tĩnh (Static, `m_AtlasPopulationMode = 0`) và cũng thiếu một số ký tự như `ự`, dẫn tới tofu `□`.

### Giải pháp chuẩn mực (Permanent Solution)
Cấy trực tiếp 100% glyphs tiếng Việt có dấu (134/134 ký tự hoa + thường) vào TrueType font gốc (`Pixellari.ttf`, `Glasstown.ttf`...) theo đúng pixel grid (unitsPerEm=1024, 64 units/pixel).
- Cập nhật trực tiếp `f.m_FontData = list(patched_ttf_bytes)` trong asset chứa font (`sharedassets0.assets`).
- Khi TrueType font gốc đã có đủ 134 glyphs tiếng Việt chuẩn, TMP Dynamic mode sẽ tự động rasterize trực tiếp từ font pixel gốc, không bao giờ phải kích hoạt fallback vector mượt nữa. Toàn bộ chữ trong game sẽ đồng nhất 100% phong cách pixel art.

---

## 2. Quy chuẩn thiết kế dấu tiếng Việt trong Pixel Typography (Stacked Diacritics)

Trong font pixel nhỏ (x-height chỉ khoảng 6–7 pixel, khoảng trống trên đỉnh thân chữ chỉ có 4–5 pixel):
- **CẤM XẾP CHỒNG THẲNG ĐỨNG:** Tuyệt đối không xếp chồng dấu nón/trăng và dấu thanh thẳng đứng lên nhau. Việc này khiến dấu vọt qua trần (quá ascent), dính liền thành vệt mờ ngang, khiến người chơi không thể phân biệt được `ể`/`ổ`/`ẩ` với `ế`/`ố`/`ấ` hoặc nhầm `ắ` thành dấu ngã `~`.

### Quy tắc tạo hình chuẩn:
1. **Dấu hỏi kép trên nón (`ể, ổ, ẩ`):**
   - Đặt dấu hỏi hình móc câu rõ nét (stem đứng ở bên phải, top bar vòm trên) ngồi ngay trên đỉnh nón (y=11), cách đỉnh nón 1 khoảng hở. Nhìn vào chữ thấy rõ ngay lập tức cả dấu nón lẫn dấu hỏi, không bao giờ bị nhầm sang dấu sắc.
2. **Dấu sắc trên nón/trăng (`ấ, ế, ố, ắ`):**
   - Vẽ nét xiên vút lên từ sườn phải / đỉnh phải của nón hoặc trăng (`(4, 10), (5, 11)`).
3. **Dấu huyền trên nón/trăng (`ầ, ề, ồ, ằ`):**
   - Vẽ nét xiên vút lên từ sườn trái / đỉnh trái của nón hoặc trăng (`(2, 10), (1, 11)`).
4. **Dấu thanh trên Ơ và Ư (`ớ, ờ, ở, ỡ, ợ` / `ứ, ừ, sử, ữ, ự`):**
   - Móc (horn) cố định ở góc trên bên phải (`x = 6..8`).
   - Dấu thanh (sắc, huyền, hỏi, ngã) **BẮT BUỘC ĐẶT LỆCH SANG TRÁI / CHÍNH GIỮA** (`x = 1..3`).
   - Khoảng cách giữa dấu thanh và móc chữ luôn đạt tối thiểu 2–3 pixel rỗng, tuyệt đối không chạm hay dính chùm vào nhau.
5. **Dấu nặng (Dot below) cho tất cả các chữ (`ạ, ặ, ậ, ẹ, ệ, ị, ọ, ộ, ợ, ụ, ự, ỵ`):**
   - Đặt cách đường chân chữ (baseline) đúng 1 pixel rỗng trong suốt (`y = -2` thay vì `y = -1`). Giữ nguyên vẹn đường cong tròn của đáy chữ cái, dấu nặng vuông vức, tách bạch.

---

## 3. GameMaker Font Patching & Binary Search Invariant

Trong GameMaker Studio (UndertaleModLib / data.win):
1. **Font phân mảnh theo ngữ cảnh:** Các màn hình Menu/Title thường dùng font riêng biệt (`font_header`, `font_subheader`) độc lập với `font_normal` và `font_dialog`. Phải rà soát và patch toàn bộ các font xuất hiện trên giao diện.
2. **Bắt buộc Sort Glyph theo Unicode:** GameMaker thực hiện binary search trên mảng `font.Glyphs`. Toàn bộ danh sách glyphs nạp vào mảng BẮT BUỘC phải được sắp xếp tăng dần nghiêm ngặt theo mã ký tự Unicode (`Character`). Nếu không sort, binary search sẽ thất bại và GameMaker sẽ fallback về ký tự lỗi góc vuông `⌈` (glyph 9647) dù glyph đã tồn tại trong texture.
