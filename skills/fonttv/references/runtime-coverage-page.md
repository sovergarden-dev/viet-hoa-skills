# Runtime coverage page: một ảnh phủ cả bảng chữ

Mục đích: người dùng chụp **một ảnh cho mỗi font** thay vì chờ gặp chữ lỗi trong lúc chơi. Proof sheet render từ atlas ngoài game không thay được ảnh này, vì nó bỏ qua layout, baseline và metrics của engine.

## 1. Chuỗi test

Dòng tham chiếu baseline ở đầu mỗi dòng (`Hx`) để thấy ngay chữ cao thấp lệch. Nhóm theo base để so dấu cạnh nhau.

```text
Hx a à á ả ã ạ ă ằ ắ ẳ ẵ ặ â ầ ấ ẩ ẫ ậ
Hx e è é ẻ ẽ ẹ ê ề ế ể ễ ệ i ì í ỉ ĩ ị
Hx o ò ó ỏ õ ọ ô ồ ố ổ ỗ ộ ơ ờ ớ ở ỡ ợ
Hx u ù ú ủ ũ ụ ư ừ ứ ử ữ ự y ỳ ý ỷ ỹ ỵ đ
HX A À Á Ả Ã Ạ Ă Ằ Ắ Ẳ Ẵ Ặ Â Ầ Ấ Ẩ Ẫ Ậ
HX E È É Ẻ Ẽ Ẹ Ê Ề Ế Ể Ễ Ệ I Ì Í Ỉ Ĩ Ị
HX O Ò Ó Ỏ Õ Ọ Ô Ồ Ố Ổ Ỗ Ộ Ơ Ờ Ớ Ở Ỡ Ợ
HX U Ù Ú Ủ Ũ Ụ Ư Ừ Ứ Ử Ữ Ự Y Ỳ Ý Ỷ Ỹ Ỵ Đ
Hx CHƠI DỮ LIỆU ĐẤT BẬT PHỤ chuột người ƯT
```

Dòng cuối là từ thật: chữ hoa có dấu chồng, `ƯT` (spacing móc), và các từ đã từng lỗi.

Dòng dài có thể tràn khung. Cắt thành nhiều chuỗi hoặc nhiều mục menu nếu consumer chỉ hiện một dòng ngắn.

## 2. Đặt chuỗi vào game

### Trước tiên: font nào thực sự cần ảnh?

Nếu nhiều font cùng lấy từ **một font nguồn** (P1 ghép 8 font TWAU vào Noto Sans), một ảnh chứng minh thiết kế đó, không phải 12 font. Chỉ những font khác thiết kế mới cần ảnh riêng (trên TWAU: `Cantoria_MT` serif, `Rockwell_*` slab, `Veteran_Typewriter_40` mono, `CCLegendary`/`ManlyMen` đậm).

**Ảnh chỉ được gán cho một font khi consumer đã được chứng minh.** Từng gán ảnh menu Settings cho `Rockwell_Std_Condensed_48_bold` chỉ vì tài liệu ghi vậy; phân tích ảnh cho thấy đó là sans nét mảnh, không phải slab. Ảnh không gán được thì ghi nhận nhưng không cấp bậc `runtime_verified`.

### Quy trình

1. Inventory consumer: màn hình nào dùng font nào. Chưa biết thì dùng màn hình có **vùng text lớn, tự xuống dòng** — nhãn menu một dòng không đủ chỗ cho coverage page.
2. Chọn id chuỗi: parse landb, tìm entry có `entry["index"] == id`. **`index` là trường riêng, không phải vị trí trong danh sách** — đọc theo vị trí sẽ sửa nhầm và kiểm cũng nhầm (`_index` đã gây hai lỗi liên tiếp).
3. Chỉ những archive mà bản patch **thực sự ghi** mới đóng gói lại được; archive khác chỉ là file copy nguyên bytes. Kiểm trước khi chọn mục tiêu.
4. Ghi bằng `serialize_landb(meta, entries, translations={index: text})`, rồi parse lại và **so chuỗi đã đọc được** với chuỗi định ghi; lệch thì dừng.
5. Repack, readback, đối chiếu tập member và đọc lại chuỗi từ container.
6. Staging ở thư mục riêng (ví dụ `build/archive_p1_coverage`), in sẵn hai lệnh: một để áp, một để lùi về bản đã duyệt. Không tự động ghi đè bản đang chạy.
7. Người dùng chụp ảnh, rồi trả text về bản chính và readback lại.

## 3. Đọc ảnh

