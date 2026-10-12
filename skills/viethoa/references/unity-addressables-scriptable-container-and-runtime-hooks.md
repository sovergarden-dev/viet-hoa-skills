# Unity Addressables + ScriptableContainer: Chống dịch sót vật phẩm, sửa lỗi Font TMP và Input Drift

## When to Use

Áp dụng khi Việt hóa game Unity (Mono hoặc IL2CPP) dùng kết hợp **Addressables bundles** cho hội thoại/màn chơi và **ScriptableObjects / C# runtime** cho vật phẩm (`Item`, `Equipment`, `Apparel`), chỉ số (`Stat`), menu cài đặt (`Options`) và giao diện kho đồ (`Inventory`).

---

## 1. Chống dịch sót vật phẩm, mô tả và chỉ số (Multi-Container Inventory Gate)

### Sai lầm thường gặp
Chỉ quét và trích xuất các file `.bundle` trong `StreamingAssets/aa/` vì thấy chứa hội thoại, dẫn đến bỏ sót toàn bộ tên vật phẩm, mô tả trang bị (`Description`), chỉ số nhân vật (`Stat`) và các nút bấm giao diện. Tuyệt đối **cấm chỉ dịch chắp vá những chỗ người dùng chụp ảnh báo lỗi**.

### Quy trình bắt buộc ở Pha 1 (Khảo sát & Trích xuất)
1. **Decompile `Assembly-CSharp.dll` trước khi chốt phạm vi:**
   - Tìm các lớp quản lý dữ liệu trung tâm: `ScriptableManager`, `LanguageManager`, `Item`, `Equipment`, `Stat`, `PopulateOptions`, `PopulateInventory`.
   - Kiểm tra cách game nạp dữ liệu: nếu có `Resources.Load<ScriptableContainer>("ScriptableContainer")`, toàn bộ vật phẩm của game nằm trong `resources.assets` / `sharedassets0.assets` chứ không nằm rải rác trong bundle hội thoại.
2. **Giải mã đầy đủ `ScriptableContainer` và PPtr MonoScript:**
   - Đọc danh sách PPtr trong `ScriptableContainer` (trong `resources.assets`), ánh xạ `m_Script` sang `MonoScript` trong `globalgamemanagers.assets` để phân loại chính xác 100% đối tượng thuộc nhóm `Item`, `Apparel`, `Weapon`, `Consumable`, `KeyItem`, `MemoryCard`.
   - Trích xuất toàn bộ trường `Name` và `Description` từ cấu trúc nhị phân của tất cả đối tượng tìm được. Phân biệt rõ trường `Description` thực sự với trường tên container (`Inventory` / `Unnamed Inventory`) hoặc đường dẫn asset nội bộ (`outfits/...`, `skin_...`).
3. **Kiểm tra các chỉ số khởi tạo bằng code (`[RuntimeInitializeOnLoadMethod]`):**
   - Nhiều chỉ số (`Stat`) không lưu trong asset mà được tạo trực tiếp trong C# qua hàm tĩnh như `CreateStats()` (ví dụ: `CreateStat("stat_count_facials", "Facial cumshots", "Amount of cumshots...")`). Phải quét toàn bộ call-site của `CreateStat` và `new Stat()` trong `Assembly-CSharp.dll` để đưa 100% vào từ điển.

---

## 2. Xử lý chốt chặn `RequiresTranslation` và Tooltip ghép động

### Nguyên nhân mô tả vật phẩm không hiển thị tiếng Việt
Nhiều game cài đặt getter của vật phẩm và chỉ số theo mẫu:
```csharp
public string TranslatedDescription {
    get {
        if (!LanguageManager.RequiresTranslation) return Description;
        return LanguageManager.GetItemTranslation(this).TranslatedDescription;
    }
}
```
Khi cờ ngôn ngữ đang ở mặc định (`Language.English`), `RequiresTranslation` trả về `false`, khiến game bỏ qua toàn bộ dữ liệu dịch trong `LanguageManager` và trả về thẳng trường `Description` tiếng Anh gốc.

