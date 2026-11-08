# Quy chuẩn Thiết kế High-DPI & Display Scaling cho Bộ cài WinForms Native (C# .NET 8)

## 1. Nguyên nhân Gốc rễ Lỗi Co giãn & Cắt chữ (High-DPI Bugs)
1. **Double Scaling / Xung đột chế độ AutoScale:**
   Khi sử dụng `AutoScaleMode.Dpi` (hoặc `Font`) trong WinForms, hệ điều hành tự động nhân tỷ lệ kích thước chữ theo DPI của màn hình. Tuy nhiên, nếu các container (`Panel`, `GroupBox`) hoặc các bounding box (`Bounds`) được viết bằng pixel cố định (hardcoded pixel), văn bản phóng to sẽ vượt quá kích thước hộp chứa, gây hiện tượng:
   - Cắt cụt chữ cái có đuôi kéo dài (descenders: `g`, `j`, `p`, `q`, `y`).
   - Mất dấu thanh tiếng Việt xếp chồng ở trên và dưới (`ệ`, `ộ`, `ặ`, `ế`, `ữ`, `ỷ`, dấu nặng `.`).
   - Nhãn trạng thái bị đáy cửa sổ xén đứt thân chữ.
2. **Kích thước cửa sổ vượt quá vùng làm việc (`WorkingArea`):**
   Trên màn hình laptop 1366x768 hoặc 1280x720 đặt tỷ lệ Windows 125%–150%, nếu cửa sổ logic 1024x576 bị scale mù quáng sẽ phình to thành `1280x720` hoặc `1536x864`, vượt quá chiều cao màn hình khả dụng (sau khi trừ Taskbar ~40-48px), khiến chân panel bị đẩy ra ngoài mép màn hình.
3. **Cạn kiệt GDI Handle / Lỗi `Font.Dispose()` khi đo đạc:**
   GDI+ nội bộ chia sẻ con trỏ font gốc (`GpFont`). Việc tạo font mới liên tục trong hàm co giãn layout và gọi `Dispose()` lên font cũ sẽ phá hủy handle font mà `TextRenderer` đang dùng dở, sinh ra `System.ArgumentException: Parameter is not valid`.

---

## 2. Các Quy tắc Bắt buộc (Mandatory Invariants - R1 đến R8)

### [R1] Tắt hoàn toàn AutoScale của WinForms - Dùng Mathematical Layout Engine
- Luôn đặt `AutoScaleMode = AutoScaleMode.None;` ngay đầu constructor của Form trước khi gán `ClientSize`.
- Tự quản lý và tính toán kích thước hiển thị theo hệ số tỷ lệ toán học:
  `int S(float val) => (int)Math.Round(val * currentScale, MidpointRounding.AwayFromZero);`

### [R2] Tự động Kẹp tỷ lệ thích ứng theo Màn hình (`Screen Clamp`)
Cửa sổ không bao giờ được phép vượt quá 95% diện tích `WorkingArea` của màn hình người dùng:
```csharp
Rectangle workArea = Screen.FromControl(this).WorkingArea;
float maxScaleW = (workArea.Width - 40) / 1024.0f;
float maxScaleH = (workArea.Height - 60) / 576.0f;
float clampedScale = Math.Min(rawDpiScale, Math.Min(maxScaleW, maxScaleH));
```

### [R3] Đơn vị Font bắt buộc dùng Pixel (`GraphicsUnit.Pixel`) & Tích hợp `FontCache`
- Tuyệt đối không dùng `FontUnit.Point` trong layout pixel native. Luôn dùng `GraphicsUnit.Pixel`.
- Sử dụng bộ nhớ đệm `FontCache` tĩnh để tái sử dụng font, tuyệt đối không dispose font đang được gán cho control hoặc tham gia đo đạc text:
```csharp
static class FontCache {
    static readonly Dictionary<(string, float, FontStyle), Font> cache = new();
    public static Font Get(string family, float px, FontStyle style = FontStyle.Regular) {
        float rpx = (float)Math.Round(px, 1);
        var key = (family, rpx, style);
        if (!cache.TryGetValue(key, out var font)) {
            cache[key] = font = new Font(family, rpx, style, GraphicsUnit.Pixel);
        }
        return font;
    }
}
```

### [R4] Cấu hình High-DPI chuẩn xác - Duy nhất một nguồn chân lý (Single Source of Truth)
- Trong `.csproj`: `<ApplicationHighDpiMode>PerMonitorV2</ApplicationHighDpiMode>`
- Trong `app.manifest`: Khai báo rõ `supportedOS` cho Windows 10/11 GUID và `<requestedExecutionLevel level="asInvoker" />`. Không khai báo lặp lại `windowsSettings` DPI gây warning `WFAC010`.

### [R5] Quy hoạch Command Dock an toàn (Safe Action Dock)
- Kích thước dock đề xuất: tối thiểu `456 x 180px`.
- Đẩy cụm nút bấm lên trục `Y=78px`, để lại tối thiểu **22–26px lề dưới an toàn** cho dòng trạng thái.
- Dòng trạng thái `status` phải có chiều cao tối thiểu 26–28px, đặt `UseMnemonic = false;` để không nuốt ký tự `&`.

