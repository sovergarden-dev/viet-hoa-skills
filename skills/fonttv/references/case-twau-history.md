# Case study: The Wolf Among Us, V3 → V9n (history)

Narrative record of fourteen P2 rounds. Each entry is a defect that survived an
audit, so the list doubles as the reason the rules in `telltale-fonts.md` exist.
Status labels: **[V]** measured in the project, **[O]** observed on TWAU only,
**[MỞ]** open.

Strategy P1 replaced this whole approach for TWAU; see `strategy-p1-replace.md`.
Read this file when a Telltale build misbehaves and you need to know whether the
cause was already diagnosed once.

## Case study: TWAU V3 vs V7

- **Texture page là contract, không phải phỏng đoán.** Với multipage, dùng size/height mirror trong descriptor khi tổng size khớp payload; nếu toàn bộ record đã collapse vào page 0 thì dùng một logical page bao phủ payload. Nếu descriptor và payload mâu thuẫn trong khi record vẫn tham chiếu nhiều page, vẫn có thể audit record/UV/metrics nhưng phải bỏ capability `ink`; cấm chia page theo một kích thước hardcode rồi báo PASS.

### Bối cảnh

LANDb tiếng Việt encode theo VN-128, ví dụ `đ`→178, `Đ`→255, `ệ`→143, `ư`→155, `ạ`→167. Font gốc có record tại các charID này, nhưng glyph ở đó là glyph legacy/Latin/symbol hoặc rỗng, không phải chữ Việt theo VN-128.

### Bằng chứng trên `Rockwell_Std_Condensed_48_bold.font` [V]

| charID (VN-128) | Gốc = V7 | V3 |
|---|---|---|
| 178 (`đ`) | UV zero-width, xAdvance 17 | glyph `đ`, UV có diện tích, xAdvance 32 |
| 143 (`ệ`) | UV zero-width, xAdvance 1 | glyph `ệ`, xAdvance 28 |

Runtime V7: chữ Việt hiện thành `2`, `©`, `¥`, `$`, ký tự rời hoặc mất glyph.

Triệu chứng khớp với việc font gốc được build theo CP1252 [O]: `0xB2` = `²` (trông như `2`), `0xA7` = `§` (trông như `$`), `0xFF` = `ÿ`, `0x8F` không được định nghĩa nên record rỗng. Chữ `ÿ` từng được quy cho lỗi sắp xếp/tra nhị phân; với `Đ`→255, đó cũng chính là glyph CP1252 gốc tại slot này. Kiểm mapping trước khi đổ lỗi cho lookup.

### V7 sai ở đâu

1. Chỉ kiểm "charID đã tồn tại trong font gốc" rồi coi là đủ.
2. Giữ 10 font byte-identical bản gốc trong khi LANDb vẫn encode VN-128.
3. Coi UV zero-width là quy ước bình thường thay vì glyph rỗng.
4. Kết luận từ structural audit; không có semantic tuple, không round-trip.
5. Injector vẫn trỏ thư mục build V3, nên archive live chứa V3 trong khi tưởng là V7. Vì 10/12 font V7 trùng byte bản gốc (chỉ Kabel khác), không thể phát hiện bằng mắt.

Trạng thái: **V7 = REJECTED**. Không tái sử dụng bytes V7.

### V8: sửa lỗi V3 và hai lỗi do chính V8 gây ra

V3 để lại `Ý` (221) rỗng ở 4 font vì tin record tồn tại. V8 thêm tầng sửa slot rỗng, nhưng bản đầu của V8 mắc hai lỗi nặng, cả hai đều lộ ra khi so record gốc với record output theo từng id:

1. **Dựng lại page 1 từ đầu** làm mất nội dung page 1 gốc cho mọi id không nằm trong hợp đồng dựng lại.
2. **Sửa slot theo `page_index`** coi mọi record page 0 là rỗng, nên chuyển 28 glyph tác giả `À Á Â …` sang page 1 dưới dạng glyph donor.

Sửa: giữ pixel page gốc tại chỗ, chỉ pack glyph mới xuống dưới hàng gốc, kiểm ink theo page thật của record, và phát payload = byte gốc verbatim + phần đuôi mã hoá. Kết quả: descriptor cộng khớp payload, 12/12 `mapping_verified`, byte payload gốc verbatim, và tổng kích thước 12 font giảm từ 21.5 MB xuống 7.0 MB.

