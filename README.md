# viet-hoa-skills

[![CI](https://github.com/sovergarden-dev/viet-hoa-skills/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/sovergarden-dev/viet-hoa-skills/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/sovergarden-dev/viet-hoa-skills)](https://github.com/sovergarden-dev/viet-hoa-skills/releases)
[![License](https://img.shields.io/github/license/sovergarden-dev/viet-hoa-skills)](https://github.com/sovergarden-dev/viet-hoa-skills/blob/main/LICENSE)

**Bộ công cụ Việt hóa game chuẩn nguyên tác (Source-Faithful Translation, Anti-Domestication) cho Hermes Agent**

Kho lưu trữ này chứa bộ 5 kỹ năng (skills) chuyên nghiệp, tự động hóa toàn diện quy trình chuyển ngữ và phát hành bản vá tiếng Việt cho các trò chơi trên PC (Steam / GOG / Epic) vận hành trên các engine phổ biến (Unity, Unreal Engine, Adobe AIR, Ren'Py, GameMaker, Telltale Tool).

---

## 1. Triết lý Cốt lõi (Core Philosophy)

1. **Source-Faithful Translation (Chuyển ngữ trung thành nguyên tác):**
   - Bản dịch tiếng Việt phải tự nhiên, mạch lạc nhưng bảo tồn trọn vẹn phong cách, thuật ngữ, danh từ riêng và mức độ nguyên bản của tác phẩm (bao gồm cả nội dung 18+, tiếng lóng, bạo lực, hoặc văn phong cổ điển).
2. **Anti-Domestication (Chống bản địa hóa văn hóa / thuần Việt gượng ép):**
   - Tuyệt đối không Hán-Việt hóa hay thuần Việt khiên cưỡng danh từ riêng phương Tây (ví dụ: *Blackdog* giữ nguyên, không dịch thành *Chó Đen*; *Titan Group* giữ nguyên, không dịch thành *Tập đoàn Khổng Lồ*).
   - Tên tiếng Nhật tuân thủ quy tắc tác giả gốc hoặc Romaji chính thống.

---

## 2. Kiến trúc 5 Kỹ năng (Toolchain Modules)

```
viet-hoa-skills/
├── _shared/                  # Hợp đồng bất biến kỹ thuật & thư viện I/O dùng chung
│   ├── contracts/            # CANONICAL-INVARIANTS-V1 (INV-ATOM, INV-LOCK, INV-CSV, INV-RB)
│   └── lib/hermes_io.py      # Module xử lý Atomic write, File lock OS, Exact-key merge
├── tools/                    # Công cụ quản lý monorepo & CI gates
│   ├── vendor_shared.py      # Đồng bộ hợp đồng và thư viện vào từng skill độc lập
│   └── check_hygiene.py      # Quét khử trùng đường dẫn máy cá nhân & tệp nhạy cảm
└── skills/
    ├── viethoa/              # [Core Orchestrator] Khảo sát, trích xuất, ma trận xưng hô, merge
    ├── cron-tuning/          # [Automation Engine] Tinh chỉnh worker dịch nền Plan 1, idempotent
    ├── fonttv/               # [Font Engineering] Forensic encoding, charset, Dual-Weight SDFAA font
    ├── bientaptay/           # [Editorial UI] Ứng dụng WPF biên tập trực tiếp canonical CSV
    └── buildpatch/           # [Release Packaging] Đóng gói installer single-EXE, transactional rollback
```

---

## 3. Quy trình Vận hành Toàn diện (Workflow Sequence)

$$\begin{aligned}
\text{1. Khảo sát \& Khóa Hash} &\longrightarrow \text{2. Trích xuất Chuỗi \& Stable Key} \\
&\longrightarrow \text{3. Thiết lập Ma trận Xưng hô (Pronoun Matrix v1)} \\
&\longrightarrow \text{4. Dịch thuật (Plan 1 Cron / Plan 2 External Handoff)} \\
&\longrightarrow \text{5. Kiểm định Nhất quán (Validator \& Pronoun Drift)} \\
&\longrightarrow \text{6. Nhập Thử nghiệm Bản sao (Staging Import)} \\
&\longrightarrow \text{7. Tinh chỉnh Font Chữ (FontTV SDFAA / Atlas)} \\
&\longrightarrow \text{8. Biên tập Tinh chỉnh (BienTapTay WPF)} \\
&\longrightarrow \text{9. Đóng gói Bản vá (Buildpatch Single-EXE Installer)}
\end{aligned}$$

---

## 4. Bảng Phân định Sở quyền Artifact (Single-Owner Matrix)

Áp dụng quy tắc mỗi artifact chỉ có **duy nhất 1 skill sở hữu quyền ghi** để loại bỏ 100% nguy cơ tranh chấp tệp:

| Skill | Quyền GHI (Exclusive Owner) | Quyền ĐỌC (Read-Only) |
| :--- | :--- | :--- |
| **`viethoa`** | Canonical CSV (`translation_vi`), Glossary, Style Guide, Pronoun Matrix, Checkpoint canonical | Không ghi file game gốc |
| **`bientaptay`** | Cột `translation_vi` khi trạng thái là `human_edited`, cờ `human_locked` | Đọc toàn bộ bảng qua shared view; không bypass lock |
| **`cron-tuning`** | File state worker (`worker_state.json`), lịch chạy, batch throughput | Chỉ đọc canonical; bỏ qua lượt nếu lock bận |
| **`fonttv`** | Font assets (TTF, OTF, SDFAA TMP font, character set definition) | Đọc canonical CSV để thống kê độ phủ ký tự |
| **`buildpatch`** | Installer payload, file game backup/rollback, SHA-256 release manifest | Chỉ đọc snapshot canonical theo hash; không sửa text |

---

## 5. Hướng dẫn Cài đặt & Sử dụng với Hermes Agent

### Cài đặt Trọn bộ Monorepo
Clone repository trực tiếp vào thư mục skills của profile Hermes:
```bash
git clone https://github.com/sovergarden-dev/viet-hoa-skills.git ~/.hermes/skills/viet-hoa-skills
```

### Cài đặt Từng Skill Riêng lẻ (Standalone)
Mỗi skill trong thư mục `skills/` đã được tích hợp sẵn cơ chế **Hermetic Vendoring** (`tools/vendor_shared.py`), chứa đầy đủ hợp đồng tại `references/contracts/` và thư viện tại `scripts/_vendor/`. Do đó, người dùng có thể sao chép hoặc cài đặt từng skill độc lập mà không lo gãy dependency:
```bash
# Cài đặt riêng skill viethoa
cp -r skills/viethoa ~/.hermes/skills/viethoa

# Cài đặt riêng ứng dụng biên tập BienTapTay
cp -r skills/bientaptay ~/.hermes/skills/bientaptay
```

---

## 6. Bản quyền & Ghi công (License & Attribution)

- **Giấy phép:** [MIT License](LICENSE).
- **Ghi công Upstream:** Kế thừa và phát triển từ ý tưởng của dự án [kann420/VH-Workflow-Skill](https://github.com/kann420/VH-Workflow-Skill). Chi tiết xem tại [NOTICE.md](NOTICE.md).
- **Nhà phát triển chính:** Rurus, Hermes Agent cùng cộng đồng đóng góp `sovergarden-dev contributors`.