### [R6] Từ vựng Trạng thái Đóng kín (Closed Vocabulary Status Strings)
Dòng text trạng thái trên dock chỉ sử dụng các thông báo ngắn gọn, xúc tích, đã được tính toán biên độ hiển thị:
- `"Sẵn sàng cài đặt"`
- `"Đang kiểm tra..."`
- `"Đang sao lưu..."`
- `"Đang cài đặt..."`
- `"Cài đặt hoàn tất"`
- `"Đang khôi phục..."`
- `"Đã gỡ cài đặt"`
- `"Thất bại"`
*Mọi thông báo chi tiết, đường dẫn file hoặc hướng dẫn dài phải hiển thị qua `MessageBox.Show()`, không bao giờ nhồi nhét vào label trạng thái chân trang.*

### [R7] Tích hợp Cổng Kiểm định Tự động CLI trong chính File EXE
Bộ cài phải hỗ trợ 2 cờ dòng lệnh phục vụ kiểm thử:
- `--layout-probe <dpi> <workW> <workH>`: Trả về kết quả JSON đo đạc kích thước thực của từng control so với font chữ.
- `--layout-matrix [out.json]`: Chạy ma trận 64 kịch bản DPI (8 mức DPI x 8 độ phân giải màn hình).
- `--render-probe <dpi> <workW> <workH> <out.png>`: Chụp lại ảnh kết quả render thực tế bằng `DrawToBitmap` để kiểm tra thị giác.

### [R8] Kiểm đủ ma trận, không suy rộng bằng chứng
Kiểm đúng tập 64 tổ hợp DPI/working-area đã khai báo trên EXE cuối. Đây là phép đo layout có tham số trên máy hiện hành, không phải kiểm thử 64 cấu hình Windows vật lý. Kiểm thêm GUI thực tế trong phạm vi màn hình/DPI cam kết.

## Evidence boundaries

- Treat `verify_installer_gui_layout.py --screenshot` as an image-dimension check only; it does not inspect pixels, bind the image to an EXE, or prove visual quality. Its C# scan is a keyword heuristic, not a compiler or runtime-control check. Require independent GUI observation before visual acceptance.
- Treat the current DPI wrapper as partial evidence: it trusts summary fields, does not enforce unique matrix tuples or report freshness, and only warns on failed renders. Independently verify every required tuple/predicate, report freshness, final EXE hash, and required image content. Missing or failed mandatory evidence blocks release even when the wrapper exits zero.
- Test the gates themselves with blank images, comment-only source, missing controls, empty/duplicate matrices, stale reports and failed render processes; a checker that accepts these cannot authorize promotion.
- Bind screenshots and sandbox receipts to the exact final EXE after signing and all byte-changing steps. Numerical layout, actual Windows rendering, visual approval, transaction correctness and crash recovery are separate evidence types.
- Keep project-source audits, synthetic copied-engine tests and exact shipped-EXE tests explicitly distinct. Synthetic tests can expose missing guards but cannot certify or condemn a different released binary.
- Verify install/uninstall with an external tree/hash oracle, including `created` cleanup, `same` preservation, unsupported sources and modified live files. A successful exit or restored single file does not prove transaction completeness.
- Distinguish process termination from VM reset and storage power loss. Atomic replacement of each file does not make a multi-file transaction atomic; journal recovery and verified rollback remain required.
- Count PASS, FAIL, SKIP and ERROR separately. Do not call skipped tests, queued consultations, elapsed calendar time, or self-reported success independent validation.


### [R9] Font Source Immutability & SDF Glyph Index Preservation
- **Nguyên lý:** Tuyệt đối KHÔNG thay thế trực tiếp nhị phân TTF (`m_FontData`) của một Font Asset gốc nếu Font Asset đó đang được TextMeshPro tham chiếu bởi một TMP Font Asset SDF đã được bake trước (pre-baked).
- **Cơ chế lỗi:** TMP Dynamic Font Engine dùng `FT_Get_Char_Index` tra glyphID từ file TTF rồi ánh xạ trực tiếp vào từ điển `m_GlyphLookupDictionary` của atlas cũ. Nếu file TTF mới có glyphID của một ký tự mới (ví dụ số `1`) trùng với index đã bake của một glyph khác (ví dụ dấu chấm `.`), TMP sẽ tái sử dụng glyph cũ và vẽ sai ký tự trên toàn bộ UI game.
- **Quy chuẩn xử lý:**
  1. Giữ nguyên vẹn 100% nhị phân file TTF gốc đi kèm với SDF asset.
  2. Mở rộng ký tự tiếng Việt thông qua chuỗi Fallback (`m_FallbackFontAssetTable`) hoặc chuyển hướng con trỏ ngôn ngữ runtime (`UILanguageFontSettings`).
  3. Mọi bản vá font TextMeshPro bắt buộc phải chạy kiểm định va chạm index chữ số (`verify_tmp_glyph_map.py`) trước khi đóng gói phát hành.