Bài kiểm bắt buộc cho mọi vòng build lại: so **từng id** giữa font gốc và font output trên ba chiều `page`, `pixel-space UV` (nhân UV với geometry của chính page đó), và `advance`. Sai lệch chỉ được chấp nhận khi slot gốc thật sự rỗng (`u0 == u1` hoặc ink = 0).

### V9: năm lỗi cơ chế mà V8 che giấu [V]

V8 pass `mapping_verified` 12/12 và vẫn hỏng nặng trong game. V9 sửa năm lỗi sau, mỗi lỗi đều im lặng:

1. **Base phải đọc từ đúng page mà record trỏ tới.** Giới hạn base vào page 0 làm mọi base nằm trên page 1 rơi xuống fallback. `ITC_Kabel_Book` có `D E I a e o u y` trên page 1, `Rockwell_Std_48_bold` có `â ê ô` trên page 1. Không được lọc `rec[1] == 0`.
2. **Fallback `ord("A")` cho mọi ký tự ≥ U+0100 là sai.** Nó biến `ạ` thành `Ạ`, `ả` thành `ỷ` (mọi ký tự cùng base chữ hoa trùng nhau). Base thiếu phải được dựng lại đúng chữ hoa/thường từ donor; base thiếu hẳn thì báo lỗi cứng, không thay bằng chữ cái trần.
3. **Canvas render donor phải chứa cả phần dưới dòng.** Canvas 256 với render size 200 cắt mất dấu chấm dưới, `extract_diff` trả `None`, composer `return base_im` và dấu biến mất. Dùng canvas lớn, neo `anchor="ls"` tại baseline.
4. **Cỡ dấu phải suy từ cap height của font đích**, không phải hằng số chọn tay. Tỷ lệ `mark/cap` dao động 0.106–0.30 theo font khi chọn tay.
5. **Base phải do MỘT hàm dựng.** `synthesised_base` dựng `Â` bằng compose còn vòng fill dựng `Â` bằng render donor → hai bitmap khác nhau cho cùng một slot, `base_overlap` 0.03. Hợp nhất về `donor_glyph_scaled()` thì `CCLegendary` base_mismatch 31→6, `ManlyMen` 41→14, `Cantoria` 30→20.

Thước đo đúng là **vùng dấu**, không phải toàn glyph: IoU toàn glyph giữa `Ầ` và `Ẩ` vẫn 0.99 khi một trong hai mất dấu hẳn, vì base chiếm phần lớn ink. Đo `added = ink(slot) & ~ink(base)` với offset base **tìm** chứ không giả định (mode `both_*` đệm trên lẫn dưới). Sau V9: `mark_absent = 0` trên 12/12 font.

Đóng gói archive phải dựng lại từ snapshot **có text bản địa hoá**, không từ `Pack_Backup_Original`. Dựng từ backup gốc chỉ thay `.font` làm toàn bộ text quay về tiếng Anh: `ui_text_english.landb` 0/67 mục có ký tự Việt so với 64/67 ở snapshot V3.

6. **Quy tắc chọn template phải dùng chung.** `synthesised_base` lấy template từ chữ cái ASCII (`E` cho `Ê`), vòng fill rơi xuống `A` → cùng một chữ cái có hai bề rộng cell khác nhau (40 vs 48). Đo được: `Cantoria_MT` tone_indistinct 9→0, base_mismatch 20→2, overlap 0.478→0.743; `ManlyMen` 7→1.
7. **`rec[7]/rec[8]` phải được đặt lại mỗi khi canvas đổi.** Mọi nhánh composer đặt, nhưng `synthesised_base` và hai chỗ fill thì không.

**Đừng đổ lỗi cho codec trước khi đo nó.** Nghi `base_overlap` 0.6–0.8 là do lượng tử hoá DXT5; test round-trip qua `encode_dxt5_blocks` → `dds_to_rgba` cho `coverage = 1.000` trên mọi glyph ở cả 256px lẫn 512px atlas. Codec của pipeline lossless ở ngưỡng `alpha > 0`; overlap thấp là chuyện khác.

Còn lại chưa giải thích được: `Arial_30` nhóm `both_horn_and_above` / `above` overlap 0.65–0.75 dù `new_rec[8]` đặt đúng. Ghi lại làm câu hỏi mở, không đoán.

### V9b: hiện diện không phải vị trí [V]

