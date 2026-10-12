# Kiến trúc: route, representation và capability

## 1. Chuỗi cần truy vết

```text
text source → bytes/encoding → normalization → encoder (nếu có)
→ lookup key (codepoint | byte/ID | GID | atlas slot)
→ font record / glyph → outline hoặc atlas rect → metrics
→ material/shader → layout → package/container → renderer binding → shipping build
```

Mỗi mũi tên có thể sai độc lập. cmap đúng không chứng minh font đang được bind; record có trong font không chứng minh glyph ở đó đúng; file build đúng không chứng minh container live chứa file đó.

## 2. Chọn route theo lookup key

| Lookup key tại font | Route | Source of truth | Ví dụ |
|---|---|---|---|
| Codepoint Unicode | A | Unicode + cmap/character table | TTF/OTF, Unity TMP, Unreal Font Face, GameMaker font từ TTF |
| Byte/ID sinh từ encoding không phải Unicode | B | Bảng mapping của encoder | bảng single-byte của dự án, font VNI/TCVN3, CP1258 |
| Glyph index | B | Bảng GID của đúng build font | text pre-shaped, engine lưu GID |
| Ô atlas cố định | B + C | Bảng ô → ký tự | bitmap grid font, sprite font |
| Rect atlas + metrics trong binary riêng | C, thường kèm B | Adapter format + mapping | BMFont `.fnt/.fnb`, Telltale `.font`, custom engine |

Chưa xác định được lookup key thì dừng ở `inventory_only`, không sửa. Engine Unicode nhưng dự án remap chữ Việt vào PUA hoặc slot Latin-1 là route B cho phần remap đó.

## 3. Route A — Unicode/OpenType

- Có source (`.glyphs`, UFO, Designspace) thì sửa source rồi build lại (fontmake/ufo2ft/AFDKO). Binary patch chỉ dùng khi chỉ còn TTF/CFF và input nằm trong capability matrix (§7).
- Font cần cả precomposed lẫn combining marks; kiểm cùng corpus ở NFC và NFD.
- Component dựng precomposed; anchor + `mark`/`mkmk` đặt dấu cho chuỗi combining. Hai hệ chạy song song, phải kiểm cả hai.
- "Không patch glyph đã có" chỉ hợp lệ ở route A, khi cmap thực sự trỏ codepoint tới đúng glyph và glyph có outline đúng; thay thế đi qua allowlist.
- Unity TMP, Unreal, GameMaker: sửa TTF chưa đủ, phải rebuild representation downstream (atlas, FontAsset, cache); phần đó đi route C.
- Kiến thức thiết kế và OpenType: `font-engineering-research.md`.

## 4. Route B — Legacy/custom encoding

- Font phải theo bảng mapping của encoder, không dựng bảng từ nội dung font.
- Kiểm tuple ngữ nghĩa từng slot, round-trip encode/decode, remap slot sai.
- Luật cmap/GPOS/OS/2 không áp dụng máy móc cho lookup bằng byte.
- Quy trình và định dạng dữ liệu: `custom-and-legacy-encoding.md`. Trên route mã hóa, chạy lại adapter là điều kiện của cả `structurally_verified` lẫn `mapping_verified`. Report đã lưu không phải trust root.

## 5. Route C — Engine-packed bitmap/atlas

- Inventory runtime consumer: font binary, atlas page, material/shader, container/archive, cache (dynamic atlas, shader cache, mod loader cache).
- Giữ bất biến format: tính duy nhất và thứ tự ID, header size/offset, texture format, nén và block alignment, số page, descriptor. Không re-encode texture khi pixel không đổi.
- Xác định shader bitmap/SDF/MSDF trước khi vẽ vào atlas.
- Adapter đọc format phải fail closed với version/header lạ (exit 3). Record/UV/ink/metrics chỉ được tính là bằng chứng khi adapter đã pin hash được `custom_encoding_audit.py` chạy lại trên font đích trong lần audit; inventory viết sẵn chỉ là kế hoạch.
- Claim sau build phải dựa trên readback từ container live (extract lại, hash).

## 6. Điểm cần khóa theo engine

| Engine/renderer | Khóa trước khi sửa | Route | Chi tiết |
|---|---|---|---|
| Unity TMP | Unity/TMP version, FontAsset static/dynamic, atlas, material, fallback table, `sourceFontFile` | A + C | research §6.1 |
| Unity legacy/IMGUI | `GUIStyle.font`, `MenuElement.font`, `PlayerMenus.SetStyles` call-site | A | research §6.1 |
| Naninovel/Addressables | ScriptableObject nameplate/character data, catalog/hash | A + C | research §6.1 |
| GameMaker | runner version; GMS2/current regenerate texture page; GMS1 inspect resource thật | A + C | research §6.2 |
| Unreal | `.ufont`, Font Face, CompositeFont, fallback, cooked reference, Pak/IoStore priority | A + C | research §6.3 |
| Adobe AIR/WebView | FTE/TextField/embedded CFF; `@font-face`, `unicode-range`, cache | A | research §6.4 |
| BMFont/MSDF custom | loại shader, metrics `.fnb`, ràng buộc texture BC3 | C (+ B) | research §6.6 |
| Telltale Tool | bảng encode LANDb, `.font` TRectNew, page DXT5, `.ttarch2` | B + C | `telltale-fonts.md` |

## 7. Capability matrix

| Input | Trạng thái trong skill |
|---|---|
| Static TrueType `glyf` | audit route A; binary patch chỉ khi có backend thật đã kiểm |
| Static CFF1 | audit; patch cần backend riêng (contour inlining, không composite) |
| Variable (`fvar`/`gvar`), CFF2 | audit default instance kèm cảnh báo; patch NOT_SUPPORTED trừ khi có source + backend variable |
| Color/bitmap (COLR/CPAL/SVG/CBDT/sbix) | audit outline nền; patch NOT_SUPPORTED |
| TTC/OTC | NOT_SUPPORTED cho tới khi tách từng face |
| Format độc quyền | NOT_SUPPORTED cho tới khi có adapter `fonttv-adapter/v1` chạy được, đã pin hash và có conformance test; external inventory chỉ tới `inventory_only` |

Không thêm "nhánh if nhỏ" để giả vờ hỗ trợ một định dạng.

## 8. Nguồn glyph và dấu theo thứ tự ưu tiên

1. Glyph/anchor native của chính font.
2. Hình trích từ spacing glyph hoặc composite cùng font.
3. Recipe/source component do nhà thiết kế cung cấp.
4. Vẽ mới có người duyệt.
5. Donor đã qua rights, style (weight/contrast/slant), UPM, metrics và outline flavor.
6. Primitive/synthesis chỉ tạo bản `DRAFT`.

Ghi provenance từng glyph (nguồn, phép biến đổi, anchor delta) trong manifest.

## 9. Artifact mỗi lượt

`manifest.json` từ template, audit JSON từng font trước/sau, `LICENSE_AUDIT.md`, bảng mapping + hash, semantic diff, readback log, screenshot + hash, sign-off. Mọi artifact gắn SHA-256 của bytes được kiểm.
