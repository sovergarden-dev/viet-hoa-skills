# Token-efficient external handoff

Mục tiêu theo thứ tự: giảm context/model work của Hermes; giữ nguyên security và QA gates; sau đó giảm thời gian/token Antigravity. New dispatch baseline: `AGY-VIETHOA-HANDOFF/2.5-TWO-PHASE-DRAFT12-PREVIEW-FINAL0-GUARDED`. Không đổi exact-key coverage, full-corpus Phase 2, challenge/recheck, provenance hay runtime gate để tiết kiệm token.

## Context budget của Hermes

1. Dùng **receipt-first**: đọc một project-state/release-lock hiện hành rồi đúng một reference liên quan. Không reload toàn bộ lịch sử, full corpus hoặc cùng một file lớn nhiều lần.
2. Đưa full report, event ledger, hash inventory và test output xuống disk. Stdout/chat chỉ giữ một compact JSON gồm state, package/run, counts, hashes chính, blocker và report path.
3. Mỗi phase chỉ có: một build, một independent verification, một host preparation, một arm/readback và một final regression suite. Chỉ lặp bước có failing evidence cụ thể.
4. Hermes không dịch, editorial review, semantic sample hoặc tạo language-QA remainder. Scripts chỉ làm bytes/schema/key/source/token/state/hash/receipt; language work thuộc Antigravity.
5. Phase 1 dùng **atomic wave**: exact `wave` expose tối đa package-configured `1..12` prompt cùng hash, một `invoke_subagent` call chứa exactly every staged worker entry, rồi exact `select` tuần tự để commit; chỉ tạo wave mới khi staged về zero. Default ceiling là `12`; nếu provider từ chối trước semantic commit thì build fresh run với cap thấp hơn, không mutate cap active. Worker description phải ghi `DO NOT CALL TOOLS`. Main ghi raw worker result unchanged. Guard yêu cầu exact wave reservation trước `select`, rồi tìm byte-exact native worker transcript mang đúng marker trước mỗi raw write và ghi `native_worker_conversation_id`; main-authored fallback bị deny. Controller commit-time structural gate chặn source-copy, edge whitespace, protected-token, locked-term và physical-newline mismatch trước commit, tránh post-final rework. `RECOVERABLE_SEQUENCE` tự sửa thứ tự WAVE/SELECT; `RECOVERABLE_WORKER_RETRY` retry một lease. Hai loại này không stop/report. Non-recoverable denied write is a hard stop. Do not dump worker payloads hoặc translation rows; dùng `scripts/diagnose_guarded_phase1_recovery.py`. Chỉ sau khi active run đóng và guard inactive mới chạy `scripts/promote_recoverable_denial_guard.py`. Controller chỉ deterministic envelope normalization top-level schema; archive `raw-response.json` và assert `target_utf8_sha256_by_handoff_id` không đổi. Đo peak từ host reservation ledger; `limit=7` với peak `1` là serial under-utilization, không phải parallel success. Phase 2 vẫn main-only cap `0`.
- Không dùng GUI/CDP để chuẩn bị hoặc gửi nếu user tự gửi. Chỉ capture read-only khi receipt/host evidence mâu thuẫn. Không poll/check sau mỗi continuation; recoverable continuation là fire-and-forget trong cùng conversation.

## Một lệnh host preparation

Sau khi package cuối đã được build/extract và package bytes đã khóa, chạy helper bằng `terminal`:

```text
python -B scripts/prepare_guarded_handoff_host.py \
  --package-root <immutable-package-root> \
  --work-root <fresh-work-root> \
  --host-private-root <fresh-host-private-root> \
  --python <receiver-python> \
  --semantic-guard <active-semantic-guard> \
  --receiver-shell powershell \
  [--challenge-overlay <phase2-host-private-overlay>]
```

Helper phải:

- derive controller/schedule/materializer từ manifest-pinned descriptors;
- tạo exact allowlist và `agy-semantic-origin-authorization/v3`;
- chạy exact receiver-shell probe trước arm; với PowerShell, executable ở đầu command phải chạy được nguyên văn, không chỉ đúng khi gọi từ Bash/CMD;
- mọi Python semantic-hook command trên Windows phải dùng `-X utf8`; nếu không, UTF-8 của `ọ` (`U+1ECD`, chứa byte `0x8D`) có thể đi qua default `cp1252` + `surrogateescape` thành `\udc8d` rồi fail khi encode lại. Preflight phải chạy một native pre/write/readback/commit payload có non-ASCII qua đúng hook command, không chỉ gọi `verify`;
- Phase 1 dùng `verify,init,wave,select,commit,status,finalize`; legacy `next` không được authorize vì rolling refill từng lease làm coordinator rơi về serial sau checkpoint. Phase 2 dùng `next,commit,status,finalize` và bắt buộc challenge overlay;
- Mọi continuation/recovery phải đưa exact `run_command` JSON args gồm cả `CommandLine` và `Cwd`. `Cwd` là package root trong allowlist, không phải Antigravity project root; cấm đổi path token, flag, separator, filename hoặc bọc thêm quote;
- ghi full immutable preparation receipt, nhưng chỉ in một compact JSON;
- không arm guard và không sửa canonical. Arm vẫn là một bounded host transaction sau khi receipt sạch và user đã authorize.

Mỗi retry dùng host-private directory mới (`auth-v2`, `auth-v3`...), không sửa authorization cũ. Receiver-shell probe thất bại là pre-dispatch blocker; archive receipt, giữ canonical untouched và sửa test-first.

## Arm và dispatch

