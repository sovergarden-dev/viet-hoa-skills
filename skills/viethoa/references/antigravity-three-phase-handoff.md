# Antigravity three-phase external handoff

Dùng khi Hermes giao phần dịch/ngôn ngữ cho Antigravity theo pipeline **Phase 0 policy audit → Phase 1 Bulk Translation → Phase 2 Language QA & Strict Rework → Phase 3 Semantic Audit**. Hermes giữ extraction, canonical, merge, import, repack, installer, runtime và final acceptance.

## Receiver-control baseline `AGY-VIETHOA-HANDOFF/2.2-MAIN-ONLY-ONE-SHOT`

### Main-only one-shot contract

Khi user yêu cầu một lần gửi/một lần nhận, hoặc subagent route đã lặp process/provenance failure, override này thắng mọi hướng dẫn concurrency bên dưới:

- Antigravity dùng duy nhất main agent; host `PreToolUse` deny mọi `invoke_subagent` với cap `0`. Cấm `send_message`, `manage_subagents`, dynamic profile, swarm, nested delegation, replacement worker và conversation-ID mapping.
- Một Master ZIP chứa Phase 2 + Phase 3, full corpus/context/glossary, packet schedule, pinned controller/validators/finalizer và append-only ledger. Package-internal pilot/preflight sạch thì tự tiếp tục; không chat round-trip.
- Main model ghi quyết định keyed cho một packet tại một thời điểm. Script chỉ stage/hash/schema/token/checkpoint/transition/package; cấm tạo translation/action/reason/question, default accepted hoặc tự khai model provenance.
- Phase-2 full coverage + deterministic readback sạch mới mở Phase 3. Phase 3 dùng thứ tự đảo/fixed khác và prompt không lộ Phase-2 action/reason/note. Resume cùng package/ledger sau interruption hoặc quota.
- Chỉ trả một final Master ZIP. Hermes vẫn tự kiểm bytes/evidence rồi mới merge. Nếu host không thể enforce cap `0`, không dispatch one-shot dưới claim main-only.

- Đây là contract lịch sử `AGY-VIETHOA-HANDOFF/2.2-MAIN-ONLY-ONE-SHOT`, chỉ audit package 2.2 đã phát hành. Dispatch mới dùng `AGY-VIETHOA-HANDOFF/2.3-TWO-PHASE-DRAFT7-FINAL0` và `antigravity-two-phase-handoff.md`; không sửa hoặc relabel bytes 2.2 thành 2.3.
- Baseline `2.0|2.1`, cap `4|7`, worker leases legacy và child lifecycle cũng chỉ là **dữ liệu lịch sử để audit** artifact cũ. Không phát attempt/amendment mới dựa trên chúng và không dùng targeted-kill/reservation workaround.
- Controller checksum-pinned là writer duy nhất của queue/checkpoint/receipt/final ZIP; main model chỉ ghi raw keyed decisions cho đúng prompt hiện tại. Script/regex/heuristic chỉ join, hash, lint, validate, transition và serialize; cấm tạo prose, action, reason, question, model provenance hoặc default/bulk `accepted`.
- Phase 2/3 bắt buộc actual per-row main-model decision evidence gắn exact key và raw-response hash. `compact-explicit-v1` phải có exact disjoint complete partition `accepted_ids ∪ rewritten IDs ∪ needs_context IDs`; parse failure hoặc omission không bao giờ thành `accepted`.
- Một package tự chứa full corpus, prompt schedule, append-only ledger, resume logic và Phase-2→Phase-3 gate. Package-internal preflight sạch thì tự chạy tiếp. Chỉ bàn giao một final Master ZIP; không chat shuttle hay packet ZIP rời.

### Native Always Proceed và update compatibility trên Windows

