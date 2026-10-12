# Đo cỡ chữ thật và nhận diện mặt chữ từ ảnh chụp màn hình

Áp dụng khi cỡ render và mặt chữ **không đọc được từ asset**, hoặc khi cần kiểm bằng chứng runtime từ ảnh người dùng gửi.

## 1. Cỡ render thật: suy từ một ảnh toàn màn hình

Cỡ thường KHÔNG nằm trong asset. Unity legacy `Font.m_FontSize` là cỡ raster của atlas (mọi mặt chữ đều khai cùng một giá trị 16), còn cỡ theo từng label của Adventure Creator nằm trong assembly ngoài, nên không MonoBehaviour nào trong asset để lộ nó.

Suy từ ảnh chụp. Với một chuỗi đã biết, bề rộng pixel khi vẽ bằng
`(tổng advance theo đơn vị font / upem) * fontSize`. Vậy **một phép đo bề rộng cho ra cỡ — và nhận diện mặt chữ nào đã vẽ dòng đó chính là cùng phép đo đó**: mặt chữ đúng là mặt cho ra cùng một cỡ khi suy từ hai dòng khác nhau của cùng một khối chữ.

Số thật từ ảnh 2560×1080 của hộp thoại: dòng 1 đo 1229 px, dòng 2 đo 430 px. Boopee suy ra 58.7 và 58.9 px (lệch 0.3%) trong khi mọi mặt khác suy ra lệch 1.1–2.0%, nên Boopee đã vẽ nó và cỡ là ~59 px em. Đối chiếu chéo bằng chiều cao dải: 53 px từ ascender tới descender trên khoảng ~0.9 em cho lại ~59 px. Menu cài đặt cho ~52.3 px em bằng cùng cách.

Cả hai đều cao hơn hẳn ngưỡng sống 24 px của Boopee, nên trong thực tế mọi dấu đều sống. Chỉ một phép đo đó đã trả lời câu hỏi mà đọc asset mãi không trả lời được.

Hai cái bẫy trong phép đo:

* **Hộp thoại bán trong suốt để cảnh lộ qua**, nên ngưỡng theo độ sáng sẽ bắt cả thế giới (sàn gỗ sáng đọc thành "chữ"). Lọc theo **trắng tinh** — `min(rgb) > 228 and (max-min) < 22` — mới tách ra đúng glyph.
* Lấy bề rộng dòng đầu từ khoảng ink của nó, và biết rằng tổng advance sẽ rộng hơn vài phần trăm; **so hai dòng của cùng một khối với nhau** thay vì tin một giá trị tuyệt đối.

Nhân lúc đo hộp, đo luôn tương phản — chữ hội thoại nằm ở 12.4:1 trên hộp giấy rách (trắng trên `(56,52,46)`), thoải mái, nhưng **nhãn tên người nói** là màu xám `(161,158,154)` chỉ đạt **4.63:1**, vừa qua WCAG AA. Báo nó như một phát hiện: đó là element sẽ hỏng trước tiên nếu phần mỹ thuật thay đổi.

## 2. Audit ảnh chụp: để model đọc chữ, để pixel đo

Phân công hiệu quả: model đọc ảnh **đáng tin ở việc ĐỌC chữ** và **không đáng tin ở việc phán glyph trông thế nào** — nó tạo ra bốn báo động giả trong dự án này. Nên nó cung cấp chuỗi, còn mọi thứ khác thì đo.

Tìm dải đúng cần ba lượt, vì một bộ lọc màu là không đủ:

* **trắng tinh** — `min(rgb) > 228 and (max-min) < 22`. Thử trước tiên, và nó cho đúng khoảng của hộp thoại.
* **tương phản cục bộ** — `grey - GaussianBlur(grey, 9) > 30`. Cần khi chữ bị hoà vào panel và không bao giờ đạt trắng tinh. Thiếu nó, hộp chọn ra **0 dải**.
* **ngưỡng hàng co giãn theo bề rộng** — `max(3, w // 120)`. Ngưỡng cố định gộp cả panel thành một dải trên mask nhiễu, và **cắt nó ra** tốt hơn **vứt nó**: cắt dải quá cao tại chính các cực tiểu trên row-profile của nó, vì viền panel giữ một sàn pixel lạc không bao giờ xuống dưới ngưỡng. Ba dòng từng về dưới dạng một dải 216 px và bị vứt là "quá cao" cho tới khi thêm bước này.

Rồi, khi đã biết chuỗi, đến phần chấm điểm — và đây là phần mất bốn lần:

