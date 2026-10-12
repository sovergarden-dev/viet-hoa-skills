# Hai lần thử gán ảnh → font, và vì sao không dùng được

Gate 12 cần ảnh chụp thật. Nhưng khi consumer **không** đọc được từ dữ liệu (menu archive không có member `.font`, Lua đã biên dịch không có chuỗi tên font), thì câu hỏi là: pixel có nói được font nào đã vẽ không?

Hai công cụ đã được viết, đo trên chính ảnh của TWAU, và **cả hai đều bị xoá** sau khi đo. Ghi lại đây để không ai dựng lại lần thứ ba.

## Lần 1 — khớp template theo pixel

Dựng lại chuỗi bằng từng font theo đúng cách engine xếp chữ (ô glyph từ atlas đặt tại `rec[9]/rec[10]`, bút chạy theo `rec[11]`), rồi tìm chỗ khớp nhất bằng tương quan FFT. Điểm = tỉ lệ mực template trùng mực ảnh.

Màn prologue, nơi font **chắc chắn** là `Cantoria_MT` (serif duy nhất):

```
ManlyMen_BB_60        0.2241
Cantoria_MT           0.2227   <- font đúng, không thắng
AvantGarde_LT_Book_14 0.2213
... toàn bộ khoảng cách: 0.02
```

Vì sao hỏng: ảnh đầy chữ, nên tỉ lệ "mực template trùng mực ảnh" thưởng cho vùng nhiều mực và **bỏ qua hình dạng**. Điểm 0 tuyệt đối còn dễ đọc sai: nó thường là lỗi tỉ lệ (template rộng hơn ảnh) chứ không phải sai font.

## Lần 2 — phân loại thiết kế theo số đo

Bốn đặc trưng bất biến theo tỉ lệ, đo **theo từng dòng** rồi lấy trung bình:

| đặc trưng | cách đo | ý nghĩa |
|---|---|---|
| `density` | mực / diện tích dòng | độ đậm, có chân serif |
| `stroke` | nửa bề rộng nét / chiều cao dòng | độ đậm |
| `stroke_cv` | biến thiên nửa bề rộng nét | serif và nét mảnh thì biến thiên cao |
| `mono_peak` | đỉnh tự tương quan của profile cột | font đơn cách lặp theo bước cố định |

Kết quả trên ảnh prologue:

```
stroke_cv:  ảnh 0.27   |  template serif 0.48
stroke:     ảnh 0.047  |  template 0.044-0.137
distance:   AvantGarde_40 0.3248 < Cantoria_MT 0.3426   -> INDISTINGUISHABLE
```

Vì sao hỏng: ảnh chơi game ở cỡ nhỏ, **nhị phân hoá làm mất nét mảnh** — dấu hiệu serif bị xoá *trước khi* kịp đo. Sửa được hai lỗi cơ học (chuẩn hoá theo cả khối thay vì từng dòng; chuỗi bị xuống dòng thì phải so cụm ngắn), nhưng lỗi mất nét mảnh thì không sửa được ở độ phân giải này.

## Kết luận — luật đang áp dụng

Ảnh chỉ cấp được `runtime_verified` cho một font khi **biết consumer**:

1. **Có tham chiếu member** — như `uiz_ConsoleButtons.lua` nêu tên `ITC_Kabel_Book.font`. Đây là bằng chứng mạnh nhất, và nó không phụ thuộc pixel.
2. **Thiết kế là duy nhất trong build** — serif, slab, mono, đậm: nếu chỉ một font mang thiết kế đó thì gán được bằng loại trừ. Phải ghi rõ là loại trừ, không phải khớp pixel.
3. **Nhiều font dùng chung một font nguồn** (TWAU: 8 font sans đều là Noto Sans) — **không** ảnh nào tách được, và cũng không cần: cái được chứng minh là *thiết kế*, không phải từng file.

Ảnh không có consumer thì ghi vào `screenshots_all` với `font: null` và **không** cấp mức nào. `scripts/p1_attach_screenshot.py` từ chối ghi ảnh vào manifest nếu thiếu `--cite`.
