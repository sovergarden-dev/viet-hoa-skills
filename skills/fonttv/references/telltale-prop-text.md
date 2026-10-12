# Text không nằm trong LANDb: prop slot [V]

Không phải mọi chuỗi người chơi nhìn thấy đều ở `.landb`. TWAU còn vẽ text từ các file `.prop`, và bỏ sót chúng nghĩa là cả một màn hình vẫn tiếng Anh giữa UI đã Việt hoá — đúng lỗi đã gặp ở màn thống kê lựa chọn (`LỰA CHỌN CỦA NGƯỜI CHƠI` nhưng câu hỏi vẫn `Did you give Faith your money?`).

## 1. Tìm text bị bỏ sót

Đừng đoán theo tên file. Quét thẳng byte của container:

```
với mỗi archive:
    ttarchext -l 54 <arc> .      -> bảng offset/kích thước từng member
    quét raw byte tìm câu ASCII (>= 15 ký tự, có dấu cách, >= 3 từ)
    offset -> member nào phủ offset đó => tên file cần sửa
```

Lọc nhiễu: `.landb` của các locale khác **cũng chứa tiếng Anh** (bản gốc nhồi nguyên văn) — chỉ slot locale đang dùng mới quan trọng. Metadata (`dlg_id:`, GUID, timestamp, `.d3dmesh`, `gamecontrollerdb.txt`, `fx_*.prop`) không phải text người chơi.

Kết quả đo trên TWAU (2026-09): 48 archive, 168 member có text Anh, trong đó **6 file prop người chơi nhìn thấy**: `choice.prop`, `stats.prop`, `ratings.prop`, `feed.prop`, `caboose.prop`, `prefs_connectedcontent.prop`. Toàn bộ 101 `.landb` slot English đã khớp bản dịch (so hash) ⇒ thoại phủ đủ, lỗ hổng nằm hết ở prop.

## 2. Hai họ format prop

| họ | nhận ra bằng | ví dụ |
|---|---|---|
| T3Meta | chuỗi node `08 00 00 00 00 00 00 00 [size u32][count u32]`, `size` tính từ chính trường size tới hết node | `choice.prop` |
| 5VSM | magic `5VSM` ở offset 0 | `stats.prop`, `ratings.prop`, `feed.prop` |

Cả hai đều có trường kích thước lồng nhau. **Đừng sửa độ dài chuỗi** trừ khi đã viết được writer đúng cho cả hai họ.

## 3. Slot và khoá ngôn ngữ

```
[8 byte key][uint32 độ dài][đúng bằng đó byte]     key = hash tên thuộc tính / ngôn ngữ
```

Khoá đã gặp ở `choice.prop`: `b1a26dad8ca8b851` = **English** (slot phải dịch), `ccb582fb752f3b2a` FR, `e0a0b5c8f4d52fa9` DE, `a80c49748a9a1bd5` ES, `1055c73953f655a9`/`4a4645fcf2912773` = biểu thức GUID/`dlg_id` (logic, không dịch), `8549893e89f5b237` timestamp.

**Cùng một tính năng dùng khoá khác nhau ở file khác nhau** — `stats.prop` để câu hỏi dưới khoá `da198f61862f2e66`, `prefs_connectedcontent.prop` để "Title" dạng ASCII thật (`0000005469746c65`). Vì vậy hãy **dịch theo nội dung text**, không theo khoá: khớp câu hỏi nguyên văn, còn câu kết quả khớp theo mẫu `trước + số + sau`.

## 4. Bản vá: giữ nguyên độ dài

Encode tiếng Việt bằng **vn128 1 byte** rồi **đệm cho đúng bằng độ dài byte của bản tiếng Anh**. Khi đó mọi trường size lồng nhau vẫn đúng, file vẫn cùng kích thước ⇒ không cần viết writer cho T3Meta/5VSM.

