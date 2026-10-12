## Preparation completion gate — bắt buộc trước khi báo sẵn sàng

Khi user yêu cầu “chuẩn bị trước, chỉ bắt đầu khi tôi báo”, phải hoàn tất **toàn bộ route kỹ thuật và batch-translation readiness trước**, không dừng ở inventory/discovery:

1. Resolve và structurally decode được corpus thật của engine/format; canonical CSV phải chứa toàn bộ source rows trong release scope, stable key/domain/key-set hash và reference languages nếu có.
2. Có extractor, validator, writer/importer, one-row copy-only roundtrip test và rollback rehearsal chạy thành công trên workspace copy. Không được gọi là “đã chuẩn bị” nếu canonical vẫn rỗng hoặc chỉ có schema header.
3. Chuẩn bị glossary/style/pronoun/context QA, `name-provenance-policy.json`, `name-provenance-ledger.csv`, batch manifest, checkpoint/lock files, translation script/worker và exact command để vào batch đầu. Policy phải có country/language/evidence; ledger phải phân biệt creator/native form, English reference và lock. Chạy `audit_name_provenance.py` sạch cho policy + ledger trước batch đầu; tên chưa đủ evidence phải là `needs_review`, không phải English fallback. Worker phải ở trạng thái idle; chưa dịch, chưa ghi target, chưa tạo patch live.
4. Chạy preflight cuối: source hashes, corpus counts, duplicate/full-key assertions, **display-field allowlist/exclusion audit**, **domain/property distribution outlier audit**, protected-token positive/negative vectors, token-pattern outliers, font/codepoint inventory, output directory readiness và report blocker. Chỉ sau preflight sạch mới chuyển state `prepared_waiting_for_translation_authorization`.
5. Chạy một verification độc lập từ artifact cuối: parse canonical, đếm exact unique keys/state, kiểm target còn trống nếu chưa được phép dịch, re-open ZIP nếu có và xác minh checksums/manifest. Không dùng self-report của worker/subagent làm bằng chứng hoàn tất; artifact phải được read back ở đúng workspace người dùng yêu cầu.
6. Khi user nói “bắt đầu dịch”, không quay lại discovery; bắt đầu ngay batch đầu từ canonical đã chuẩn bị. Nếu preflight chưa đạt, phải báo thiếu gì và tiếp tục chuẩn bị, không tuyên bố sẵn sàng.

