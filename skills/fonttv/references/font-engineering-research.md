# Font engineering tiếng Việt — kiến thức nghiên cứu

Reference kỹ thuật tổng hợp từ ba nguồn nghiên cứu (§1). Không phải quy trình; quy trình và gate nằm ở `SKILL.md` và `quality-gates.md`. Mọi kết luận runtime vẫn cần kiểm trên đúng game/build.

## 1. Nguồn và phạm vi

| Nguồn | Nội dung chính dùng ở đây | Giới hạn |
|---|---|---|
| Báo cáo "Việt hóa font chuẩn Unicode/OpenType" | source-first, NFC/NFD, anchor + `mark`/`mkmk`, license trước tiên, stack build/QA, test strings | hướng tới font phát hành độc lập, không nói về custom engine |
| Blueprint "Bộ công cụ Việt hoá font" (22.09.2026) | 146 dạng chữ/134 codepoint, 8 combining marks, `top_viet`, horn là dấu bên, soft-dotted `i`, dấu hoa, pipeline 10 cửa, ma trận bằng chứng | nhiều nguồn chỉ ở mức "chỉ mục", chưa đọc trực tiếp |
| Master plan + starter kit "Vietnamese Font Engineering" (22.09.2026) | preserve/allowlist, 5 failure mode của `tecix/viet-hoa-font` (tái lập lại, §7), status model, corpus NFC/NFD/canonical, quality gates | scaffold; engine compose/build chưa có |

## 2. Repertoire và Unicode

- 12 họ nguyên âm (A Ă Â E Ê I O Ô Ơ U Ư Y) × 6 trạng thái thanh × hoa/thường + Đ/đ = 146 dạng chữ; bỏ 12 nguyên âm ASCII còn 134 codepoint. Dựng tập này từ vowel bases × tone marks qua NFC, không hardcode U+1EA0–U+1EF9: chữ Việt nằm rải ở Latin-1, Latin Extended-A/B, Combining Diacritical Marks và Latin Extended Additional.
- Tám combining marks: U+0300 huyền, U+0301 sắc, U+0303 ngã, U+0309 hỏi, U+0323 nặng, U+0302 mũ, U+0306 trăng, U+031B móc.
- `GF_Latin_Core` + `GF_Latin_Vietnamese` (Google Fonts glyphsets, 240 mục) là định nghĩa phạm vi tốt hơn danh sách tự lập. Con số 134 của một tool chỉ là repertoire của tool đó.
- Canonical equivalence: chuỗi dựng sẵn và chuỗi tách phải hiển thị như nhau. Test cả NFC, NFD và biến thể canonical hợp lệ: `A+U+0302+U+0323` ≡ `A+U+0323+U+0302` vì combining class khác nhau (230 và 220). Không hoán đổi hai dấu cùng combining class.
- Thứ tự Unicode khác thứ tự dựng hình: NFD của `ậ` là `a + nặng + mũ`, nhưng hình vẫn là mũ trên, chấm dưới.
- Không dùng NFKC/NFKD để "sửa font" cho toàn corpus.
- Trước khi sửa font: dump bytes, Unicode scalars, dạng normalization và grapheme cluster. Font không sửa được mojibake.
- `₫` (U+20AB) là extension thực dụng ngoài 134 chữ.

## 3. Thiết kế dấu tiếng Việt