- Người dùng có thể bật native `Always Proceed` toàn cục cho Planning/Artifact Review, terminal, browser JavaScript và non-workspace access. Dùng native policy thay cho auto-click extension vì không phụ thuộc text/layout nút và ít vỡ hơn sau update.
- Approval-free chỉ bỏ thao tác bấm duyệt; không nới receiver contract, exact-key lease, một writer, package cap, per-row model evidence hoặc artifact readback. Credentials/payment, destructive delete, publish và irreversible system changes vẫn phải nằm trong explicit task scope.
- Windows chưa có Antigravity terminal sandbox; đừng báo sandboxed nếu setting không có hiệu lực. Khi terminal chạy trực tiếp, package-pinned tooling/checkpoint/rollback và deterministic validators vẫn là gate.
- Giữ top-level named `PreToolUse` deny hooks cho `invoke_subagent`, `send_message` và `manage_subagents`; status phải là `limit=0`. Không dùng hook terminal/browser deny nếu user đã chọn native Always Proceed. Main agent chạy packet tuần tự và chỉ `blocked` khi immutable contradiction, package/tool integrity failure, quota/service limit hoặc compatibility gate thật; uncertainty ngôn ngữ phải được xử lý trong internal resolution stage của cùng package.
- Mỗi update phải backup config/install trước, xác minh publisher/version, rồi read back native enums, hook schema, skill lint và một runtime command không approval. Launch-time guard chỉ tự reapply khi exact enum còn tồn tại trong binary; enum bị đổi phải fail visible thay vì đoán.

### Tool/data integrity phía receiver

- Input extraction, validator, finalizer, manifest và checksums là immutable. ReDoS/CWD/schema bug trong package phải tạo minimal repro ngoài extraction rồi `blocked`; Hermes phát hành attempt mới với bytes/checksums mới. Receiver không tự patch validator hoặc checksum.
- Loop script hợp lệ cho deterministic join/hash/lint/serialize; bất hợp lệ khi sinh translation hoặc semantic action. Nối nhiều command shell không biến automation thành model review.
- Chạy package Python bằng `python -B`; queues/locks/prompts/responses/cache/temp ở sibling `evidence_work`. Extraction bẩn thì quarantine và re-extract từ verified ZIP, không xóa file lạ in-place.
- Dùng documented `cwd` hoặc absolute paths. Prompt file **at rest** vẫn checksum-pin exact bytes/declared encoding; cấm dummy prefix/comment/BOM ngoài schema. Khi host buộc model tự sinh một JSON-string tool argument và không thể bảo toàn raw file bytes qua lớp escaping, package mới có thể khai báo `canonical-json-wire-v1`: Hermes hash canonical parsed JSON object, đọc actual Prompt từ host-owned main transcript, yêu cầu actual Prompt parse được và canonical object byte-equal sau deterministic serialization; cấm hook/file-loader/placeholder và cấm permissive repair/normalization sau invocation. Text có literal `\\n` hoặc physical newline phải encode thành segment arrays + explicit separator/count trước dispatch, không giao chuỗi escape mơ hồ để model gõ lại. Parsed-object/hash mismatch vẫn reject. Một coordinator sở hữu queue bằng lock + atomic replace + readback; worker chỉ nhận immutable lease.

## Role boundary

- **Hermes:** khóa build/source, tạo stable keys, policy/glossary/context, ZIP/receipts; kiểm incoming; merge; tạo patch và rollback.
- **Antigravity:** chịu toàn bộ công việc ngôn ngữ: phân tích policy khi áp dụng, dịch, **full-corpus language QA**, strict rework, **full-corpus cold semantic audit**, consistency/xưng-hô/glossary review và trả artifacts đúng schema.
- **Hermes không làm dịch hoặc QA ngôn ngữ bằng model trong Plan 2.** Hermes chỉ kiểm deterministic: ZIP/checksum, schema, exact identity/envelope, immutable fields, states, protected tokens, phase/parent/receipt; sau đó exact-key merge, import/repack/runtime acceptance.
- “Tiết kiệm token” nghĩa là tiết kiệm token phía Hermes bằng delta-only outputs, manifests và deterministic scripts; không được cắt coverage/model/QA của Antigravity.
- Antigravity không sửa canonical, validator, importer, game files hoặc technical payload. `PASS`, `100%`, receipt và manifest do bên nhận tự ghi không thay thế kiểm bytes deterministic của Hermes.

## Package architecture

Dùng cùng một contract Multi-Packet kể cả khi chỉ có một packet; không duy trì nhánh legacy single-root riêng:

```text
project-manifest.json
work-queue.json                 # derived cache, không phải authority
START-HERE.md
handoff-id-map.csv
glossary.csv
english-policy.csv              # bắt buộc khi source là English
style-guide.md                  # khi có nội dung project-specific
character-and-pronoun-guide.md  # khi có
protected-tokens.md
batch-schema.json
output-schema.json
token-profile.json
checksums.sha256
packets/<packet-id>/
  packet-manifest.json
  batch.csv
skill/game-translation-contributor/SKILL.md
TRANSLATION-PROMPT.txt
```

