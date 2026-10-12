# Strategy P1: thay trọn glyph từ font Việt bên ngoài

Mục tiêu: chữ Việt **hiển thị đúng và đọc tốt**. Style của font game là thứ yếu. Đây là strategy mặc định.

P1 không ghép dấu. Mọi glyph (ASCII lẫn Việt) được render từ một font nguồn đã có sẵn tiếng Việt do người thiết kế vẽ. Dấu, vị trí dấu, dấu chồng và khoảng hở do font nguồn quyết định, nên không cần thước đo vị trí dấu.

## 1. Khi nào chọn P1

- Font dùng cho hội thoại, phụ đề, menu, UI: nhiều chữ, phải đọc nhanh.
- Font game không có glyph Việt, hoặc P2 đã tốn nhiều vòng QA mà vẫn lỗi.
- Người dùng chấp nhận style gần giống thay vì đúng style.

Không chọn P1 khi người dùng yêu cầu rõ giữ style (logo, tiêu đề chương), và chấp nhận vòng QA dài. Khi đó dùng P2 (`strategy-p2-compose.md`).

## 2. Thay cả bảng chữ, không chỉ chữ Việt

Thay **mọi glyph mà encoder có thể phát ra** trong font đó: `a–z A–Z 0–9`, dấu câu, và toàn bộ repertoire Việt.

Chỉ thay chữ Việt mà giữ Latin gốc sẽ tạo lại đúng lỗi P2: hai nguồn glyph có cap height, x-height, weight và baseline khác nhau, nên chữ cao thấp không đều trong cùng một từ (`CHƠI` = `C H I` gốc + `Ơ` mới).

Ngoại lệ: ký hiệu đặc biệt (icon nút bấm, ký hiệu tiền, glyph trang trí) mà font nguồn không có. Giữ glyph gốc cho các slot đó và liệt kê trong manifest (`preserved_ids`).

## 3. Chọn font nguồn

Ba cổng, theo thứ tự. Trượt cổng nào thì loại font đó.

1. **Rights.** Ưu tiên OFL/Apache: `Be Vietnam Pro`, `Noto Sans`, `Noto Serif`, `Roboto`, `Roboto Slab`, `Roboto Mono`, `Source Sans 3`, `Source Serif 4`, `Lora`, `Merriweather`. Font hệ điều hành (Arial, Segoe UI, Tahoma, Calibri, Times New Roman) là độc quyền: được dùng để thử trên máy mình, **không được đóng gói vào bản patch phát hành**. Ghi license + file LICENSE + SHA-256 vào manifest (`source_font`). Reserved Font Name của OFL: không đặt lại tên font thành tên gốc.
2. **Coverage.** `scripts/fonttv_audit.py FONT --corpus <repertoire>` phải PASS cho toàn repertoire precomposed. Ký tự trắng (`\n`, space) bị bỏ khỏi phép đếm.
3. **Hình dấu.** Render `ọ` và `o`, trừ ảnh, đo `fill = ink / (w × h)` của mask dấu chấm dưới. `fill ≈ 0.79` là tròn; `1.000` là vuông đặc. Arial, Tahoma, Verdana vẽ tittle vuông (đã đo, xem `telltale-fonts.md` V9l). Nhìn vuông ở runtime là lỗi người dùng thấy được, không phải khác biệt style.

Rồi chọn style gần nhất:

| Font game | Họ | Nguồn gợi ý |
|---|---|---|
| serif chữ đọc (Cantoria, Times-like) | serif | Noto Serif, Source Serif 4, Lora |
| slab (Rockwell) | slab serif | Roboto Slab |
| geometric sans (AvantGarde, Kabel) | geometric sans | Be Vietnam Pro, Noto Sans |
| humanist/grotesk sans (Arial-like) | sans | Noto Sans, Roboto, Source Sans 3 |
| typewriter | mono | Roboto Mono, Noto Sans Mono |
| display/trang trí (ManlyMen, Legerdemain) | display | chọn font display có Việt; không có thì dùng sans đậm, ghi chú style lệch |

Weight: khớp weight chữ gốc (Bold với Bold). Đo bằng tỷ lệ `ink / (cap_h × advance)` của `H` gốc và `H` nguồn đã scale; lệch quá 20% thì đổi weight.