- **Horn là dấu bên**: U+031B bám cạnh phải O/U, không đặt giữa như dấu trên. Horn Ơ và Ư cùng hình, cùng cao; horn Ư đủ ngắn để không phá `ƯT`. Nên vẽ `Ohorn/ohorn/Uhorn/uhorn` có chủ ý (chữ + nét horn) rồi dùng làm base cho thanh.
- **Hỏi có hình riêng**: như dấu hỏi nhỏ; khi đi với mũ thường nằm bên phải mũ. Không thay bằng sắc hay dấu tùy ý.
- **Soft-dotted `i`**: `í ì ỉ ĩ` dùng `ı` (dotless) để dấu trên thay tittle; `ị` giữ tittle và thêm chấm dưới (recipe Shantell: `idotbelow = idotless + dotaccentcmb + dotbelowcmb`). NFD `i + U+0323` cũng phải giữ tittle.
- **Dấu hoa riêng**: thu nhỏ hoặc đổi góc thay vì phóng chữ; dấu hoa có thể rộng và thấp hơn dấu thường, không chạm cap.
- **Dấu chồng**: mũ/trăng là dấu cấu trúc, thanh bám lên chúng qua `mkmk` hoặc quy tắc composition tương đương. Sắc/huyền/hỏi thường nằm bên cạnh mũ (anchor `side`/`top_viet`), ngã nằm trên đỉnh; trên trăng các thanh đều bám `top`.
- **`top_viet`** là convention của workflow Glyphs (mekkablue script chuyển acute/grave/hook sang anchor này trên circumflex), không phải chuẩn OpenType; kết quả vẫn phải biên dịch thành GPOS hoặc composite.
- **Đ/đ**: dựng từ D/d của chính font với thanh ngang theo stem/contrast của font; không nhập nguyên Đ/đ từ donor. Thanh ngang của Đ cắt thân đứng, không nằm trên đỉnh (ví dụ lỗi họ Cinzel: `cinzel-fantasy-fonts-dcroat-floating-crossbar-repair.md`).
- **Tiếp xúc có chủ ý**: horn và thanh ngang Đ/đ chạm thân chữ theo thiết kế; collision check cần allowlist cho chúng.
- Dấu nặng của chữ có móc căn theo thân `o`/`u`. Không scale dấu Latin sẵn có 80% cho mọi font; kiểm stroke weight, terminal, độ rộng, khoảng cách base–dấu, italic angle, contrast, x-height/cap-height, chiều cao chồng và optical centering.
- Không dùng vòng AI tự chỉnh vị trí dấu; chỉnh sửa phải là recipe/patch xác định, có giới hạn, có lý do và undo.

## 4. OpenType và source engineering

- Bảng cần kiểm: `cmap`, `glyf/loca` hoặc `CFF`/`CFF2`, `hmtx`, `hhea`, `OS/2`, `GPOS`, `GSUB`, `GDEF`, variation tables, composite graph.
- Anchor tối thiểu: base có `top`, `bottom`; dấu trên có `_top` (bám) và `top` (cho dấu kế tiếp); dấu dưới có `_bottom`; horn có anchor bên. Sinh `mark`/`mkmk` từ anchor (ufo2ft, Adobe markFeatureWriter) thay vì hardcode hàng trăm tọa độ.
- Recipe dựng từ NFD (`base + modifier + tone`), độc lập với tên glyph (AGL, `uniXXXX`, production name).
- Chữ có dấu kế thừa advance/sidebearing và kerning group của chữ gốc; sao chép kerning exception cho dấu kép (ý tưởng từ mekkablue "Copy Kerning Exceptions to Double Accents").
- Vertical metrics: chữ hoa hai tầng dấu dễ clip; phối hợp `usWin*`, `sTypo*`, `hhea` và test line spacing thay vì chỉ tăng ascender.
- OS/2 `ulUnicodeRange` bit 29 = Latin Extended Additional (U+1E00–U+1EFF); bit 57 = Non-Plane 0. Code page Windows-1258 có bit riêng trong `ulCodePageRange`. Để fontTools tính (`recalcUnicodeRanges`, `recalcCodePageRanges`) rồi đối chiếu font chuẩn, không đặt bit bằng tay.
- CFF → TrueType là rebuild (Unreal cần decompose/convert trước `TTGlyphPen`), phải regression ở pixel size thật. Composite chỉ dùng khi toolchain/rasterizer/runtime hỗ trợ.
- Hinting làm sau khi outline/metrics ổn định.
- Variable: component/anchor tương thích mọi master, test extremes, named instances và điểm trung gian.

## 5. Donor

