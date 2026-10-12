# Strategy P2: sửa font game để hỗ trợ tiếng Việt, giữ style

Mục tiêu: giữ style của font game. Giữ chữ gốc, thêm dấu Việt lên chữ gốc. Chi phí QA cao hơn P1 nhiều: mỗi tổ hợp base × dấu × font có thể sai riêng, và nhiều lỗi chỉ lộ ra ở runtime.

Chỉ chọn P2 khi người dùng yêu cầu rõ giữ style (tiêu đề, logo, font ít chữ) và chấp nhận vòng QA dài. Mặc định dùng P1 (`strategy-p1-replace.md`).

Case study đầy đủ: `telltale-fonts.md` §6 (TWAU V3 → V9n). File này gom thành luật. Áp dụng cụ thể lên Unity legacy `Font` + Adventure Creator: `unity-adventure-creator-monofont-vietnamese-compose.md`.

## 1. Nguồn dấu

Theo thứ tự ở `architecture.md` §8: glyph native của font → trích từ composite cùng font → donor. Donor là lựa chọn cuối.

Kiểm `glyf[name].isComposite()` trên chính glyph có dấu của font trước khi quyết định. Nếu `á` là `a` + `acute` ở một offset, font **đã tự công bố** hình dấu và quy ước đặt dấu của nó, và P2 trở nên rẻ và trung thành:

- `acute grave tilde circumflex breve dotaccent macron caron ring dieresis comma` có mặt dưới dạng glyph rời, và `collect_offsets()` lấy lại đúng `(base, mark) -> (dx, dy)` mà hoạ sĩ đã dùng cho `á à ã â ă å ä ā`.
- Vì offset đó là của hoạ sĩ, một người duyệt nói "dấu cao quá" đang chê chính font đã phát hành, không phải bản dựng của ta. **Không được dịch chúng.**

Chỉ dấu thật sự vắng mới cần donor. Với Boopee đó là **hook above, horn** (và `breve` trên BradBunR). Chấm dưới thì không: dùng lại chính `dotaccent` của font làm `vn_dotbelow` để chấm có đúng độ dày và hình dạng.

### 1.1 Dấu do CHÍNH font vẽ phải đặt ở tỉ lệ 1.0 (C12)

Triệu chứng: hai chữ cùng mang một dấu mà dấu khác cỡ — `Ã` của font có tilde mập, `Ẽ` dựng ra có tilde mảnh, và cả hai nằm trong cùng một từ.

Nguyên nhân: scale cho mọi dấu là `target_h * (donor_ratio_for_this_base / donor_median)`. Công thức đó tồn tại để dấu HOA lớn hơn theo tỉ lệ — đúng cho dấu **nhập từ donor** — nhưng nó cũng áp lên dấu mà glyph là **của chính font**, và tỉ lệ theo từng chữ của donor không liên quan gì tới thiết kế của host. Tilde của Boopee ra **47%** cỡ tilde của chính Boopee (native 132 đơn vị, đặt 62).

```python
if not mg.startswith("vn_"):   # glyph của chính host -> nó LÀ đặc tả
    scale = 1.0
else:
    scale = (target_h * (r["mark_h_over_base_h"] / donor_ratio)) / mh_ink
```

Đo trước khi tin bất cứ bên nào: Boopee dùng **một** cỡ cho mỗi họ dấu bất kể hoa/thường (grave 148 trên cả `À` và `à`, acute 152, tilde 132) và chúng bằng đúng glyph dấu rời — nên "cỡ dấu của host" là xác định và không phụ thuộc hoa/thường. Kiểm trên font mới chứ đừng giả định.

Kiểm bằng pixel, không bằng ý kiến: residue `Ẽ` trừ `E` phải khớp `Ã` trừ `A` về mực VÀ hộp (sau khi sửa: 750 px / 228x136 so với native 751 px / 228x132, IoU 0.87).

### 1.2 Dấu donor co cho vừa luôn mỏng hơn dấu của host

Đo cả hai trước khi tin một hệ số scale. Dấu của Boopee: acute 83, grave 74, circumflex 74, breve 64, tilde 54 (đơn vị độ dày nét). Móc của Yomogi dày 55 ở upem 1000 — co về cỡ hợp lý còn ~22–35, tức **một nửa** dấu mỏng nhất của host. Đó đúng là thứ bị đọc thành "khác font".

Scale không sửa được, vì scale đổi cỡ và độ dày cùng lúc. Vẽ dấu thành **nét đều**: lấy mẫu một chuỗi cubic, offset ±w/2 theo pháp tuyến, thêm round cap, phát ra một contour đơn. Khi đó cỡ và độ dày là hai đầu vào độc lập:

- `stroke_w  = 0.92 * median(độ dày dấu của chính font)` đo bằng cách raster `´ ` ` ~ ˆ ˘ ˙` ở 640 px rồi erode tới khi mask rỗng (thickness ≈ 2·iterations).
- `hook_ink = (0.95 * bề rộng tilde của chính font) × (0.95 * chiều cao dấu median của chính font)`
- `horn_ink_h = 0.38 * x_height`, `horn_w = 0.85 * horn_ink_h`, nét móc ≈ `0.85 * stroke_w`

Khai báo cỡ theo INK và trừ nét ra: offset `±w/2` của outline cộng đúng `w` vào cả hai chiều bbox, nên `box = ink - stroke`, không thì mọi dấu đều to hơn một nét.

## 2. Dựng base: làm phẳng, không lồng

Vẽ mọi glyph mới thành outline **đơn**: tạo một `TTGlyphPen(font.getGlyphSet())` và vẽ base + từng dấu qua một `TransformPen` mỗi dấu. Truyền `None` làm glyph set sẽ ném `TypeError: argument of type 'NoneType' is not iterable` ngay khi vẽ một base tổ hợp (như `acircumflex`). Composite lồng nhau cũng là rủi ro vô ích cho rasteriser của engine.

- Base đọc từ **đúng page** mà record trỏ tới.
- Base thiếu: dựng lại đúng hoa/thường; thiếu hẳn thì lỗi cứng. Cấm fallback chữ cái trần.
- **Một hàm dựng base, một quy tắc chọn template** dùng chung cho mọi nhánh.
- 28 slot Latin-1 có glyph tác giả thì giữ nguyên.

### 2.1 Không đánh tay bộ ký tự — sinh từ Unicode