- Đệm bằng dấu cách ở cuối; nếu chuỗi kết thúc bằng `\n` thì **đệm trước `\n`**, giữ `\n` ở vị trí cuối.
- Số phần trăm giữ nguyên từng chữ số (engine thay số lúc chạy) — chỉ dịch phần chữ quanh nó.

Kiểm bằng `scripts/ttprop_slots.py --verify ORIG PATCHED --charset DIR --plan PLAN.json`. Bất biến bắt buộc:

1. file cùng kích thước;
2. số slot, offset, độ dài từng slot không đổi;
3. **mọi byte đổi phải nằm trong thân một slot** (thiếu luật này, một file bị hỏng byte ngoài slot vẫn PASS — đã xảy ra thật);
4. slot đã dịch khớp đúng text trong plan, decode lại được, và không có `%%`.

## 5. Bẫy đã gặp thật

- **Vùng node bị nuốt làm một "slot".** Luật "tỉ lệ byte in được" đủ để một node T3Meta (chứa cả en/fr/de/es) được coi là *một* slot, nên bộ quét nhảy qua các slot thật bên trong và **bỏ sót tiếng Anh ngay giữa file đã vá**. Phát hiện bằng cách kiểm lại bản live chứ không tin bản staged. Luật đúng: payload text thật **không được chứa NUL/byte điều khiển** (trừ `\n\r\t`).
- **Ngưỡng quét quá cao bỏ sót nhãn ngắn.** Bộ quét đầu đòi câu ≥ 15 ký tự và ≥ 3 từ, nên `PREVIOUS MENU` (13 ký tự) nằm trong `uiz_button_back.prop` bị bỏ qua — người chơi vẫn thấy tiếng Anh ở góc màn. Quét lại prop với ngưỡng thấp (≥ 6 ký tự, ≥ 2 từ, có stopword) mới thấy: `uiz_button_back.prop`, `ui_panel_episode.prop` (`EPISODE`), `ui_menu_chapterselect_episode4/5.prop` (`Episode 4/5`).
- **Đừng đòi slot phải có dấu cách.** `EPISODE` không có dấu cách nên bộ kiểm không thấy nó là slot, còn bộ vá thì thấy; sau khi đệm thì bộ kiểm lại thấy ⇒ hai bên lệch nhau và verify báo FAIL sai. Luật đúng: payload là text nếu ≥ 90% byte in được **và** (có dấu cách **hoặc** khớp mẫu chữ-số-câu).
- **Archive Menu là phạm vi vá riêng.** Bản P1 chỉ gồm 5 archive Project; nhãn UI lại nằm ở archive Menu (`Fables_pc_Menu_data` + 4 `*_Menu_all`). Nguồn để dựng lại chúng là **chính game**, không phải `build/archive_p1` (trong đó không có archive Menu).
- **`%%`**: regex số của tôi đã bao gồm dấu `%`, mảnh sau còn thêm `%` nữa ⇒ `78%%`. Kiểm tự động phải có luật `%%`.
- **Bảng dịch không lưu ra đĩa**: sinh lại từ bảng thiếu thì 3 file **hoàn nguyên về tiếng Anh** mà verify vẫn PASS (vì file giống bản gốc thì đương nhiên hợp lệ). Luôn ghi bảng dịch ra JSON và kiểm lại *có thật sự còn slot tiếng Việt*.
- `ttarchext -m` **không có `-f`** dễ treo/không trích gì; luôn kèm filter (`-f "*.lenc"`, `-f "choice.prop"`). `-m` giải mã `.lenc` thành `.lua` (script) — prop thì không cần.
- Script `.lenc` giải mã ra Lua bytecode: chuỗi hằng vẫn đọc được, nên **quét tên font trong đó được**, nhưng đó là cách duy nhất tìm consumer trong dữ liệu.
- `.dlog` có nhiều tiếng Anh nhưng là **ghi chú của lập trình viên** ("I had to delete a bunch of the cut folder stuff on 6-28-13") trong dữ liệu nhị phân — không hiển thị, đừng dịch.
- `ttarchext` là binary Windows: đường dẫn kiểu MSYS (`/tmp/...`) làm nó báo `Error: No such file or directory`.

