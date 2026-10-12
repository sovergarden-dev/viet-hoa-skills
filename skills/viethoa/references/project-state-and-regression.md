# Project state and regression

Load khi khởi tạo dự án, đổi writer/phương án dịch, sửa matcher hoặc nâng patch sang build mới.

## Project state

Copy `templates/project-state.json` vào workspace cạnh canonical CSV. Cập nhật nguyên tử tại ranh giới giao dịch sạch. Mọi writer đọc state trước khi ghi; nếu `canonical_csv_sha256` lệch file thật, dừng và báo.

State tối thiểu: phase, evidence level, canonical path/hash, counts, active writer identity, external handoff lock, checkpoint cuối và timestamp.

## Cron pin khác live runtime

`model_pin.json`/migration receipt chỉ chứng minh identity và routing bất biến: job ID, provider, model, reasoning effort, fallback policy và workdir. Không dùng `schedule`, `enabled`, `state`, `next_run_at`, `last_status` hoặc PID trong snapshot đó làm trạng thái hiện tại.

Live cron state phải đọc từ `cronjob list`/scheduler store tại thời điểm kiểm tra. Nếu cần lưu observation, đặt dưới object có `observed_at` và `source`, không ghi đè nó từ pin cũ trong mỗi canonical commit. Writer nên xóa hoặc không phát sinh các volatile field không có live readback; một report stale phải fail closed thay vì nói job đang chạy.

Progress canonical chỉ hợp lệ khi hash/count khớp latest receipt/manifest (hoặc recovery journal exact). Project-state, receipt và canonical lệch nhau là temporal snapshot conflict: retry/read lại, không chọn con số thuận mắt.

`external_handoff_in_flight` là `null` hoặc object có batch ID, key-set hash, output format, phase, parent-phase hash và sent time. Không stage Plan 1 trên key range bị lock. `external_pipeline` theo dõi Phase 0/1/2/3 từ receipts thật. `preview_patch` chỉ lưu derived artifact/state/hashes; không đổi phase hoặc nâng draft thành reviewed.

## Glossary canonical

Copy `templates/glossary.csv`. Schema:

```text
term,translation_vi,rule,locked,evidence
```

`rule`: `keep_english`, `translate`, `transliterate`, `context_dependent`. `locked=true` nghĩa đã chốt; dùng boundary-aware QA và flag review, không bulk replace. External handoff đóng băng glossary kèm hash.

## Name provenance

Glossary không đủ để chứng minh vì sao một proper name giữ English, romaji, Hán–Việt hay form Latin khác. Mỗi project phải có `name-provenance-policy.json` và `name-provenance-ledger.csv` theo templates. Project state ghi country/language/evidence, policy/ledger path + hash, `audit_status` và số entry chưa resolve. Trước bulk/handoff, chạy `scripts/audit_name_provenance.py --policy <...> --ledger <...>` từ skill root hoặc pin script vào project. Trước release, chạy thêm `--require-resolved --require-complete`; policy chỉ được đánh `complete` sau audit proper-name toàn release corpus có evidence. English localization là reference, không phải name authority trừ khi nó là form gốc/creator-published đã ghi ledger.

## Temporal output và namespace

Background/subagent output có thể đến trễ sau một build mới hơn. Trước khi áp kết luận hoặc copy artifact, đối chiếu path hiện tại, expected parent/canonical hash, output SHA-256, mtime/receipt và project state; stale success/failure chỉ archive, không được rollback state mới.

Mọi generation dùng namespace theo canonical/source version và phase: `staging/<batch-or-rc>/`, `candidates/<rc>/`, `final/`. Builder final chỉ đọc allowlisted authoritative paths; legacy/default output path không được tồn tại như một fallback im lặng. Nếu job cũ từng ghi nhầm path, quarantine kèm manifest/hash và làm builder fail closed khi path đó tái xuất hiện. Candidate không ghi đè final; promotion là transaction riêng sau runtime acceptance.

## Matcher regression

Mỗi thay đổi canonical matcher phải có test-first vector tái hiện false pass/fail và chạy lại toàn bộ vectors dự án. Vector kiểm matcher, không chứng minh runtime engine.

## Build regression corpus

Sau release, giữ một tập nhỏ các hàng khó: xưng hô, macro, char limit sát, duplicate source khác context. Khi source drift, mọi thay đổi translation/state trong tập này phải có lý do; corpus không thay runtime QA.

Không xây abstraction chung giả tạo giữa engine routes. Không tự động thay thế runtime checkpoint do người dùng thực hiện.