Triệu chứng: MỘT ký tự hiện ra bằng mặt chữ khác hẳn các chữ cạnh nó.
Nguyên nhân: nó chưa từng được dựng, nên fallback theo từng ký tự của engine phục vụ nó bằng mặt chữ khác.

Một chuỗi repertoire tiếng Việt đánh tay đã bỏ sót `ở`/`Ở`. Hai chữ đó vì thế vắng mặt trong kế hoạch dựng, và `ở` trong câu ra bằng mặt chữ dự phòng trong khi mọi chữ khác ra từ host. Không gì trong bản dựng hay con số phủ phát hiện được, vì cả hai đều suy từ cùng một danh sách sai.

Sinh nó ra, và để định nghĩa base + dấu tổ hợp quyết định thành viên:

```python
bases = set("aăâeêioôơuưyAĂÂEÊIOÔƠUƯYđĐ")
marks = {0x0300, 0x0301, 0x0303, 0x0302, 0x0306, 0x0309, 0x031B, 0x0323}
for cp in 0x00C0..0x017F + 0x01A0..0x01B0 + 0x1EA0..0x1EF9:
    ch = chr(cp)
    if ch in bases: keep(ch)
    elif nfd(ch)[0] in bases and all(ord(c) in marks for c in nfd(ch)[1:]): keep(ch)
```

Đối chiếu danh sách sinh ra với ký tự mà corpus thực sự dùng. **Hai nguồn độc lập đồng ý với nhau mới là điểm tựa.**

### 2.2 Một font có thể map một mã điểm sang glyph RỖNG

Boopee map `ỳ`/`Ỳ` sang `ygrave`/`Ygrave`, mỗi glyph **zero contour**. Chúng hiện ra thành khoảng trắng — chữ `kỳ` ra thành `k     lạ`.

Chỉ dựng những mã điểm VẮNG khỏi cmap sẽ để nguyên mọi lỗ như vậy, vì font tự nhận là có hỗ trợ. Kiểm **có mực**, không kiểm **có mặt**:

```python
if cmap.get(ord(ch)) is not None and glyf[cmap[ord(ch)]].numberOfContours != 0:
    skip(ch)          # genuinely native
else:
    compose(ch)       # absent, or present but empty
```

Và audit phải quét **toàn bộ repertoire** tìm contour, không chỉ các glyph builder sinh ra. Vòng kiểm trên `report['added']` không thể thấy một lỗ nó chưa từng lấp.

### 2.3 Bẫy fontTools tốn thời gian thật

* `glyf.__setitem__` **đã tự thêm** tên mới vào `glyf.glyphOrder`. Tự thêm lần nữa tạo tên trùng, `len(glyphOrder) != len(glyphs)`, và `AssertionError` bên trong `maxp.compile` lúc save. Chỉ thêm nếu vắng, rồi gán `font.glyphOrder = glyf.glyphOrder` để `font.getGlyphOrder()` thấy tên mới.
* Glyph mới chưa có bbox cho tới khi `glyph.recalcBounds(glyf)`; đọc `g.xMin` trước đó ném `AttributeError`.
* Bỏ qua subtable cmap có `format < 4` khi thêm mã điểm — format 0 assert với bất kỳ giá trị nào trên 0xFF (`set(cmap.keys()).issubset(range(256))`).
* Một bảng recipe key theo **chữ cái BASE** sẽ tự ghi đè chính nó (`_r('A','A',[DOT])` rồi `_r('A','A',[hook])` chỉ còn hook). Key recipe theo **ký tự đích tiếng Việt**, không bao giờ theo base.

## 3. Thứ tự dựng

Thứ tự quan trọng khi một base chính nó đang được dựng (`ấ` cần `â`). Sắp mục tiêu theo mã điểm và phân giải `built.get(base) or cmap.get(base)`; gieo sẵn recipe cho các base mang dấu (`â ê ô ă đ`) để font nào thiếu chúng thì chúng được dựng trước tập thanh điệu của mình.

## 4. Đọc bố cục từ donor, không viết tay

Một bảng `target -> (base, [marks])` đánh tay là nguồn của **mọi** lỗi trong dự án này. Donor có sẵn tiếng Việt đã mã hoá đúng bảng đó, không sai, trong các composite glyph của nó:

```
ohorn = o   @ (0,0)   + uni031B @ (106,-222)
acircumflex_hook = a @ (0,0) + circumflex @ (-7,-52) + hookabovecomb @ (-169,-238)
```

Đó cho base, danh sách dấu VÀ vị trí chính xác. Thu hoạch:

- `base = donor.char_of(parts[0][0])` — thành phần base là phần tử đầu.
- tên thành phần dấu -> mã điểm -> họ dấu; lưu ý composite HOA của donor dùng `gravecomb.case`, `hookabovecomb.case`, … **không có entry trong cmap**. Bỏ hậu tố `.case` rồi tra tên gốc, không thì mọi dấu HOA phân giải thành `None` và lặng lẽ rơi về fallback.
- nhiều dạng HOA được phát hành dưới dạng outline PHẲNG, không phải composite. Suy kế hoạch của chúng từ Unicode: `unicodedata.normalize('NFD', ch)` cho base + dấu tổ hợp. `Đ/đ` không có dạng NFD — xếp riêng chúng lên thanh ngang.

### 4.1 Key quan hệ theo TOÀN BỘ chuỗi dấu, không theo (base, mark)

Đây là lỗi đã tạo ra một bản dựng hỏng nhìn thấy được. Hook trên `a` trần nằm ở `dy_top = 0.069`; cũng hook đó xếp trên circumflex của `ẩ` cần offset hoàn toàn khác. Với `rel.setdefault((base_ch, mark), …)` thì chữ nào gặp trước sẽ thắng, mọi dạng xếp chồng dùng lại vị trí phẳng, và hook đáp xuống trên đầu circumflex ở mọi `ẩ ể ổ ẳ ữ ự`.

Key thành `rel[(base_ch, tuple(marks))][mark]`, và thêm fallback cùng độ dài để base HOA mượn được quan hệ của bản thường.

Chuẩn hoá mọi quan hệ bằng hộp ink của base (`dx_center`, `dx_right`, `dy_top`, `dy_below`, `mark_h_over_base_h`, `mark_w_over_base_w`). Toạ độ thô của donor vô dụng trên host có chữ với tỉ lệ khác.

