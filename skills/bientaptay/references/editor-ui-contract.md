## UI/UX baseline

- DataGrid virtualization cho corpus lớn; cache validation/source search; search debounce; filter phạm vi/status/group/QA.
- Hai pane: danh sách bên trái, source/reference/final/context bên phải.
- Glossary liên quan và quy tắc xưng hô hiện cạnh dòng đang chọn.
- Phím tắt: `Ctrl+F` lọc bảng hiện tại, `Ctrl+Shift+F` tìm read-only xuyên mọi bảng, `Ctrl+H`, `Ctrl+S`, `F5`; `Ctrl+G` tìm full canonical key chính xác; `F3`/`Ctrl+Enter` vẫn chỉ nhảy tới dòng pending/cần ngữ cảnh/lỗi QA. `Ctrl++`, `Ctrl+-`, `Ctrl+0` đổi cỡ chữ.
- Dark neutral, một accent, custom `WindowChrome` title bar không dải sáng, scrollbar tối mảnh có hover/drag state, keyboard navigation và standard focus states.
- Phân trang: mặc định 17 hàng, người dùng chọn 10/17/25/50/100; bấm `Trang N / M` để nhập trang đích, mũi tên trái/phải chỉ đổi trang khi không gõ trong ô.
- Find/replace dùng overlay nên không làm thay đổi 17 hàng; preview hiển thị key, số occurrence, trước/sau và lỗi QA.
- Pane context hiển thị tối đa bốn lượt trước/sau trong cùng scene; speaker liền nhau được gộp, lượt hiện tại dùng viền accent; mỗi card bấm được để tới exact key đầu lượt. Bookmark giữ `(translationId, exactKey)` trong session.
- Cỡ chữ 90/100/115/130%; High Contrast lấy semantic/system colors đúng cặp selection; process dùng `PerMonitorV2`; smoke ép `1080×700` ở font 130%. Tỷ lệ splitter và độ rộng cột được lưu trong session, có clamp để không đưa cửa sổ/điều khiển ra ngoài vùng hợp lệ.
- Tab **Thay đổi ngoài** hiển thị file, loại đổi, key, field, baseline/local/file ngoài và full value của dòng chọn; watcher quét tất cả translation/reference files, kể cả file bị xóa.
- Tab tìm kiếm project chỉ đọc, không trộn row giữa các store và không tự merge.
- Tab **QA nhất quán** mặc định **Chưa phân loại**. **Lưu quyết định** giữ cảnh báo; **Lưu & kế tiếp** nhảy tới cảnh báo còn lại. Trên tab QA, `Ctrl+S` lưu sidecar chứ không ghi canonical; `Ctrl+Shift+Enter` là lưu-và-kế-tiếp. `F3`/`Ctrl+Enter` không đổi. **Xuất báo cáo** là JSON/CSV chỉ đọc. **Sao chép context** chỉ retry `CLIPBRD_E_CANT_OPEN`. Lỗi đã hiện cho người dùng có thể ghi `<project>/diagnostics/app.log` đã che, 64 KiB, 3 file; sao chép/lưu thành công không ghi. Receipt v3 ghi metadata `qa_decisions`; sidecar vắng hợp lệ, sidecar hỏng fail release.
- **Hoàn tác batch** chỉ khả dụng cho batch thay gần nhất trước khi lưu và tự khóa khi phát hiện dòng đã bị sửa sau batch.
- Glossary dùng longest-match-first, không trả kết quả chồng lấn, bỏ protected token như `<br>` và character term CJK một ký tự gây false-positive.
- Nút **Hoàn tác dòng** reset riêng dòng đang chọn về snapshot vừa lưu; trạng thái dirty toàn bảng được tính lại sau reset.
- Không animation, telemetry, network, plugin system hoặc background database.