## 4. Scale và metrics

Metrics phải bám **font game**, không bám font nguồn, để UI không tràn khung.

- **Cỡ render:** chọn px size sao cho cap height ink của `H` nguồn bằng cap height ink của `H` gốc (đo trên atlas gốc sau decode). Kiểm thêm x-height `x`; nếu lệch > 10% thì báo, không tự bóp méo.
- **Advance:** lấy từ font nguồn ở cỡ đã scale. So tổng advance của một câu mẫu tiếng Anh giữa gốc và nguồn; lệch > 8% nghĩa là chuỗi dài có thể tràn khung. Chỉnh bằng letter-spacing đồng đều hoặc đổi font hẹp hơn (Condensed), không scale ngang.
- **Baseline:** mọi glyph render trên **cùng một baseline** trong canvas (neo `anchor="ls"`), rồi cắt ô theo **đúng quy ước ô của font game**. Quy ước ô đọc từ record gốc, không đoán:
  - Telltale: đo trên record gốc `H`, `x`, `A`→`À` của chính font (xem `telltale-fonts.md` V9g, V9i). Có font ô khít theo ink, có font ô cố định có headroom. Ô mới phải theo cùng quy ước, và vị trí baseline trong ô phải khớp giữa mọi glyph.
  - TMP/BMFont: dùng `ascent`, `lineHeight`, `yOffset` theo công thức engine.
- **Không có kerning** nếu engine không đọc kerning. Không cố nhét kerning vào record.

## 5. Build

- Render từng glyph từ font nguồn ở cỡ đã chọn, anti-alias, canvas đủ lớn cho cả phần dưới dòng.
- Với route C, được phép **dựng lại toàn bộ page** khi mọi record encoder phát ra đều được render lại và mọi record còn lại (`preserved_ids`) được copy pixel nguyên vẹn sang page mới. Đây là ngoại lệ có điều kiện của luật "không dựng lại page" ở P2. Vẫn giữ bất biến format: thứ tự và tính duy nhất ID, texture format, block alignment, descriptor cộng khớp payload.
- Pack xong phải đếm: số glyph đã đặt = số glyph dự kiến.

## 6. Kiểm chứng

P1 kiểm bằng **identity theo cấu tạo**, không bằng heuristic đặt dấu.

1. **Identity pixel:** mỗi slot giải mã từ atlas output phải khớp ảnh render trực tiếp của đúng ký tự từ font nguồn ở cùng cỡ. Đây là semantic tuple của P1: `(ký tự, byte, glyph mong đợi = render nguồn, glyph thực = atlas)`. Luật đúng khi atlas nén DXT5 (8 mức alpha mỗi block 4×4): **không có ink mới** ở chỗ nguồn trống, **không mất pixel đậm** (alpha ≥ 32), và sai số alpha tối đa ≤ 19. Không dùng IoU nhị phân `> 0`: viền alpha < 18 bị làm tròn về 0 là hợp lệ, IoU sẽ báo sai ở glyph nhỏ (TWAU `default` `-` chỉ đạt 0.67 dù đúng glyph).
   - Crop UV phải dùng `round(u * w)`, không `int()`: UV là float32, `516/th` đọc ngược ra `515.9999`, `int()` mất một hàng và lệch shape (TWAU: 131 glyph báo sai giả).
2. **Baseline đồng nhất:** với mọi slot, `baseline_in_cell` (vị trí baseline suy từ record) sai lệch ≤ 1 px so với `H`. Đây là phép đo trực tiếp cho lỗi "chữ cao thấp không đều".
3. **Cap/x-height đồng nhất:** ink top của mọi chữ hoa không dấu cùng hàng ±1 px; tương tự x-height chữ thường.
4. **Không có luật vị trí dấu.** Dấu là của font nguồn; nếu nghi dấu sai, kiểm font nguồn bằng `shaping_audit.py`/render, không viết luật ad-hoc.
5. `custom_encoding_audit.py` với adapter đã pin, như mọi route B/C.
6. **Runtime:** một ảnh coverage page cho mỗi font (`runtime-coverage-page.md`). Người dùng không phải soi từng từ trong lúc chơi.