`mark_absent = 0` vẫn để lại ảnh chạy thật đầy lỗi. Ba thước đo trước chỉ hỏi *có dấu không*; ảnh runtime hỏi *dấu nằm ở đâu*. project-local vn_mark_placement.py (script lịch sử, không đi kèm skill) đo `ink(slot) & ~ink(base)` rồi đối chiếu với neo của từng mode: `above*` phải trên đỉnh ink của thân, `dot_below` phải dưới đáy, `horn` phải qua mép phải, các mode còn lại phải cân trên tâm ink.

Kết quả thô: **525/1272 slot (41.3%)** lệch. `centre_off` 199, `horn_left_of_edge` 132, `dot_overlaps_body` 116, `mark_sinks_into_body` 77.

**Chưa được tin ngay.** `best_offset` chọn offset theo `|slot ∩ base| / |base|` lớn nhất, và khi dấu chiếm phần lớn ink nó có thể khoá nhầm offset — lúc đó `mark_sinks_into_body` là ảo giác của thước đo chứ không phải lỗi font. Phải kiểm chứng `best_offset` bằng ground truth tổng hợp trước khi lấy 525 làm sự thật.

Bốn nguyên nhân nghi ngờ trong composer, chưa sửa:

- `above` / `above_circumflex`: `target_x = mid_x + max(2, rel_x)` — chặn dưới `max(2, ...)` phá mọi `rel_x` âm, đẩy dấu sang phải (khớp `centre_off` dương tới +15.7px ở `ITC_Kabel_Book` `Ỗ`).
- `horn`: `target_x = r - 2` neo vào mép phải ink của thân, không theo tâm dấu móc.
- `dot_below`: `target_y = h + 1` dùng chiều cao *ảnh* thân, không phải đáy *ink* — sai khi ô có nhiều khoảng trắng dưới.
- `pad_top` suy từ chiều cao ảnh dấu, không từ khoảng cách cần thiết tới đỉnh ink của thân.

### V9a: mảnh anti-alias của phép trừ [V]

`extract_diff(base, acc)` bằng `clip(im_acc - im_base)` giữ lại viền anti-alias của thân chữ: `o→ơ` cho bbox 61×100 trong khi dấu móc chỉ ~40 cao — phần còn lại là 1–2 px mỗi hàng dọc mép `o`. Dán mảnh đó cạnh chữ thành vệt dọc cao bằng cả glyph, ở runtime đọc ra như dấu `'` lạ (ảnh `CHƠI'`, `DỰ'LIỆU`).

Sửa: opening 3×3 (`denoise_mark`) trước khi cắt/scale. `o→ơ` 61×100 → 27×60; `D→Đ` 131×68 → 73×16 (đúng thanh ngang).

### V9c: thước đo tự bịa base [V]

Probe viết tay map `{"Ơ":"o", "Ư":"u"}` báo 12 slot “có ink dưới base”, lớn nhất `Cantoria_MT` `Ơ` 136px. Sai: `SPEC 'Ơ': base_cid=79` = chữ **`O`**, `Ư` = **`U`**. Đối chiếu với chữ thường thì mọi slot hoa đều báo lỗi giả.

**Luật:** base id chỉ được lấy từ `EXHAUSTIVE_SPEC`, không bao giờ viết tay trong script đo. Đo lại đúng base: **0/768 slot** (`above` + `above_circumflex` + `horn`) có ink dưới base.

Tác dụng phụ có ích: 768 slot đó đi qua `best_offset` mà không sinh ink thừa, tức `best_offset` khoá đúng offset trên tập này — nâng độ tin của 525 cảnh báo vị trí ở V9b.

### V9d: `max(2, rel_x)` là lỗi neo dấu chính [V]

`above_circumflex` đặt dấu ở `target_x = mid_x + max(2, rel_x)` với `rel_x = d_bb[0] - donor_mid_x`. `rel_x` gần như luôn **âm** (dấu bắt đầu trái tâm thân), nên `max(2, ...)` kéo dấu sang phải đúng `|rel_x| + 2` px. Đo được `centre_off` dương tới +15.7px.

Sửa: `target_x = max(0, min(mid_x + rel_x, res.width - dia_rgba.width))` — giữ nguyên dấu của `rel_x`, chỉ kẹp trong canvas.

Kết quả sau sửa (luật audit đã mode-aware): `misplaced` 274 → **105** trên 1272; `centre_off` 194 → 22.