`project-manifest.json` khóa source/target language, build, canonical source hash, exact ordered full-key hash, policy/glossary/token-profile hashes, phase contract và output naming. Immutable packet manifests + Hermes acceptance receipts + append-only `merge-ledger.jsonl` là authority. `work-queue.json` chỉ là derived cache liệt kê disjoint packet IDs/state; khi lệch, tái dựng từ ba nguồn authority, không tiếp tục bằng cursor/index hoặc chat memory.

Mọi identity là `(domain,key)`. Nếu adapter Antigravity chỉ nhận một `key`, tạo `handoff_id` opaque, deterministic, manifest-pinned và one-to-one với `(domain,key)`; trả lại `handoff_id`. Không nối chuỗi mơ hồ, không drop domain và không dùng bare key khi có collision.

Các adapter translation-only được đóng gói sẵn, checksum-pinned và data-driven theo manifest. Không để Antigravity tự sinh writer ad-hoc hardcode `source_ja`, `reference_en`, key-only hoặc batch size. Adapter không được biết canonical path.

## Compatibility guard cho Antigravity

Có thể tham khảo pipeline/memory của skill `dichgame`, nhưng không copy các sample scripts thành authoritative writer nếu chúng:

- map bằng bare `key` thay vì `(domain,key)`/manifest-pinned `handoff_id`;
- hardcode cột `source_ja`, `reference_en`, batch size hoặc output path;
- dùng ZIP `extractall` không kiểm path traversal;
- thêm cột/đổi schema hoặc ghi CSV in-place không checkpoint + atomic replace;
- set `translated` chỉ vì model trả một key, không kiểm blank/action/source/policy/token;
- tạo queue/audit state theo row index rồi coi đó là canonical identity.

Dùng workflow 3 pha và memory files làm **receiver-side translation workspace**; output vẫn là untrusted artifact. Hermes tạo adapter fixed, data-driven từ manifest, xác minh checksum trước dispatch và là writer duy nhất của canonical.

## Phase contract

### Phase 0 — English policy audit

Bắt buộc khi authoritative source là English. Làm theo `english-source-semantic-policy.md`; trả `policy-audit.csv` và receipt. Không bắt đầu Bulk Translation khi còn row có `policy_status != locked` hoặc `policy_ready_for_bulk != true`.

### Phase 1 — Bulk Translation

- Input là immutable source/context/policy rows; `current_translation_vi` rỗng. Output dùng skeleton riêng, không ghi đè `batch.csv`.
- `review_action` chỉ dùng `translated` hoặc `needs_context`; không dùng `rewritten`.
- Với `keep_identity`, `translation_vi` phải bằng `identity_expected`; vẫn dùng `review_action=translated`.
- Với `translate_with_locked_terms`, dịch prose và giữ đúng term; với `translate_full`, dịch đầy đủ.
- Phase 1 complete chỉ có nghĩa **draft coverage + structural gates**, chưa phải language QA hay release quality.

Tại ranh giới sạch, Antigravity phải xuất snapshot không ghi đè:

```text
returns/phase1/<packet-id>/attempt-<n>/
  translated_<packet-id>.csv
  phase-receipt.json
  checksums.sha256
```

Mỗi return package chỉ chứa đúng một `(packet_id,attempt)`. Receipt bind exact lease/phase/parent/input payload, row/action counts, ordered key hash, source/policy/glossary/token-profile hashes, unresolved IDs và output SHA-256. Retry tạo attempt path mới; không overwrite.

### Phase 2 — Full-corpus Language QA & Strict Rework

Sau Phase-1 envelope sạch, Hermes chỉ tạo deterministic parent acceptance receipt và data-driven Phase-2 package. **Phase 2 gửi toàn bộ release-scope corpus cho Antigravity**, không chỉ Phase-1 subset hoặc flagged remainder. Gói phải materialize Phase-1 draft cùng mọi target có trước đó từ Hermes/community/reference route, mỗi row có immutable `current_translation_vi`, current source/context/policy/glossary/xưng-hô evidence. Antigravity phải editorial-review 100% release rows, gồm source faithfulness, tiếng Việt tự nhiên, glossary, xưng hô, consistency, punctuation, residual, line breaks và UI constraints; output skeleton riêng, không sửa Phase-1 input hoặc gate.

Deterministic flags của Hermes, nếu có, chỉ là reason hints ưu tiên; chúng không giới hạn Phase-2 coverage và không thay thế language QA. Hermes không dùng LLM/model để review hoặc chữa câu trong Plan 2.