## 7. Case study: TWAU P1 — ACCEPTED [V]

Sau 14 vòng P2 (V3–V9n) vẫn lỗi dấu và chữ cao thấp, chuyển 12 font sang P1 trong **một vòng build**. Người dùng test runtime và chấp nhận: "bản hiện tại đã hoàn hảo".

| font game | nguồn |
|---|---|
| Arial_30, AvantGarde_*, ITC_Kabel_*, ManlyMen_BB_60 (chỉ hoa) | Noto Sans Regular |
| default, CCLegendaryLegerdemain_34 | Noto Sans Bold |
| Cantoria_MT | Noto Serif Regular (OFL) |
| Rockwell_Std_48_bold, Rockwell_Std_Condensed_48_bold | Roboto Slab Bold (**Apache-2.0**, không phải OFL; nằm ở `google/fonts/apache/`) |
| Veteran_Typewriter_40 | Cascadia Mono (UbuntuMono bị loại: thiếu 88 ký tự) |

Mỗi font thay 222 glyph (ASCII + 32 CP1252 + 102 VN-128), pack dưới hàng gốc của page cuối, byte page gốc verbatim. Kết quả: identity 12/12, baseline lệch ≤ 1 px (≤ bản gốc), `mapping_verified` 12/12, archive 5/5 (text Việt 343 mục giữ nguyên), inject nguyên tử `sha_match` 5/5.

Bài học: khi P2 cần nhiều hơn hai vòng runtime, chuyển P1 sớm. Chi phí P1 là một vòng; chi phí P2 tăng theo số tổ hợp base × dấu × font.

## 8. Công cụ P1

| Script | Việc | Không chứng minh |
|---|---|---|
| `scripts/p1_source_select.py FONT… [--license FONT=SPDX:PATH]` | ba cổng chọn font nguồn: coverage 134+ASCII, glyph có nét, hình chấm dưới so với **chấm câu của chính font**, license file. Đọc đúng argv, không dùng danh sách cứng | font đúng style, runtime |
| `scripts/p1_core.py` | hàm dùng chung: `render` neo `anchor="ls"`, `size_for_cap`, DXT5 encode/decode, `identity_dxt5`, `uv_box` (làm tròn), `vn_repertoire` (suy ra, không hard-code) | container, engine |
| `scripts/p1_telltale_build.py` | dựng toàn bộ glyph cho Telltale `.font`, đọc quy ước ô từ font game, pack dưới hàng gốc page cuối | engine khác |
| `scripts/p1_width_audit.py --font F --source-font G --mapping M --pairs P` | so bề rộng pixel chuỗi nguồn (đo bằng font gốc) với chuỗi đích (đo bằng font mới) | **không chứng minh tràn khung**: thiếu bề rộng hộp UI và luật wrap |
| `scripts/coverage_page.py --font F --mapping M [--max-width px]` | sinh dòng phủ repertoire để chụp một ảnh mỗi font | tự nó không chèn vào game |

### Đo bề rộng chỉ để phân loại

Trên TWAU: 57.932 cặp câu, tỉ lệ `vi/en` trung vị **1.11–1.25**, p90 1.48–1.66 tuỳ font. Đuôi cao (ratio > 3) hầu hết là câu tiếng Anh rất ngắn được dịch đầy đủ (`I` → `Tao`, `No…` → `Không đời nào...`), không phải lỗi. Muốn kết luận tràn khung phải có bề rộng hộp thật; nếu chưa có, chỉ xếp hạng để người xem soi.

Hai lỗi đo đã gặp, cả hai cho số rác: giải mã text VN-128 bằng `latin1` (379.709 ký tự "không có record") và không đưa câu qua `encode_vn` nên đếm cả `… — ©` là glyph không bao giờ tới font.

## 9. Recipe P1 cho engine khác

Nguyên tắc chung: thay cả bảng chữ, scale theo cap height, một baseline, rồi dựng lại representation mà engine thực sự đọc.