### V9e: luật audit phải theo mode [V]

Áp một luật “horn” cho cả mode `both_horn_and_*` sinh 132 cảnh báo giả (`horn_left_of_edge`) — dấu thanh trong mode ghép nằm giữa thân, không phải ở mép phải. Tương tự `dot_overlaps_body` 116 cảnh báo giả.

Luật đúng: tách theo mode. `wants_above = mode.startswith("above") or "and_above" in mode or mode == "both_breve_and_dot"`; `wants_below = "dot" in mode`; `wants_right = "horn" in mode`; kiểm **có ink trong vùng** tương ứng, không kiểm tâm của hợp hai dấu. Kiểm tâm chỉ cho `above` / `above_circumflex` thuần.

Kết quả: 525 → 274 (trước khi sửa composer), tức 251 trong số 525 là lỗi của thước đo.

### V9f: base synthesised và base fill phải cùng gốc dán [MỞ]

`mark_sinks_into_body` 77 slot còn lại, toàn bộ ở `above_circumflex`. Đo trên Cantoria: slot `Â` (194) cao 97, ô `Ầ` cao 107, donor `Â` cao 61 — tức ô base có ~36px trống. `synthesised_base` và vòng fill đã dùng chung `base_template` và `donor_glyph_scaled` nhưng **chưa chứng minh dùng chung gốc dán glyph trong canvas**; lệch gốc làm `best_offset` khoảng chịu, sinh sink giả hoặc sink thật. Sửa tiếp ở đây, chưa làm.

Còn lại: `Ổ/ổ` đi nhánh riêng (`target_x = mid_x + max(3, dia_rgba.width // 3)`) vẫn kéo dấu sang phải — cùng lớp lỗi V9d.

### V9g: quy ước `rec[10]` phải đọc từ font, không áp hằng số [V]

Triệu chứng runtime: thân chữ của glyph ghép tụt xuống dưới baseline, chữ cao thấp không đều. `Ơ`/`Ư` (chỉ móc, không pad trên) thì thẳng hàng — khoanh vùng được vào nhánh `above`.

**Ground truth:** chính font gốc đã có cặp `A`→`À` do nhà phát hành dựng. Đo bộ ba `(d_cellh, d_rec8, d_rec10)` của nó, ra ba quy ước:

| nhóm | font | d_cellh | d_rec10 | quy ước |
|---|---|---|---|---|
| I | Arial_30, ITC_Kabel_Book, ITC_Kabel_Medium, Veteran_Typewriter_40, default | +2..+13 | bằng đúng −d_cellh | cell tăng thì `rec[10]` **trừ đi** mức tăng |
| II | Cantoria_MT, ManlyMen_BB_60, CCLegendaryLegerdemain_34 | +48..+73 | 0 | `rec[10]` **giữ nguyên** |
| III | Rockwell_Std_48_bold, Rockwell_Std_Condensed, AvantGarde_LT_Book_14/40 | ≈0 | 0 | ô vốn đã đủ chỗ, không tăng |

Suy hệ số `slope = d_rec10 / d_cellh` từ cặp `A`→`À` và dùng `rec[10] = base_rec[10] + slope * rows_added`. Kiểm chứng: glyph `Â` do composer dựng lặp lại **đúng bộ ba** của `À` nhà phát hành ở **12/12 font**.

Bài học phụ: trước đó đã thử hai hằng số toàn cục (`−pad_top` sẵn có, và `+rows_added` do tôi thêm) — cả hai đều sai vì nhóm II cần 0. Không đoán hệ số; đọc nó ra.

### V9h: `mark_sinks_into_body` là dương tính giả đã chứng minh [V]

Đối chứng: chạy `vn_mark_placement` lên chính glyph nhà phát hành (`A→À`, `A→Á`, `O→Ô`, `E→Ê`) — nó chấm `misplaced` cho **32/48**. Luật “dấu phải nằm trên đỉnh ink của thân” không đúng cho font mà dấu sống trong phần headroom sẵn có của ô. Đã loại luật đó.

**Luật chung:** trước khi tin một luật audit, chạy nó lên glyph do nhà phát hành dựng. Luật nào chấm cả glyph gốc là luật sai.

Sau khi loại: 61/1272 (4.8%) — `centre_off` 38, `no_ink_below_body` 15, `no_mark` 3, `no_ink_above_body` 3, `no_ink_right_of_body` 2.