`review_action`: `accepted`, `rewritten`, `needs_context`. `accepted` phải giữ nguyên `current_translation_vi`; `rewritten` phải khác và có reason ngắn; không mặc định accept hàng loạt. Với package `compact-explicit-v1`, model chỉ cần liệt kê explicit accepted IDs; accepted không cần boilerplate note, nhưng mọi ID vẫn phải hiện đúng một lần trong raw response. Output/receipt mới không ghi đè Phase 1. Phase-2 completion yêu cầu một action cho mọi exact input identity; không key nào được biến mất hoặc bị copy source để lấp chỗ.

### Phase 3 — Full-corpus cold Semantic Audit

Sau Phase-2 envelope sạch, Hermes chỉ tạo deterministic parent acceptance receipt và derived full snapshot. Antigravity phải audit **toàn bộ corpus**, độc lập/cold pass, không chỉ flagged rows hoặc `audit_queue` cũ. Auditor không được mặc định tin Phase-1/2 self-report. Mỗi row mang immutable `current_translation_vi`; kiểm source fidelity, wrong-row attachment, omissions/additions, glossary variants, xưng hô, mixed-language, residual, branding, duplicate targets và UI-fit indicators. `accepted` giữ nguyên current target; `rewritten` phải khác + reason; trả đúng một action cho mọi release-scope key. Không đổi input/key/source/context/policy.

Regex/glossary replacement/formatting sweeps chỉ là deterministic lint, **không phải Phase-3 cold semantic audit** và không được tự cấp `accepted`. Cấm global rewrite mù như `'? ' → '?'`, auto-capitalization hoặc bulk glossary replacement không kiểm exact source/key/context; mọi target đổi ở Phase 3 phải có per-key `rewritten` evidence. Phase 3 chỉ bắt đầu sau Hermes Phase-2 acceptance parent.

Hermes không chạy semantic review bằng model. Hermes chỉ xác minh Phase-3 envelope/action/parent/hash/token deterministic rồi merge exact keys.

Mỗi phase receipt chứa `phase`, `parent_phase_sha256`, exact key union/hash, input/output hashes, action counts, unresolved keys và validator version. Parent mismatch là whole-envelope rejection. `review_action` là external evidence, không mở rộng canonical enum: Phase-1 clean rows map tối đa `translated`; chỉ Phase-2/3 per-key `accepted|rewritten` qua Hermes QA mới có thể map `reviewed`; `needs_context` giữ target rỗng/câu hỏi cụ thể.

## Phase-1 preview patch để chơi tạm

Chỉ làm khi user yêu cầu và Phase 1 đã trả complete envelope:

1. Lưu incoming Phase-1 bytes immutable; kiểm filename/schema/row count/exact keys/source-policy hashes/tokens và identity policy.
2. Tạo **derived preview snapshot** từ canonical source + independently clean Phase-1 targets. Không ghi draft vào canonical final và không sửa Phase-1 snapshot mà Antigravity dùng để tiếp tục.
3. `needs_context`, rejected hoặc missing rows dùng runtime fallback nếu engine hỗ trợ. Nếu full replacement bắt buộc đủ target, materialize English/source fallback **chỉ trong build-derived file**; ghi exact fallback count/key list, không set canonical `translated/reviewed`.
4. Tên artifact phải chứa `PREVIEW_PHASE1_NOT_QA`; namespace riêng, không public/share, không promote final và không gọi “hoàn hảo/100%”.
5. Vẫn bắt buộc import/readback, payload integrity, build/hash guards, reversible install/uninstall và user runtime QA. Language quality còn pending.
6. Antigravity tiếp tục Phase 2/3 từ exact Phase-1 parent hash. Final return thay preview bằng upgrade transaction chỉ khi live preview hashes còn đúng installed state; nếu user/mod khác đã đổi file, dừng.

Suggested states:

```text
external_phase1_return_received
preview_phase1_offline_validated
preview_phase1_runtime_accepted_language_qa_pending
external_phase2_in_progress
external_phase3_in_progress
final_external_return_received
```

Preview runtime PASS chỉ chứng minh route/font/playability, không nâng bản dịch Phase 1 thành reviewed.

## Community Vietnamese baseline salvage

Dùng khi cộng đồng đã có patch Việt hóa:

