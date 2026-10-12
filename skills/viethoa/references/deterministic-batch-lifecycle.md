# Deterministic Batch Lifecycle Protocol

Protocol này áp dụng bắt buộc cho mọi quy trình dịch tự động (Plan 1 / Cron Automation) nhằm bảo đảm an toàn dữ liệu, chống vòng lặp vô hạn và tránh mất mát ngữ cảnh.

## 1. Nguyên tắc Deterministic Lifecycle
- **Deterministic Manager sở hữu toàn bộ:** Phân loại (`pending`, `translated`, `reviewed`, `needs_context`), recovery, commit và archive.
- LLM chỉ đóng vai trò tạo keyed translation payload, không can thiệp vào cấu trúc file hay commit logic.
- **Báo cáo thành công (Success Criteria):** Chỉ báo thành công khi canonical CSV có verified delta, hoặc `pending == 0`, `needs_context == 0` và bộ validator đạt 0 lỗi.

## 2. Xử lý Dòng `needs_context`
- Nếu công việc dịch thông thường đã hoàn thành nhưng còn sót dòng `needs_context`:
  - Dòng có source, secondary reference và current target hợp lệ phải đi qua `context_review` deterministic, chỉ nhận quyết định cuối `accepted | rewritten`.
  - Chỉ những dòng thực sự thiếu dữ liệu ngữ cảnh mới trở thành hard gate thủ công với danh sách exact keys.
  - Tuyệt đối không coi công việc là hoàn tất nếu còn dòng `needs_context` chưa được xử lý trong release scope.

## 3. Quy trình Tự dừng & Gỡ bỏ Cron An toàn (Self-Pause / Removal)
- Tick cuối cùng (khi `pending == 0`) **CHƯA ĐƯỢC COI LÀ HOÀN TẤT** nếu cron job chưa được tự dừng hoặc gỡ bỏ:
  1. Gửi lệnh self-pause hoặc remove bằng verified job ID qua CLI `hermes cron remove <job_id>`.
  2. Đọc lại danh sách cron bằng `hermes cron list` để xác nhận job đã bị xóa hoặc tạm dừng (`removal_verified: true`).
  3. Ghi cờ hoàn tất `completion_done.json` kèm hash và timestamp.
- Mọi lần kiểm tra tiến độ thấy `pending == 0` nhưng cron vẫn còn `enabled` đều bị coi là lỗi quy trình (lifecycle failure).

## 4. Xử lý Tranh chấp Tệp trên Windows (WinError 32 Sharing Violation)
- Trên Windows, nếu một tiến trình hoặc worker khác đang mở handle đọc canonical CSV (hoặc reader đang giữ file descriptor), lệnh `os.replace` sẽ bị chặn với lỗi `PermissionError: [WinError 32] The process cannot access the file because it is being used by another process`.
- Trước khi commit:
  - Đảm bảo đóng toàn bộ file descriptor đang đọc.
  - Sử dụng temp sibling file nằm cùng thư mục cha.
  - Tuân thủ cơ chế `CanonicalLock` trước khi thực hiện replace.
