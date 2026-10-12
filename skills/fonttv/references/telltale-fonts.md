# Telltale Tool fonts và case study TWAU

Nhãn độ tin cậy: **[V]** đã đo trong dự án; **[O]** quan sát ở The Wolf Among Us (TWAU), chưa kiểm trên game/phiên bản khác; **[H]** giả thuyết. Offset và công thức [O] phải đo lại trên từng file.

## 1. Chuỗi runtime [O]

LANDb (`5VSM`/`6VSM`) chứa text đã encode single-byte → mỗi byte là một charID → `.font` tra record trong mảng `TRectNew` → rect UV trên page DXT5 → quad vẽ theo metrics của record. Font và LANDb nằm trong `.ttarch2`.

- Tầng font không đọc UTF-8. Tiếng Việt đi qua bảng single-byte do dự án định nghĩa (VN-128: ASCII + `0x80–0xFF`). Bảng này là encoding contract, nên Telltale là route B + C.
- Mỗi màn hình có thể dùng font riêng (dialog, Pause/Settings dùng `Rockwell_Std_Condensed_48_bold.font`, …). Inventory đủ consumer trước khi kết luận.

## 2. Bất biến format [O]

- charID là uint32, duy nhất, tăng dần tuyệt đối; engine có dấu hiệu tra nhị phân. Trùng hoặc lệch thứ tự làm tra hỏng, có thể rơi về font mặc định (Arial 16 px).
- Bản gốc có đúng một record mỗi charID; charID xuất hiện hai lần là dấu vết pipeline ghi đè.
- `tex_header` (stride 193 hoặc 213 tùy font): `w @ -92`, `h @ -88`, `pitch @ -16`, `data_size @ -8`. `v` chuẩn hóa theo chiều cao DATA (page0 Condensed 1004 px, không phải descriptor h=512), `u` theo 512.
- Khi đổi kích thước atlas (ví dụ 848 → 2048): cập nhật width, height, pitch, data_size trong header texture và `headerSize = new_header_before_tex - (16 + countElements * 12 + 4)`. Sai offset làm game crash khi khởi động.
- Không re-encode DXT5 khi pixel không đổi. Giữ byte payload gốc **verbatim** và chỉ mã hoá phần hàng mới thêm; re-encode cả vùng gốc sẽ tái lượng tử hoá block DXT5 đã tác giả. Điều kiện: nội dung mới phải bắt đầu ở hàng chia hết 4 nằm dưới các hàng gốc.
- Field descriptor là **span-relative**, không phải offset tuyệt đối: `w @ span_end-92`, `h @ span_end-88`, `size @ span_end-20` và mirror `@ span_end-8`. Độ dài span khác nhau theo font (Rockwell_Std_48 = 189, ITC_Kabel_Book = 233, Rockwell_Std_Condensed = 209) nên cấm hard-code offset. Dùng project-local font_descriptor.py (không đi kèm skill) trong workspace để đọc/ghi cùng phép tính với adapter.
- Bất biến bắt buộc: `sum(descriptor_sizes) == len(payload)`. Không thoả thì adapter phải bỏ capability `ink` và audit dừng ở `structurally_verified`. Đây là lý do gốc khiến `Rockwell_Std_48_bold` không đo được ink ở cả V3 lẫn V8-đầu.
- Có font gốc khai height lệch với payload: `Rockwell_Std_Condensed` page 1 ghi `h=80` nhưng `size=20480` (= 512×40). Chuẩn hoá `h = size // width` trên bản sao, chỉ khi kết quả chia hết 4; không tin field height.
- **Không dựng lại page từ đầu.** Pixel page gốc phải sống nguyên tại chỗ và record của chúng chỉ được rescale V. Dựng lại page làm mất mọi record mà glyph không được dựng lại (Rockwell_Std_48 gốc có 42 record trên page 1).
- Sửa slot "rỗng" phải kiểm ink **trên đúng page mà record trỏ tới**. Record nằm page 0 không rỗng chỉ vì bạn đang dựng page 1.
- 28 id Latin-1 (`À Á Â È É Ê Ì Í Ò Ó Ô Ù Ú Ý à á â è é ê ì í ò ó ô ù ú ý`) là identity trong VN-128. Chúng đã có glyph tác giả trong font CP1252, nên thay bằng glyph donor là thoái hoá phong cách dù audit vẫn PASS (ink có, identity từ manifest). Chỉ tô lại khi slot thật sự rỗng.

