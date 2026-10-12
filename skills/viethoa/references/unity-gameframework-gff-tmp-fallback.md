# Unity GameFramework GFF VFS and TextMeshPro SDF Fallback

## Architecture

Tựa game sử dụng GameFramework (EllanJiang/GameFramework) trên Unity IL2CPP:
1. **GameFramework Virtual File System (`GFF\0`):**
   - File `.dat` trong `StreamingAssets` (ví dụ `Local.dat`, `Font.dat`, `Data.dat`, `UI.dat`):
   - Header 4096 bytes (Cluster size = 4096).
   - Offset 0: `GFF\0` magic (4 bytes).
   - Offset 28 (`0x1C`): payload length (int32 little-endian).
   - Payload bắt đầu tại cluster 1 (offset 4096).
   - Mã hóa: XOR 8-byte lặp lại. Key suy ra tức thì từ `first_8_bytes ^ b"UnityFS\0"`.
   - Khi đóng gói lại: nén UnityFS bundle bằng `LZ4`, mã hóa lại bằng XOR key cũ, ghi header với độ dài mới tại offset 28, pad toàn bộ file tới bội số 4096 bytes.

2. **TextMesh Pro SDF Font Fallback Forensics:**
   - UI forms trỏ tĩnh vào các font asset chính (`BagUI55_Ali`, `BagUI_SY`), không đổi font runtime qua code.
   - Các font chính chứa bảng fallback (`m_FallbackFontAssetTable`) cho các ngôn ngữ khác (Tây Ban Nha, Nga, Hàn, Nhật), nhưng hoàn toàn thiếu tiếng Việt (tofu `□` trên 66 ký tự có dấu).
   - **Giải pháp chuẩn:**
     - Tận dụng một font asset có sẵn trong `Font.dat` nhưng không dùng đến (`AlegreyaSans-ExtraBold SDF`).
     - Render SDF 8x supersampled bằng OpenCV distanceTransform (`cv2.DIST_L2`), padding 3px, point size 43pt.
     - Đưa toàn bộ bảng ký tự tiếng Việt vào atlas 1024x1024.
     - Chèn font này vào vị trí `Fallback 0` trong `m_FallbackFontAssetTable` của `BagUI55_Ali`, `BagUI_SY`, và `BagUI_SP`.
     - PPtr cùng SerializedFile (`m_FileID = 0`), không cần sửa external table hay hook code.

3. **Quy chuẩn danh xưng & Proper Nouns:**
   - Tên lá bài Tarot (`c_tarot` `Tarot.Name.*`): Giữ nguyên tiếng Anh ("The Fool", "The Magician", v.v.).
   - Đối thoại video mở đầu: Người nói là cha ("con là đứa con yêu quý nhất của cha", "Cha mong con hạnh phúc mãi mãi").