## 6. Tầng cache tải từ server trong Documents [V]

Màn `LỰA CHỌN CỦA NGƯỜI CHƠI`, popup cộng đồng và feed **không** lấy chữ từ archive. Chúng lấy từ cache server trong thư mục save:

```
%USERPROFILE%\Documents\Telltale Games\The Wolf Among Us\
  IN_choice_tracker    JSON: 28 câu hỏi + 75 dòng kết quả; mỗi chuỗi có 4 ngôn ngữ
                           (german/spanish/french/english) + `percent` theo server (84.5%, 15.5%...)
  IN_caboose           JSON: header + description của popup cộng đồng
  IN_developer_feed    JSON: text của feed
  choice.prop, caboose.prop, feed.prop   bản prop cục bộ, nằm cạnh save
```

Vì vậy vá `choice.prop` trong archive là **không đủ**: câu hiển thị vẫn tiếng Anh vì nó đến từ `IN_choice_tracker`. Đã gặp đúng cảnh này — archive sạch tiếng Anh, màn vẫn tiếng Anh, và nguyên nhân chỉ lộ ra khi quét cả thư mục save.

Cách sửa:

1. Sao lưu `.bak` **trước khi ghi** — đây là dữ liệu người chơi, không phải file game.
2. JSON không có trường độ dài ⇒ dịch tự do, không cần đệm; giữ **nguyên số phần trăm** vì đó là số của server.
3. Chỉ sửa khoá `english`; mọi ngôn ngữ khác phải nguyên byte.
4. Prop cục bộ trong thư mục save cũng phải vá như prop trong archive (giữ nguyên độ dài).
5. **Đặt read-only cho các file này** (`os.chmod(p, stat.S_IREAD)` / `attrib +R`): game ghi bằng `open(...,"wb")` nên sẽ nhận `EACCES` và giữ nguyên nội dung đã vá.

### 6b. Game tự tải lại rồi ghi đè [V]

Đã gặp đúng cảnh: vá 5 file xong, mở game, **cả 5 file trở về nguyên bản tiếng Anh** (sha trùng đúng bản `.bak`, mtime = lúc game khởi động). Thủ phạm không phải Steam Cloud (TWAU appid 250320 không bật cloud) mà là dịch vụ đồng bộ của Telltale, tên host **nằm trong `TheWolfAmongUs.exe`**:

```
https://services.telltalegames.com/1/syncfs/        <- đồng bộ file, ghi đè cache
https://services.telltalegames.com/1/bulkresource   <- tải nội dung (choice/feed/caboose)
```

Cách xử (dùng cùng lúc cả hai):

1. Vá file, rồi **khoá read-only** — chặn đường ghi tại chỗ.
2. Chặn host ở `C:\Windows\System32\drivers\etc\hosts`:
   ```
   0.0.0.0 services.telltalegames.com
   ```
   (sao lưu hosts trước; không cần quyền admin trên máy này, nhưng nếu bị từ chối thì phải chạy bằng quyền quản trị).
3. Kiểm tra tên host bằng cách quét chuỗi trong `TheWolfAmongUs.exe` — **đừng đoán** host, và đừng kết luận "Steam Cloud" khi chưa đọc `appmanifest` của appid.

Bài học thứ tự chẩn đoán: **file đã vá bị hoàn nguyên ⇒ đi tìm nguồn ghi đè trước khi vá lại.** So `sha256` và `mtime` với bản `*`.bak` là cách nhận ra ngay.

`percent` không nhất thiết xuất hiện trong câu (nhóm "Bạn đã cứu / không cứu Prince Lawrence" có 3 lựa chọn không kèm số) — đừng coi đó là lỗi.