### V9i: cắt dọc về ink [MỞ]

`tighten_vertical` cắt ảnh ghép về bbox ink và đặt `rec[7]/rec[8]`. Ăn rõ với `Arial_30`, `default`, `ITC_Kabel_Book`, `ITC_Kabel_Medium`, `Veteran_Typewriter_40`: spread `cell_h − ink_bot` về 1 cho **mọi** slot. Nhưng ô nguyên bản của `Rockwell_*`/`AvantGarde_*` vốn đã không khít (spread 35–41), nên khít **không** phải bất biến toàn cục — cần đối chiếu với `cell_h − rec[10]` của chính font đó.

So sánh cùng chuẩn với bản trước: `centre_off` 22→38, xuất hiện `no_ink_below_body` 15. Hai font (`CCLegendary`, `ManlyMen`) làm `vn_mark_placement` chết `ValueError: zero-size array to reduction operation minimum` — lỗi trong chính audit. Chưa giải quyết.

### V9j: ngưỡng audit phải hiệu chuẩn theo chính font [V]

Luật `centre_off` đặt dung sai 3px cứng lại chấm **11/72 glyph nhà phát hành** (Cantoria `Ê` +5.6, `È` +5.7). Glyph ghép của ta là 38/768 = 5%, tức **tốt hơn cả bản gốc** về mặt chỉ số này. Luật sai, không phải font sai.

Sửa: `calibrate_centre_tolerance(cells, records)` đo độ lệch lớn nhất trên 23 cặp nguyên bản `À Á Â È É Ê Ì Í Ò Ó Ô Ù Ú Ý à á â è é ê ì í ò ó ô ù ú ý`, rồi đặt `tol = max(3, worst × 1.25)`. Dung sai kết quả: 3.00 (`Rockwell_48`, `AvantGarde_14`, `default`, `Veteran`) → 7.12 (`Cantoria_MT`).

Kết quả: 61 → **39/1272 (3.1%)**; `Cantoria_MT` về 0.

**Nguyên tắc chung, đã đúng ba lần trong dự án này:** mỗi luật audit chỉ hợp lệ nếu nó KHÔNG chấm glyph do nhà phát hành dựng. Trước khi thêm luật mới, chạy nó lên cặp `A→À` / `o→ô` của font. Luật nào chấm glyph gốc là luật sai.

### V9k: còn lại sau hiệu chuẩn [MỞ]

```
misplaced 39/1272 (3.1%)
  no_ink_below_body    15     lớp MỚI — do tighten_vertical cắt sát, chấm dưới lẫn vào thân
  centre_off           16
  no_mark               3
  no_ink_above_body     3
  no_ink_right_of_body  2
```

`no_ink_below_body` không có đối chứng nhà phát hành (28 slot Latin-1 giữ nguyên chỉ có grave/acute/circumflex, không có chấm dưới), nên chưa chứng minh được nó là lỗi thật hay lỗi thước đo. Phải tìm cách khác trước khi sửa theo nó.

`vn_mark_placement` vẫn chết `ValueError: zero-size array to reduction operation minimum` trên `CCLegendaryLegerdemain_34` và `ManlyMen_BB_60` — vùng ink rỗng khi slot không có ink. Chưa sửa.

### V9l: chọn donor theo HÌNH DẤU, không theo độ phủ [V]

Ảnh runtime: dấu chấm dưới hiện ra như **một ô vuông rời**, không phải chấm tròn (`chuột`, `PHỤ`, `ĐẬT`).

Nguyên nhân: donor suốt dự án là `arialbd.ttf`, và Arial vẽ tittle **vuông**. Đo `fill = ink / (w×h)` của mask dấu:

| donor | `ọ` (w,h,ink,fill) | kết luận |
|---|---|---|
| `arialbd.ttf` | 28×28, 784, **1.000** | vuông đặc |
| `arial.ttf` | 21×19, 399, **1.000** | vuông đặc |
| `tahoma.ttf` | 21×19, 399, **1.000** | vuông đặc |
| `verdana.ttf` | 21×19, 399, **1.000** | vuông đặc |
| `segoeui.ttf` | 20×19, 309, **0.813** | tròn |
| `seguisb.ttf` | 25×22, 440, **0.800** | tròn |
| `calibri.ttf` | 20×19, 338, **0.889** | tròn |
| `times.ttf` | 23×22, 402, **0.794** | tròn |
| `georgia.ttf`, `trebuc.ttf` | 150×150 | `.notdef` — thiếu glyph |

