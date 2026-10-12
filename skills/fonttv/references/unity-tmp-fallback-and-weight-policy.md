# Unity TextMeshPro Mixed-Weight & Ransom-Note Fallback Prevention Policy

Quy chuẩn này quy định chi tiết việc cấu hình và kiểm định Dynamic Font Asset trong Unity TextMeshPro (TMP) nhằm triệt tiêu hoàn toàn hiện tượng lệch trọng lượng nét ("chỗ đậm chỗ nhạt" hoặc "chữ rơi rụng / ransom-note fallback").

---

## 1. Bản chất Hiện tượng Rớt Từng Chữ Cái (Per-Character Fallback Defect)
Trong Unity TMP, khi một ký tự tiếng Việt có dấu (ví dụ: `á`, `ế`, `ộ`, `Đ`) không tồn tại trong font chính của UI, TMP sẽ tự động tìm ký tự đó trong danh sách `Fallback Font Assets`.
Nếu font chính là font tiêu đề nét dày đậm (ví dụ: `Orbitron-Black`, `Montserrat-ExtraBold`), nhưng font fallback lại là một font trung tính nét mảnh thông thường (ví dụ: `Arial-Regular`, `LiberationSans-Regular` 16pt):
- Các chữ cái ASCII không dấu (`N`, `H`, `I`, `E`, `M`) được vẽ bằng font chính (dày, đậm, x-height lớn).
- Các chữ cái có dấu (`Ệ`, `Ụ`) bị rớt sang font fallback (mảnh, nhỏ, x-height thấp).
- **Hậu quả:** Chuỗi hiển thị loang lổ, gãy khúc, thiếu chuyên nghiệp nghiêm trọng trên giao diện game.

---

## 2. Quy tắc Chuẩn hóa Ký tự Tiếng Việt ở Runtime
Khi viết script hook hoặc override logic phát hiện chuỗi có tiếng Việt (`HasVietnameseCharacters`):
```csharp
public static bool HasVietnameseCharacters(string text)
{
    if (string.IsNullOrEmpty(text)) return false;
    for (int i = 0; i < text.Length; i++)
    {
        char c = char.ToLowerInvariant(text[i]);
        // Phủ trọn vẹn cả chữ thường lẫn chữ IN HOA có dấu trong dải U+00C0..U+1EF9 và U+0110..U+0111 (Đ/đ)
        if (c >= '\u00C0' && c <= '\u1EF9') return true;
        if (c == '\u0110' || c == '\u0111') return true;
    }
    return false;
}
```
**Lưu ý bắt buộc:** Phải luôn gọi `char.ToLowerInvariant(c)` (hoặc kiểm tra tường minh cả chữ HOA lẫn chữ thường). Tránh lỗi chỉ kiểm tra dải chữ thường khiến các chuỗi IN HOA của game (`NHIỆM VỤ`, `VẬT PHẨM`, `CHỈ SỐ`) bị bỏ qua và rớt từng ký tự sang fallback mặc định.

---

## 3. Cấu hình Cặp Dynamic TMP_FontAsset Đồng bộ Trọng lượng
Tuyệt đối không dùng một font đơn lẻ cho toàn bộ game. Phải khởi tạo và gán cặp FontAsset tách biệt theo vai trò ngữ cảnh:
1. **Dynamic Font Bold:** Dành riêng cho Display, Title, Header, Button nhãn lớn. Sử dụng tệp font TTF/OTF có trọng lượng Bold thật (Black/Bold).
2. **Dynamic Font Regular:** Dành riêng cho Dialogue, Subtitle, Description, Item Details. Sử dụng tệp font TTF/OTF Regular thật.

### Thông số kỹ thuật bắt buộc:
- **Sampling Point Size:** Đồng bộ cùng kích thước lấy mẫu nét (ví dụ: 48pt hoặc 64pt SDFAA).
- **Atlas Resolution:** Tối thiểu 2048×2048 để chứa đủ glyph động cho tiếng Việt mà không bị tái sinh atlas liên tục gây giật khung hình.
- **Tắt Faux-Bold:** Khi đã gán Dynamic Font Bold thật sự, bắt buộc tắt thuộc tính `FontStyles.Bold` nhân tạo trong TMP Component (tránh trường hợp Unity áp dụng thuật toán làm dày nét giả lập lên một font vốn đã Bold, gây nhòe nét hoặc phình vỡ bố cục UI).
