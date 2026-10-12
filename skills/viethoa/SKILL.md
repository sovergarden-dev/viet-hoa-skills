---
name: viethoa
description: "Use when translating a game into Vietnamese end-to-end (source-faithful; anti-domestication)."
version: 2.24.0
contract_version: "1.0.0"
author: Hermes Agent, sovergarden-dev contributors
license: MIT
metadata:
  hermes:
    tags: [game-localization, vietnamese, unity, unreal, adobe-air, patch-packaging]
    related_skills: [game-localization, game-localization-review-workflows, bientaptay, fonttv, buildpatch, cron-tuning]
---

# Việt hóa game (Source-Faithful Localization)

"Việt hóa" (Localization) là **chuyển ngữ tiếng Việt tự nhiên nhưng trung thành tuyệt đối với nguyên tác và bảo tồn trọn vẹn bản sắc game gốc (Source-Faithful Translation)**, tuyệt đối **KHÔNG** phải là bản địa hóa văn hóa hay thuần Việt hóa khiên cưỡng (Anti-Domestication).

Quy trình: **Khảo sát → Trích xuất → Ma trận Xưng hô → Dịch → Kiểm định → Nhập bản sao → Font → Runtime QA → Đóng gói Patch**. Đầu ra là CSV canonical đã kiểm định và bản vá tối thiểu có thể gỡ bỏ hoàn toàn; không phân phối tệp game gốc.

Mọi thao tác ghi tệp, khóa tiến trình và merge tuân thủ **`references/contracts/canonical-invariants-contract.md`** và thư viện **`scripts/_vendor/hermes_io.py`**.

## Ranh giới Sở quyền Artifact (Single Owner Matrix)

$$\text{draft} \xrightarrow[\text{viethoa / cron}]{} \text{mt\_done} \xrightarrow[\text{bientaptay}]{} \text{human\_edited (human\_locked)} \xrightarrow[\text{viethoa}]{} \text{frozen / release}$$

- **`viethoa` (Exclusive Owner):** Sở hữu canonical CSV (`translation_vi`), Glossary, Style Guide, Pronoun Matrix, Checkpoint canonical. **CẤM ghi đè dòng có cờ `human_locked`**. Không ghi trực tiếp tệp game gốc.
- **`bientaptay`:** Sở hữu sửa đổi thủ công khi trạng thái là `human_edited`, đặt cờ `human_locked`. Cấm tự chế lock hay bypass `canonical.lock`.
- **`cron-tuning`:** Sở hữu lịch chạy, batch throughput, worker state. Chỉ đọc canonical; bỏ qua lượt nếu lock bận.
- **`fonttv`:** Sở hữu font TTF/OTF, độ phủ glyph, asset font nhúng (SDFAA). Đọc canonical CSV để lấy tập ký tự.
- **`buildpatch`:** Sở hữu độc quyền installer, backup và rollback tệp game gốc, hash manifest.

## 10 Bất biến Cốt lõi Tầng A (Tier-A Invariants)

1. **Một nguồn sự thật:** Khóa `game_root`, executable, build ID, workspace và hash đầu vào trong manifest trước mọi thao tác ghi.
2. **Không đoán format:** Ưu tiên dữ liệu localization có cấu trúc. Raw-string scan chỉ để dò tìm; cấm vá chuỗi biến thiên trực tiếp.
3. **Không sửa live khi chưa chứng minh:** Trích xuất và nhập thử nghiệm trên bản sao; giữ hash bản gốc và mọi sidecar.
4. **CSV là canonical; `bientaptay` là view/editor trực tiếp:** Không tạo XLSX hoặc database bóng. Parser xử lý CSV; không đếm dòng vật lý.
5. **Stable key là đơn vị merge [INV-CSV]:** Dùng toàn bộ composite key `(domain, key)`. Cấm positional merge, cấm fallback theo suffix.
6. **Một validator/matcher:** Mọi writer và QA helper dùng chung canonical validator và token profile theo format (`canonical-validation-and-merge-protocol.md`).
7. **Một writer, ghi nguyên tử [INV-ATOM, INV-LOCK]:** Ghi atomic write bắt buộc: khóa `.hermes/locks/canonical.lock` → checkpoint `.checkpoint/` → temp sibling + `os.replace` → reload → validate.
8. **Dịch theo ngữ cảnh & Ma trận Xưng hô:** Glossary, style guide, speaker, listener và pronoun matrix (`scripts/pronoun_validator.py`); không suy đại từ từ tiếng Anh `I/you`.
9. **Name-provenance & Anti-Domestication:** Tên riêng giữ nguyên dạng Latin hoặc theo form gốc tác giả/thị trường (Latin brand/user lock giữ nguyên). CẤM Hán-Việt hóa danh từ riêng phương Tây (Blackdog, Titan Group, Dino...).
10. **Font contract trước glyph [fonttv]:** Xác định encoding contract trước khi kết luận thiếu font. Triệt tiêu lỗi font đậm nhạt bằng font nhúng chuẩn, tắt synthetic bold.