### 4.2 Chuẩn hoá theo nguyên âm trần khi base mang sừng

Triệu chứng: cùng một dấu thanh trông nhỏ hơn và nằm cao hơn trên `ở` so với trên `ỏ`.

Nguyên nhân: `ở` của donor được composite trên `ohorn`, nên quan hệ chuẩn hoá theo hộp của base đó đã đo trên một cái hộp đã chứa sừng — hộp cao hơn và nặng phần trên. Hook vì thế nhận phần nhỏ hơn của hộp và bị đặt so với đỉnh sừng.

Bỏ sừng trước khi chuẩn hoá, ở **cả hai phía**:

```python
def base_body(ch):
    d = nfd(ch)
    return d[0] if len(d) == 2 and ord(d[1]) == 0x031B else ch   # o/u + horn only
```

**Không** bỏ circumflex/breve: tilde của `ẫ` thật sự xếp trên circumflex, và quan hệ của nó đo theo hộp đầy đủ của `â`. Bỏ hết cũng sai như không bỏ gì.

Kiểm chứng: `ở` và `ỏ` phải đặt hook ở cùng khe hở và cùng cỡ mực, và `ơ` với `ở` phải đặt sừng ở vị trí và cỡ y hệt. **So các con số trong build report** thay vì nhìn pixel.

## 5. Đặt dấu

- **Mọi khoảng cách giữa hai phần ink suy từ ink của cả hai**, không từ chiều cao ảnh hoặc ô. Suy từ ô làm khe hở bằng đúng đệm ô (V9m).
- Neo ngang giữ nguyên dấu của độ lệch donor (`rel_x`), chỉ kẹp trong canvas. Không có hằng số chặn dưới kiểu `max(2, rel_x)` (V9d).
- Mode ghép (`both_*`) có hai dấu, neo riêng từng dấu.
- `Ổ/ổ`, `Ơ/Ư` có nhánh riêng; kiểm riêng.

### 5.1 Móc: neo vào GÓC TRÊN-PHẢI, không bao giờ vào tâm chữ

Đặt móc ở `x = xMin + r*bw`, `y = yMax + h*bh` (r≈0.68, h≈-0.20) đặt cả thân nó **BÊN TRONG** bbox của chữ — nó nằm trên thân phải và biến mất. Chữ sau đó đọc ra thành `u`/`o` trần ở mọi cỡ. Neo vào góc:

```python
sc = horn_ink_h / mark_h
parts.append((HORN,
              (bx1 + 0.02 * bw) - mb[2] * sc,   # mép phải = mép phải của chữ
              (by1 - 0.10 * bh) - mb[1] * sc,   # base chồng lên đỉnh thân 10%
              sc))
```

Kiểm lại rằng bbox của glyph dựng ra **VƯỢT** bbox của base: `ư` phải cao hơn `u` ~25%, không phải bằng. Cao bằng = móc bị chôn.

### 5.2 Dấu thanh trên `i` THAY THẾ dấu chấm

`ì ỉ ĩ í` không có chấm. Dựng `ỉ` từ `i` sẽ giữ dấu chấm và cho nó đâm vào hook. Nếu font có `dotlessi` (Boopee có), dùng nó làm base mỗi khi recipe chứa dấu ở trên; để yên `ị`/`i`, chúng giữ chấm. Kiểm bằng bbox: `ì` và `ĩ` của hoạ sĩ đỉnh ở 623/633, nên `ỉ` dựng ra phải rơi quanh đó — 640 sau khi sửa, so với 803 trước đó.

### 5.3 Dạng thanh điệu của chữ có sừng dựng TRÊN chính chữ có sừng

`_r("ớ", "o", [HORN, "acute"])` dựng lại sừng, nên font có sẵn `ohorn` (SF Pixelate có) nhận một sừng tổng hợp cho `ớ` nhưng sừng của chính nó cho `ơ` — **hai chiếc sừng khác nhau trong một font**. Viết `_r("ớ", "ơ", ["acute"])` và phân giải base đệ quy: glyph native nếu cmap có, không thì dựng từ recipe của chính nó. Thêm chốt chặn đệ quy để recipe tự tham chiếu không lặp vô hạn.

### 5.4 Dấu thanh trên chữ có sừng đặt TRÊN BẦU chữ

Xếp nó ở `cur_top + stack_gap` (mà `cur_top` đã gồm sừng) sẽ ném nó lên quá cao. Với `ơ`/`ư`, đặt dấu ở đúng offset hoạ sĩ dùng cho nguyên âm trần — `off_for("o", "acute")` cho đúng chỗ `ó` mang acute, và đó là chỗ `ớ` muốn.

### 5.5 Cỡ: host đặt thang tổng, donor đặt tỉ lệ theo từng chữ

Một luật phẳng kiểu "mọi dấu nhập đều bằng chiều cao dấu median của host" làm dấu HOA nhỏ đi rất nhiều: composite HOA của chính donor mang dấu lớn hơn theo tỉ lệ.

```
scale = target_h * (r['mark_h_over_base_h'] / donor_median_ratio) / mark_ink_h
```

`donor_median_ratio` là median `mark_h_over_base_h` trên các quan hệ chữ thường của donor. Với chữ thường nó ≈1; với chữ HOA nó nâng dấu lên như donor làm.

### 5.6 Méo hình mới là thứ trông sai — đổi cỡ lấy méo, và đo nó

Nong một outline để đạt độ dày nặng hơn sẽ đổi hình dạng nó. Khi dấu của host nặng hơn donor nhiều thì mức nong cần thiết lớn và dấu thôi trông giống donor — mắt đọc thành "cái móc đó là một vạch thẳng".

Vì độ dày tỉ lệ tuyến tính với scale, chọn scale đã mang sẵn độ dày của host và để CỠ trôi trong một cửa sổ có chặn:

```
k_size   = target_h / mark_h                 # cỡ dấu của host muốn gì
k_weight = target_t / thickness_at_scale_1   # độ dày của host muốn gì
k = clamp(k_weight, 0.80 * k_size, 1.28 * k_size)
```

Offset còn lại khi đó nhỏ và vô hại. Hiệu quả đo được trên một mặt chữ: IoU móc so với donor 0.82 → 0.96, hook 0.96 → 0.97.

Đo hình, đừng nhìn:

