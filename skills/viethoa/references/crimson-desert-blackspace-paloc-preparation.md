# Crimson Desert — BlackSpace `.pamt`/`.paz` và `.paloc`

Case evidence cho quy trình chuẩn bị localization của Crimson Desert trên Pearl Abyss BlackSpace Engine. Không mặc định áp dụng cho game/build khác.

## Build đã chứng minh

- Steam App ID: `3321460`
- Build ID: `24236217`
- Depot: `3321461`; manifest: `3181503578355214830`
- Executable: `bin64/CrimsonDesert.exe`
- Archive localization English: group `0020`, entry `gamedata/localizationstring_eng.paloc`
- Archive UI có khả năng nằm ở group `0012`; đây mới là discovery evidence, chưa phải coverage proof.

Khóa lại build ID, source hashes và inventory ở mỗi phiên bản. Không tái sử dụng số liệu/hashes của case này cho build mới.

## Công cụ và tuyến extract đã chứng minh

Các repo MIT hữu ích:

- `lazorr410/crimson-desert-unpacker`: parser PAMT, ChaCha20 filename-derived key, LZ4 và repack.
- `MrIkso/CrimsonDesertTools`: parser BlackSpace/PALOC và ImHex template.
- `NattKh/CrimsonDesertModdingTools`: PAZ/PABGB parsers và schemas.

Ghim commit trong project manifest thay vì chạy trực tiếp từ nhánh nổi.

Quy trình an toàn:

1. Chỉ sao chép `0020/0.pamt` và `0020/0.paz` vào workspace; hash bản sao và nguồn.
2. Parse PAMT trước. Entry đã thấy có `comp_size=7,461,110`, `orig_size=16,815,038`, compression type `2`.
3. Dù metadata parser có thể báo `encrypted=false`, blob PALOC thực tế cần **ChaCha20 decrypt trước LZ4 decompress**. Dùng basename lowercase `localizationstring_eng.paloc` để derive key/IV.
4. Sau decrypt, LZ4 block decompress tới exact `orig_size`.
5. Hash extracted PALOC, parse cấu trúc và tạo canonical CSV; không dịch trong bước preparation.

### Pitfall: tin cờ `encrypted` quá sớm

Extractor phổ thông có thể bỏ decrypt vì chỉ gắn encryption cho XML, khiến LZ4 trả lỗi corrupt input. Khi một entry LZ4 thất bại:

- kiểm raw header;
- thử deterministic filename-derived decrypt trên bản sao;
- chỉ chấp nhận nếu decrypt + decompress tạo exact `orig_size` và parser cấu trúc đọc hết file không trailing/truncation;
- không sửa live archive để thử.

Đây là controlled format probe, không phải lý do để decrypt bừa mọi entry.

## Cấu trúc PALOC đã chứng minh

Little-endian:

```text
u32 header
repeat until EOF:
  u32 pad
  u32 key_len
  u8  key[key_len]       # UTF-8
  u32 text_len
  u8  text[text_len]     # UTF-8
  u32 index
```

ImHex equivalent:

```text
struct TextEntry {
  u32 pad;
  u32 keyLen;
  char key[keyLen];
  u32 textLen;
  char text[textLen];
  u32 index;
};
```

Parser gate:

- bounds-check mọi `u32` và length trước slice;
- UTF-8 decode nghiêm ngặt;
- đọc tới exact EOF, không trailing bytes;
- unique stable keys;
- canonical key là `(domain, key)`, domain ví dụ `localizationstring_eng`;
- giữ `pad` và `index` trong metadata/notes để roundtrip;
- bảo toàn protected tokens trước mọi merge.

Build trên cho 187,521 stable keys duy nhất. Số lượng chỉ là case evidence, không phải invariant.

## Preparation-only gate

Khi người dùng yêu cầu chuẩn bị rồi chờ:

- tạo workspace, project state, glossary/style guide, tool pins, source/extracted/canonical/reports/backups/incoming/handoff/release/temp;
- canonical CSV có toàn bộ hàng `pending`, `translation_vi` trống;
- ghi rõ `translation_started=false`, `live_game_modified=false`;
- state cuối: `READY_TO_TRANSLATE_WAITING_FOR_USER`;
- không tạo cron, không stage batch, không sinh bản dịch;
- chỉ làm one-row repack/import proof khi có tuyến writer đảo ngược được và trước lần import đầu. Nếu chưa chứng minh, ghi gate còn thiếu, không tuyên bố import-ready.

## Repack constraints cần kiểm lại trước import

Theo tooling/community documentation:

- PAMT không được sửa nếu game kiểm integrity;
- payload repack phải khớp kích thước/ràng buộc entry;
- bảo toàn timestamp PAZ nếu build kiểm CreationTime;
- thử trên bản sao, reload/reparse và hash untouched regions;
- runtime proof vẫn do người dùng chạy đúng build và gửi checkpoint.