### Giải pháp can thiệp 2 tầng
1. **Tầng 1 (Ghi đè đối tượng gốc trong RAM):**
   - Duyệt `ScriptableManager.GetAll<Item>()` và `Stat.All`, ghi đè trực tiếp `item.Name`, `item.Description`, `stat.Name`, `stat.Description` bằng bản dịch tiếng Việt, đồng thời điền vào `LanguageManager.Items`. Khi trường gốc đã là tiếng Việt, mọi hàm gọi `GetTooltipString()` hay `GetName()` đều tự động nhận tiếng Việt bất kể trạng thái của `RequiresTranslation`.
2. **Tầng 2 (Quét và thay thế chuỗi RichText động trên UI):**
   - Hàm tạo Tooltip (`Item.GetTooltipString`) thường ghép động nhiều thành phần: tiêu đề bọc tag `<size=...><color=...><b>Tên</b></color></size>`, dòng vị trí `<color=...>Slots: MainHand</color>`, và đoạn mô tả phía dưới.
   - Bộ quét UI phải hỗ trợ cả so khớp chính xác (exact match), biến đổi hoa/thường động, thay thế cụm nhãn (`Slots:` ➔ `Vị Trí:`, `MONEY:` ➔ `TIỀN:`, `PERVERSION:` ➔ `ĐỒI TRỤY:`), và thay thế chuỗi con cho các đoạn mô tả dài nằm bên trong khối RichText.

---

## 3. Khắc phục lỗi Font chữ ("Chỗ đậm chỗ nhạt" & Ô vuông `□` Tofu)

### Nguyên nhân gốc rễ
- Game dùng các font tĩnh SDF (`BigNoodleToo SDF`, `Play-Regular SDF`) chỉ chứa ký tự ASCII.
- Khi gặp chữ tiếng Việt có dấu, TextMeshPro nhảy sang font dự phòng (`LiberationSans SDF - Fallback`).
  1. Ký tự có trong Latin-1 (`á, à, é, ó...`) được lấy từ font fallback (nét mảnh, cỡ khác), còn chữ không dấu lấy từ font chính (nét dày) ➔ tạo ra hiện tượng **"chỗ đậm chỗ nhạt"** ngay trong cùng một từ hoặc một câu.
  2. Ký tự tiếng Việt mở rộng (`đ, ẹ, ơ, ư, ẵ, ặ, ậ...`) không có trong cả font chính lẫn font fallback tĩnh ➔ biến thành **ô vuông `□` (Tofu)**.

### Giải pháp chuẩn theo `fonttv`
1. **Khởi tạo Dynamic `TMP_FontAsset` từ TrueType đầy đủ tiếng Việt:**
   - Tìm `Font` TrueType có sẵn dữ liệu vector đầy đủ trong `resources.assets` (như `Arial` 775 KB hoặc `Roboto-Regular`) hoặc nạp từ OS (`Font.CreateDynamicFontFromOSFont`), sau đó gọi `TMP_FontAsset.CreateFontAsset(baseFont)` để tạo font asset động (`AtlasPopulationMode.Dynamic`).
2. **Tiêm Fallback ưu tiên số 0 (Chống ô vuông toàn cục):**
   - Chèn `VietHoa_Dynamic_FontAsset` vào vị trí `Index 0` của `TMP_Settings.fallbackFontAssets` và của mọi `fa.fallbackFontAssetTable` trong bộ nhớ.
3. **Đồng bộ hóa Font trên khối văn bản (Chống "chỗ đậm chỗ nhạt"):**
   - Đối với các `TextMeshProUGUI` hiển thị mô tả (`Description`), chú giải (`Tooltip`), hội thoại (`Dialogue`) hoặc chứa ký tự tiếng Việt có dấu, gán trực tiếp `tmp.font = _vietnameseTMPFont`. Nhờ đó toàn bộ chữ không dấu và có dấu trong câu đều render từ cùng một font duy nhất, nét chữ đồng đều tuyệt đối.

---

## 4. Native Plugin Injection & Các bẫy kỹ thuật cần tránh