## Triết lý Chuyển ngữ (Fidelity Core)

| Nguyên tác (English) | Dịch Sai (Thuần Việt khiên cưỡng / Domestication) | Dịch Đúng (Source-Faithful & Chuẩn Phong cách) |
| :--- | :--- | :--- |
| *Blackdog Cartel enforcer* | *Kẻ thi hành của Băng Đảng Chó Đen* | *Tay sai của Blackdog Cartel* |
| *Titan Group HQ* | *Trụ sở Tập đoàn Khổng Lồ* | *Trụ sở Titan Group* |
| *Trenchcoat (Black)* | *Áo mưa măng tô màu đen* | *Áo Choàng Dài (Đen)* |
| *HORNY stat meter* | *Chỉ số háo sắc / thèm muốn* | *Thước đo DÂM DỤC* (đúng ngữ cảnh 18+) |

## Reference Router — Lazy-Load Contract

Không nạp toàn bộ references khi khởi động. Chỉ nạp file tương ứng với phase công việc:

- **Hợp đồng bất biến dùng chung:** `references/contracts/canonical-invariants-contract.md`
- **Khảo sát & Lập kế hoạch:** `references/foundational-documents.md`, `references/task-reference-map.md`
- **Phong cách dịch & Tên riêng:** `references/source-faithful-translation-policy.md`, `references/name-provenance-policy.md`
- **Ma trận Xưng hô & Kiểm định:** `references/pronoun-consistency-policy.md`, `templates/pronoun-matrix-template.json`
- **Canonical Merge & Validation:** `references/canonical-validation-and-merge-protocol.md`
- **Động cơ Engine chuyên sâu:** `references/engine-guides/unity-addressables-and-tmp-guide.md`, `references/injection-ladder.md`
- **Tự động hóa Cron (Plan 1):** `references/translation-execution-modes.md`, `references/unattended-model-routing-and-prompt-budget.md`, `references/deterministic-batch-lifecycle.md`
- **Bàn giao Biên tập viên:** `references/editor-handoff-protocol.md`

## Operational Routing & Core Policy Pointers

Mọi tiến trình tự động hóa và phân luồng tuân thủ các chỉ dẫn kỹ thuật sau:
- **Canonical & Exact-Key Merge:** `references/canonical-validation-and-merge-protocol.md` thực thi bắt buộc composite key `(domain, key)` stable key và token verification.
- **Source-Faithful & Anti-Domestication:** `references/source-faithful-translation-policy.md` và `references/name-provenance-policy.md` bảo vệ proper nouns và thực thể phương Tây khỏi thuần Việt khiên cưỡng.
- **Protected Tokens & Residual QA:** `references/foundational-documents.md` bảo vệ protected tokens và rich-text markup trong runtime QA.
- **DLC Scope & Game Updates:** `references/game-update-delta-protocol.md` xử lý ranh giới DLC và đối chiếu delta ba phía.
- **Needs_Context & Triage:** Các hàng chưa rõ ngữ cảnh phân luồng qua `needs_context` triage thay vì suy đoán giới tính/vai trò.
- **Bounded Continuous Run & Cron:** Vận hành theo `cron-tuning` và `references/translation-execution-modes.md` cho bounded continuous run và prompt budget.
- **Deterministic Batch Lifecycle:** `references/deterministic-batch-lifecycle.md` bắt buộc atomic commit, self-pause và kiểm tra hoàn thành gỡ cron.
- **English-Source Semantic Policy:** `references/english-source-semantic-policy.md` quản lý locked terms và giữ nguyên định danh gốc.
- **Safety & Handoff:** Quét rào cản kiểm duyệt bằng `scripts/plan1_safety_detector.py`; phân luồng ngoại lệ qua `scripts/external_agent_handoff.py`.

## Checklist Nghiệm thu (Release Gate)

```text
[ ] Game root & Executable SHA-256 đã khóa trong manifest
[ ] Canonical CSV đầy đủ 100% dòng, pending == 0, needs_context == 0
[ ] Bộ validator và pronoun_validator đạt 0 lỗi, canonical_modified == false
[ ] Không còn rò rỉ đường dẫn máy cá nhân (check_hygiene đạt PASS)
[ ] Font tiếng Việt hiển thị sắc nét tại runtime, không tofu, không rớt dòng
[ ] Gỡ bỏ sạch sẽ mọi cron job tự động hóa (hermes cron list trống)
[ ] Bản vá đóng gói qua buildpatch có khả năng cài đặt và rollback sạch 100%
```
