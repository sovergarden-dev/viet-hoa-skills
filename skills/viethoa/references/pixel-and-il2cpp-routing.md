# Pixel và IL2CPP theo build

Tọa độ/RVA là case-specific, không áp máy móc.

14. **Pixel typography & dynamic font fallback:** Với game pixel-art (Unity TMP hoặc GameMaker):
    - Không để TMP Dynamic fallback sang font vector mượt (như `LiberationSans SDF`), gây lỗi hiển thị pha trộn nửa pixel nửa vector và tofu `□`. Phải cấy 100% glyphs tiếng Việt trực tiếp vào TrueType font gốc theo đúng lưới pixel (`references/unity-tmp-pixel-font-vietnamese-refinement.md`).
    - Dấu kép (stacked diacritics) trên pixel font: CẤM xếp chồng thẳng đứng làm dính liền hay vọt trần. Dấu hỏi trên nón (`ể, ổ, ẩ`) phải có móc câu rõ nét trên đỉnh; dấu sắc/huyền vút lên từ sườn phải/trái; dấu thanh trên Ơ/Ư phải đặt lệch sang trái/giữa cách móc 2-3 pixel; dấu nặng đặt cách đáy chữ 1 pixel rỗng trong suốt (`y = -2`).
    - Với GameMaker: toàn bộ mảng `font.Glyphs` bắt buộc phải sort strictly tăng dần theo mã Unicode ID để binary search không bị gãy.
15. **Unity IL2CPP Source-Language Bypass & Multi-Table Databases:**
    - Kiểm tra các hàm `GetLocalized*` trong `GameAssembly.dll`: nếu có kiểm tra `if (CurrentLanguage == Language.English) return rawField;` thì game sẽ bỏ qua hoàn toàn CSV khi chạy ở ngôn ngữ mặc định (thường do `AvailableLanguages` thiếu Tiếng Việt).
    - CẤM vá mù diện rộng toàn bộ DLL (sẽ phá vỡ `System.Globalization.CultureInfo/CompareInfo`, gây crash màn hình trắng `NullReferenceException` khi dựng Canvas/UIFX). Chỉ cân nhắc patch đã được cho phép và exact-build/byte-guarded tại đúng RVA của entity methods đó (như `QuestDefinition`), hoặc nạp bản dịch vào trực tiếp các trường fallback của ScriptableObject/MonoBehaviour trong `.assets` (`references/unity-il2cpp-source-language-bypass-and-multitable-localization.md`).
    - Với tooltip chiêu thức và nội tại nhân vật: khảo sát các TextAsset cân bằng game ngoài catalog (`MasterSpellSettings`, `SpellTooltipDatabase`) và database MonoBehaviour (`PassiveManager`).