- **IoU** — raster glyph donor và glyph dựng ra, chuẩn hoá mỗi cái về cùng bbox, giao trên hợp. Rẻ, và bắt được outline bị làm hỏng thật. Nó cũng tụt khi dấu được làm dày một cách hợp lệ, nên coi IoU thấp là "khác về độ dày" trừ khi mức nong nhỏ.
- **Elongation** — `ink_area / thickness²` bất biến với cả scale lẫn độ dày, nên nó trả lời "đây có còn là cùng một dấu không?" thay vì "có cùng cỡ không?". So host với donor và fail ngoài khoảng [0.70, 1.45]. Một vạch thẳng ở chỗ đáng ra là cái móc rơi rất xa ngoài khoảng đó.

### 5.7 Bẫy offset outline

- `TTGlyphPen.glyph()` **không** tính bbox. `glyph.xMin` sau đó ném `AttributeError: 'Glyph' object has no attribute 'xMin'`. Tự gán biên từ điểm contour, hoặc gọi `recalcBounds(glyf)` trước.
- Quyết định chiều offset từ **diện tích có dấu** của contour (thử cả hai dấu, giữ cái làm |area| đổi theo chiều đã yêu cầu). Không bao giờ giả định winding.
- Cho góc nhọn một join TRÒN (một cung điểm giữa hai pháp tuyến cạnh). Miter bị kẹp sẽ nhô thành gai trên curve chặt.
- Tôn trọng dấu là quan trọng: một offsetter luôn phình làm hiệu chỉnh âm lặng lẽ không làm gì, nên dấu "quá nặng" vẫn nặng.

## 6. Audit

### 6.0 Biến lời chê thành phép kiểm trước khi động vào builder

Người duyệt không nói bằng số. Việc đầu tiên khi nhận phản hồi là **dịch câu chê thành id
phép kiểm**, rồi chạy đúng phép đó — không sửa theo cảm giác, không "chỉnh cho giống hơn".

| lời người duyệt | phép kiểm | đo cái gì |
|---|---|---|
| "quá nhỏ", "dấu bé" | **C10** | chiều cao thân dấu so với cỡ suy lại từ font đích |
| "nét mảnh", "nhạt", "mỏng" | **C5** | độ dày nét, so với **chính dấu đó** ở font đích |
| "lệch", "cao quá", "thấp quá" | **C2** | mép dấu vượt khỏi hộp chữ bao nhiêu |
| "lệch ngang", "móc không nhô ra" | **C11** | vị trí ngang hai chiều so với donor |
| "dính chữ", "chôn vào chữ" | **C3** | khe hở dấu–chữ |
| "không thẳng hàng" | **C4** | dấu căn giữa có căn giữa |
| "trông khác", "thẳng đơ", "mất nét" | **C9** | chữ ký hình dạng (elongation) vs donor |
| "dấu to nhỏ không đều", hai chữ cùng dấu mà khác cỡ | **C12** | dấu do CHÍNH font vẽ phải đặt ở tỉ lệ 1.0 |
| "dấu đè lên nhau" | **C7** | xếp chồng, lấy mức donor làm trần |
| "ô trống", "không thấy chữ" | **C1** | mã điểm ảnh phân giải ra outline **có mực** — không phải "có mặt" |
| "dấu chạm chữ bên cạnh" | **C13** | mực của glyph có nằm trong hộp lề mà chính font giữ |

Bảng phép kiểm đầy đủ — mỗi phép một trục:

| id | câu hỏi | cách làm |
|----|---------|-----|
| C1 | mã điểm có phân giải ra outline không? | cmap + số contour, **có mực** |
| C2 | dấu có vượt khỏi base theo hướng họ dấu dùng không? | độ nhô kỳ vọng từ quan hệ donor |
| C3 | bay hay bị chôn? | khe hở so với khe donor, ±(0.85·gap + 0.04·base_h) |
| C4 | dấu căn giữa có căn giữa không? | chỉ khi donor căn giữa nó |
| C5 | dấu nhập có đúng độ dày của host không? | thickness / độ dày dấu của host |
| C6 | nét hay là vệt? | ink/bbox và thickness/min-side; bỏ qua bar và dot |
| C7 | dấu xếp chồng có đâm nhau không? | **đối chiếu** — mức chồng của chính donor là trần |
| C8 | có nằm trong hộp không? | so với thứ CHÍNH mặt chữ đã vẽ, không phải hhea |
| C9 | có còn là hình của donor không? | tỉ lệ elongation vs donor |
| C10 | dấu có đúng CỠ không? | chiều cao dấu so với đích suy lại từ font host + spec donor |
| C11 | dấu neo phải có nằm đúng chỗ donor đặt không? | hai chiều vs `dx_right` của donor, chạy cả khi nó ≤ 0 |
| C12 | dấu của chính font có ở tỉ lệ 1.0 không? | scale của part, theo §1.1 |
| C13 | glyph dựng có phá hộp lề của chính mặt chữ không? | so lề trung vị của glyph gốc, có đường cơ sở gốc |

C10 và C11 tồn tại vì một điểm mù do **hiệu chuẩn** tìm ra, không do nhìn glyph:
**C2 hỏi MÉP của dấu ở đâu và C5 hỏi NÉT dày bao nhiêu; không phép nào hỏi nó TO cỡ nào.**
Một phép thu nhỏ áp lên cả dấu để mép nằm đúng chỗ neo đặt nó và nét đúng độ dày của host, nên cả hai phép đều PASS trong khi mọi dấu trong font chỉ còn 45% cỡ đúng. C10 suy lại chiều cao kỳ vọng từ font host và spec donor. Tương tự, luật ngang của C2 chỉ hỏi dấu có nhô RA ĐỦ không và bỏ qua hoàn toàn khi độ nhô của donor ≤ 0 — đúng với sừng — nên một chiếc sừng đậu đâu cũng qua; C11 so hai chiều.

Luật:

* **Không có phép kiểm nào khớp = inventory thiếu một trục.** Đó là tín hiệu phải thêm phép
  kiểm mới, không phải tín hiệu sửa tay. (Ca thật: "thu mọi dấu còn 45%" không phép kiểm
  nào bắt được vì lúc đó chỉ hỏi mép và độ dày, không ai hỏi kích thước.)
* **Chạy lại phép kiểm trên toàn bộ repertoire** sau khi sửa, không chỉ trên chữ bị chê —
  cùng một lỗi thường nằm ở nhiều chữ.
