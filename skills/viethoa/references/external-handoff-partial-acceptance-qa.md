# QA và merge từng phần khi nhận bản dịch ngoài

Áp dụng khi output từ Notion AI, Vertex AI hoặc dịch vụ ngoài có cả hàng đạt và hàng lỗi.

## Tách ba lớp kiểm tra

1. **Envelope/canonical identity:** header/schema, row count, exact unique key set, key-set hash.
2. **Structural per-row:** protected tokens, giá trị rỗng, phase-specific `review_action` hợp lệ. `source` và context trong output chỉ là metadata không tin cậy; so với batch canonical nhưng không dùng chúng để ghi đè canonical.
3. **Language/semantic evidence:** trong baseline 2.3, Phase 1 chỉ tạo full exact-key draft coverage; Phase 2 main-only review 100% corpus và thực hiện targeted recheck cho high-risk/runtime-flagged/rewritten rows. Hermes không dùng model để tự dịch, editorial review hoặc semantic QA; deterministic flags chỉ kiểm gate/ưu tiên chứ không thay evidence của Antigravity.

Không diễn giải Phase-1 structural report hoặc preview runtime PASS thành quality proof. Chỉ Phase-2 final clean output mới final-eligible; Phase 1 chỉ tạo accepted parent snapshot và không merge canonical final.

## Partial acceptance

Chỉ dùng cho **Phase-2 final return có whole envelope exact** nhưng một số rows fail deterministic gate. Phase 1 không partial-merge canonical final; nó chỉ tạo derived accepted parent snapshot cho Phase 2.

Nếu Phase-2 final envelope/key set sạch nhưng một số hàng lỗi:

1. Khóa writer/cron và xác minh canonical master hash đúng manifest.
2. Lập `accepted` và `rejected` theo stable key; assert union bằng exact Phase-2 final input và giao rỗng.
3. Chỉ nhận hàng có review action đúng phase, target không rỗng khi bắt buộc, token sạch, không corruption/forbidden term. Target trùng source chỉ hợp lệ khi exact English-policy row là `keep_identity` và target bằng `identity_expected`; không cho qua bằng source text/glossary chung.
4. Merge atomically `accepted` final-eligible rows; tuyệt đối giữ `source/context` từ canonical batch.
5. Xuất `remainder.csv` cho union của mọi hàng bị loại, với cột `reasons`, rồi gửi Antigravity rework; Hermes không tự chữa bằng model.
6. Backup master trước merge, validate master sau merge, ghi before/after hash và accepted/rejected counts.
7. Chỉ resume một writer sau khi giao dịch sạch.

Nếu envelope sai/missing/extra/duplicate/immutable mismatch, reject whole attempt; không partial merge.

## Đếm lỗi đúng

Các nhóm lỗi có thể chồng nhau. Báo cả:

- số occurrence theo từng reason;
- số **unique rejected rows** bằng union key;
- giao của các nhóm khi cần giải thích.

Không cộng số nhóm để tuyên bố tổng hàng lỗi.

## Proper-term matching

Không dùng substring thuần cho `SAM`, `Alter`, v.v.; nó bắt nhầm `sample`, `same`, `alternative`, `alternator`. Dùng boundary/token-aware matcher và khai báo biến thể số ít/số nhiều trong glossary. Cảnh báo heuristic không được tự động chặn merge nếu chưa xác minh.

## Bằng chứng tối thiểu

```json
{
  "incoming_sha256": "...",
  "master_before_sha256": "...",
  "master_after_sha256": "...",
  "accepted_merged": 0,
  "rejected_unique_rows": 0,
  "rejection_reason_occurrences": {},
  "remainder": "...",
  "validator_errors": 0
}
```