- **Unity TMP**: nếu FontAsset là **Dynamic** thì thay TTF nguồn là đủ. Nếu **Static**, dùng `tmpro_audit.py` + `tmpro_atlas_audit.py` xem characterTable và atlas rồi regenerate từ TTF mới. Phải kiểm cả fallback table: khi font chính là Static SDF chỉ có ASCII và fallback mặc định (`LiberationSans SDF - Fallback`) chỉ có Latin-1 cơ bản, chữ không dấu lấy từ font chính (nét dày) còn chữ có dấu Latin-1 nhảy sang fallback (nét mảnh) gây hiện tượng **"chỗ đậm chỗ nhạt"**, trong khi ký tự Việt mở rộng (`đ, ẹ, ơ, ư, ẵ, ặ, ậ...`) biến thành **ô vuông `□`**. Nếu áp dụng runtime plugin: (1) Tạo `TMP_FontAsset.CreateFontAsset(baseFont)` động (`AtlasPopulationMode.Dynamic`) từ TrueType đầy đủ bảng mã Việt (ví dụ `Arial` 775 KB có sẵn vector trong `resources.assets` hoặc font OFL); (2) Chèn vào `Index 0` của `TMP_Settings.fallbackFontAssets` và của mọi `fa.fallbackFontAssetTable` trong bộ nhớ để triệt tiêu ô vuông toàn cục; (3) **Gán trực tiếp `tmp.font = vietnameseTMPFont`** trên các `TextMeshProUGUI` hiển thị mô tả (`Description`), chú giải (`Tooltip`), hội thoại (`Dialogue`) hoặc chứa ký tự tiếng Việt có dấu để toàn bộ câu render từ cùng một font duy nhất, xóa bỏ hoàn toàn hiện tượng chỗ đậm chỗ nhạt.
- **Unreal**: thay `.ufont`/Font Face; nếu dùng CompositeFont phải kiểm `TypefaceEntry` và thứ tự fallback. Pak/IoStore quyết định file nào thắng, nên sau khi cook phải **đọc lại từ container** như gate 11.
- **GameMaker**: font sinh texture page lúc build, sửa TTF vô nghĩa cho tới khi regenerate page. Kiểm ngưỡng antialias và giới hạn kích thước page; chữ nhỏ dễ mất dấu chồng.
- **BMFont/MSDF**: atlas + metrics nằm ngoài TTF; P1 phải dựng lại cả hai và giữ đúng mã khoá glyph mà text phát ra.
- **Telltale**: `p1_telltale_build.py` (route C + B).

Với mọi engine: kiểm baseline đồng nhất và identity pixel trên **artefact engine đọc**, không phải trên TTF đã render.

## 10. Chi phí texture, đo được

Thay trọn glyph làm atlas lớn lên, và không có kiểm tra nào khác thấy việc đó: descriptor vẫn khớp, audit vẫn PASS, game vẫn load.

TWAU, 12 font, 222 glyph mỗi font:

```
tổng font        8.17 MB sau khi dựng, 8.03 triệu pixel
tăng theo font   1.39x (Arial_30) … 3.12x (Cantoria_MT)
page cao nhất    1956 px (AvantGarde_LT_Book_40), 1852 (ITC_Kabel_Book)
archive Project  1.32 MB bản gốc tiếng Anh -> 17.54 MB sau P1   (13.3x)
               so với baseline V3 17.69 MB -> 17.54 MB         (0.99x)
```

Hai điều rút ra: (1) so với bản gốc Steam thì đắt, so với baseline đã chấp nhận thì **rẻ hơn một chút** — phải nói rõ đang so với cái nào; (2) page vẫn dưới ngưỡng 2048 px, nhưng `AvantGarde_LT_Book_40` chỉ còn 5% dư địa.

## 11. Rủi ro đã biết

- Chuỗi dài tràn khung khi font nguồn rộng hơn. Đo bằng tổng advance (§4).
- Chữ nhỏ (cỡ ô ≤ 16 px): dấu chồng khó phân biệt ở bất kỳ font nào. Chọn font có x-height lớn và dấu gọn (Be Vietnam Pro, Noto Sans), kiểm ảnh zoom.
- Font nguồn thiếu ký hiệu riêng của game → `preserved_ids`, không thay bằng glyph gần giống.