1. **Bypass kiểm tra CRC của Addressables:**
   - Khi sửa `.bundle`, `Unity.ResourceManager.dll` sẽ chặn nạp do lệch CRC so với `catalog.json` (`CRC Mismatch in AssetBundle`). Cần patch nhánh kiểm tra CRC trong `AssetBundleResource.LoadLocalBundle` (hoặc cập nhật CRC trong catalog) và kiểm tra `Player.log`.
2. **Cấu hình nạp Plugin tự động không cần BepInEx:**
   - Đặt `VietHoaPlugin.dll` (`netstandard2.1`) vào `Managed/`, thêm tên DLL vào `ScriptingAssemblies.json`, và khai báo entry point (`loadTypes: 1` = `AfterSceneLoad`) trong `RuntimeInitializeOnLoads.json`.
3. **Bẫy `TypeInitializationException` do trùng key hoa/thường:**
   - Khi khởi tạo `new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase)` trong C#, nếu có 2 key chỉ khác nhau chữ hoa/thường (ví dụ `"Fullscreen"` và `"FULLSCREEN"`), constructor sẽ ném `ArgumentException` làm sập toàn bộ class tĩnh ngay khi nạp. Bắt buộc deduplicate theo `.lower()` bằng script trước khi sinh mã C#.
4. **Sửa lỗi nhân vật tự di chuyển (`InputAxis` thiếu Deadzone):**
   - Nếu hàm đọc trục điều khiển dùng `Input.GetAxisRaw` với `!Mathf.Approximately(0f, val)` mà không có deadzone, tín hiệu trôi vi mô từ tay cầm hoặc driver ảo sẽ làm nhân vật tự đi.
   - Giải pháp: Khi không nhấn phím di chuyển trên bàn phím (`WASD` / phím mũi tên), tự động gọt mọi giá trị `|Horizontal| < 0.25f` và `|Vertical| < 0.25f` về `0f`, đồng thời đặt `MovementDirection = Vector3.zero`.

---

## 5. Bẫy trích xuất chuỗi nhiều dòng — Python `isprintable()` vs `\n
\t`

### Nguyên nhân chuỗi dài / nhiều dòng bị mất trắng
Hàm `str.isprintable()` trong Python trả về `False` trên các ký tự điều khiển như `\n` (ASCII 10, xuống dòng), `
` (ASCII 13, về đầu dòng), và `\t` (ASCII 9, tab).
Khi trích xuất chuỗi nhị phân thô từ Unity Assets hoặc Bundles:
```python
# SAI - LÀM MẤT TOÀN BỘ MÔ TẢ VÀ NHẬT KÝ CÓ XUỐNG DÒNG:
if s.isprintable() and len(s) > 0: ...