1. Trong một `terminal` call fail-fast: arm phase guard, arm semantic guard, đọc lại cả hai exact bindings và verify event heads. Nếu semantic arm thất bại, Phase 1 rollback về cap `0`; Phase 2 giữ lockdown cap `0`.
2. Ghi model user chọn vào release lock/dispatch receipt; model là operator metadata, không thay package identity.
3. User tự gửi exact prompt. Hermes không click `Send`. Không yêu cầu user báo `đã gửi` riêng: pre-arm readback là gate chính, còn exact conversation/model/package và first valid commit được xác minh từ host ledger ở lần status/blocker/final check kế tiếp. User chỉ cần báo non-recoverable blocker, expected return/final ZIP, hoặc khi chủ động muốn xem trạng thái. Deterministic recoverable continuation trong cùng conversation là fire-and-forget, không re-check.
4. Chỉ đặt `dispatched=true` khi exact conversation đã bind từ host evidence. Chỉ đặt `translation_started=true` khi có worker reservation/native semantic write/accepted commit evidence; arm, model UI hoặc lời báo `đã gửi` không đủ. Release lock có thể giữ `armed_waiting_unobserved_dispatch` cho tới lần evidence check tự nhiên tiếp theo.
5. Nếu first turn bị blocker kỹ thuật trước worker output, sửa host auth bằng fresh receipt rồi dùng short continuation prompt trong cùng conversation; không resend full runbook.

## Compact monitoring

Dùng `scripts/compact_guarded_handoff_status.py` thay cho nhiều lần đọc state/event/controller hoặc gọi controller `status` chỉ để quan sát. Helper đọc state trực tiếp, fail closed khi binding/event head sai, không khởi tạo controller và ghi full report ngoài chat.

Một status check phải đủ trả lời:

- exact package/run/phase/model;
- dispatched/bound conversation;
- cap/reserved;
- pending/staged/committed/finalized;
- translation đã thật sự bắt đầu hay chưa;
- full report path.

Không poll liên tục. Chỉ kiểm khi user hỏi, Antigravity báo milestone/blocker, expected return xuất hiện hoặc host event thay đổi.

## Phase boundary

- Phase 1 return: chạy `scripts/accept_guarded_phase1_snapshot.py` đúng một lần để tạo clean preview-grade snapshot, exact remainder và compact receipt. Không đọc corpus, worker payload hoặc provenance ledger vào chat nếu receipt bind/hash sạch. Receipt bắt buộc emit `direct_phase2_eligible`, `recommended_next=await_user_direction`, `allowed_next_routes` và exact `carry_blockers`. Ghi `phase1_accepted_waiting_for_user_direction`, hỏi user chọn `build_demo_patch|external_phase2_antigravity|hermes_cron_phase2|pause`; không tự build demo hoặc chuẩn bị Phase 2. Demo route mới build `PREVIEW_PHASE1_DEMO_NOT_FINAL`, thu runtime feedback, ghi `phase1_demo_ready_waiting_for_user_direction` rồi hỏi lại.
- `direct_phase2_eligible=true` chỉ chứng minh accepted snapshot có thể làm parent cho route Phase 2; nó không tự chọn Antigravity hay Hermes cron. Khi user chọn một route Phase 2, remainder nonzero trở thành `mandatory_rewrite_reasons`; không build Phase-1 rework package và không hỏi model phân loại lại. Chỉ reissue exact Phase-1 remainder khi receipt false, như blank/non-string target, stale source-token declaration hoặc Unicode corruption.
- External Phase 2 builder chỉ chạy sau route `external_phase2_antigravity`; lấy accepted snapshot/hash + optional demo runtime feedback làm parent, profile packet trước build (mandatory/runtime/explicit-high-risk `30`, dialogue/lore `60`, short UI `100`, clean identity UI `120`, thêm hard prompt-byte cap), chạy build + independent validator và chỉ in một-line receipt. `prepare_guarded_handoff_host.py` phải tự đọc schedule/overlay ngoài package, kiểm exact slot coverage, unique challenge IDs, visible-source derivation và reject whitespace-only challenge donors trước khi gọi package-pinned materializer; receipt phải ghi `challenge_count == prompt_derivable_challenge_count`. Hidden free-translation hash hoặc spacer target chỉ gồm whitespace fail trước arm, không được dispatch rồi mới chẩn đoán.
- Hermes chỉ cần ba compact receipts: Phase-1 acceptance, Phase-2 build/independent verification và host preparation. Chỉ mở full report khi receipt mismatch/fail; không mở full overlay, 14k-row CSV hoặc transcript để “check thêm”. Antigravity vẫn review 100% corpus.
- Sau full-pass finalizer, dùng `scripts/materialize_guarded_phase2_recheck.py`; không viết project-specific recheck wrapper. Recheck all rewritten/runtime/explicit high-risk + stratified >=10% accepted theo domain/content/policy. Clean `keep_identity` là stratum riêng, không tự động là high-risk toàn bộ.
- Final return: deterministic provenance/recheck gate tạo exact clean/rejected sets; Hermes chỉ model-review khi validator phát hiện một loại lỗi mới chưa có rule, rồi thêm regression fixture trước khi tiếp tục.

## New-project template

Mỗi project-side builder phải xuất cùng interface: `build`, `verify`, `prepare`, `compact-status`, `accept-return`. Các lệnh ghi full receipts và một-line summaries. Không tạo UI automation, duplicated validators hoặc project-specific orchestration mới nếu hai helper chung đã đủ.

## Verification

- Receiver-shell regression chạy command đầu tiên bằng đúng shell Antigravity dùng.
- Helper tests chứng minh no-arm không đổi live guard state, status không tạo controller state, binding mismatch fail closed, Phase 2 action set là main-only.
- Chạy targeted RED/GREEN trong lúc sửa; chạy full package lint và full project suite đúng một lần trước dispatch/promotion.