## 3. Metrics [O]

- Fixed-cell (`AvantGarde_LT_Book_40` @ 64 px, `AvantGarde_LT_Book_14` @ 25 px): mọi record có `charHeight`/`yOffset` cố định (64/0); chữ thường có sẵn headroom trong ô. Vẽ dấu trong headroom, không nới canvas bằng `yOffset` âm.
- Proportional (`ITC_Kabel_Book`, `Rockwell_Std_Condensed`): `xAdvance` lấy từ chữ gốc của ký tự đích trong cùng font, không cộng padding canvas.
- Tổng `ch + yo` không đổi thấy ở Kabel (`a` 43/30, `â` 57/16, tổng 73). Nhưng V3 giữ đúng tổng này ở Rockwell Condensed (`ch` 76→85/86/94, `yo` 0→-9/-10) mà dấu vẫn bay trên menu, nên mô hình neo quad của engine chưa được xác minh [H].
- Template metric lấy từ record chữ có dấu gốc của chính font: Rockwell_Std_Condensed gốc `A` ink 10..56, `Á` ink 0..79, cả hai `ch=76 yo=0`; Rockwell_Std_48_bold gốc `A` ink 17..60, `Á` ink 3..60, cả hai `ch=75 yo=0` — dấu nằm trong headroom. Xác nhận bằng screenshot runtime.
- Headroom hẹp hơn chiều cao dấu: không thu dấu xuống 1–2 px cho vừa (dấu vô hình). Dùng pad trung thực rồi kiểm runtime.
- Pack atlas: đếm số glyph đã đặt bằng số glyph dự kiến. Một lần `target_h=2048` không đủ cho Rockwell_Std_48_bold đã cắt 59 glyph cuối mà pipeline vẫn báo OK.

## 4. Dựng dấu [O]

- Tách dấu độc lập: móc lấy từ hiệu `u`→`ư`, thanh lấy từ hiệu `u`→`ũ`, rồi neo riêng (móc ở góc trên phải, thanh trên đỉnh thân chữ cách 1–2 px). Không lấy nguyên cụm hiệu `u`→`ữ`.
- `Ổ`: đặt hỏi ở sườn phải dấu mũ (`mid_x + max(3, w//3)`).
- Trích dấu bằng hiệu ảnh với chữ gốc (`á` − `a`). Render combining mark đứng riêng qua shaper sẽ sinh dotted circle U+25CC.
- Căn dấu theo trục hình học thực của chữ `(col_min + col_max) // 2`.
- Crop từ atlas có bleed: đo ink bbox bằng số và so với chữ gốc. AI từng đọc mực rỉ từ hàng kề thành dấu thứ hai.

## 5. UV zero-width

Nhiều record trong font gốc có `u0 == u1`. Điều đó chỉ vô hại ở charID mà encoder không bao giờ phát ra. Ở charID mà bảng VN-128 gán cho một chữ nhìn thấy được, UV zero-width nghĩa là không có glyph (`outline_nonempty` FAIL) và slot phải được remap. UV có diện tích vẫn chưa chứng minh ink: decode DXT5 và đếm pixel.

## 6. Case study TWAU (V3 → V9n)

Chi tiết lịch sử: `case-twau-history.md`. Phần dưới chỉ giữ luật còn hiệu lực.

### Luật rút ra, còn hiệu lực

- **Mapping trước, glyph sau.** `record_present` không phải `mapping_correct`: font gốc có record tại charID nhưng glyph ở đó là ký tự legacy/CP1252 khác.
- **Nguồn text để đóng gói** là snapshot có bản địa hoá, không phải backup gốc. Dựng từ backup chỉ thay `.font` sẽ đổi toàn bộ text.
- **Byte page gốc verbatim.** Chỉ mã hoá phần hàng mới thêm, bắt đầu ở hàng chia hết 4 dưới hàng gốc.
- **Kiểm ink trên đúng page mà record trỏ tới**, không lọc `rec[1] == 0`.
- **Không dựng lại page** trừ khi mọi record encoder phát ra đều được render lại (đó là P1).
- **Descriptor là span-relative**, cấm hard-code; điều kiện bắt buộc `sum(descriptor_sizes) == len(payload)`.
- **`rec[10]` là quy ước của từng font**, đọc từ cặp `A→À` của chính font, không áp hằng số.
- **Quy ước ô:** font ô khít theo ink và font ô cố định tồn tại song song; đọc từ record gốc.
- **Mọi khoảng cách giữa hai phần ink suy từ ink**, không từ chiều cao ảnh/ô.
- **Chọn donor/font nguồn bằng số đo:** phủ đủ repertoire, hình dấu (`fill` của chấm dưới so với chính dấu chấm câu của font), weight, license.
- **Luật audit phải tự hiệu chuẩn:** chạy lên glyph do nhà phát hành dựng trước; luật nào chấm glyph gốc là luật sai.
- **Mọi thay đổi phải được đo lại trên chính bytes đó**; báo cáo lưu là cache, không phải trust root.

