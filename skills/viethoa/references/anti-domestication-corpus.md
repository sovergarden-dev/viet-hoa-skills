# Anti-Domestication & Source-Fidelity Corpus Policy

Tài liệu này quy chuẩn danh mục các quy tắc phát hiện hiện tượng thuần Việt hóa gượng ép (domestication), nói giảm nói tránh quan liêu (bureaucratic euphemism), và Hán-Việt hóa khiên cưỡng tên nhân vật/thực thể trong các dự án chuyển ngữ trò chơi.

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

## 2. Cơ Chế Ghi Đè Theo Dự Án (Project Glossary Override)

Mỗi dự án game có thể có bối cảnh lịch sử hoặc thuật ngữ đặc thù riêng:
- Nếu một trò chơi cố tình lấy bối cảnh cổ trang phương Đông yêu cầu dùng âm Hán-Việt, dự án được phép định nghĩa tệp `rules.json` riêng hoặc ghi đè thông qua sổ cái `templates/proper-noun-ledger.csv`.
- Công cụ `scripts/domestication_detector.py` hỗ trợ cờ `--rules <path>` để nạp quy tắc tùy chỉnh theo từng tựa game cụ thể.
