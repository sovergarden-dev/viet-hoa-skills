# Cross-Skill Editor Handoff Protocol

Protocol này quy định việc bàn giao dữ liệu từ khâu chuẩn bị / dịch tự động của `viethoa` sang ứng dụng biên tập trực quan `bientaptay`.

## 1. Quy chuẩn Generator & Mapping
- Khi preparation có bàn giao editor, chạy `scripts/prepare-editor-handoff.py` với các flag mapping tường minh (`explicit flags`):
  1. Generate dữ liệu trong thư mục `staging/`.
  2. Validate trên CSV authoritative thật.
  3. Publish nguyên tử (atomic replace, không overwrite mù quáng).
  4. Xuất biên nhận `bientaptay/install-receipt.json`.

## 2. Ràng buộc Hệ thống Tệp & An toàn Dữ liệu
- Thư mục cha đích phải tồn tại trong workspace. Nếu filesystem không hỗ trợ hardlink, dừng tiến trình và báo lỗi; không tự ý fallback sang copy mù.
- Installer của `bientaptay` phải revalidate tính toàn vẹn ngay trước khi cài đặt. Biên nhận preparation không thay thế được file lock.
- Contract v1 khóa chặt: exact key, source, target, state columns, stable composite scope `(domain, key)`, file SHA-256, tổng số dòng và key-set SHA-256. Mọi sai lệch mapping stale đều là điểm dừng bắt buộc (hard stop).
- Script chẩn đoán read-only: `scripts/editor_handoff_status.py` xuất trạng thái (`verified`, `stale_canonical`, `stale_handoff`, `mapping_mismatch`, `path_mismatch`). Trạng thái khác `verified` là hard stop.