- Chỉ dùng khi dấu native, dấu trích từ chính font và vẽ mới đều không khả thi.
- Chuẩn hóa UPM, advance, bearings, vertical placement, anchors và outline flavor; không copy tọa độ nguyên xi.
- Không mượn nguyên chữ `Ơ Ư Ă Â Ê Ô`; chỉ mượn dấu khi runtime đọc outline TTF/OTF.
- Confidence thay cho ngưỡng phổ quát kiểu "stem lệch < 5%":
  - High: cùng family/instance hoặc component của chính font; normalized metrics và pixel regression đạt.
  - Medium: donor ngoài family nhưng trong envelope của target; blind visual và runtime đạt.
  - Low: chỉ giống tên/style/weight hoặc chỉ đạt một phép đo.
- So UPM-normalized x-height/cap-height, stem, contrast, baseline, advance, bearing, slant, optical size và raster ở cỡ game.
- License: quyền của tool (`viet-hoa-font` MIT) không cấp quyền trên font nguồn hay donor. Adobe Fonts cấm sửa font software và cấm tạo font software mới từ outline chuyển đổi. OFL cho sửa nhưng ràng buộc Reserved Font Name và tên derivative; copy glyph OFL vào font khác có thể buộc bản phân phối theo OFL. Be Vietnam Pro là reference chất lượng, không phải donor mặc định.

## 6. Ghi chú theo renderer

### 6.1 Unity

- UI Toolkit, uGUI, TMP, IMGUI và renderer tùy biến không mặc định chung pipeline. IMGUI: kiểm `GUIStyle.font`, `MenuElement.font`, `PlayerMenus.SetStyles`; không suy từ prefab TMP.
- TMP static asset có glyph table, lookup table, fallback table, feature data và atlas riêng; sửa TTF có thể phải rebuild cả chuỗi. Kiểm `sourceFontFile`.
- Fallback trap: TMP tính `scaleFactor = base.pointSize / fallback.pointSize` và dịch baseline theo fallback; pointSize/baseline/capLine lệch làm câu lúc to lúc nhỏ, lúc cao lúc thấp. Hoặc hiệu chuẩn FaceInfo của fallback khớp base, hoặc nạp đủ ký tự vào base.
- TMP fallback có thể làm chữ Việt mượt hơn pixel font gốc; đó là lỗi phong cách.
- Texture có `m_StreamData` trỏ `.resS`: ghi bytes vào `.resS` tại đúng offset, không nhúng lại vào `.assets` (lệch offset, crash "Position out of bounds").
- Texture2D lưu hàng từ dưới lên; mảng top-down (PIL/OpenCV) phải lật dọc trước khi nạp.
- SDF: độ dốc gradient khớp `_GradientScale` (≈ `256 / (2 * spread)`, ví dụ 21.33 với spread 6).
- Advance bám độ rộng ink + 2–3 px đệm; không nhân scale tùy tiện.
- Không gọi là "dynamic atlas eviction" khi chưa có telemetry/source chứng minh trên đúng TMP version.
- Addressables/AssetBundle: catalog, hash và dependency có thể vô hiệu hóa patch; Naninovel có nameplate/character data trong ScriptableObject, không chỉ TextAsset thoại.

### 6.2 GameMaker

- GMS2/current: font range raster thành texture page; phải regenerate sau khi đổi range. `font_add()` có giới hạn page và lifecycle riêng; sprite font có origin/spacing riêng.
- Mảng glyph phải theo thứ tự codepoint; nối glyph mới vào cuối mảng làm mất ký tự có codepoint nhỏ hơn phần tử cuối.
- GMS1: khóa runner version và inspect resource thật; không suy từ GMS2.

### 6.3 Unreal

- Phân biệt `UFont` runtime-cached và offline-cached; kiểm `FCompositeFont`, sub-typeface, fallback, Slate font cache.
- `.locres` compile và cook/package là lớp riêng; Pak/IoStore phải kiểm cooked representation, mount/priority và binding thực.

### 6.4 Adobe AIR / WebView