* **Đối chiếu chéo:** lời chê nói X, số đo nói pass → kiểm lại bằng cách đếm điểm mực trên
  ảnh render (model đọc ảnh đã báo động giả hai lần). Số và mắt lệch nhau thì phải giải
  thích được vì sao trước khi sửa.
* Chỉ áp luật mà họ dấu của nó được neo bởi. Kiểm `dx_right` trên một hook sẽ báo "horn overhangs -14" trên mọi hook trần.
* Danh sách `parts` trong build report **KHÔNG gồm base**. Cắt nó lần nữa (`parts[1:]`) ghép hình học của dấu N với tên của dấu N-1 và sinh ra hàng chục fail giả.
* Loại glyph của chính host khỏi phép kiểm ribbon và shape — chúng là tham chiếu.
* Một bar và một dot below là khối đặc theo thiết kế; phép kiểm ribbon phải bỏ qua chúng.
* Vài mặt chữ vẽ vượt `hhea` một cách hợp lệ (một mặt có `ă` gốc tới 1792 so với ascent 1434). Chặn C8 bằng chính biên của mặt chữ.
* Memoise các số đo theo từng glyph, không thì audit chạy hàng phút.

### 6.1 Hiệu chuẩn bằng sabotage — và phải chứng minh bản phá có tác dụng

**Một phép kiểm đọc kỳ vọng từ chính artifact nó đang kiểm thì không phải phép kiểm.**

Ca thật: builder ghi `target_mark_h` vào report, audit lấy kỳ vọng từ chính report đó. Khi bản phá nhân `target_h × 0.45`, cả bản dựng lẫn kỳ vọng cùng nhỏ đi, nên các phép kiểm vị trí/độ dày đều **PASS** trong khi mọi dấu teo còn 45%. Không ai thấy cho tới khi chạy sabotage và hỏi "vì sao không phép kiểm nào nổ?".

Luật:
1. Mỗi lỗi đã biết phải có **một bản phá tái lập được nó**, và audit phải FAIL đúng phép kiểm đó.
2. **Bản phá phải được chứng minh có tác dụng** trước khi kết luận. So **vị trí đặt dấu** của bản phá với bản sạch (từ report, dung sai ~3 đơn vị). Không đổi = phép phá vô hiệu, xếp loại riêng (`KHÔNG ĐỔI`), **không** đếm là "lọt lưới". Đừng dùng hash outline chính xác: nó bắt cả dao động 1 đơn vị, nên một phép phá gần như vô hiệu bị đọc thành audit mù — và một lỗ hổng thật sẽ nấp ngay sau đó. Ca thật: neo móc "vào tâm" vs "vào mép phải" nghe như hai chỗ khác nhau, nhưng `dx_center` và `dx_right` chỉ là hai cách mô tả *cùng một* vị trí, nên bản phá không dịch dấu đi đâu cả. Kiểu vô hiệu thứ hai: một tham số **không bao giờ ràng buộc** trên font đang xét — đặt `grow_cap ≈ 0` (tắt phần nong nét) không đổi gì khi dấu donor ở cỡ đích vốn đã dày bằng hoặc hơn dấu nhà phát hành, nên "audit không bắt được" là kết luận sai. Cổng hiệu lực phân loại đúng nó thành `KHÔNG ĐỔI`, và đó là lý do phải có cổng: nếu không, mỗi lần chạy lại tưởng mình có một lỗ hổng trong khi thật ra phép phá chưa bao giờ chạm tới bản dựng.
3. **Kỳ vọng suy lại từ nguồn độc lập**: số đo trên chính font đích + spec donor. Cấm đọc ngưỡng/kích thước mục tiêu từ report của builder.
4. **Mỗi dấu có năm trục độc lập**, cần một phép kiểm cho mỗi trục: vị trí mép · kích thước · độ dày nét · hình dạng · khoảng cách tới base. Kiểm mép (dấu vượt lên bao nhiêu) + kiểm độ dày tuyệt đối (nét dày bao nhiêu) **cùng PASS** một dấu đúng nét, đúng mép, nhưng sai kích thước — vì mép do neo quyết định, còn độ dày do phép nong quyết định, không trục nào ràng buộc chiều cao thân dấu.

Một bản phá có kỳ vọng sai cũng nói dối: "thu mọi dấu còn 45%" cần C10 trong danh sách, không phải C2/C5, không thì một vụ bắt thật bị báo thành lỗ hổng.

**Dấu gốc của chính font đích là tham chiếu weight/size trung thực nhất** — nó do hoạ sĩ của font vẽ, và không cần donor. Tách nó bằng `mask(acc) & ~dilate(mask(base))` (hai glyph vẽ từ cùng gốc nên mask đã thẳng hàng). Font nào có ≥3 chữ mang dấu gốc thì lấy median làm chuẩn. Boopee vẽ 52 chữ mang dấu natively; độ dày dấu median 72 đơn vị bằng phương pháp đó so với 74 đo từ glyph `´` rời — hai phép đo độc lập đồng ý trong 3%. Lưu kết quả vào một corpus tham chiếu (`--build` / `--check`) để bản dựng sau được đối chiếu với đúng hình học đã được duyệt.

**Bẫy Windows:** `TTFont(path, lazy=True)` giữ file handle mở → `unlink()` sau đó ném `WinError 32`. Đọc qua `io.BytesIO(path.read_bytes())` khi cần đo rồi xoá.

**Giữ hiệu chuẩn tất định, và dùng nó để chốt nguồn gốc.** Cùng builder + cùng danh sách bản phá ⇒ log giống hệt từng byte. Nên khi một thông báo trễ từ job nền cũ làm nghi ngờ không biết lần chạy nào ghi ra file dùng chung, **chạy lại rồi so hash** thay vì suy luận theo mtime. Hash bằng nhau = file vốn đã đúng, không bị ghi đè; hash khác = coi các số cũ là chưa biết và phải kiểm lại trước khi phát hành thứ gì trích dẫn chúng. Không bao giờ để một báo cáo không tái lập được làm bằng chứng cho bản phát hành.

