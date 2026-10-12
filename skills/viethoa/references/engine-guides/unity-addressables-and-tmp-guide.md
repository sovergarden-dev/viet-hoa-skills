# Unity Addressables, TextMeshPro & Binary Patching Guide

Tài liệu hướng dẫn chi tiết quy trình xử lý game Unity engine (Addressables, MonoBehaviour, TextMeshPro, TMP_Dropdown).

## 1. Unity Binary String UTF-8 Length Rule
- Khi patch chuỗi trực tiếp trong binary Unity (`MonoBehaviour`, `TMP_Dropdown`, `TextMeshProUGUI`), length prefix 4-byte (`<i`) bắt buộc là **tổng số byte UTF-8** (`len(s.encode('utf-8'))`), **cấm dùng số lượng ký tự** (`len(s)`), kèm padding `\x00` căn chỉnh 4-byte (`(4 - (byte_len % 4)) % 4`).
- Sai lệch giữa `len(s)` (10 ký tự) và `len(s.encode('utf-8'))` (14 byte cho `"Tiếng Việt"`) sẽ khiến Unity cắt cụt chuỗi ngay giữa chừng (`"Tiếng Vi"`).

## 2. Multi-Font Dropdown Audit
- Với `TMP_Dropdown` chọn ngôn ngữ (như `I2.Loc.SetLanguageDropdown`), decompile script C# để kiểm tra xem mỗi dòng thứ `i` có bị gán cứng một `TMP_FontAsset` riêng biệt (`LanguageFont(i)`) hay không.
- Kiểm tra cả font mặc định của `CaptionText`/`ItemText` khi đang ở ngôn ngữ khác (`EnglishFont`).
- Nhúng TTF tiếng Việt và làm sạch bảng glyph cho cả font slot thay thế lẫn font mặc định menu. Tắt `m_enableWordWrapping = 0` và xóa lề ép dọc.