- AIR/FTE phân biệt embedded CFF, device font, `FontDescription` và `TextField`.
- WebView: kiểm `@font-face`, `unicode-range`, `font-display`, resource load và cache; font có trên đĩa không chứng minh đang render.

### 6.5 Bitmap, pixel, SDF/MSDF

- Pixel font: cấy glyph vào TTF/atlas gốc, giữ lưới, baseline, weight; không fallback sang vector. Dấu rõ, không chồng lên móc, dấu nặng có khoảng trống.
- Crop bitmap chỉ an toàn khi giữ origin/baseline chung; kiểm cell, padding, filtering, bleed, nén, mipmap.
- MSDF atlas đi với MSDF shader; SDF atlas + MSDF shader là lệch cấu trúc. Ghi sampling size, padding, render mode, field range, material, shader.

### 6.6 Custom engine (BMFont `.fnb` + MSDF/BC3)

- Đọc shader (HLSL/DXIL) để biết MSDF, SDF hay bitmap trước khi đụng texture. Không vẽ bitmap thô lên MSDF: median contour tính sai, nét vỡ thành gai.
- Không thay texture BC3 bừa bãi: texture đóng gói riêng có ràng buộc metadata/checksum/block alignment; nén lại qua DirectXTex/texconv từng gây crash `0xC0000005` hoặc opacity 0 làm mất toàn bộ chữ.
- Bẫy Đ: font châu Âu hay vẽ Đ như Eth (`Ð`) có gạch rời hoặc padding âm làm chữ bay. Nếu `Ð` (U+00D0) của chính font liền nét và cùng `yoffset` với `D`, có thể trỏ `Đ` sang glyph đó; hoặc chỉnh bbox trong metrics mà không đụng texture nén.

## 7. Failure mode đã tái lập

Probe của starter kit trên font tổng hợp, snapshot `tecix/viet-hoa-font` commit `b16a676…`. Chạy lại khi cập nhật skill này: Python 3.11.15, fontTools 4.63.0, Unicode 14.0.0 — cả năm đều tái lập, tập đích 134 khớp dựng độc lập.

| Failure mode | Quan sát | Hệ quả cho quy trình |
|---|---|---|
| Remap glyph đã tồn tại | U+00E2 trỏ `acircumflex_original` bị đổi sang `uni00E2` khi thêm mark | preserve mặc định có điều kiện; replace qua allowlist; semantic diff |
| Gộp sai mark class giữa lookup/subtable | hai MarkBase subtable cùng class 0; lookup sau ghi đè, acute chọn anchor dưới (300, -100) | namespace class theo lookup/subtable; đọc cả MarkToMark và ExtensionPos |
| Donor không scale UPM | donor 2000 UPM copy nguyên bounds vào target 1000 UPM | chuẩn hóa UPM/metrics/anchors |
| OS/2 Unicode range sai | đặt bit 57 thay vì bit 29 | để fontTools tính; `fonttv_audit.py` cảnh báo |
| Exit 0 khi còn thiếu | font thiếu Y/y vẫn xuất file, exit 0, còn thiếu 10 chữ | strict: exit khác 0, report máy đọc được |

Thêm từ lần cập nhật này (probe HarfBuzz 0.56.2 trên font tổng hợp): với font có `aacute` nhưng không có U+0301, HarfBuzz shape `a + U+0301` thành một glyph `aacute`, không có `.notdef`; `.notdef` chỉ xuất hiện khi thật sự không render được. Vì vậy `.notdef` trong output HarfBuzz luôn là lỗi thật, còn thiếu combining mark là rủi ro cho renderer không compose (`shaping_audit.py` báo riêng hai tín hiệu).

Chưa tái lập (không được coi là đã biết): chất lượng mỹ thuật trên serif/display/script/italic/mono/nhiều weight; bảo toàn hinting và GPOS/GSUB phức tạp; color font, TTC/OTC; CFF2 và variable interpolation; tương thích OS/app thực; chất lượng vòng AI review của tool (prompt chỉ nhìn grid, bước chỉnh cố định 20/50/100 units, không có geometry guard).

