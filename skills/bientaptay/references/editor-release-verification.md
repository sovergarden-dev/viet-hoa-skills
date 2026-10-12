## Verification

Hoàn tất chỉ khi:

- [ ] core tests pass, gồm full-row save preflight và reference validator theo explicit `keyColumn`;
- [ ] WPF startup/first-layout smoke pass, gồm lock hai chiều WPF ↔ Python/Hermes;
- [ ] smoke đóng/mở nhiều cửa sổ chứng minh bounds/maximize, tab, bảng, filter, exact selected key, page và page size phục hồi;
- [ ] `Ctrl+G`, longest-match glossary và hoàn tác một dòng có regression test;
- [ ] find/replace atomic + protected-token reject, dialogue-turn grouping và external three-way diff có Core regression test;
- [ ] WPF smoke mở overlay, render selected dialogue card, auto-reload ngoài, khóa save khi conflict và gỡ khóa sau reload;
- [ ] WPF smoke tìm xuyên mọi translation file, bookmark/context điều hướng exact key, triage sidecar không đổi canonical, related context packet, High Contrast selection pair, `PerMonitorV2`, font 130% ở minimum layout và splitter/cột khôi phục;
- [ ] Smoke chứng minh lock cùng project, undo batch atomic/stale-safe và tab QA read-only không mutation;
- [ ] Full consistency audit đã chạy trên mọi translation file, số cảnh báo theo loại đã được ghi và canonical hash không đổi;
- [ ] bảng xưng hô có exact speaker set, không còn placeholder `needs_context` và mọi evidence key tồn tại; key thuần xuất hiện nhiều lần trong canonical bị từ chối khi được dùng làm evidence. Key trùng không được tham chiếu không làm hỏng evidence duy nhất. Regression thuộc Core `PronounValidationRejectsBadRows`, không chỉ suite sibling viethoa; chưa có định dạng evidence kèm ID bảng;
- [ ] mọi translation file full QA báo 0 lỗi hoặc đúng blocker đã được ghi rõ;
- [ ] benchmark full corpus ghi baseline read-only; timing không chặn release theo tốc độ máy; filter/project search dùng comparison ổn định theo locale;
- [ ] một lần chạy `Launch-Publish.cmd` đạt đủ 7 bước, process query fail-closed, metadata EXE khớp release, promote staging có rollback byte-exact và receipt v3 readback xác nhận mọi translation/reference hash + count không đổi;
- [ ] EXE tồn tại và runtime UI hiển thị đúng project/counts;
- [ ] không có XLSX hoặc Excel dependency mới;
- [ ] config, glossary và pronouns đều nằm trong workspace;
- [ ] process test đã đóng.

## Installer transaction

Chỉ đọc phần này khi sửa hoặc xác minh installer. Không chạy lại toàn bộ release cho thay đổi docs-only.

- `template_swap.py` staging source/test rồi giữ bản cũ tới verify cuối. `DirBackup` sao lưu toàn bộ `app/`; snapshot file gồm project.json, glossary, pronouns, install-receipt.json và performance-baseline.json. Release ghi app/receipt/baseline trước khi installer verify nên cả ba phải thuộc rollback.
- `verify_install_result` phải nằm trước commit: CSV hash/inventory không đổi; schema/version, cờ boolean đúng kiểu, tổng số dòng, đường dẫn và SHA-256 EXE khớp. Không chỉ dựa vào subprocess exit 0.
- Khi một bước restore lỗi, vẫn thử các bước còn lại và trả đủ lỗi. Không báo đã khôi phục khi còn lỗi; không discard backup cần dùng. Rollback đang dở chỉ được tiếp tục rollback; commit cleanup đang dở chỉ được tiếp tục cleanup trong cùng process.
- `.template-staging`, `.template-previous`, `.app.installer-backup` còn sót là hard stop cần kiểm tra. Chưa có bằng chứng crash/power-loss recovery; không tự xóa hoặc tự phục hồi mù.
- InstallerLock nằm tại workspace/.bientaptay.installer.lock, chỉ chống installer chạy chồng. WriterLock của editor/release nằm ở app root và khác phạm vi. Giữ WriterLock ở cha rồi gọi release subprocess sẽ tự chặn. Hiện vẫn phải đóng editor/dừng worker trước cài; chưa có shared lock xuyên toàn installer.

### Regression theo phạm vi

```text
python -B -m unittest discover -s scripts/tests -p "test_template_swap.py" -v
python -B -m unittest discover -s scripts/tests -p "test_install_*.py" -v
```

Chạy trong skill directory, đặt TMPDIR/TEMP/TMP vào scratch Hermes. Test installer thật cần Windows + .NET 8 SDK + sibling viethoa; skip không được tính là PASS.

- Helper tests: rollback retry, cấm commit sau rollback, cleanup failure, bảo toàn file temp không thuộc mình, restore nhiều file khi một file lỗi, path ownership, backup app, loại trừ hai process.
- `VerifyStageFaultTests`: cài thật trong workspace tổng hợp rồi chèn lỗi ở verify. So hash toàn cây ngoại trừ bin/obj/__pycache__. App cũ có rollback-sentinel.bin không nằm trong bản publish mới: file này phải quay về, tránh PASS giả vì EXE build lại ra cùng bytes. Kiểm receipt/baseline và không còn backup tạm.
- `InstallerLockTests`: giữ lock rồi gọi installer thứ hai; phải bị từ chối trước mutation. Mutation test bỏ lock phải làm regression fail.
- Test AST về thứ tự commit chỉ bổ trợ; không thay fault injection chạy thật.

## Kỷ luật thực thi

Dùng tool call có cấu trúc, không viết `Tool call: ...` thành nội dung trả lời. Chỉ kết luận từ tool result; văn bản mô tả lệnh không chứng minh lệnh chạy. Patch và test phụ thuộc nó phải chạy tuần tự, không batch song song. Sau gián đoạn, chỉ kiểm target đang làm rồi tiếp tục; không gọi là lỗi mạng, CRLF hay công cụ treo nếu chưa có evidence. Không pipe test qua grep/tail làm mất exit code. Dùng scope test nhỏ trong vòng sửa, chạy full suite tại mốc tích hợp thay vì build lại toàn bộ sau mỗi thay đổi chữ.
