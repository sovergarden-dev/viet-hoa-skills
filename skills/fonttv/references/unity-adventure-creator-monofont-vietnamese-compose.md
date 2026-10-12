# Unity + Adventure Creator: một mặt chữ cho mỗi menu, phủ tiếng Việt bằng ghép dấu

Áp dụng P2 lên Unity legacy `Font` + Adventure Creator. **Toàn bộ luật ghép dấu, đặt dấu và bộ audit nằm ở `strategy-p2-compose.md`** — file này chỉ giữ những gì đặc thù engine/khung này.

## Khi nào dùng

Game Adventure Creator, asset **Unity legacy `Font`** (không phải TMP). Chữ Việt render ra nhưng dòng đọc như trộn hai mặt chữ: chữ cái base từ mặt của game, một số nguyên âm có dấu hoặc `ơ ư` trông mảnh/lạ, hay cả từ đổi mặt giữa câu.

## Nguyên nhân gốc là fallback theo từng ký tự, không phải một font hỏng

Unity legacy `Font` phân giải glyph theo codepoint và **fallback theo từng ký tự** khi cmap không có entry. Fallback tôn trọng `m_FallbackFontReferences` của chính font; khi danh sách đó rỗng thì engine tự chọn một mặt khác. Kết quả: trong **một** từ, `c` và `h` đến từ mặt của game còn `ư` và `ậ` đến từ mặt dự phòng.

**Đừng kết luận phạm vi từ mặt chữ bạn soi đầu tiên.** Đo mọi mặt chữ mà UI nạp.

```
# kiểm kê consumer font (MonoBehaviour -> m_Script -> tên class MonoScript)
# đếm asset MenuElement theo từng PPtr font, rồi audit repertoire Việt của từng font
```

Số thật từ Sally Face (1.859 MenuElement): Boopee 794, SF Pixelate 115, BradBunR 13, Ascender Uni_210 8, DroidSansFallback 4, riffic-bold 4, PixeloidMono 1, Yomogi-Regular 1. Riêng Boopee thiếu 92 trong 196 mã điểm repertoire — đó là mặt chữ người chơi thấy nhiều nhất, nên là mặt phải sửa trước, nhưng các mặt khác cũng lộ ra và mỗi mặt cần một lượt riêng.

## Chỉ chọn P2 khi mặt chữ của game DỰA TRÊN COMPOSITE

Kiểm `glyf[name].isComposite()` trên chính glyph có dấu của font trước khi quyết định. Có composite = font đã tự công bố hình dấu và quy ước đặt dấu của nó, nên P2 rẻ và trung thành. Không có composite thì P1.

Với Boopee, chỉ **hook above** và **horn** thật sự vắng (và `breve` trên BradBunR) — luật nguồn dấu, C12 và cách dùng lại `dotaccent` làm `vn_dotbelow` ở `strategy-p2-compose.md` §1 / §1.1.

## Chọn donor: ưu tiên mặt chữ đã có trong cùng game

Cả `Ascender Uni_210` lẫn `Yomogi-Regular` đều có sẵn trong Sally Face với phủ 196/196. Dùng chúng làm donor **không thêm câu hỏi bản quyền nào** (bản vá chỉ đụng vào asset của chính game) và bỏ được bước tải về. Chọn theo style: mặt chữ vẽ tay của game muốn donor vẽ tay, không phải một sans trung tính. Khớp cỡ bằng **một tỉ lệ đo được** — `tilde ink width(target) / (tilde ink width(donor) * tỉ lệ UPEM)` — không bằng mắt.

## Slot ngôn ngữ 0 của Adventure Creator bỏ qua bảng dịch

`SpeechManager.GetTranslation(originalText, lineID, language)` trả về chuỗi gốc khi `language == 0`. Hệ quả:

- Ở slot 0 mọi `MenuButton`/`MenuLabel` hiện nhãn đã serialize, nên bản dịch chỉ nằm trong `translationText[]` sẽ không xuất hiện và UI vẫn tiếng Anh.
- Đặt ngôn ngữ chơi vào một slot KHÁC 0 và điền `translationText[]` cho slot đó (ghi tiếng Việt vào **mọi** slot cũng làm mọi lựa chọn ngôn ngữ an toàn).
- Dùng `languages[index]` để đặt tên slot cho trung thực (ví dụ slot 11 -> `Tiếng Việt`) và giữ slot 0 là `English`.

## Vô hiệu hoá remap font theo từng ngôn ngữ