1. Hash/archive artifact, unpack/decompile **read-only**, không chạy installer/launcher lạ. Audit provenance/license/branding. Community text có thể làm internal QA reference, nhưng identical carry vào public patch chỉ khi license/permission cho phép; nếu không, Antigravity phải rewrite từ current source hoặc giới hạn artifact private-use. Không tái phân phối binary/font/text mơ hồ quyền.
2. Extract current-build authoritative source riêng. Reconcile community text bằng exact `(domain,key)` hoặc identity path/table/key đã chứng minh; cấm positional, suffix và source-only merge.
3. Community Vietnamese chỉ vào cột `community_vi_reference`; current source vẫn authority. Unmatched community rows vào report riêng, không ép ghép.
4. Classify current keys:
   - `review_existing`: exact key + unchanged source + tokens structurally clean;
   - `retranslate`: source changed, token mismatch, semantic/branding suspicion hoặc wrong-row evidence;
   - `translate_missing`: current key không có community target;
   - `exclude`: obsolete/non-player-facing.
5. Áp English policy từ **current source**. Community target đã Việt hóa item/skill/location trái policy phải được sửa về identity English; không coi legacy wording là glossary lock.
6. Handoff gửi `community_vi_reference`, source-build hashes, alignment confidence/reason và route. Antigravity review/rewrite theo current source; không auto-passthrough chỉ vì tiếng Việt có sẵn.
7. Phase 1 chỉ cần dịch `retranslate/translate_missing`; `review_existing` đi thẳng vào Phase 2 editorial review. Cách này tiết kiệm token nhưng mọi accepted row vẫn cần action/evidence.
8. Nếu community artifact không có stable exact identity, chặn salvage merge và chỉ dùng reference-only cho điều tra ngôn ngữ; không dựng mapping bằng source/position. Incoming final dùng cùng envelope/partial-acceptance/canonical gates như bản dịch mới. Xóa old team branding chỉ ở exact proven keys; quét toàn corpus và assets riêng.

## Token/cost discipline — chỉ tối ưu phía Hermes

- Mục tiêu là giảm model/token work của Hermes về gần 0 trong Plan 2: Hermes dùng deterministic scripts, manifests, hashes, schema/token validators và exact-key merge; không dịch hoặc language/semantic QA bằng model.
- **Không tối ưu chi phí Antigravity bằng cách cắt coverage.** Phase 2 và Phase 3 đều phải xử lý 100% release corpus exact-key, gồm target có trước Phase 1. Model/parallelism/budget phía Antigravity do bên nhận tự chịu; không hạ quality tier, skip rows hoặc chỉ review flagged remainder.
- Shared policy/glossary/style/token profile ở root; packet giữ hash + subset terms/context thực sự liên quan để tránh lặp dữ liệu, nhưng mọi row vẫn xuất hiện đúng một lần trong mỗi full-corpus phase.
- Packet theo estimated input/output tokens và context locality: khoảng 15–25 cho dialogue/context nặng, 40–80 dialogue thường, tối đa khoảng 80–150 UI ngắn. Nếu provider có dung lượng lớn hơn có thể tăng sau proof sạch, nhưng không trả partial/truncated.
- Group theo domain/conversation/semantic class; không cố đủ quota bằng rows không liên quan.
- Output delta-only: `handoff_id/domain/key`, `translation_vi`, `review_action`, `reason_codes`, `notes`; không echo source/context/token list/output path. Đây là tối ưu truyền/parse và Hermes verification, không phải giảm QA.
- Phase 2/3 reports im lặng theo packet nhưng vẫn ghi receipt/checkpoint máy đọc cho mỗi attempt và một action cho mọi key.
- Reuse chỉ với exact source + equivalent context class + glossary version + token profile; không source-dedupe toàn cục.
- Antigravity nên dùng model mạnh cho Phase 2/3, dialogue/lore và ambiguity; routine Phase 1 có thể dùng model nhanh hơn nếu vẫn đạt gates và user cho phép.

## Attempt, recovery và Hermes incoming gate

