# bientaptay

Ứng dụng biên tập trực tiếp các CSV authoritative. Release hiện tại: **0.7.0**. Không tạo database riêng và không cần Excel.

## Mở ứng dụng

Chạy `Launch-BienTapTay.cmd`.

## Quy tắc an toàn

- Bộ chọn **Phạm vi** chuyển giữa `Kịch bản`, `UI hệ thống` và `UI runtime`; mỗi lựa chọn ghi thẳng đúng CSV nguồn.
- `Ctrl+S`: lưu tab/bảng hiện tại. Trước khi ghi, app validate toàn bộ dòng của CSV đang mở; một dòng lỗi có sẵn cũng chặn transaction. App chỉ tự đổi `pending ↔ translated` trên dòng thật sự dirty.
- `Ctrl+F`: lọc trong nguồn, tham khảo, key, ghi chú và bản dịch của bảng đang mở.
- `Ctrl+Shift+F` hoặc **Mọi bảng**: tìm chỉ đọc xuyên mọi CSV authoritative, hiển thị bảng + trường khớp + exact key; bấm đúp hoặc **Tới exact key** để chuyển đúng bảng. Có edit chưa lưu thì app không tự chuyển bảng.
- `Ctrl+H`: tìm/thay chuỗi nguyên văn chỉ trong cột bản dịch của bảng hiện tại. App luôn dựng preview, đếm occurrence và kiểm protected token; một dòng lỗi sẽ khóa cả batch. Kết quả chỉ nằm trong RAM cho tới khi bấm `Ctrl+S`.
- `Ctrl+G`: dán full canonical key để tới đúng dòng Hermes báo. Exact key khác `F3`: `F3` chỉ tìm dòng pending/cần ngữ cảnh/lỗi QA kế tiếp.
- `F5`: nạp lại dữ liệu từ đĩa.
- Bấm **Trang N / M** để nhập số trang cần tới; Enter hoặc **Đi tới** để nhảy thẳng.
- Bấm **17 hàng** để đổi số dòng cố định mỗi trang: 10, 17, 25, 50 hoặc 100. Mũi tên trái/phải chuyển theo số dòng đã chọn.
- `F3` hoặc `Ctrl+Enter`: nhảy tới dòng chưa dịch, cần ngữ cảnh hoặc lỗi QA.
- **Hoàn tác dòng**: trả riêng target, trạng thái và ghi chú của dòng đang chọn về snapshot vừa lưu; không đọc/ghi lại cả CSV.
- **Hoàn tác batch**: sau `Thay tất cả`, mở lại `Ctrl+H` để hoàn tác toàn bộ batch gần nhất trước khi lưu. Nếu một dòng trong batch đã bị sửa tiếp, app từ chối hoàn tác một phần và tắt thao tác để không ghi đè edit mới.
- Mỗi `project.json` chỉ cho một writer giữ quyền: app dùng named Mutex và byte-range lock dùng chung với Python/Hermes. Mở instance hoặc writer thứ hai cùng project sẽ bị từ chối; process chết tự nhả lock.
- App nhớ vị trí/kích thước/maximize, tab, bảng dịch, filter, exact key đang chọn, trang, số hàng, bookmark, cỡ chữ, tỷ lệ splitter và độ rộng cột. Session ghi nguyên tử; bounds ngoài màn hình được kéo về vùng nhìn thấy.
- Glossary ưu tiên cụm dài không chồng lấn; không hiện protected token như `<br>` và bỏ character term CJK quá ngắn gây false-positive.
- Pane phải hiển thị context thành các lượt hội thoại trong cùng scene: gộp speaker liền nhau, giữ narrator/lựa chọn/luận điểm và đánh dấu lượt chứa dòng đang chọn. Mỗi card bấm được để tới exact key đầu lượt; **Đánh dấu** lưu `(bảng,key)` vào `session.json`.
- Mỗi bảng chỉ cho sửa bản dịch, trạng thái và ghi chú; key/source/metadata là bất biến.
- Mất/dư protected token sẽ chặn lưu.
- Mỗi lần lưu dùng temp + replace nguyên tử và tạo `.bientaptay.bak`.
- Mỗi reference khai `keyColumn` rõ ràng. Glossary chặn key trống/trùng, translation trống và status lạ; pronouns còn chặn profile thiếu dữ liệu và `evidence_keys` không tồn tại trong full canonical key set.
- Nếu Hermes hoặc công cụ khác sửa bất kỳ canonical/reference CSV nào, tab **Thay đổi ngoài** giữ file + diff theo exact key giữa snapshot đã nạp, edit local và file ngoài. App sạch tự nạp đúng file nhưng vẫn giữ lịch sử diff; app đang dirty hoặc file bị xóa/chuyển chỗ sẽ khóa mọi thao tác lưu cho tới khi nạp lại. Không fallback positional khi key trống/trùng.
- Tab **QA nhất quán** là bộ quét chỉ đọc, chạy theo yêu cầu hoặc khi mở tab. Lần đầu mở tab, filter quyết định mặc định **Chưa phân loại**. Nó gom ba nhóm: cùng source + speaker có target khác nhau, glossary locked/reviewed/approved bị thiếu trong target, và form xưng hô khác profile khi nguồn Nhật có dấu hiệu ngôi thứ nhất/thứ hai. Có filter loại/speaker/quyết định và ba trạng thái triage: **Cần sửa**, **Chấp nhận khác biệt**, **Đã xử lý**.
- **Lưu quyết định** ghi sidecar và giữ cảnh báo đang chọn. **Lưu & kế tiếp** ghi rồi nhảy tới cảnh báo còn lại trong hàng đợi hiện tại. Trên tab QA, `Ctrl+S` lưu sidecar chứ không ghi canonical; `Ctrl+Shift+Enter` là lưu-và-kế-tiếp. `F3` / `Ctrl+Enter` vẫn là next-work-item, không đổi hàng đợi QA.
- Mỗi quyết định QA lưu có chủ ý vào `qa-decisions.json` cùng fingerprint source/target. Nếu nội dung đổi, quyết định cũ không được áp dụng và cảnh báo trở lại **Chưa phân loại**. Sidecar này không sửa canonical và không phải receipt của `Ctrl+S`.
- **Xuất báo cáo** ghi JSON/CSV bằng chứng chỉ đọc (`bientaptay-qa-report/v1`); không import lại, không phải receipt từng lần lưu, và không đè canonical/sidecar/`app/`.
- Nếu `qa-decisions.json` hỏng hoặc không đọc được, app vẫn cho biên tập canonical nhưng khóa mọi thao tác ghi quyết định QA và giữ nguyên sidecar để sửa bên ngoài.
- Cảnh báo được chọn hiển thị các target của mọi full related key để so sánh; nút trước/sau và **Tới key này** luôn điều hướng bằng exact key. **Sao chép context** đưa project, bảng, cảnh báo, source/reference, target, glossary và xưng hô vào clipboard; chỉ retry khi clipboard trả `CLIPBRD_E_CANT_OPEN`; không tạo corpus phụ.
- Lỗi đã hiện cho người vận hành (sao chép clipboard hết lượt, xuất báo cáo thất bại, sidecar QA chỉ đọc) có thể ghi `<project>/diagnostics/app.log` dạng JSONL đã che, tối đa 64 KiB, giữ `app.log` / `app.log.1` / `app.log.2`. Sao chép/lưu thành công không ghi. `diagnostics/` không phải canonical và publisher/receipt bỏ qua.
- Chuyển bảng bị khóa nếu còn thay đổi chưa lưu, tránh bỏ sót edit.
- Bảng thuật ngữ và xưng hô là CSV trong `data/`; thay đổi được lưu trực tiếp.
- Bộ chọn **Cỡ chữ** hỗ trợ 90/100/115/130%; `Ctrl++`, `Ctrl+-`, `Ctrl+0` đổi/reset nhanh. Mọi màu trạng thái dùng semantic brush; Windows High Contrast lấy palette hệ thống. Process được pin `PerMonitorV2`; smoke còn ép cửa sổ `1080×700` ở font 130% để chặn control thiết yếu bị cắt. Icon có accessible name và control chính có tab order/focus ring rõ.