## 6b. Bằng chứng consumer và độ đồng nhất [V]

**Consumer phải có bằng chứng, không suy từ tài liệu.** Quét member đã extract (TWAU: `Fables_pc_Menu_data`, `Fables_pc_Boot_data`) tìm tên `*.font` — chỉ một chỗ nêu tên font: `uiz_ConsoleButtons.lua` ghi `Text Font ... ITC_Kabel_Book.font ... Text Scale 0.5`, tức nút bấm/console dùng `ITC_Kabel_Book`. Các archive còn lại không nêu tên font nào, nên mọi gán consumer khác phải đến từ ảnh runtime. Một lần đã gán sai ảnh menu Settings cho font slab chỉ vì tài liệu ghi vậy, trong khi chữ trong ảnh là sans.

Vài font dùng chung một font nguồn (P1 ghép 8 font vào Noto Sans) thì **một ảnh chứng minh thiết kế đó**, không phải từng font.

**Hệ quả cho gate 12:** 8 font sans dùng chung Noto Sans nên không phân biệt được bằng mắt, và cũng **không phân biệt được bằng khớp ảnh**: thử trên màn prologue, điểm số chỉ chênh 0.02 và font đúng (`Cantoria_MT`) không thắng — ảnh nhiều chữ nên tỉ lệ "mực template trùng mực ảnh" thưởng cho vùng nhiều mực và bỏ qua hình dạng. Vì vậy ảnh chụp một màn hình sans **không** cấp `runtime_verified` cho từng file sans. Chỉ cấp được khi biết consumer qua member (như `uiz_ConsoleButtons.lua` → `ITC_Kabel_Book.font`), hoặc khi thiết kế font là duy nhất (serif/slab/mono/đậm).

**Mục tiêu chụp ảnh cụ thể cho TWAU [V]:** `ITC_Kabel_Book.font` là consumer duy nhất đọc được từ dữ liệu — `Fables_pc_Menu_data.ttarch2` → `uiz_ConsoleButtons.lenc` (trích bằng `ttarchext -m` để giải mã thành `.lua`) có `Text Font = ITC_Kabel_Book.font`, `Text Scale 0.5`, cùng `ui_menu_navhelp.prop`, `uiz_menu_facebutton.prop`, `ui_menu_navhelp_facebutton_down.d3dtx` và `UIZ_Widget_GamepadOnly`. Nghĩa là thứ cần chụp là **thanh nav-help có icon nút tay cầm đặt cạnh một chữ lệnh ngắn** — đã gặp thật ở màn hồ sơ nhân vật: `RB` + `Cuộn`, `B` + `Menu trước`. Phải **cắm tay cầm**, vì widget chỉ chạy khi có gamepad; không có tay cầm thì thanh đó không sinh ra và không có gì để gán.

Widget lựa chọn hội thoại (hình thoi `Y/X/B/A` cạnh câu thoại) **không** phải chỗ này: chữ ở đó là nội dung lựa chọn, không phải lệnh, nên không gán được cho font nào — dù ảnh trông rất giống.

**Đã quét cạn tầng dữ liệu TWAU [V] — đừng đi tìm consumer nữa.** Trích và giải mã toàn bộ tầng UI rồi grep tên font:

| tầng | số file đã giải mã | nêu tên `.font` |
|---|---|---|
| script `.lenc` → `.lua` (Menu_data, Boot_data, Menu_anichore) | 106 | **1**: `uiz_ConsoleButtons.lua` |
| `.prop` (Menu_data, Boot_data) | 237 | 0 |
| `.dlog` (Menu_data, Fables101_data, Boot_data) | 24 | 0 |