- Baseline `2.2` khóa immutable `(package_id, run_id, phase, batch_id, prompt_sha256, input_payload_sha256, parent_phase_sha256)`. Resume dùng cùng package/run và append-only ledger; invalid response được lưu dưới rejected attempt mới, không overwrite accepted evidence. `lease_id/expires_at` chỉ áp dụng khi audit baseline legacy `2.0|2.1`, không xuất hiện trong dispatch main-only mới.
- Receiver phải tạo output attempt mới bằng sibling temp/fresh file rồi atomic replace; cấm mở CSV cũ bằng append theo cursor vì retry/crash sẽ lặp cả batch. Trước receipt, reopen và assert exact row count, unique ordered `handoff_id/domain/key` và một action mỗi identity.
- Chỉ khi audit package legacy `2.0|2.1`, receipt lấy UUID `lease_id` và attempt từ đúng packet manifest. Với `2.2`, receipt bind exact `package_id,run_id,phase,batch_id,prompt_sha256,input_payload_sha256,parent_phase_sha256`; không có lease/expiry. Mọi baseline đều phải lấy Counter thực sau reopen và bỏ action có count 0; ordered full-key hash là bắt buộc.
- Receiver ghi response vào attempt path mới, reopen rồi mới phát receipt. Hermes tự tính lại hash/count; self-reported receipt chưa xác minh không có authority. **Không nhúng SHA-256 của chính ZIP vào file bên trong ZIP**: đó là self-reference bất khả ổn định vì sửa receipt làm đổi ZIP bytes. `phase-receipt.json` chỉ hash output/internal payload; final ZIP SHA-256 nằm ở sidecar receipt ngoài ZIP hoặc được công bố sau khi ZIP đã đóng và không sửa nữa.
- Append-only merge ledger ghi packet/attempt, accepted output hash, canonical before/after hash và remainder hash. Replay cùng accepted hash là no-op; cùng packet/attempt nhưng hash khác là conflict hard stop.

Incoming gate:

1. Lưu bytes gốc và hash. Với `2.2`, verify package/run/phase/batch/prompt/input/parent bindings, host cap-0 proof, schema, schedule union/reverse order, exact keys, immutable hashes và all checksums; attempt/lease chỉ áp dụng cho legacy `2.0|2.1`.
2. Rejoin qua `handoff_id → (domain,key)`; ignore returned source/context. Một action cho mọi input identity; không silent skip.
3. Hermes chỉ chạy deterministic gate: action/state, blank target, exact policy identity, protected-token multiset, source/reference identity hashes, glossary exact locks và parse integrity. **Không dùng Hermes model để làm editorial/semantic QA.** Language/semantic evidence phải đến từ Antigravity Phase 2/3 full-corpus output.
4. Với baseline `AGY-VIETHOA-HANDOFF/2.2-MAIN-ONLY-ONE-SHOT`, final Master ZIP phải chứa exact prompt + unmodified raw main-model response + normalized decision receipt cho mọi Phase-2/Phase-3 batch, append-only ledger chain, Phase-2 acceptance/transition receipt và complete final outputs. `compact-explicit-v1` chỉ hợp lệ khi exact ID partition đủ, rời nhau, không missing/extra/duplicate; serializer parse raw response trực tiếp. Omission-default accept, CSV bulk-`accepted`, script-generated accepted IDs, fabricated metadata, prompt-only trace, missing evidence hoặc receipt không khớp Counter thực đều reject. Phase-3 prompt/evidence phải chứng minh reverse-order full coverage và không lộ Phase-2 action/reason/note. Baseline `2.0|2.1` giữ encoding cũ chỉ để audit historical returns.
5. Audit cả script trong receiver workspace và thư mục cha liên quan, không chỉ cây package trả về. Main model dùng shell/script loop để gán hàng loạt `accepted`, translations, reasons hoặc questions vẫn là automation-only dù lệnh do model tự gọi. Mọi suffix/substring/fuzzy key repair làm nhiễm toàn bộ fresh decisions đã đi qua nó, kể cả khi serializer cuối có exact key union. Receiver sửa checksum-pinned controller/validator/finalizer hoặc tự cập nhật package checksum để hợp thức hóa tool đã sửa là whole-run rejection; mọi tool hash phải byte-equal dispatch manifest. Đánh dấu exact batch/row bị nhiễm; cấm coi note/model label, tên tool Hermes hoặc self-reported validator PASS là semantic evidence.
6. Phase-1 clean envelope chỉ tạo acceptance parent/derived snapshot cho Phase 2; không merge thành canonical final. Phase-2 clean full-corpus output tạo parent cho Phase 3. Chỉ Phase-3 clean full-corpus output mới final-eligible; partial merge chỉ khi envelope exact và từng rejection có exact stable-key remainder.
7. Canonical checkpoint → sibling temp + fsync + atomic replace → reload + validator. Fail thì rollback; receipt/merge ledger chỉ append sau readback sạch. Import và runtime vẫn do Hermes.
8. Recovery dựng lại queue từ packet manifests + verified receipts + merge ledger; không dùng cursor/index hoặc chat history.