* **Tối đa hoá số DẢI KHÁC NHAU, không phải số khớp.** Một mặt chữ sai luôn khớp được một dải nào đó ở một cỡ nào đó. Đếm khớp thô để ba dải nhiễu 25 px trong một mặt monospace thắng hai dòng hội thoại thật ở 59 px. Thứ nhận diện một mặt chữ là nó giải thích **mọi** dòng của khối **Ở CÙNG MỘT CỠ** với mỗi dòng nằm trên **MỘT DẢI KHÁC NHAU**. Hai chuỗi tranh nhau cùng một dải là dấu hiệu của mặt chữ sai.
* **Loại dải có chiều cao mâu thuẫn với cỡ.** Ink trải từ ascender tới descender, nên dải cao 70 px không thể là chữ 19 px. Đòi `0.40 ≤ h/S ≤ 1.50` là thứ cuối cùng giết được đáp án sai-mặt đã sống sót qua mọi phép khác.
* **Ưu tiên khoảng CHẶT hơn khi hai mask trùng nhau.** Mask tương phản cục bộ cũng bắt cả quầng của glyph, mà quầng chỉ **thêm** pixel, nên khoảng của nó rộng hơn và làm cỡ suy ra bị phồng — 66 px so với 59 px thật. Giữ cái chặt hơn, trừ khi nó dưới 70% cái rộng hơn và vì thế chắc chắn là một mảnh vỡ.
* **Ghép theo THỨ TỰ ĐỌC, không ghép-gần-nhất.** Ghép mỗi chuỗi với dải gần nó nhất để một mặt chữ sai thắng: menu cài đặt chấm `BradBunR 43px` bằng tiebreak sai số trung bình, trong khi cùng số pixel đó ghép bằng **khớp đơn điệu** cho `Boopee 52.3px` với **lệch 0.6% so với 9.4%** của mặt kế tiếp. Chữ trên màn xuất hiện theo thứ tự, nên phép ghép là một **gán đơn điệu bảo toàn thứ tự** (một DP nhỏ trên chuỗi × dải, cho phép bỏ qua ở cả hai phía); ghép-gần-nhất không phải bản yếu hơn của phép này, nó là một model khác và sai.
* **Dòng không đọc được thì truyền vào dưới dạng placeholder, không bỏ qua.** Một dòng menu nằm dưới highlight của mục đang chọn — một hộp sáng mà khoảng đo được (371 px) thuộc về cái hộp, không thuộc chữ. Đưa một phỏng đoán cho dòng đó làm bộ ghép buộc chuỗi của dòng KẾ sang dải sau và báo về một bản sinh đôi y hệt về số đo. Truyền `"(dòng đang chọn — không đọc được)"` vào chỗ đó giữ danh sách thẳng hàng và công cụ sau đó báo đúng rằng dải ấy không thuộc chuỗi nào.
* **Gặp thế hoà thì BÁO RA, đừng tự quyết.** `"Chất lượng đồ họa : Cao"` và `"Đặt lại dữ liệu thành tựu"` vẽ ra 355 px và 354 px trong Boopee ở 52.3 px — lệch 1 px. Không phép đo bề rộng nào tách được chúng, nên công cụ in "bề rộng không phân biệt được với" và để người đọc, vốn nhìn thấy dòng nào là dòng nào, quyết định.
* **Từ chối khi bằng chứng yếu.** Đòi ≥3 cặp khớp và sai số trung bình ≤3% làm công cụ nói "CHƯA ĐỦ TIN CẬY" thay vì gọi tên mặt chữ ít-sai-nhất. Một mặt chữ sai mà có con số kèm theo sẽ bị chép vào báo cáo như sự thật; một phép kiểm vô kết luận **là một kết quả** và phải được báo như vậy. Trước khi có ghép-bảo-toàn-thứ-tự, công cụ này từng tự tin trả `riffic-bold 32px` cho hộp thoại và `Boopee 19px` cho hộp chọn — cả hai đều sai, cả hai đều trông chính xác.

Đã đối chiếu với ground truth: hai dòng hội thoại đo tay 1229 px và 430 px, ba dòng hộp chọn 503, 526 và 203 px; công cụ trả 58.7/58.8 và 60.2/60.1/58.0 px trên Boopee, mỗi chuỗi nằm trên dải riêng của nó.

Đây là thứ đã tìm ra dấu tilde 47%. Audit cấu trúc đã cho nó PASS (mép dấu đúng chỗ và độ dày nét khớp); chỉ cỡ render mới lộ ra.

## 3. Không bao giờ nhận "thiếu dấu" từ model đọc ảnh — đếm điểm mực

Model đọc chữ nhỏ đã nhiều lần báo `chưa` thành `chua` (mất móc) và `Đổi` thành `Đôi` (mất hook). Cả hai đều sai. **Bốn báo động giả riêng biệt trong công việc này.**

Dấu hiệu loại trừ, chỉ cần một cái là đủ để bỏ qua phán quyết:

* nó **đọc sai những ký tự nào đang có trong ảnh** (nó đọc `Ã Õ ã ô à` thành `Ẵ Ỗ ẫ ỗ ạ` — một model không nhận ra được glyph thì không phán được dấu của chúng);
* nó mô tả một khác biệt về cỡ hay độ dày mà phép đo bác bỏ;
* nó báo một dấu "thiếu" trong khi phép đếm mực cho thấy dấu có đó.

Bác bỏ hoặc xác nhận bằng cách raster từng ô rồi đếm mực:

```python
# theo ô của từng ký tự: x0 = font.getlength(s[:i]), x1 = font.getlength(s[:i+1])
# so số điểm mực của cùng một ký tự trong các từ khác nhau
'chưa'[2] -> 445 px, 'lưu'[1] -> 445 px, 'ư' một mình -> 445 px   # giống hệt, móc có đó
'Đổi' -> 1670 px mực   'Đôi' -> 1544 px   => hook tồn tại (126 px của nó)
```

Chỉ sau khi phép kiểm pixel cho kết quả âm thì mới là lỗi thật. Hai lỗi trong phiên này **thật** và được tìm ra bằng cách này: một chiếc móc bị chôn, và một dấu chấm `i` bị giữ lại.