# ĐÚNG - BẮT BUỘC CHO PHÉP XUỐNG DÒNG VÀ KÝ TỰ IN ĐƯỢC:
if all(c.isprintable() or c in '\n
\t' for c in s) and any(c.isalpha() for c in s): ...
```
Nếu dùng `isprintable()` đơn thuần, toàn bộ các mô tả vật phẩm có 2 đoạn văn trở lên (như set đồ Cosplay, vũ khí huyền thoại) và các trang nhật ký, thư từ sẽ bị bỏ qua trong âm thầm mà không hề có lỗi báo ra.

---

## 6. PPtr liên file (`m_FileID > 0`) trong Unity Serialized Files

Trong `ScriptableContainer` hoặc các bộ chứa asset trung tâm, mỗi tham chiếu PPtr là một cặp `(m_FileID, m_PathID)`:
- `m_FileID == 0`: Trỏ tới đối tượng nằm ngay trong file `.assets` hiện tại (`resources.assets`).
- `m_FileID > 0`: Chỉ mục (1-based) trỏ vào mảng `externals` của file (ví dụ `fid=1` là `globalgamemanagers.assets`, `fid=3` là `sharedassets0.assets`).

**Bẫy nghiêm trọng:** Nếu giải mã container mà chỉ gom `m_PathID` rồi tra cứu trong `resources.assets`, bạn sẽ:
1. Bỏ sót hoàn toàn các đối tượng thuộc file ngoài (thường là trang phục mặc định khởi đầu của nhân vật trong `sharedassets0.assets`).
2. Tra nhầm Path ID của file ngoài sang một đối tượng ngẫu nhiên trùng Path ID trong `resources.assets` (ví dụ PPtr nhầm sang `Texture2D` hoặc `AudioClip`).
**Giải pháp:** Luôn phân giải `m_FileID` qua `externals` để tải đúng asset file đích trước khi đọc dữ liệu `MonoBehaviour`.

---

## 7. Chuẩn mực dịch thuật 18+ Adult Game: Tuyệt đối KHÔNG chêm ngoặc giải thích (Zero Explanatory Parens/Glossing)

Trong các tựa game người lớn 18+, bản dịch phải đạt độ tự nhiên, trần trụi, chuẩn xác và nhập vai tuyệt đối theo đúng văn phong của thể loại:
1. **Cấm chêm chú thích trong ngoặc đơn / ngoặc kép:**
   - SAI: `"Móc Lồn (Thủ Dâm)"`, `"Đụ Lồn (Quan Hệ Âm Đạo)"`, `"Bắn Đầy Lồn (Creampie)"`, `"Nứng (Hưng Phấn)"`, `"Bú Cặc (Blowjob)"`, `"Chịch tập thể 3 người (1 Nam 2 Nữ)"`.
   - ĐÚNG: `"Móc Lồn"`, `"Đụ Lồn"`, `"Bắn Đầy Lồn"`, `"Nứng"`, `"Bú Cặc"`, `"Chịch tập thể 3 người"`.
   - *Lý do:* Chêm ngoặc giải nghĩa làm phá vỡ tính thẩm mỹ của giao diện, biến game thành một cuốn từ điển giải nghĩa và phá hủy cảm giác nhập vai (immersion) của người chơi.
2. **Tránh ngôn từ y khoa / học thuật khi ngữ cảnh là tình dục lóng:**
   - Trong game khiêu dâm, không dùng các từ quá trịnh trọng mang tính giải phẫu như *"sử dụng âm đạo / sử dụng hậu môn"* khi nhân vật đang nói về hành vi làm tình; hãy dùng thẳng ngôn từ bản địa chân thực: *"đụ lồn"*, *"đụ lỗ đít"*, *"kẹp vú sục cặc"*, *"bú cặc"*.

---

## 8. Phân định an toàn: Ghi đè trường RAM vs Ghi đè giao diện UI

Khi game bỏ qua bảng dịch và bắt buộc phải can thiệp hook vào RAM, phải phân loại rõ trường nào được phép ghi đè trong bộ nhớ:
1. **Trường an toàn ghi đè trực tiếp trong RAM:**
   - Các đối tượng dùng `UnityEngine.Object.name` (`base.name`) làm khóa định danh (`ID`):
     - `Item.Name`, `Item.Description`
     - `Stat.Name`, `Stat.Description`
     - `NewMission.DisplayName`, `NewMission.Description`
     - `NewTask.DefaultDisplayName`
     - `GalleryImage.DisplayName`, `GalleryImage.UnlockHint`
     - `PerversionLevel.Data` (`LevelName`, `LevelDescription`)
2. **Trường CẤM ghi đè trong RAM — CHỈ được dịch trên UI `TMP_Text`:**
   - Các đối tượng mà mã C# tự động ghép `ID` hoặc bảng tra cứu từ chính chuỗi hiển thị:
     - `JournalEntry.Name` & `JournalEntry.Category`: Vì `JournalEntry.ID => Category.ToLower() + ":" + Name.ToLower()`. Nếu đổi `Name` hay `Category` trong RAM, toàn bộ save game của người chơi sẽ bị gãy khóa tra cứu nhật ký (`JournalManager.Current`). Với nhật ký, chỉ ghi đè `JournalEntry.Contents` trong RAM; còn `Name` và `Category` chỉ dịch trên UI qua `ExactTranslations`.
     - `CC_OptionType.DisplayName` & `CC_Option.DisplayName`: Vì `TypeLookup[item.DisplayName] = item`. Ghi đè trong RAM sẽ làm hỏng chức năng tra cứu tùy biến nhân vật.