Kết luận: tiêu đề, tệp lưu, màn cài đặt, thẻ tập phim đều lấy font từ **engine/prefab**, không từ dữ liệu. Một ảnh chụp các màn đó **không** cấp được mức nào vì không có consumer để trích dẫn, và cũng không loại trừ được bằng thiết kế: 8 file sans dùng chung Noto Sans (kể cả `ManlyMen_BB_60`), 2 file slab dùng chung họ RobotoSlab. Trần chứng minh được của TWAU là **2/12**: `Cantoria_MT` (thiết kế serif duy nhất) và `ITC_Kabel_Book` (consumer qua member). 10 file còn lại dừng ở `archive_verified` — và điều đó **không** chặn claim `archive_verified`; gate 12 chỉ bắt buộc nếu muốn claim `runtime_verified`.

**Độ đồng nhất sau P1 [V]:** `cap_spread` 0–1 px trên cả 12 font (bản gốc 0–3), `x_spread` 0–1 px. Đây là chỉ số trực tiếp cho lỗi "chữ cao thấp không đều". Chỉ đo chữ thường `m n r u`: chữ tròn (`a c e o s`) overshoot và `i` có dấu chấm, đưa vào thì thước đo tự báo sai (spread 14–16 px trên font có chữ hoa lệch 1 px).

## 6c. Member `.font` nằm rải ở archive update [V]

Đo trên TWAU đã đóng gói: font **không** nằm hết ở archive base.

```
Fables_pc_Project_all.ttarch2                            11 member .font
Fables_pc_PC-Mac_TTG_Update_02_Episode_02_Project_all    1
Fables_pc_PC-Mac_TTG_Update_03_Episode_03_Project_all    1
Fables_pc_PC-Mac_TTG_Update_03_Episode_04_Project_all    1
Fables_pc_PC-Mac_TTG_Update_03_Episode_05_Project_all    4
   -> CCLegendaryLegerdemain_34, Cantoria_MT, ITC_Kabel_Book, Veteran_Typewriter_40
```

`Veteran_Typewriter_40.font` **chỉ** có ở Episode_05. Ba font kia có tên ở cả base lẫn Episode_05, nên archive nào thắng là do thứ tự nạp, không phải do tên.

Luật rút ra:

- Readback phải quét **cả chuỗi nạp**, không chỉ base. Quét base thôi thì `Veteran` "đạt" mà không hề có member nào để đối chiếu.
- Trích nhiều archive vào **một thư mục chung** rồi đánh index mọi file đang có là sai: archive cuối sẽ được ghi công cho cả 12 file. Phải ghi index theo **danh sách member của từng archive**.
- Kích thước member ở Episode_05 khớp bản đã dựng, tức bản vá phải phủ cả 5 archive. Vá base thôi là còn 4 font chưa vá.

## 7. Quy trình cho một job font Telltale

1. Khóa bảng VN-128 từ encoder LANDb (file + hash).
2. Adapter của dự án xuất inventory từng `.font`: records, UV, metrics, ink sau decode DXT5, identity từ build manifest hoặc native encoding đã đối chiếu.
3. Chạy `custom_encoding_audit.py --adapter-script <parser đã pin> --font-file <đúng .font đó>`. `scripts/adapters/telltale_5vsm.py` hỗ trợ read-only profile TWAU PC `5VSM` với record `TRectNew` 48 byte (`<III4f5f`) và atlas DXT5 rộng 512 px. Adapter parse record/UV/metrics trên mọi layout đã nhận diện; chỉ công bố capability `ink` khi ranh giới texture page được descriptor hoặc layout collapse chứng minh. `6VSM`, descriptor lạ, hoặc profile không được xác minh phải fail closed/`NOT_SUPPORTED`; inventory viết tay chỉ để planning và exit 4.
4. Remap mọi slot FAIL; preserve slot PASS; metrics theo template chữ có dấu gốc cùng font.
5. Re-audit output; semantic diff gốc → mới.
6. Cập nhật injector theo output dir mới (đường dẫn là một field trong manifest), đóng gói.
7. Extract lại từ `.ttarch2` live (ttarchext hoặc tương đương), so SHA-256 với output.
8. Screenshot Pause/Settings, dialog, subtitle trên đúng build; người duyệt kết luận.
9. Chạy `proof_level_check.py --verify-files`. Checker chạy lại adapter một lần cho mỗi font trước khi cấp `structurally_verified`. Report tự khai, hoặc adapter không chạy được, dừng ở `inventory_only`.
