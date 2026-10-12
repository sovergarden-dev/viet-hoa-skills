# Canonical Invariants Contract (SemVer 1.0.0)

**Contract ID:** `CANONICAL-INVARIANTS-V1`  
**Schema:** `hermes/localization-contract/v1`  
**License:** MIT  
**Authors:** Rurus, Hermes Agent, kann420, sovergarden-dev contributors  

Tài liệu này là nguồn chân lý duy nhất (Single Source of Truth) quy định 4 bất biến kỹ thuật bắt buộc phải tuân thủ trong toàn bộ hệ thống công cụ Việt hóa game (`viethoa`, `cron-tuning`, `fonttv`, `bientaptay`, `buildpatch`).

---

## 1. Bất biến Kỹ thuật Cốt lõi (Core Technical Invariants)

### [INV-ATOM] Atomic Write & Checkpoint Protocol
Mọi thao tác ghi dữ liệu vào tệp canonical CSV hoặc metadata cấu hình **bắt buộc phải thực hiện nguyên tử (atomic write)**:
1. Ghi toàn bộ dữ liệu ra tệp tạm nằm cùng thư mục cha (temp sibling, ví dụ `.tmp.PID.TIMESTAMP`).
2. Xác thực kích thước và tính toàn vẹn của tệp tạm (non-empty, đúng định dạng).
3. Đổi tên đè nguyên tử bằng `os.replace()` (trên Windows / POSIX).
4. Lưu bản sao lưu an toàn tại `.checkpoint/canonical_last_valid.csv` trước khi thực hiện giao dịch ghi.
5. **CẤM:** Không bao giờ mở tệp canonical trực tiếp với cờ `"w"` để ghi dần từng dòng (tránh mất dữ liệu khi tiến trình bị ngắt đột ngột).

### [INV-LOCK] Unified Cross-Process Lock Protocol
Để ngăn chặn tình trạng hai tiến trình (ví dụ worker nền `cron-tuning` và ứng dụng giao diện `bientaptay`) cùng ghi đè dữ liệu vào canonical CSV một lúc:
1. **Đường dẫn lock chuẩn duy nhất:** `<project>/.hermes/locks/canonical.lock`.
2. **Cơ chế khóa Sentinel & Sidecar Envelope:**
   - Sentinel lock file `.hermes/locks/canonical.lock` giữ byte-range lock OS (`msvcrt.locking` LK_NBLCK trên Windows, `fcntl.flock` trên POSIX).
   - Metadata envelope được ghi nguyên tử ra sidecar file `.hermes/locks/canonical.lock.json` chứa: `{ "version": "1.0.0", "pid": PID, "owner": "skill_name", "acquired_at": TIMESTAMP }`.
3. **Fail-Closed khi gặp version lạ:** Nếu một tiến trình phát hiện version khóa không tương thích trong `canonical.lock.json`, tiến trình đó phải chuyển ngay sang chế độ **Chỉ Đọc (Read-Only)** để bảo vệ dữ liệu.
4. **Non-blocking / Bỏ qua lượt:** Worker tự động hóa (`cron-tuning`) khi thấy lock đang bận phải ghi log bỏ qua lượt (skip tick), tuyệt đối không block vô tận gây tràn bộ nhớ.

### [INV-CSV] Exact-Key Matching & Reconcile Protocol
1. **Đơn vị hợp nhất (Merge Unit):** Sử dụng toàn bộ cặp khóa ổn định `(domain, key)`.
2. **CẤM:** Tuyệt đối cấm positional merge (ghép theo số thứ tự dòng), cấm suy đoán khóa theo suffix hoặc cắt ngắn chuỗi `rsplit('::')`.
3. **Assert Exact Key Set:** Trước khi ghi, writer phải assert tập khóa đích khớp chính xác 100% với danh mục khóa đã cấp phát. Mọi sai lệch (mất khóa, thừa khóa) đều phải kích hoạt rollback về bản checkpoint sạch gần nhất.
4. **Bảo tồn trạng thái người duyệt:** Không bao giờ ghi đè các dòng đã được đánh dấu `human_locked` hoặc `status == "human_edited"`.

### [INV-RB] Ownership & Rollback Separation
Phân định ranh giới sở quyền độc quyền để triệt tiêu 100% xung đột trách nhiệm:
1. **Dữ liệu Bản dịch (Canonical CSV):** Do `viethoa` và `bientaptay` sở hữu độc quyền. Khôi phục dữ liệu bản dịch được thực hiện từ `.checkpoint/` của `viethoa`.
2. **Tệp Game Nhị phân & Bản vá (Patch/DLL/AssetBundles):** Do `buildpatch` sở hữu độc quyền. Khôi phục tệp game gốc khi gỡ cài đặt hoặc cài lỗi bắt buộc phải thông qua cơ chế backup/rollback của `buildpatch`.
3. **Tiến trình & Lịch chạy (Automation):** Do `cron-tuning` sở hữu độc quyền. `cron-tuning` chỉ đọc dữ liệu và gọi entrypoint của `viethoa`, không can thiệp cấu trúc file game hay tự ý rollback tệp hệ thống.

---

## 2. Bảng Phân định Sở quyền Artifacts (Artifact Ownership Matrix)

| Skill | Quyền GHI (Exclusive Owner) | Quyền ĐỌC (Read-Only) |
| :--- | :--- | :--- |
| **`viethoa`** | Canonical CSV (`translation_vi`), Glossary, Style Guide, Pronoun Matrix, Checkpoint canonical | Không ghi file game gốc |
| **`bientaptay`** | Cột `translation_vi` khi trạng thái là `human_edited`, cờ `human_locked` | Đọc toàn bộ bảng qua shared view; không bypass lock |
| **`cron-tuning`** | File state worker (`worker_state.json`), lịch chạy, batch throughput | Chỉ đọc canonical; bỏ qua lượt nếu lock bận |
| **`fonttv`** | Font assets (TTF, OTF, SDFAA TMP font, character set definition) | Đọc canonical CSV để thống kê độ phủ ký tự |
| **`buildpatch`** | Installer payload, file game backup/rollback, SHA-256 release manifest | Chỉ đọc snapshot canonical theo hash; không sửa text |

---

## 3. Trạng thái Vòng đời Dữ liệu (Translation Data Lifecycle State Machine)

$$\text{draft} \xrightarrow[\text{viethoa / cron}]{} \text{mt\_done} \xrightarrow[\text{bientaptay}]{} \text{human\_edited (human\_locked)} \xrightarrow[\text{viethoa}]{} \text{frozen / release}$$