## 8. Công cụ QA và trạng thái tích hợp

| Công cụ | Vai trò | Trạng thái trong skill |
|---|---|---|
| fontTools | đọc cấu trúc, cmap, outline, metrics | dùng trong `fonttv_audit.py`; đã chạy trong test |
| HarfBuzz (`uharfbuzz`) | shaping NFC/NFD | dùng trong `shaping_audit.py`; đã chạy trong test |
| OTS | sanitizer cấu trúc | chưa tích hợp, chưa chạy |
| Fontspector / FontBakery | QA profile | chưa tích hợp, chưa chạy |
| Shaperglot, Hyperglot | language support | chưa tích hợp, chưa chạy |
| Diffenator2/3, Collidoscope | regression hình ảnh, va chạm | chưa tích hợp, chưa chạy |
| Google Fonts glyphsets | định nghĩa repertoire | tham khảo; chưa vendored |

Khi dùng công cụ chưa tích hợp: ghi version, lệnh và log vào manifest.

## 9. Dự án tham khảo

| Dự án | Nên học | Không sao chép máy móc |
|---|---|---|
| `tecix/viet-hoa-font` (MIT) | pipeline fontTools gọn; NFD decomposition; anchor-first; horn theo right stem | coverage làm tiêu chí chính; mutation rộng; AI tự chỉnh bằng bước cố định; 5 lỗi §7 |
| Shantell Sans recipes (OFL) | vẽ horn có chủ ý; stacked-mark component; dot below bám base; `side` anchor cho mũ | recipe của một phong cách không hợp mọi font |
| GlyphConstruction | recipe DSL có version control, anchor/formula/preview | tên anchor của một editor không phải chuẩn |
| mekkablue Glyphs-Scripts (Apache-2.0) | `top_viet`; copy kerning exception cho dấu kép | phụ thuộc Glyphs/macOS và source |
| FontForge Build Accented Glyph | decomposition + component | tài liệu tự cảnh báo phải kiểm tay, italic dễ sai |
| fontmake / ufo2ft / gftools / AFDKO | build reproducible, sinh `mark`/`mkmk`/kern từ anchor | round-trip source phức tạp chưa kiểm |
| mf-glyphs-scripts QA | policy checker cấu trúc glyph Việt (anchor stacking, tránh `acutecomb.loclVIT` mặc định) | không tạo glyph |
| Be Vietnam Pro | reference native nhiều weight | không làm donor mặc định |
| Nerd Fonts patcher | đóng gói, đặt tên, capability flag | yêu cầu icon patch khác ngôn ngữ |
| viparse, funput, vietnameseConverter | chuyển VNI/TCVN3/VISCII/VPS → Unicode NFC | tầng text, không phải font |

Code third-party không được chép vào skill; mọi phần tái sử dụng phải ghi license và provenance.

## 10. Quan sát lịch sử trên font thật

Lần audit trước (chưa chạy lại trong phiên bản này; shaping khi đó chỉ kiểm cmap): LiberationSans và NotoSerif-Regular đủ precomposed + 8 marks; Roboto-Medium đủ precomposed nhưng thiếu U+0302, U+0306, U+031B (HarfBuzz vẫn compose được, renderer không compose sẽ rơi dấu); NotoSerifSC-Regular thiếu cả 8 marks.

## 11. Không tự động hóa hoàn toàn

Chọn donor theo phong cách; chấp nhận visual/layout drift; CFF conversion; flatten variable/composite; binary hook; thay toàn bộ font; NFKC/NFKD toàn corpus; kết luận chỉ từ OCR hoặc AI.

## 12. Khoảng trống cần xác minh `[E/V]`

GameMaker Studio 1; console stack; renderer độc quyền chưa gặp; backend shaping chính xác của Unreal; hành vi TMP theo package version; dynamic-cache eviction từng project; bit code page chính xác và hành vi Windows-1258 trong từng engine; chưa có generator tiếng Việt cho FontLab hay web service tương đương; `moolekkari/unicode-font-skill` chưa được thẩm định.