`CustomLanguageSettings` (ScriptableObject) remap mặt chữ theo ngôn ngữ và sẽ **âm thầm** đổi mặt bạn vừa ghép sang một mặt khác (`SF Pixelate -> PixeloidMono`). Với mỗi entry `FontSettings` của object ngôn ngữ đã chọn (`font, remappedFont, sizeAdjustment` = 12 + 12 + 4 byte), đặt `remappedFont` thành PPtr null `(0,0)` và `sizeAdjustment` thành `0.0`.

**Không đụng vào ngôn ngữ khác**: remap của họ (ví dụ `Boopee -> Yomogi-Regular` cho tiếng Nhật) là của chính game và vẫn đúng.

## Không đọc được tĩnh việc gán font theo element

Trước khi kết luận "mặt X vẽ chuỗi Y", kiểm xem điều đó có biết được không. Trên bản dựng này thì **không**: không MonoBehaviour nào tham chiếu một asset `Font`, không có key nào tên `font` trong bất kỳ typetree nào, và duyệt path-id đệ quy qua mọi object trong cả hai file trả **0 hit cho 7 trong 8 mặt chữ**. Adventure Creator phân giải font lúc chạy từ assembly riêng của nó, nên "BradBunR vẽ 13 element" không phải thứ dữ liệu đã serialize xác nhận được — và một khẳng định dựng trên nó không phải bằng chứng.

Hệ quả: **không thể chứng minh một mặt chữ sẽ không bị hỏi vẽ một ký tự nào đó.** Nên hãy làm cho câu hỏi thành vô nghĩa — **mọi mặt chữ phải vẽ được mọi ký tự mà corpus dùng**. Điều đó biến một câu hỏi không trả lời được thành một phép kiểm hữu hạn.

Hệ quả kèm theo: **phép kiểm phủ phải quét TOÀN BỘ repertoire**, không chỉ danh sách glyph builder đã thêm — một ký tự thiếu khỏi kế hoạch dựng sẽ không bao giờ xuất hiện trong `report['added']` (xem `strategy-p2-compose.md` §2.1, §2.2).

## Thang kiểm chứng đã dùng ở đây

1. Phủ repertoire trên TTF đã dựng (196/196 cho mọi mặt) — rẻ, bắt ngay một lớp recipe bị bỏ sót.
2. Specimen thị giác ở 96 px và 22 px cho lưới base + thanh điệu, để bắt một dấu đáp xuống sai glyph.
3. Ảnh chụp runtime từ người dùng. Render chỉ-đọc không giải quyết được style: PIL vẽ ra outline rỗng cho vài mặt, và một model duyệt sẽ gọi chính dấu của hoạ sĩ là "đặt sai". Người dùng tự chạy game và gửi ảnh checkpoint.

**Đừng đốt lượt để điều khiển cửa sổ game bằng keystroke tổng hợp**: focus không chuyển được một cách đáng tin và khung hình trả về không đổi. Hỏi người dùng ảnh chụp.

## Số liệu cụ thể của bản dựng này

Dùng làm mốc so sánh, không phải hằng số toàn cục.

- **SpeechManager** = `resources.assets` path_id **4785**, class `AC.SpeechManager`. Menu: `AC.MenuButton` pid 454, `AC.MenuLabel` pid 617, `AC.Menu` pid 790.
- **Bản đồ font**: `resources.assets` `{1239: DroidSansFallback, 1240: PixeloidMono, 1241: riffic-bold, 1242: Yomogi-Regular, 1243: SF Pixelate, 1244: BradBunR, 1245: Ascender Uni_210}`; `sharedassets0.assets` `{13: Boopee}`.
- **`fontSize` mọi font = 16.0** — đó là cỡ raster của atlas, KHÔNG phải cỡ render. Cỡ render thật phải đo từ ảnh chụp (`screenshot-font-measurement.md`): Boopee vẽ hội thoại ~59 px em, menu ~52.3 px, hộp chọn ~60 px.
- **`CustomLanguageSettings`** path 4402; slot 11 từng remap `SF Pixelate -> PixeloidMono`, đã null.
- **Ngưỡng sống** (cỡ nhỏ nhất mọi dấu còn sống): Boopee 24 · SF Pixelate 23 · BradBunR 23 · riffic-bold 30 · PixeloidMono None. Cả ba cỡ render ở trên đều cao hơn hẳn, nên trong thực tế mọi dấu sống.
- **Kết quả sau khi ghép**: 148/148 glyph mỗi mặt, 0 FAIL; `original_intact` 0 lệch outline/advance trên cả 5 mặt.