`fill ≈ π/4 = 0.785` là hình tròn; `1.000` là chữ nhật đặc. Đã đổi `DONOR_TTF` sang `segoeui.ttf`.

**Luật:** chọn donor bằng hai phép đo, không bằng cảm giác — (1) phủ đủ repertoire, (2) **hình dạng dấu** qua `fill` của mask sau phép trừ. Độ phủ đủ không nói gì về hình dạng, và hình dạng sai vẫn nhìn ra được ở runtime.

### V9m: khe hở dấu bằng đệm ô của base [V]

Ảnh runtime: dấu mũ và dấu chấm "rời", có khe hở; khe hở to ở font ô rộng, không có ở font ô khít.

Nguyên nhân, suy ra từ số học của nhánh `above`:

```
pad_top = dia_rgba.height + 2
res.paste(base_im, (0, pad_top))
target_y = 1
khe hở = (pad_top + t) - (1 + dia_rgba.height) = t + 1
```

`t` là hàng ink trên của base **trong ô của nó**. Vậy khe hở **bằng đúng phần đệm trong suốt trên ô của base** — một đại lượng của container, không phải của typography. `Cantoria_MT` (`Â` ô 97 / ink 61 → `t` ≈ 18) hở 19px; `Arial_30` (`t` ≈ 1) hở 2px. Đúng như ảnh: font ô rộng hở to.

Sửa: tính khe hở từ **ink** hai bên, không từ chiều cao ảnh:

```python
d_ink = dia_rgba.split()[-1].getbbox()
gap   = max(1, (b - t) // 12)          # b, t = ink bottom/top của base
target_y = 1 - d_ink[1]                 # ink dấu bắt đầu ở hàng 1
pad_top  = max(0, target_y + d_ink[3] + gap - t)
if pad_top == 0:                        # base đã có sẵn headroom (nhóm III)
    target_y = max(0, t - gap - d_ink[3])
```

Đã áp cho 3 chỗ: `dot_below` (`target_y = b + gap - dot_ink[1]`), nhánh headroom nội tại, và nhánh pad. **Quy tắc: mọi khoảng cách giữa hai phần ink phải suy từ ink của cả hai, không bao giờ từ chiều cao ảnh/ô.**

### V9n: thước đo không ổn định dưới thay đổi dọc [MỞ]

Sau khi sửa khe hở (một thay đổi **dọc**), `vn_mark_placement` nhảy 39 → 129/1060 (12.17%), trong đó `centre_off` 16 → **78** — một chỉ số **ngang**. Thay đổi dọc không được phép làm chỉ số ngang đổi. Nguyên nhân: `tighten_vertical` cắt canvas khác đi, `best_offset` dời điểm canh, sai số ngang đổi theo.

Kết luận: **thước đo hiện tại không dùng được để phê duyệt thay đổi dọc.** Nó đã cho 3 lớp dương tính giả đã chứng minh (`mark_sinks_into_body` 32/48 glyph gốc, `centre_off` 11/72 glyph gốc, `dot_overlaps_body` 116) và giờ mất ổn định. Phải canh base theo **neo gốc ô** (như `BASE_ALIGN` của `vn_mark_presence.py`) thay vì `best_offset` IoU trước khi tin bất kỳ con số nào của nó.

### V3 đúng và sai ở đâu

- Đúng: remap semantic byte → glyph theo VN-128 cho mọi font, nên chữ đọc được.
- Sai: dựng lại cả 106 ký tự trong mọi font, kể cả glyph gốc có thể đã đúng, và guard `t >= accent_h + 6` hỏng với headroom 7–10 px (dấu 7 px) nên mọi dấu rơi vào nhánh pad_top → dấu bay, lệch baseline trên menu. Đây là lỗi metrics, không phải lý do bỏ remap.

Trạng thái: V3 remap đúng hướng, metrics chưa đạt, chưa qua runtime gate.

### Phần còn giá trị từ V7

Lo ngại "đừng dựng lại glyph gốc đã tốt" đúng với slot có tuple PASS (ví dụ nếu đo được chữ có dấu mà encoding gốc của font và VN-128 cùng nghĩa). Nó sai khi áp cho mọi charID tồn tại.
