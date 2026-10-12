# Unreal Engine 5.5 IoStore: Phân tách Container Kismet và Tránh Vá In-place Bytecode

## 1. Bản chất sự cố và Bài học từ Hariti (UE5.5 IoStore)
- **Cấu trúc AsyncLoading2 & Zen Package**:
  - Trong UE5.5, mỗi IoStore container pack các assets thành Zen chunks.
  - Các Level Sequence (`.uasset`) tự sinh ra mã Blueprint bytecode (`DirectorBP` / `ExecuteUbergraph`).
  - Các Level Map (`.umap`) chứa hàng nghìn Actor components, con trỏ Export/Import và con trỏ Name Index cố định.
- **Sai lầm chết người (In-place binary patching / Zero-Delta)**:
  - Khi cố thay thế chuỗi bằng cách cắt xén/bù trừ byte ở ngôn ngữ khác (ES, DE, RU), rất dễ vi phạm biên giới giữa các Export object nhỏ (ví dụ Export chỉ dài 137 byte bị lấn sang Export liền kề).
  - Hậu quả: Gây ra chuỗi crash nghiêm trọng của `AsyncLoading2`:
    - `Bad import index 1991254681/54`: lệch offset Import Table.
    - `Bad export index 4390910/4845`: lệch offset Export Map trong Map `.umap`.
    - `Bad name index 50688/324`: lệch offset Name Index trong bytecode `DirectorBP`.
  - Hơn nữa, việc sửa chay từng Actor/Sequence khi người chơi di chuyển tới đâu mới sửa tới đó là cực kỳ bị động, luôn bỏ sót các nhánh rẽ và các trigger thoại khác trong game.

## 2. Kiến trúc chuẩn: Phân tách 2 Container IoStore
Để Việt hóa trọn vẹn toàn bộ game UE5.5 mà không bị xung đột bytecode:
1. **Container chính (`<ProjectName>-Windows_P`)**:
   - Chứa: Font chữ (.pak), DataTables (`DT_Dialog`, `DT_noteDetails`, `多语言`), UI Blueprints (`WB_*`), và toàn bộ các file Map (`.umap`).
   - Xử lý triệt để toàn bộ các trigger nhặt đồ, thông báo vật phẩm và hội thoại cố định trên bản đồ.
2. **Container Kismet riêng biệt (`<ProjectName>-Windows_kismet_P`)**:
   - Chứa riêng biệt toàn bộ các Level Sequence có bytecode Kismet (`DirectorBP`).
   - Tách riêng container giúp UE5 nạp độc lập bảng chỉ mục Import/Export của các Sequence động mà không làm xáo trộn bảng địa chỉ của Map chính.
   - Container này có thể dùng container header version riêng hoặc mount priority riêng.

## 3. Quy trình áp dụng bản dịch chuẩn (Canonical Translation)
- Tuyệt đối KHÔNG phân phối lại bản dịch máy thô hay giữ nguyên text của cộng đồng khi đã có `canonical.csv`.
- Sau khi khảo sát được container và layout chuẩn:
  1. Trích xuất toàn bộ các chunk dạng raw (`retoc pack-raw` / `unpack-raw`).
  2. Nạp toàn bộ các DataTable đã dịch chuẩn từ `canonical.csv` vào các slot chunk tư��ng ứng (`DT_Dialog`, `DT_noteDetails`, `多语言`).
  3. Quét và thay thế toàn bộ danh xưng/thuật ngữ dịch sai (ví dụ tên nhân vật bị Hán-Việt hóa như `Hân Hân` -> `Cindy`, `Cô Đơn` -> `Cô Đan`) trên toàn bộ 100% các chunk trước khi đóng gói.
  4. Đóng gói lại thành 2 container verified bằng `retoc pack-raw`.