`data/glossary.csv` có thuật ngữ hệ thống và tên nhân vật từ nguồn game. `data/pronouns.csv` đã phân loại đủ 41 speaker với form chính, ngoại lệ theo scene, trạng thái evidence và full canonical key làm bằng chứng. Alias không có lời thoại dùng `inherited`; speaker im lặng dùng `not_applicable`; speaker gộp nhiều danh tính dùng `mixed_context`, không ép một cặp đại từ giả.

Tab **Dự án** hiển thị hash, đường dẫn của mọi bảng dịch và receipt/manifest/patch liên quan. Khi game update, Hermes reconcile build mới vào đúng CSV. App tự nhận file đổi và hiển thị các dòng `pending` mới, không cần import/export.

Artwork Control Panel là sprite bake chữ, không phải text CSV; app chỉ quản lý phần text. Sửa artwork vẫn đi qua builder/round-trip riêng.

## Writer ngoài và phát hành

- Mọi deterministic writer chạy qua `python bientaptay/writer_lock.py run --project bientaptay/project.json -- <writer-command>`; nhận `LOCK-REFUSED` thì dừng, không retry ghi đè.
- `bientaptay\Launch-Publish.cmd` là lệnh phát hành duy nhất. Launcher chỉ gọi Python `release_publish.py`; pipeline khóa writer, snapshot mọi translation/reference CSV, chạy test + validator + benchmark + WPF smoke, publish staging, kiểm metadata phiên bản, chứng minh hash/count không đổi, promote có rollback rồi đọc ngược `install-receipt.json`.
- Receipt v3 ghi metadata `qa_decisions`: sidecar vắng là hợp lệ; sidecar hỏng/malformed làm fail release. Receipt không chứa file báo cáo QA hay đường dẫn `diagnostics/`.
- `install-receipt.json` là receipt phát hành, không phải nhật ký từng lần `Ctrl+S`.

## Baseline hiệu năng 34.530 dòng

Chạy lại bằng:

`dotnet run --project "bientaptay/tests/BienTapTay.Benchmarks/BienTapTay.Benchmarks.csproj" --configuration Release -- "bientaptay/project.json" "bientaptay/performance-baseline.json" 7`

Baseline tham chiếu của corpus phát triển 0.6.0 ngày 2026-09-02 trên .NET 8.0.24, 16 logical processors, query cố ý không khớp để ép full scan:

| Đường đo | Median | Max |
|---|---:|---:|
| Nạp config + 34.530 dòng | 253,107 ms | 253,107 ms |
| Dựng view-model + validation | 181,779 ms | 217,592 ms |
| Filter bảng 34.367 dòng | 12,894 ms | 14,159 ms |
| Tìm xuyên 34.530 dòng | 21,344 ms | 29,639 ms |
| QA nhất quán toàn project | 174,783 ms | 490,205 ms cold |

Đổi search sang `OrdinalIgnoreCase` ổn định theo locale đã giảm filter 95,9% và project search 94,2%. QA median dưới 200 ms và cold dưới 500 ms, nên 0.6.0 không thêm background worker/progress/cancel chưa cần thiết. Mỗi project tự tái tạo `performance-baseline.json`; timing là số đo, không phải quality gate theo tốc độ máy.
