# Game Update Delta Reconcile & DLC Boundary Protocol

Protocol này quy định việc xử lý khi game phát hành bản cập nhật (game update) hoặc gói mở rộng (DLC), đảm bảo không ghi đè mất mát dữ liệu canonical hiện có và phân định rõ ranh giới nội dung.

## 1. Ranh giới DLC & Base Game (Scope Isolation)
- **Manifest Khóa Phạm vi:** Mọi quy trình trích xuất phải ghi rõ `base_scope` và danh mục các gói `dlc_scope`.
- Không trộn lẫn các chuỗi của DLC vào cùng tệp canonical của game gốc nếu game quản lý ngôn ngữ theo từng gói độc lập.
- Mỗi DLC có bảng canonical riêng hoặc sử dụng trường `domain` để cô lập hoàn toàn không gian khóa.

## 2. Reconcile Ba Phía (Three-Way Delta Reconcile)
Khi game có bản cập nhật mới từ nhà phát triển:
1. **Trích xuất Candidate:** Trích xuất toàn bộ chuỗi của build mới vào thư mục `staging/candidate/`. Tuyệt đối không trích xuất đè lên `03_canonical/`.
2. **So khớp Full Composite Key:**
   - So sánh bộ khóa `(domain, key)` giữa build cũ và build mới.
   - **Khóa mới (New Keys):** Dòng mới xuất hiện trong build mới được thêm vào canonical với trạng thái `pending`.
   - **Khóa thay đổi nguồn (Source Drift):** Dòng có key trùng nhưng source text tiếng Anh thay đổi được chuyển trạng thái thành `needs_context` để con người hoặc AI rà soát lại ngữ cảnh.
   - **Khóa bất biến (Unchanged Keys):** Giữ nguyên 100% bản dịch `translation_vi` và cờ `human_locked`.
   - **Khóa bị xóa (Deprecated Keys):** Giữ nguyên trong canonical hoặc đánh dấu `deprecated`, không tự ý xóa dòng để phục vụ đối chiếu lịch sử.

## 3. Giao dịch Cam kết An toàn (Deterministic Commit)
- Reconcile hoàn tất phải được ghi nguyên tử qua `hermes_io.atomic_write` kèm checkpoint `.checkpoint/canonical_last_valid.csv`.
- Mọi thao tác đều thực thi dưới sự bảo vệ của `hermes_io.CanonicalLock`.