**Log bằng chứng phải do script tự ghi, và đặt tên theo nội dung.** Đừng để `script > reports/fixed_name.txt`: đường dẫn cố định làm bằng chứng phụ thuộc vào *lịch chạy job*, nên một lần chạy cũ xong muộn sẽ ghi đè lần mới và không ai đọc file mà biết được. Cho script tự tính hash nội dung rồi ghi `calibration_<sha12>.txt` + một con trỏ `calibration_latest.txt`; bên đọc đi qua con trỏ và ghi lại **tên file + hash** vào manifest. Vì phép chạy tất định, cùng toolchain ⇒ cùng tên file (idempotent), còn toolchain đã đổi thì không thể đội lốt kết quả cũ.

**Áp cho MỌI artifact bằng chứng, không riêng log.** Trong một phiên, cùng một lớp lỗi xuất hiện bốn lần ở bốn file khác nhau (log hiệu chuẩn, corpus, kết quả audit cỡ nhỏ…). Mỗi lần một file tên cố định bị một job cũ ghi đè muộn là một lần phải dừng lại điều tra xem số đang đọc thuộc lần chạy nào. Danh sách phải kiểm: mọi file được bước đóng gói đọc. Với mỗi file: **hoặc** đặt tên theo nội dung + con trỏ, **hoặc** ghim hash vào manifest để lệch là phát hiện được. File không thuộc cả hai loại là chỗ bằng chứng có thể đổi sau lưng.

**Tên-theo-nội-dung phải hash ĐÚNG BYTE ghi ra đĩa.** `Path.write_text(...)` trên Windows dịch `\n` thành `\r\n`, nên hash tính trên chuỗi Python không bằng hash của file — tên file nói một đằng, `sha256sum` nói một nẻo. Người kiểm sau chạy `sha256sum` thấy lệch sẽ kết luận bằng chứng hỏng, chứ không đoán ra đó là quy ước xuống dòng. Ghi bằng `write_text(..., newline="")` để byte trên đĩa **chính là** chuỗi đã hash, và bên đọc hash bằng `read_bytes()` chứ không phải `read_text()` (chế độ text cũng đổi `\r\n` → `\n`). Kiểm bằng chính công cụ ngoài: `sha256sum <file>` phải khớp phần hash trong tên file.

**Đừng quên chính file phán quyết.** Luật này được áp cho log hiệu chuẩn và kết quả cỡ nhỏ, nhưng bị bỏ sót ở file log của lệnh kiểm tra tổng — nó vẫn tên cố định. Một thông báo muộn của lần chạy cũ mang theo **kết quả HỎNG** đã tới trong phiên, và chỉ nhờ thứ tự may mắn mà file trên đĩa còn giữ kết quả ĐẠT. Đảo thứ tự là bản phán quyết đạt bị ca hỏng xóa mất, không dấu vết. File tổng hợp dễ bị bỏ sót nhất vì nó "chỉ là bản tóm tắt" — nhưng nó là thứ người ta đọc để kết luận. Cùng luật: tên theo nội dung + con trỏ.

**Ghi kết luận vào chính nội dung đã hash, đừng in nó ra ngoài.** Dòng `log: reports/verify_all_<hash>.txt` chỉ ra stdout: nếu nó nằm trong thân file thì hash phải phụ thuộc vào chính tên của nó — bất khả. Tương tự, đừng đưa bản phán quyết tổng vào gói kiểm chứng: gói được tạo ra *trong* chuỗi kiểm tra, nên nó chỉ có thể chứa phán quyết của lần chạy TRƯỚC. Gói chứa **bằng chứng gốc** (hiệu chuẩn, cỡ nhỏ, audit, phủ); bản phán quyết là dẫn xuất và đứng riêng.

**Và ghim luôn ĐẦU VÀO của phép kiểm.** Corpus/hằng số tham chiếu là input của audit, nên nếu nó bị ghi lại sau khi audit chạy thì kết quả đã ghi lại đang mô tả một thứ khác — mà file kết quả vẫn trông bình thường. Cho audit **ghi lại hash của input nó đã dùng** vào chính output, rồi để bước đóng gói so hash đó với input trên đĩa và **từ chối** nếu lệch hoặc nếu audit không khai. Cổng này tự chứng minh tác dụng ngay lần đầu: nó chặn cả 5 audit cũ vì chúng không khai đã dùng corpus nào.

### 6.2 Cổng tự hiệu chuẩn

**Mọi luật tự động phải chạy lên glyph do nhà phát hành dựng trước.** Luật chấm glyph gốc là luật sai. Dung sai suy từ chính font (`tol = max(3, worst_publisher × 1.25)`). Trong TWAU, cổng này bác bỏ ba lớp cảnh báo (`mark_sinks_into_body` 32/48 glyph gốc, `centre_off` 11/72, `dot_overlaps_body`).
- Base id trong script đo chỉ lấy từ spec của pipeline, không viết tay.
- Tách **presence** (có dấu) và **placement** (dấu ở đâu).
- Thước đo phải ổn định: một thay đổi dọc không được làm đổi chỉ số ngang. Nếu đổi, thước đo không dùng được để phê duyệt (V9n). Canh base theo neo gốc ô, không theo IoU tối đa.
- Không đổ lỗi codec trước khi đo round-trip.

**Đường cơ sở cho mọi phép kiểm theo tỉ lệ.** Một phép kiểm so tỉ lệ (mật độ chạm, hộp lề, độ phủ) chỉ có nghĩa khi đặt cạnh tỉ lệ mà **chính font gốc** tạo ra trên cùng văn bản. Lần chạy đầu của phép kiểm chạm báo **31.437 cặp** trên BradBunR — đó không phải số lỗi, đó là bản mô tả kiểu chữ. Và khi chính 49–60% glyph gốc của một mặt chữ nằm ngoài hộp lề trung vị của nó, phép kiểm hộp lề phải **bỏ qua** mặt chữ đó thay vì báo 94/94.

### 6.3 Tái lập được, và đọc ngược từ container

* **Dựng hai lần, so hash.** Pipeline phải tất định: chạy lại từ cùng input và so hash của
  asset + font + trang duyệt. Khác nhau = có nguồn ngẫu nhiên (thứ tự dict, timestamp,
  đường dẫn tuyệt đối) và mọi bằng chứng trước đó mất giá trị. Ở đây hai lần deploy cho ra
  **cùng hash**, nên nhãn "bản đã kiểm" mới có nghĩa.
