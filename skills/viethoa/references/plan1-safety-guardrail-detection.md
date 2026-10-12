# Đặc tả Kỹ thuật: Plan 1 Safety Guardrail Detector & Escalation Bridge

Tài liệu này quy định kiến trúc, tiêu chuẩn phân loại và giao thức vận hành của module `scripts/plan1_safety_detector.py` (Schema: `viethoa/safety-guardrail-detector/v1`).

---

## 1. Mục đích & Nguyên tắc Cốt lõi

1. **Phát hiện chính xác rào cản kiểm duyệt:**
   Trong quá trình dịch bằng Phương án 1 (Local continuous cron), các mô hình AI có thể gặp rào cản an toàn (Safety Guardrails) đối với các nội dung bạo lực, 18+, kinh dị hoặc nhạy cảm. Hệ thống tự động quét và phân loại các trường hợp này sau khi batch dừng hoặc hoàn thành.
2. **Quy tắc Bất biến — Không chạy song song:**
   Phương án 1 và Phương án 2 **tuyệt đối không bao giờ chạy đồng thời trên cùng một dự án**. Phương án 2 chỉ được kích hoạt như một bước bổ sung (khi số dòng bị từ chối vượt quá ngưỡng xử lý tay), hoặc được chọn ngay từ đầu (`scope="full"`) đối với game 18+/bạo lực nặng.
3. **Bất biến Bất khả xâm phạm (Canonical Immutability):**
   Detector và Bridge hoạt động ở chế độ **hoàn toàn Read-Only đối với file CSV canonical**. Tuyệt đối không tự ý thêm, bớt hoặc sửa đổi dữ liệu trên đĩa.
4. **Phân định Minh bạch: Xác định (Deterministic) vs Heuristic:**
   - **Xác định 100%:** Các trường hợp Hard Refusal (lời xin lỗi/từ chối của AI, rò rỉ meta, target rỗng trên dòng đã dịch, hoặc dòng pending chứa từ khóa nhạy cảm bị bỏ lại sau khi chạy xong).
   - **Heuristic (Khuyến nghị xem xét):** Các trường hợp nghi vấn làm mềm (suspected softening). Mọi trường hợp này đều được gắn nhãn độ tin cậy `medium` và **chỉ mang tính chất gợi ý cho con người**, không bao giờ tự ý kích hoạt chuyển giao ngoài trừ khi có chỉ định rõ ràng.

---

## 2. Tiêu chuẩn Phân loại & Cấu trúc Phân nhóm (Operational Buckets)

Hệ thống phân chia các phát hiện thành các nhóm độc lập:

| Phân nhóm | Mã sự cố (`issue_type`) | Mức độ tin cậy | Ý nghĩa kỹ thuật |
|---|---|---|---|
| **Hard Refusal** | `refusal_meta_leak` | High | AI trả về câu từ chối / meta rò rỉ ("As an AI...", "Tôi không thể dịch...") |
| **Hard Refusal** | `refusal_safety_rejected` | High | Dòng canonical bị `rejected` có kèm lý do an toàn trong `notes` hoặc source chứa từ khóa bạo lực/18+ |
| **Hard Refusal** | `empty_target` | High | Dòng ở trạng thái hoàn thành (`translated`, `reviewed`) nhưng target bị rỗng (lỗi xả hoặc từ chối ngầm) |
| **Sensitive Pending** | `untranslated_sensitive_pending` | Medium (High khi `--run-completed`) | Dòng ở trạng thái `pending` có chứa từ khóa bạo lực/18+ chưa được dịch |
| **Context Gaps** | `rejected_state`, `needs_context_state` | High | Dòng cần làm rõ ngữ cảnh hoặc bị từ chối vì lý do chuyên môn (không phải do AI censorship) |
| **Passthrough** | `untranslated_passthrough` | High | Target trùng hoàn toàn với source tiếng Anh (bỏ qua nếu nằm trong danh mục tên riêng) |
| **Suspected Softening** | `suspected_softening` | Medium | Nghi vấn AI làm mềm chi tiết nhạy cảm hoặc độ dài dịch bị sụt giảm bất thường (< 40%) |

---

## 3. Cây Quyết định Phân luồng (Escalation Decision Logic)

Cơ chế điều phối dựa trên chỉ số `escalation_refusal_count` (tổng số Hard Refusals + Sensitive Pending khi chạy `--run-completed`):

- **Trường hợp 1: `escalation_refusal_count == 0`**
  * Nếu không có bất kỳ ngoại lệ nào: `recommendation = "clean"`.
  * Nếu có nghi vấn làm mềm, passthrough hoặc cần làm rõ ngữ cảnh: `recommendation = "review_advisory"` (khuyến nghị kiểm tra trong `bientaptay`).
- **Trường hợp 2: `0 < escalation_refusal_count <= manual_fix_threshold` (Mặc định: <= 15 câu)**
  * `recommendation = "manual_fix"`: Số lượng ít, khuyến nghị người dịch sửa nhanh bằng tay trong `bientaptay`.
- **Trường hợp 3: `escalation_refusal_count > manual_fix_threshold` (Mặc định: > 15 câu)**
  * `recommendation = "plan2_handoff"`: Số lượng nhiều, kích hoạt Phương án 2 để xuất Gói Ngoại lệ chuyển giao cho Agent ngoài chuyên biệt.

---

## 4. Hướng dẫn CLI & Lệnh Vận hành

### Bước 1: Quét kiểm định sau khi hoàn thành Plan 1
```bash
python scripts/plan1_safety_detector.py scan \
  --workspace /path/to/project \
  --config /path/to/scan_config.json \
  --ledger /path/to/host_private/safety-exception-ledger.jsonl \
  --report /path/to/host_private/safety-report.json \
  --run-completed \
  --threshold 15
```

### Bước 2: Kích hoạt Cầu nối xuất Exception Plan (Nếu chọn Plan 2)
```bash
python scripts/plan1_safety_detector.py bridge-plan2 \
  --workspace /path/to/project \
  --config /path/to/scan_config.json \
  --ledger /path/to/host_private/safety-exception-ledger.jsonl \
  --package-id pkg_safety_exceptions \
  --project-id my_game_project \
  --out-plan /path/to/host_private/exception-plan.json
```

### Bước 3: Đóng gói và Xuất Gói Ngoại lệ sang Plan 2
```bash
python scripts/external_agent_handoff.py export \
  --workspace /path/to/project \
  --plan /path/to/host_private/exception-plan.json \
  --outbound /path/to/outbound_exceptions \
  --host-private /path/to/host_private \
  --scope exception
```

---

## 5. Ranh giới Bảo mật Host-Private (Security Boundaries)

- Tệp `safety-exception-ledger.jsonl`, `safety-report.json` và `exception-plan.json` là **tài liệu lưu trữ nội bộ (Host-Private)**, tuyệt đối không gửi trực tiếp cho Agent ngoài.
- Khi xuất qua `external_agent_handoff.py export --scope exception`, hệ thống tự động lọc bỏ mọi đường dẫn tệp nội bộ (`path`), cấu hình cột nội bộ và mã định danh máy chủ trước khi bàn giao cho Agent ngoài qua thư mục `outbound_exceptions/`.
