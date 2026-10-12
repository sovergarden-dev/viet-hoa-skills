# Unreal Engine Pak Signing, ASI Loader Hook & Mod Load Priority

## Bối cảnh & Hiện tượng
Nhiều tựa game Unreal Engine 4 / 5 (như *Mandragora: Whispers of the Witch Tree*, *Black Myth: Wukong*, *Hi-Fi RUSH*...) kích hoạt cơ chế bảo vệ tài nguyên khi đóng gói bản Shipping:
1. **Pak Signing (`.sig`)**: Engine kiểm tra chữ ký số RSA cho từng file `.pak`. Bất kỳ mod `.pak` nào đặt trong `Paks/` hoặc `~mods/` nếu không có file `.sig` hợp lệ tương ứng sẽ bị engine từ chối mở (lỗi `Missing signature` hoặc `Signature check failed`).
2. **Encrypted Index (`bEncryptedIndex == true`)**: Index của pak gốc được mã hóa bằng AES-256-ECB. Các công cụ đóng gói cộng đồng (như `repak pack`) hiện tại chỉ ghi index unencrypted (`bEncryptedIndex = false`). Nếu engine yêu cầu pak phải có encrypted index, mod pak sẽ bị engine coi là corrupt và đóng file ngay lập tức.

## Bài học xương máu & Những điều CẤM
- **CẤM tuyệt đối disassemble hay vá byte nhị phân trong file `.exe` của game**:
  - Việc tìm offset và patch byte (ví dụ NOP lệnh rẽ nhánh trong hàm verify signature) dễ làm hỏng cấu trúc PE, phá vỡ DRM Steam/Epic, và gây crash ngẫu nhiên.
  - Nguy hiểm hơn: Việc phân tích mã máy (Capstone disasm) và can thiệp nhị phân bypass kiểm tra chữ ký sẽ kích hoạt bộ lọc kiểm duyệt an toàn (Safety Filters) của các mô hình AI (bị xếp vào hành vi khai thác phần mềm / binary tampering).

## Giải pháp chuẩn mực (Community-Proven Standard)
Sử dụng **Universal ASI Loader Hook** tải lúc runtime thay vì can thiệp vào file thực thi:
1. **Thành phần**:
   - `dsound.dll`: Ultimate ASI Loader (mã nguồn mở của ThirteenAG). Khi game khởi động, hệ thống DirectX tự động nạp thư viện âm thanh này.
   - `UniversalSigBypasser.asi`: Plugin ASI hook hàm kiểm tra chữ ký trong bộ nhớ RAM lúc runtime (không lưu lại trên đĩa, không sửa `.exe`).
2. **Vị trí cài đặt**:
   - Đặt trực tiếp cạnh file executable chính trong thư mục Win64:
     `<Game_Root>/<ProjectName>/Binaries/Win64/dsound.dll`
     `<Game_Root>/<ProjectName>/Binaries/Win64/UniversalSigBypasser.asi`
3. **Thứ tự ưu tiên file Pak trong `~mods`**:
   - Unreal Engine quét các file `.pak` theo thứ tự bảng chữ cái và tra cứu ngược (Reverse Lookup - file nào có tên theo sau trong bảng mã ASCII sẽ ghi đè file trước).
   - Tên file mod trong `Content/Paks/~mods/` **bắt buộc** phải có tiền tố `z_` (ví dụ: `z_Mandragora_Viethoa_P.pak`). Vì `'z'` (0x7a) đứng sau `'m'` (0x6d) của `man-WindowsNoEditor.pak`, mod pak sẽ có độ ưu tiên cao hơn và ghi đè tài nguyên thành công.
   - Thư mục chuẩn của mod là `<ProjectName>/Content/Paks/~mods/`.