* **Đọc ngược từ container mà game thực sự load**, không tin file staging. Unity legacy
  `Font`: lấy `m_FontData` từ typetree, **đừng** so `get_raw_data()` — object serialize lớn
  hơn blob ~120 byte (header của Unity), nên so raw sẽ báo LỆCH giả cho mọi font. Kiểm luôn
  cả khối U+1EA0–U+1EF9 có đủ trong bản đọc ra.
* **Hash phải nằm trong biên nhận.** Builder ghi hash của cả bản staging lẫn bản đã cài;
  bước đóng gói đọc lại từ đĩa và **từ chối** nếu lệch — không thì "đã cài" là lời khai,
  không phải bằng chứng.
* **Ghi lại việc sửa để nó kiểm được.** Khi builder tự sửa một glyph (co dấu cho vừa ô, lấp glyph rỗng), ghi mọi ca đã sửa vào report kèm số đo trước/sau. Một thay đổi không nằm trong report là một thay đổi không ai audit được.

### 6.4 Đo ở cỡ người chơi thật đọc

Mọi thứ ở trên audit **outline**. Một dấu hoàn hảo ở 130 px vẫn có thể là một vết 2 pixel ở cỡ phụ đề được vẽ, và không phép kiểm cấu trúc nào thấy điều đó.

Phương pháp — raster chữ có dấu và base của nó ở cùng cỡ, cùng gốc, rồi trừ; phần còn lại đúng bằng phần dấu đóng góp:

* **KHÔNG** dilate base trước khi trừ. Dilate đang ăn mất 1–2 px của một dấu 2–3 px và báo hàng trăm ca chết giả. Hiệu chính xác là dấu.
* "Sống" = còn ≥ ~2 px residue và ≥ 1 px chiều cao.
* Báo **ngưỡng sống** (cỡ nhỏ nhất mà mọi dấu còn sống) và residue median theo cỡ, theo mặt chữ và theo họ dấu — họ yếu nhất là kết quả có ích.
* So với dấu của CHÍNH mặt chữ ở cùng cỡ. Dấu của Boopee chỉ 2–3 px ở 16 px, và `À` của nó không to hơn `Ẽ` dựng ra — nên "nhỏ" một mình không phải lỗi; "nhỏ hơn cái chính font vẽ" mới là.

**Luôn đo cả hai phía ở cùng cỡ trước khi gọi nó là lỗi.** Boopee ở 16 px: dấu của chính hoạ sĩ là 0/16 dưới 2 px mực (min 2, max 4 — tất cả sống) trong khi 18/94 dấu dựng ra rơi dưới ngưỡng đó. Đó là khoảng cách thật, và nguyên nhân thấy được trong danh sách: 10 là `hook`, 1 `horn` (cả hai nhập từ donor, còn ở cỡ donor) và 6 `dotbelow` (chấm nhỏ của chính mặt chữ). Cùng phép đo trên SF Pixelate ở 16 px cho kết quả ngược lại — 10/16 dấu của CHÍNH nó đã dưới 2 px trong khi chỉ 5/90 dấu dựng ra ở dưới, nên ở đó dấu dựng ra khoẻ hơn thiết kế của mặt chữ và không có gì phải sửa.

Nên con số để báo theo từng mặt chữ là một **chia ba nhánh**, không phải một tổng:

| ở cỡ S | dấu của hoạ sĩ | dấu dựng ra | kết luận |
|---|---|---|---|
| cả hai sống | tốt | tốt | không phải làm gì |
| hoạ sĩ sống, ta chết | tốt | hỏng | **lỗi của ta — sửa dấu** |
| cả hai marginal | marginal | marginal | CỠ quá nhỏ; **không** bóp méo mặt chữ để bù |

Nhánh thứ ba là cái bẫy: làm dấu dày vượt quá độ dày của chính mặt chữ để nó sống ở cỡ render tí xíu là đánh đổi một mất mát trung thực thật lấy một vấn đề cỡ render. Báo ngưỡng sống ra và để cỡ render được nâng lên.

### 6.5 Lỗi chỉ tồn tại GIỮA hai ký tự

Mọi phép kiểm glyph soi từng ký tự một, nên tất cả đều mù trước lỗi chỉ tồn tại trong ngữ cảnh: một glyph dựng ra có mực rộng hơn advance của chính nó, nên nó đâm vào chữ theo sau. Người đọc thấy "dấu đang chạm chữ bên cạnh"; không lưới ký tự nào thấy được. **Audit corpus như VĂN BẢN** — đặt mọi glyph ở tổng tích luỹ của advance rồi so hộp mực của mỗi glyph với hộp của glyph kế tiếp.

Ba phép đo, và cách hiệu chuẩn từng cái:

* **Mật độ chạm.** Hiệu chuẩn hai lần, vì con số thô vô nghĩa: (a) so với tỉ lệ mà **bản GỐC** tạo ra trên cùng văn bản — mặt chữ vẽ tay để chữ chạm nhau có chủ đích; (b) so với một mặt chữ **có tiếng Việt bản địa** — Yomogi-Regular chạm 0.05% trên 173.971 cặp, đó là tham chiếu; Boopee 16.7% là style bút lông của nó, còn riffic-bold đi từ **0% lên 3.8%** mới là lỗi. Chỉ gọi là lỗi khi tỉ lệ gốc < 5% và tỉ lệ dựng ra vượt 15% tương đối.
* **Hộp lề của chính mặt chữ.** Đo hộp mà glyph gốc giữ (lề trái/phải trung vị) và cờ glyph dựng ra vượt khỏi nó — nhưng so với tần suất glyph GỐC vượt khỏi chính nó: Boopee 49% và BradBunR 60% thì **bỏ qua**, thay vì báo 94/94. Nơi phép kiểm có nghĩa, nó tìm ra hỏng thật — 30/90 glyph SF Pixelate, 42/104 của riffic-bold, 7/32 của PixeloidMono, so với tỉ lệ gốc 6%, 18% và 3%.

**Nguyên nhân và cách sửa: dấu lấy cỡ cho base RỘNG, đặt lên base HẸP.** Cỡ dấu đến từ mặt chữ host, lấy từ chỗ mặt chữ vẽ nó — thường trên một base rộng (`o`, `e`). Composite lên một base hẹp (`i`, `I`, `ă`) nó tràn cả hai bên. Cả 153 glyph có dấu gốc của riffic-bold giữ đúng 30 đơn vị lề; `ĩ` của ta ra 396 đơn vị mực trên advance 278 — 142% của ô, xMin −69.

