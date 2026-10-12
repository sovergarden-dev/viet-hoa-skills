# Thang đưa tiếng Việt vào game

Dừng ở bậc đầu tiên fail. Mỗi lần thử chỉ đổi một biến. Không sửa font và bảng chữ trong cùng một lần.

1. **Marker.** Một chuỗi chắc chắn hiện ở màn đầu: marker ASCII duy nhất trước, rồi mẫu Việt `ă â đ ê ô ơ ư` và dấu kép. Giữ schema/token/độ dài theo format; không đổi canonical để thử. Chưa import cả corpus.
2. **Readback.** Marker nằm đúng key, đúng asset, đúng hash trên bản sao.
3. **Mount.** Process đang chạy đọc đúng file đó: slot locale game thật sự chọn, thứ tự pak, catalog/hash, cache. Không thấy marker chưa đủ kết luận mount: kiểm selected key, điều kiện UI, encoding và font lookup; ASCII hiện nhưng Việt mất thì chuyển font/encoding contract.
4. **Renderer.** Khóa đúng widget: TMP, IMGUI, `.ufont`, bitmap, hay atlas tĩnh. Không sửa TTF khi runtime vẽ atlas cũ.
5. **Một ảnh, một bucket.**
   - Vẫn tiếng gốc hoặc trống: chưa đủ bằng chứng; đối chiếu ASCII marker, binding và encoding trước phân loại.
   - Ký tự lạ có quy luật: kiểm text encoding; nếu byte encoder đúng nhưng glyph slot sai, chuyển route B/C của `fonttv`.
   - Ô vuông: thiếu glyph ở font/atlas đang vẽ.
   - Có chữ Việt nhưng sai weight, baseline, fallback: đúng lớp font, chỉ font đó.
   - Màn khác sai: bảng hoặc font thứ hai. Chỉ sau khi màn đầu đúng.
6. **Scale.** Marker và dấu đúng rồi mới import phần còn lại, rồi inventory, nameplate, font phụ.

Ghi tiếng Việt vào slot game thật sự load. Không tạo locale mới rồi cho rằng game sẽ chọn. Hai container chỉ khi exact build/format chứng minh cần; có Level Sequence không tự đủ điều kiện.

Mỗi lần thử ghi một dòng, không viết báo cáo:

```text
step=3 asset=pakchunk0 hash=abc123 key=UI/START shot=menu.png bucket=string_not_reached next=fix_mount
```

`step` là bậc đang fail. `bucket` là một trong: `string_not_reached`, `encoding`, `missing_glyph`, `metric`, `second_surface`. Session sau đọc dòng cuối, không khám phá lại. Ảnh là bằng chứng của một widget, không phải cả game.

QA ngôn ngữ sau cron: người xem là cổng bắt buộc. Model thứ hai có thể dùng dò lỗi thừa, nhưng không thay người xem chốt.

## Font ownership

Sau khi text path được chứng minh, `fonttv` quyết định route A/B/C và P1/P2. Không áp luật donor P2 cho P1 thay trọn glyph. Không nhập tọa độ atlas từ case khác.
