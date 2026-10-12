# Tách nguyên nhân crash trên game Telltale đã mod [V]

Dùng khi người dùng báo "cài mod xong thì game crash" — đặc biệt crash chỉ xảy ra ở một cấu hình (có tay cầm, một màn cụ thể, một save cụ thể).

## Nguyên tắc

**Không sửa gì trước khi biết lớp nào gây crash.** Trả lời "có thể do mod" mà không đo là bịa. Mỗi lớp bật/tắt một mình, chạy lại, ghi offset.

## Thang chẩn đoán (rẻ → đắt)

1. **Xem lịch sử crash trước khi kết luận.** Nếu log có crash *trước* ngày mod thì nghi phạm số một không phải mod:
   ```bash
   powershell.exe -NoProfile -Command "Get-WinEvent -FilterHashtable @{LogName='Application'; Id=1000} -MaxEvents 500 | Where-Object { \$_.Message -match 'GameName' } | ForEach-Object { '{0}  offset={1}' -f \$_.TimeCreated.ToString('yyyy-MM-dd HH:mm:ss'), [regex]::Match(\$_.Message,'Fault offset: (0x[0-9a-f]+)').Groups[1].Value }"
   ```
   `Application Error` id 1000, exception `0xc0000005` + `Faulting module name: unknown` = access violation trong code của chính game.
2. **Ghi lại sha256 của từng lớp trước khi đụng vào**, để hoàn nguyên chính xác (file save của người dùng không có bản gốc!).
3. **Gỡ từng lớp, chạy lại, so offset**:
   - chặn mạng (hosts) → gỡ
   - cờ read-only → gỡ
   - file cache trong thư mục save → hoàn nguyên `.bak`, hoặc **đổi tên** cho game tự tải bản gốc
   - archive đã repack → trả bản gốc
   Mỗi lần chạy ghi lại: process còn sống sau ~35s hay không, và offset crash mới.
4. **Offset lặp lại trên nội dung gốc = crash của game**, không phải của mod. Offset đổi loạn xạ cũng vậy (access violation ở vùng init).

## Kết quả đã gặp thật (The Wolf Among Us, 2026-09-29)

Ma trận đo được, crash **luôn xảy ra** khi tay cầm đã cắm sẵn lúc khởi động:

| cấu hình | crash? |
|---|---|
| chặn host + read-only + mọi bản vá | có (0x006feb08) |
| bỏ khoá read-only | có (0x006fece0) |
| bỏ luôn chặn host | có (0x006feb08 rồi 0x004febcc) |
| hoàn nguyên 5 file cache | có (0x004febcc) |
| **hoàn nguyên toàn bộ archive đã vá (nội dung gốc)** | **có (0x00027624)** |
| bỏ luôn `choice.prop` cục bộ | có (0x00027624, lặp y hệt) |

→ Bản Việt hoá **không** gây crash. Tay cầm + game 2013 = crash ở đường init input.

### Ma trận đầy đủ (làm lại trên bản gốc thật `Pack_Backup_Original/`)

| cấu hình | crash? | offset |
|---|---|---|
| game nguyên bản (18 archive gốc) + user data gốc + không chặn host | **có** | `0x0036f14c` |
| như trên, khởi động qua `steam://rungameid/250320` | **có** | `0x006ff214` |
| bản đã vá đầy đủ | có | `0x006feb08` |

Hai chục lần chạy, **offset khác nhau mỗi lần** ⇒ access violation ở đường init, không phải lỗi nội dung file.

### Nghi phạm còn lại (đã gặp thật)

- **Tay cầm ảo do phần mềm tạo, không phải phần cứng**: `HID\VMULTI&COL06\...` — driver `vmulti.inf` của **Parsec** (`parsecvirtualds.inf` cũng có). Máy có Parsec đang chạy ⇒ luôn có **2** "HID-compliant game controller" được enumerate lúc khởi động.
- Driver tay cầm thật (Xbox 360, `VID_045E&PID_028E`) cài ngày 17/09/2026 — xem `DEVPKEY_Device_InstallDate` để biết cái gì mới xuất hiện.
- Engine 2013 chỉ enumerate tay cầm **một lần lúc khởi động** ⇒ "mở game trước rồi cắm tay cầm" không dùng được. Phải sửa nguyên nhân, không lách được.
- `pnputil /disable-device` có thể trả "Device is pending system reboot" ⇒ phải khởi động lại máy rồi mới tắt được thiết bị ảo.

### ĐÃ TÌM RA THỦ PHẠM: tay cầm ảo của Parsec [V]

Kết quả cuối 2026-09-29: gỡ node thiết bị ảo bằng

```bash
pnputil /remove-device 'HID\VMULTI&COL06\1&2D595CA7&0&0005'
# -> "Removing device … System reboot is needed to complete configuration operations!"
```

rồi chạy game với **tay cầm thật vẫn cắm**: game lên bình thường, không crash. Trước đó, đủ mọi cấu hình (kể cả game nguyên bản) đều crash.

**Bẫy quan trọng:** **thoát ứng dụng không xoá thiết bị ảo.** Node HID do driver tạo là thiết bị root-enumerated — Parsec tắt hẳn (`Parsec Stopped`, 0 process) mà `Get-PnpDevice` vẫn báo `Present = True`. Người dùng test bằng cách quit app rồi báo "không liên quan" ⇒ kết luận sai. Phải kiểm `Present` **sau khi** thoát app, hoặc gỡ/tắt node.

**Cách nhận diện máy có tay cầm ảo:** đọc `InstanceId` của từng "HID-compliant game controller"; chuỗi không phải `VID_xxxx&PID_xxxx` thật (ví dụ `HID\VMULTI&...`) là thiết bị do phần mềm tạo; tra ngược driver bằng `pnputil /enum-drivers` (khớp `Original Name` với `vmulti.inf`/`parsecvirtualds.inf`).

**Cách dùng vẫn chơi được:** mở game trước (**không cắm tay cầm**), rồi cắm tay cầm khi đã vào menu. Chính các ảnh chụp trước đó của người dùng cho thấy đường này chạy tốt (widget nhắc nút chỉ hiện khi có tay cầm).

## Bẫy

- **Kiểm tra "bản gốc" trước khi dùng nó để miễn trừ.** Lần đầu tôi test bằng một thư mục snapshot trong project (archive **nhỏ hơn** bản thật — dấu hiệu đã bị repack/prune) và kết luận vội. Phải tìm đúng bản gốc: game Telltale hay có sẵn `Pack_Backup_Original/` trong thư mục game, hoặc dùng Steam verify. **So kích thước**: archive gốc của TWAU ~200 KB–4,5 MB mỗi cái; bản bị repack thường nhỏ hơn hẳn.
- **Đừng kết luận "do Steam Cloud"** khi chưa đọc `appmanifest_<appid>.acf` của chính game — TWAU (250320) không bật cloud.
- **Crash trước khi game kịp đồng bộ mạng**: file trong thư mục save giữ nguyên mtime cũ ⇒ không phải "game ghi đè", mà là game chết sớm.
- **Đường khởi động cũng là một biến**: chạy thẳng `.exe` và chạy qua `steam://rungameid/<appid>` có thể khác nhau (Steam Input/overlay). Phải thử cả hai trước khi kết luận.
- Sau khi test xong **phải khôi phục đủ mọi lớp** và in lại sha256 để chứng minh đã về đúng trạng thái.