Sửa bằng cách **thu hẹp dấu theo chiều NGANG quanh tâm của chính nó**, để nguyên base và mọi số đo dọc, cho tới khi mực gộp nằm trong hộp lề của mặt chữ. Đây là điều một mặt chữ có tiếng Việt bản địa vốn đã làm: tilde của `ĩ` ở Yomogi bằng 59% bề rộng tilde của `õ`, vì base `i` của nó hẹp hơn `o`. Chặn hệ số (sàn 0.45) và ghi mọi glyph đã co vào report để thay đổi kiểm được.

Ví dụ một ca cụ thể: `ĩ` của riffic-bold từ **395 đơn vị mực xuống 218** (k = 0.552) là đủ để nó nằm trong hộp lề của mặt chữ; mặt đó có 51 glyph phải co, PixeloidMono 7.

Hiệu quả đo được: riffic-bold 3.78% → 2.6%, ca nặng nhất 4.4% → 2.3% của em, và cả năm mặt chữ vẫn 0 FAIL, phủ 148/148 sau đó.

Phần còn lại là sừng và dấu xếp chồng vốn nhô sang phải một cách hợp lệ — thu hẹp chúng nữa là bóp méo hình chữ. **Dừng ở đó và báo phần tồn dư** thay vì đuổi con số về 0.

### 6.6 Phủ corpus: phân loại ký tự thiếu

Một phép kiểm phủ toàn corpus báo thừa, và báo nó như một lỗi là sai hai lần. Phân loại từng ký tự thiếu:

| loại | ví dụ | hành động |
|------|---------|--------|
| trong phạm vi | mọi chữ Latin/Việt, mọi dấu câu corpus dùng | lỗi thật: mặt chữ đổi giữa câu |
| chữ hệ khác, nội dung gốc | `Русский` trong menu ngôn ngữ, `Piotr Domański, Sandra Sęk` trong credits | game giữ chúng ở ngôn ngữ của chúng; bản dựng của ta render y hệt bản gốc. Bịa chữ Cyrillic cho một mặt chữ vẽ tay là **vẽ glyph**, không phải bản địa hoá |
| CJK | nhãn menu Nhật/Trung/Hàn | đúng thiết kế, chúng thuộc mặt chữ CJK dự phòng |

### 6.7 Một ký tự văn bản nguồn dùng mà mặt chữ chưa từng có

Gạch ngang en là ca điển hình: chữ trên bia mộ của chính game mang `1976 – 2004`, Boopee và ba mặt khác có `–`, mặt thứ năm có em dash mà không có en dash. **Không sửa được bằng cách chọn dấu câu khác** — ký tự đến từ source.

Suy nó từ glyph CỦA CHÍNH mặt chữ, đúng cách `đ` được dựng từ `d`: lấy em dash, co ngang quanh tâm nó, giữ nguyên dải dọc và độ dày nét, đặt advance theo tỉ lệ. Kết quả nằm trong ngôn ngữ thiết kế của mặt chữ chứ không phải bịa ra:

```python
glyphset = font.getGlyphSet()
g = glyf[cmap[0x2014]]                 # em dash của chính mặt chữ
cx = (g.xMin + g.xMax) / 2.0
pen = TTGlyphPen(glyphset)
glyphset[cmap[0x2014]].draw(TransformPen(pen, Transform(0.5, 0, 0, 1, cx * 0.5, 0)))
new = pen.glyph(); new.recalcBounds(glyf)
```

Kiểm với chính nguồn: em dash rộng 1639 đơn vị với advance 1696 thành một gạch rộng 819 với advance 882 — **đúng một nửa** (tỉ lệ đo được 0.4997), cùng dải `y`, và nó nằm giữa hyphen (880 rộng, 923 advance) và em dash, đúng chỗ en dash thuộc về. Cả ba gạch dày 237 đơn vị như nhau.

### 6.8 Phép kiểm phủ phải loại ký tự không cần outline

`covered()` hỏi "mã điểm này có mực không". Dấu cách map sang glyph zero contour, nên nó không bao giờ được coi là phủ — và mọi dòng chứa dấu cách bị tính là bị ảnh hưởng. Con số dòng bị ảnh hưởng trên bản dựng này đọc ra **5611 cho cả năm mặt chữ kể cả mặt không thiếu gì**, và đã vô nghĩa từ khi phép kiểm được viết. Bỏ qua mã điểm mà glyph rỗng là đúng (`cp <= 0x1F`, hoặc category Unicode `Z`) trước khi hỏi về mực. **Một con số không bao giờ đổi giữa ca lành và ca hỏng là một con số không đo gì cả.**

### 6.9 Bản dựng lại không được đổi glyph gốc

Ghi lại font bằng fontTools viết lại **toàn bộ** file, nên mọi glyph có sẵn đi qua một vòng parse/serialize. Nếu vòng đó đổi một outline thì hỏng **âm thầm**: audit chỉ soi glyph ta thêm, còn readback chỉ chứng minh file trên đĩa khớp bản dựng.

So mọi mã điểm có trong CẢ font gốc lẫn bản dựng: outline, advance, bbox. Phân loại khác biệt trước khi kết luận:

* **glyph gốc RỖNG được lấp** — chủ ý (§2.2). Đừng đếm là hỏng, nhưng cũng đừng đếm cả ký tự điều khiển U+0000… vốn **phải** rỗng: chỉ tính là đã lấp khi nó KHÔNG còn rỗng.
* **bbox lệch trên glyph tổ hợp** — giá trị cache, không phải hình dáng. Outline của chúng đã khớp.
* **outline hoặc advance lệch** trên một glyph mà font gốc THẬT SỰ VẼ — đây mới là lỗi, phải điều tra.

Kết quả đúng phải là: outline và advance khớp từng ký tự, chỉ glyph ta thêm và glyph gốc rỗng được lấp là khác.

## 7. Dấu hiệu nên chuyển sang P1

- Hai vòng runtime liên tiếp vẫn có lỗi người dùng nhìn thấy.
- Thước đo tự động không còn tin được (dương tính giả lặp lại, không ổn định).
- Người dùng phải soi từng chữ.

Khi gặp một trong ba dấu hiệu, đề xuất P1 cho font đó thay vì tiếp tục sửa từng tổ hợp.
