# Unity IL2CPP Source-Language Bypass & Multi-Table Localization

## 1. Cạm Bẫy Nhảy Tắt (Source-Language Bypass Trap) trong Unity IL2CPP

### Hiện tượng
Toàn bộ file ngôn ngữ CSV (kể cả slot tiếng Anh `Language.English = 0` lẫn slot tiếng Việt `Language.Vietnamese = 4`) đã được dịch và nạp 100% vào `.assets`. Giao diện tĩnh và các menu chính hiển thị tiếng Việt hoàn hảo, nhưng:
- Toàn bộ danh sách nhiệm vụ, mô tả nhiệm vụ, checklist mục tiêu (`QuestDefinition`).
- Hoặc danh sách vật phẩm, trang bị (`Item`).
- Hoặc hội thoại cốt truyện NPC (`NPCDatabase`).
Vẫn bị kẹt lại 100% bằng tiếng Anh gốc trên màn hình.

### Nguyên nhân kỹ thuật
Trong mã nguồn C# biên dịch IL2CPP (`GameAssembly.dll`), nhà phát triển game thường viết mã tối ưu hóa để tránh tra cứu dictionary khi người chơi chọn ngôn ngữ nguồn (thường là tiếng Anh):
```csharp
public string GetLocalizedDescription() {
    if (LocalizationManager.Singleton == null || LocalizationManager.Singleton.CurrentLanguage == Language.English) {
        return this.QuestDescription; // TRẢ VỀ FIELD HARDCODED TIẾNG ANH TRONG SCRIPTABLEOBJECT!
    }
    return LocalizationManager.Singleton.Get(Category.Quests, this.LocalizationKeyDescription, this.QuestDescription);
}
```
Đồng thời, trong danh sách ngôn ngữ hiển thị tại Menu Cài đặt (`GameConfig.AvailableLanguages`), nhà phát triển thường chỉ nạp `[English, Portuguese, Chinese, Spanish, German, Russian]` mà **KHÔNG CÓ Tiếng Việt (`Language.Vietnamese = 4`)**.
Do đó game luôn khởi động ở `CurrentLanguage = 0 (English)`. Khi vào bảng nhiệm vụ, mã máy:
```x86asm
cmp dword ptr [rax + 0x30], 0   ; [LocalizationManager.Singleton.CurrentLanguage] == 0?
je return_hardcoded_english;     ; NHẢY TẮT VÀ BỎ QUA HOÀN TOÀN HỆ THỐNG CSV!
```

### CẢNH BÁO TỬ HUYỆT: CẤM VÁ MÙ DIỆN RỘNG (NEVER BLIND-PATCH THE DLL)
Nếu tìm kiếm chuỗi byte `cmp dword ptr [rax + 0x30], 0` (`83 78 30 00`) trên toàn bộ `GameAssembly.dll` (100MB+) rồi NOP hóa tất cả các lệnh `je`:
- Bạn sẽ vô tình can thiệp vào các thư viện mscorlib / BCL bên trong DLL (`System.Globalization.CultureInfo.GetCultureInfo`, `System.Globalization.CompareInfo.GetCollator`, `System.String.StartsWith`).
- Khi vào game, Canvas và Shader hiệu ứng UI (`ChocDino.UIFX`, `CanvasUpdateRegistry`) sẽ ném `NullReferenceException`, dẫn tới **chết game tại màn hình trắng (White Screen of Death)** ngay khi mở Menu chính!

### Quy trình xử lý chuẩn xác (Surgical Patching)
1. **Xác định RVA chính xác:** Mở `il2cpp_dump/script.json` hoặc `dump.cs`, tìm chính xác địa chỉ của các hàm entity cần vá (ví dụ `QuestDefinition$$GetLocalizedName`, `QuestDefinition$$GetLocalizedDescription`, `QuestDefinition$$GetLocalizedTaskGroupName`, `QuestDefinition$$GetLocalizedTaskDescription`).
2. **Vi phẫu đúng mục tiêu:** Chỉ NOP đúng các byte lệnh nhảy `je` tại các RVA đã xác minh (ví dụ 4 hàm của `QuestDefinition` chỉ tốn đúng 16 byte thay đổi trên toàn bộ DLL).
3. **Dual-Layer Fallback (Vá kép tại nguồn):** Đồng thời nạp chuỗi tiếng Việt vào các trường fallback của MonoBehaviour / ScriptableObject trong `.assets` (ví dụ `MasterSpellSettings` PathID 6783, `PassiveManager` PathID 264211) để đảm bảo dù game có rơi vào nhánh nào cũng 100% hiển thị tiếng Việt.

---

## 2. Dữ Liệu Đa Bảng Ngoài Localization Catalog

Trong các game Unity RPG có hệ thống kỹ năng phức tạp:
- **Tooltip phép thuật, cơ chế sát thương:** Thường không lưu trong CSV localization mà lưu trong một TextAsset riêng của cơ sở dữ liệu cân bằng game (ví dụ `MasterSpellSettings` / `SpellTooltipDatabase`).
- **Nội tại nhân vật / Archetype Passives:** Thường lưu trực tiếp trong mảng của MonoBehaviour Singleton (ví dụ `PassiveManager` / `PassiveEntries`).
- **Khảo sát bắt buộc:** Quét toàn bộ TextAsset phi hội thoại và các MonoBehaviour có chứa chuỗi văn bản trong `sharedassets*.assets`. Nếu có, phải cập nhật trực tiếp dữ liệu tiếng Việt vào các asset này.

---

## 3. Quy Chuẩn Danh Từ Riêng (Proper Nouns) trong Western/Action RPG

1. **Khóa Latin 100% cho:**
   - Tên Class & Archetype (Brawler, Spellblade, Elemental Ranger, Blood Knight...).
   - Tên Kỹ năng & Chiêu thức (Weapon Swap, Fireball, Aimed Shot, Blizzard...).
   - Tên Trang bị & Vật phẩm (Iron Sword, Alpha Claw, Apple Juice...).
   - Tên Quái vật & Boss (Monstrous Droop, Basilisk, Goblin Caves...).
   - Tên Địa danh / Scenes (The Lost Caverns, Earlwood Village...).
2. **Chỉ dịch nghĩa cho:**
   - Phần diễn giải, công dụng, chỉ số sát thương, mô tả hiệu ứng, lore, lời thoại NPC và chỉ dẫn checklist nhiệm vụ.
3. **Kỹ thuật lọc:** Quét toàn bộ các khóa kết thúc bằng `_NAME` trong CSV, so sánh đối chiếu với danh từ gốc tiếng Anh và thiết lập bộ lọc tự động khôi phục trước khi đóng gói patch.
