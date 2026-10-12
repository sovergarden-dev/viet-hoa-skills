# Anti-Domestication & Source-Fidelity Corpus Policy

Tài liệu này quy chuẩn danh mục các quy tắc phát hiện hiện tượng thuần Việt hóa gượng ép (domestication), nói giảm nói tránh quan liêu (bureaucratic euphemism), và Hán-Việt hóa khiên cưỡng tên nhân vật/thực thể trong các dự án chuyển ngữ trò chơi.

**CẢNH BÁO NỘI DUNG (18+ DISCLAIMER):**
Tài liệu này và bộ quy tắc kiểm toán có chứa các thuật ngữ tình dục trực diện, tiếng lóng người lớn và ngôn từ nhạy cảm nhằm mục đích bảo tồn tính chân thực của nguyên tác tác phẩm 18+, chống lại việc tự ý làm mềm nội dung (softening) hoặc biến tướng thành ngôn từ hành chính quan liêu.

---

## 1. Triết Lý Cốt Lõi (Core Principles)

1. **Bảo Tồn Bản Quyền & Định Danh Tác Giả (IP & Brand Preservation):**
   - Danh từ riêng phương Tây (Western Proper Nouns), thương hiệu giả tưởng (Fictional Brands), linh vật (Mascots) phải được giữ nguyên dạng ký tự Latin gốc.
   - Ví dụ: *Blackdog* giữ nguyên, không dịch thành *Chó Đen*; *Titan Group* giữ nguyên, không dịch thành *Tập đoàn Khổng Lồ*; *Night City* giữ nguyên, không dịch thành *Thành phố Đêm*.
2. **Nguyên Tắc Naming Tiếng Nhật (Japanese Romaji Policy):**
   - Tên nhân vật/địa danh Nhật Bản trong game nguyên tác tiếng Nhật hoặc bản dịch tiếng Anh chuẩn mực phải được giữ ở dạng Romaji nguyên bản (theo quyết định của tác giả gốc).
   - Tuyệt đối cấm Hán-Việt hóa ngược khiên cưỡng (Ví dụ: *Suzume* giữ nguyên, cấm dịch thành nghĩa đen *Chim sẻ*; *Kazuha* giữ nguyên, cấm phiên âm *Nhất Diệp*; *Shinji* giữ nguyên, cấm phiên âm *Chân Nhị*).
3. **Bảo Toàn Văn Phong 18+ (Explicit Adult Fidelity):**
   - Không sử dụng các thuật ngữ hành chính/pháp lý quan liêu để nói giảm nói tránh từ lóng hoặc hành vi tình dục (Ví dụ: *Horny* là ham muốn/dâm dục, cấm làm mềm thành *hưng phấn/phấn khởi*; *Pervert/Perversion* là biến thái, cấm dịch thành văn bản luật *đồi trụy*).

---

## 2. Danh Mục 18 Quy Tắc Mặc Định Cốt Lõi (Default Generic Rules)

Bộ quy tắc mặc định trong `domestication_detector.py` bao gồm **18 quy tắc độ tin cậy cao** đã được tổng quát hóa (Generic Rules):
- **18+ Euphemisms & Softening:** `horny_euphemism`, `perversion_bureaucratic`, `creampie_softening`, `slut_whore_bureaucratic`, `cum_ejaculation_softening`, `dildo_flattening`.
- **Western Brands & Proper Nouns:** `blackdog_brand`, `titan_group_brand`, `styx_brew_brand`, `silver_bullet_brand`, `night_city_proper_noun`.
- **Japanese Romaji Names:** `romaji_suzume`, `romaji_yukari`, `romaji_kazuha`, `romaji_shinji`, `romaji_hotaru`.
- **Archaic Loanwords & Brand Flattening:** `trenchcoat_archaic_loanword`, `weatherbear_brand_flattening`.

### Lưu Ý Về Quy Tắc Hẹp Cấp Dự Án (Project-Specific Narrow Rules):
Các thuật ngữ quá ngắn hoặc có khả năng trùng với danh từ chung (Ví dụ: mascot *Dino* trong một game cụ thể có thể trùng với tiền tố từ vựng sinh vật học *dinosaur fossil* -> *hóa thạch khủng long*) **KHÔNG ĐƯỢC ĐƯA VÀO DEFAULT RULES TOÀN CỤC** nhằm tránh cảnh báo sai (false positive).
Các thuật ngữ này được quản lý riêng ở cấp dự án thông qua sổ cái `proper-noun-ledger.csv` nằm ngoài kho lưu trữ mở.

---

## 3. Cơ Chế Tiền Xử Lý & Khử Nhiễu (Preprocessing & Masking Architecture)

Động cơ nhận diện áp dụng quy trình so khớp 3 lớp an toàn:
1. **Masking Whitelist Thẻ Định Dạng:** Tự động che các thẻ rich-text của Unity TMP (`<color=...>`, `<sprite=...>`, `<b>`, `<i>`) và các placeholder (`{player}`, `{0}`, `%s`, `\n`) bằng khoảng trắng trước khi so khớp, đồng thời bảo vệ các toán tử so sánh (`<` và `>`) không bị nuốt nhầm.
2. **NFKC Matching View:** Chuẩn hóa `NFKC` kết hợp `casefold()` trên một bản sao tạm chỉ dùng để dò tìm regex (bảo đảm bắt trúng chữ Latin toàn khổ full-width `Ｂｌａｃｋｄｏｇ` hay Katakana nửa khổ do người chơi gõ từ bàn phím tiếng Nhật).
3. **NFC Preservation Output:** Chuỗi nguồn và chuỗi đích trả về trong báo cáo vi phạm được bảo tồn 100% dạng chuẩn Unicode `NFC` nguyên gốc của tệp canonical.

---

## 4. Cơ Chế Ghi Đè Theo Dự Án (Project Glossary Override)

Mỗi dự án game có thể có bối cảnh lịch sử hoặc thuật ngữ đặc thù riêng:
- Nếu một trò chơi cố tình lấy bối cảnh cổ trang phương Đông yêu cầu dùng âm Hán-Việt, dự án được phép định nghĩa tệp `rules.json` riêng hoặc ghi đè thông qua sổ cái `templates/proper-noun-ledger.csv`.
- Công cụ `scripts/domestication_detector.py` hỗ trợ cờ `--rules <path>` để nạp quy tắc tùy chỉnh theo từng tựa game cụ thể.
