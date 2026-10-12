---
name: bientaptay
description: "Use when cài app biên tập CSV Việt hóa. Đồng bộ an toàn."
version: 0.8.0
contract_version: "1.0.0"
author: rurus, Hermes Agent
license: MIT
platforms: [windows]
metadata:
  hermes:
    tags: [game-localization, csv, editor, windows, wpf]
    related_skills: [viethoa]
---

# bientaptay

Ứng dụng Windows WPF nhẹ cho workspace Việt hóa. Đọc và ghi trực tiếp một hoặc nhiều CSV authoritative, hiển thị nguồn, đối chiếu, bản dịch Việt, trạng thái, glossary, xưng hô và lỗi QA. Không tạo XLSX, không có database bóng và không tự build patch.

Mọi thao tác ghi tệp, khóa tiến trình và merge tuân thủ **`references/contracts/canonical-invariants-contract.md`** và thực thi qua **`scripts/_vendor/hermes_io.py`**.

## Khi dùng

- Thay Excel bằng cửa sổ biên tập bản dịch chuyên dụng.
- Người dùng tự sửa dòng mới sau khi game update.
- Dự án đã có CSV canonical với stable key, nguồn chuẩn, target Việt và state/status.
- Cần cài mới hoặc cập nhật app cho workspace khác.

Không dùng để extract game, reconcile update, dịch tự động, import bundle hoặc cài patch. Các bước đó thuộc `viethoa`.

## Điều kiện

- Windows 10/11 với `.NET 8 SDK` (app phát hành framework-dependent cần .NET 8 Desktop Runtime).
- CSV canonical nằm trong workspace, có ít nhất: stable key, một cột nguồn, target Việt và status/state.
- Mọi writer tuân thủ **[INV-LOCK]**: giữ shared lock tại `.hermes/locks/canonical.lock`. Chỉ một writer hoạt động tại một thời điểm.

## Hợp đồng dữ liệu & Bất biến

1. **Authoritative Store:** Mỗi CSV trong `translationFiles` là authoritative cho đúng domain của nó. App không import/export bản sao để merge ngược.
2. **Nguồn chuẩn:** Cột nguồn đầu tiên trong `sourceFields` là chuẩn cho token validation. Cấm đoán từ tên ngôn ngữ.
3. **Phạm vi sửa đổi [INV-CSV]:** Chỉ `translation_vi`, `status` và `notes` được sửa. Khi lưu, dòng được gán cờ `human_locked = true` hoặc `status = "human_edited"`. `viethoa` cấm ghi đè các dòng này.
4. **Ghi nguyên tử & Khóa [INV-ATOM, INV-LOCK]:** Lưu canonical bắt buộc ghi ra temp sibling + `os.replace`, kiểm tra stale SHA-256 và giữ `CanonicalLock`.
5. **Rollback [INV-RB]:** App tạo checkpoint `.checkpoint/canonical_last_valid.csv` trước khi save. Rollback file game thuộc thẩm quyền độc quyền của `buildpatch`.

## Cài đặt & Cấu hình

```bash
python scripts/install_bientaptay.py \
  --project-dir <path> \
  --translation-file <canonical.csv> \
  --key-column <key> \
  --source-column <source_primary> \
  --target-column <translation_vi> \
  --status-column <status> \
  --notes-column <notes> \
  --speaker-column <speaker> \
  --group-column <domain>
```

Installer thực hiện: khóa hash canonical, kiểm tra template từ `templates/bientaptay/`, chạy smoke tests, publish một EXE framework-dependent, xóa `bin/obj`, xác nhận canonical hash không đổi và ghi `bientaptay/install-receipt.json`. Xem chi tiết tại `references/editor-release-verification.md`.

## Quy trình Vận hành

### 1. Người dùng sửa bản dịch
1. Dừng các worker tự động hóa nền và đọc lại canonical hash.
2. Mở `Launch-BienTapTay.cmd`, tìm/lọc dòng cần sửa và biên tập.
3. Nhấn `Ctrl+S`: Ghi thẳng vào CSV authoritative qua atomic replace.
4. Hermes reload canonical, chạy validator dự án. Nếu validator không sạch, hoàn tác từ checkpoint `.checkpoint/`.

### 2. Game Update (Reconcile ba phía)
1. `viethoa` trích xuất build mới vào candidate/staging (không ghi đè canonical).
2. Reconcile ba phía bằng full composite key `(domain, key)`. Dòng mới/đổi gán `pending` hoặc `needs_context`.
3. Deterministic writer commit CSV canonical. Nếu BienTapTay đang mở không có unsaved edit, app tự reload.
4. Người dùng có thể dịch các dòng pending trực tiếp trong app, sau đó build patch bình thường.

## Reference Router

- Giao diện & phím tắt: `references/editor-ui-contract.md`
- Quy trình nghiệm thu & verify release: `references/editor-release-verification.md`
- Hợp đồng bất biến chung: `references/contracts/canonical-invariants-contract.md`