- **Baseline:** đáy thân chữ cùng hàng với `H`/`x` đầu dòng.
- **Dấu chồng:** `ầ ấ ẩ ẫ ậ` phân biệt được từng cái.
- **Chấm dưới:** tròn, sát thân, không chạm dòng dưới.
- **Móc:** `ơ ư` móc nối vào thân; `ƯT` không dính.
- **Không tofu, không ký hiệu lạ.**

AI vision chỉ được xếp hạng ô nghi vấn cho người xem nhanh hơn. Kết luận gate 12 do người đọc tiếng Việt.

## 4. Cửa sổ duyệt font ngoài game (trang HTML tự chứa)

Khi người dùng phải soi cả bộ repertoire ngoài game, dựng một trang HTML tự chứa (woff2 subset nhúng base64 — một mặt chữ vẽ tay 29.8 MB subset còn 18 KB) với ma trận base × thanh điệu đầy đủ, các chuỗi UI thật của game, và các chuỗi corpus.

Hai thứ làm nó **đáng tin** chứ không phải trang trí:

* **Trang phải tự kiểm font.** Webfont nạp thất bại sẽ fallback im lặng, và người duyệt khi đó đang chấm **SAI mặt chữ**. So mực vẽ ra của vài ký tự test với `monospace`; số bằng nhau = nó không nạp. Hiện kết quả đó trong trang. Tự kiểm luôn đường cắt dấu và `localStorage`, để một tính năng hỏng là thấy được thay vì vắng mặt im lặng.
* **Trang phải cho thấy bytes đang duyệt chính là bytes đã deploy.** In sha256 của bản dựng mà mỗi mặt chữ đến từ đó trong panel chi tiết ký tự.

Ghi chú triển khai:

* KHÔNG quét pixel từng canvas để tìm hộp ink của một glyph — ở ~2M vòng lặp mỗi ô, ma trận 146 ô làm trang đông cứng. `ctx.measureText(ch).actualBoundingBox*` cho khoảng ink trong O(1); ánh xạ hộp theo đơn vị font đã biết lên đó.
* Cho trang cắt theo hộp của **chính dấu** ("chỉ hiện dấu") là cách duy nhất để phán **HÌNH** dấu ở cỡ người nhìn thấy được. Tính hộp dấu trong builder (hợp của các thành phần dấu đã đặt) và lưu theo từng ký tự; với glyph có dấu **native** thì không có parts list, nên suy hộp bằng cách trừ bbox của glyph base.
* Liệt kê luôn các ký tự mà **bản dịch dùng mà KHÔNG có trong repertoire** và hiện chúng ra — đó là câu trả lời trực tiếp cho "tôi đã thật sự nhìn thấy mọi ký tự chưa?", và nó bắt được dấu câu CJK hay một ký tự Cyrillic lạc mà không ai định đưa vào.

### Trang phải đi theo vòng duyệt, không phải danh sách tính năng

Vòng là **nhìn → phóng → đánh dấu → gửi**, và mỗi bước có đúng một điều khiển. Bản đầu gom năm toggle, bảy tab ngang nhau và một inspector luôn mở vào một màn hình, và phán quyết của người dùng là "hơi rối". Thứ thật sự làm nó dùng được:

* **Bấm vào ký tự KHÔNG được đánh dấu nó.** Ở bản rối, một cú bấm vừa chọn vừa gắn cờ, nên chỉ soi glyph thôi cũng để lại một vệt dấu và người dùng phải dọn sau khi nhìn. Chọn và phán là hai hành vi tách biệt: bấm chọn và mở inspector, `Space` (hoặc nút) mới đánh dấu. Giữ thêm một đường nhanh không cần khám phá: bấm chuột phải để gắn cờ mà không mở gì.
* **Inspector là một drawer mở ra khi chọn**, không bao giờ là panel đậu giữa toolbar và các chữ. Lưới repertoire phải là thứ đầu tiên trên màn hình.
* **Tiến độ nằm ở toolbar.** Số cờ và nút gửi luôn hiện, không giấu trong tab, để người duyệt luôn biết còn bao nhiêu.
* **Cho các tab phụ trọng lượng thấp hơn** (mờ hơn, nhỏ hơn, sau một dấu phân cách) thay vì bảy nút giống hệt nhau. Thứ bậc là toàn bộ khác biệt giữa "có tổ chức" và "chen chúc".
* **Chỉ dựng lại thứ đã đổi.** Chọn một glyph nên chỉ dịch highlight và vẽ lại drawer; serialize lại 700 dòng corpus mỗi lần bấm phím mũi tên là thứ làm trang chậm.
* **Một dòng gợi ý bỏ được** dạy mô hình một lần, rồi biến mất vĩnh viễn.
