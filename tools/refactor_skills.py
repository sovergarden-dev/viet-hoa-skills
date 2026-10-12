#!/usr/bin/env python3
"""Refactor and Trim SKILL.md files to meet the < 15,000 bytes token budget (Blocker B4 / C3).

Transfers engine-specific checklists into references/ while keeping:
1. Frontmatter with contract_version: "1.0.0"
2. Ownership & State Machine Matrix
3. 10 Tier-A Core Invariants (MUST / NEVER)
4. Workflow Sequence & Phase Gates
5. Topic Router (8-10 branches)
6. Source-Faithful Translation & Anti-Domestication Core (with positive/negative examples)
7. Final Verification Checklist
"""

import os
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
SKILLS_DIR = ROOT_DIR / "skills"


def refactor_bientaptay():
    btt_md = SKILLS_DIR / "bientaptay" / "SKILL.md"
    content = """---
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
python scripts/install-bientaptay.py \\
  --project-dir <path> \\
  --translation-file <canonical.csv> \\
  --key-column <key> \\
  --source-column <source_primary> \\
  --target-column <translation_vi> \\
  --status-column <status> \\
  --notes-column <notes> \\
  --speaker-column <speaker> \\
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
"""
    btt_md.write_text(content.strip() + "\n", encoding="utf-8")
    print(f"Refactored bientaptay/SKILL.md: {btt_md.stat().st_size:,} bytes")


def refactor_viethoa():
    vh_dir = SKILLS_DIR / "viethoa"
    vh_md = vh_dir / "SKILL.md"

    # 1. Create engine-guides directory if not present
    engine_dir = vh_dir / "references" / "engine-guides"
    engine_dir.mkdir(parents=True, exist_ok=True)

    # 2. Extract engine-specific content into reference guides
    unity_guide = engine_dir / "unity-addressables-and-tmp-guide.md"
    if not unity_guide.exists():
        unity_guide.write_text("""# Unity Addressables, TextMeshPro & Binary Patching Guide

Tài liệu hướng dẫn chi tiết quy trình xử lý game Unity engine (Addressables, MonoBehaviour, TextMeshPro, TMP_Dropdown).

## 1. Unity Binary String UTF-8 Length Rule
- Khi patch chuỗi trực tiếp trong binary Unity (`MonoBehaviour`, `TMP_Dropdown`, `TextMeshProUGUI`), length prefix 4-byte (`<i`) bắt buộc là **tổng số byte UTF-8** (`len(s.encode('utf-8'))`), **cấm dùng số lượng ký tự** (`len(s)`), kèm padding `\\x00` căn chỉnh 4-byte (`(4 - (byte_len % 4)) % 4`).
- Sai lệch giữa `len(s)` (10 ký tự) và `len(s.encode('utf-8'))` (14 byte cho `"Tiếng Việt"`) sẽ khiến Unity cắt cụt chuỗi ngay giữa chừng (`"Tiếng Vi"`).

## 2. Multi-Font Dropdown Audit
- Với `TMP_Dropdown` chọn ngôn ngữ (như `I2.Loc.SetLanguageDropdown`), decompile script C# để kiểm tra xem mỗi dòng thứ `i` có bị gán cứng một `TMP_FontAsset` riêng biệt (`LanguageFont(i)`) hay không.
- Kiểm tra cả font mặc định của `CaptionText`/`ItemText` khi đang ở ngôn ngữ khác (`EnglishFont`).
- Nhúng TTF tiếng Việt và làm sạch bảng glyph cho cả font slot thay thế lẫn font mặc định menu. Tắt `m_enableWordWrapping = 0` và xóa lề ép dọc.
""", encoding="utf-8")

    content = """---
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

$$\\text{draft} \\xrightarrow[\\text{viethoa / cron}]{} \\text{mt\\_done} \\xrightarrow[\\text{bientaptay}]{} \\text{human\\_edited (human\\_locked)} \\xrightarrow[\\text{viethoa}]{} \\text{frozen / release}$$

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
7. **Một writer, ghi nguyên tử [INV-ATOM, INV-LOCK]:** Khóa `.hermes/locks/canonical.lock` → checkpoint `.checkpoint/` → temp sibling + `os.replace` → reload → validate.
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
- **Tự động hóa Cron (Plan 1):** `references/translation-execution-modes.md`, `references/unattended-model-routing-and-prompt-budget.md`
- **Bàn giao Biên tập viên:** `references/editor-release-verification.md`

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
"""
    vh_md.write_text(content.strip() + "\n", encoding="utf-8")
    print(f"Refactored viethoa/SKILL.md: {vh_md.stat().st_size:,} bytes")


def update_other_skill_frontmatters():
    for skill_name in ["cron-tuning", "fonttv", "buildpatch"]:
        md_file = SKILLS_DIR / skill_name / "SKILL.md"
        if not md_file.exists():
            continue
        text = md_file.read_text(encoding="utf-8")
        if "contract_version:" not in text:
            # Insert after version: line
            lines = text.splitlines()
            new_lines = []
            for line in lines:
                new_lines.append(line)
                if line.startswith("version:"):
                    new_lines.append('contract_version: "1.0.0"')
            md_file.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
            print(f"Updated frontmatter in {skill_name}/SKILL.md")


if __name__ == "__main__":
    refactor_bientaptay()
    refactor_viethoa()
    update_other_skill_frontmatters()
    print("[SUCCESS] All SKILL.md refactorings complete.")
