# Promise Mascot Agency — postmortem phương án 2 đầu-cuối

Case này là lần đầu workflow Antigravity hai phase đi từ corpus đã khóa đến canonical merge và runtime QA artifact. Đây là evidence để sửa workflow; không phải template dự án hay lý do hạ fail-closed.

## Kết quả đã chứng minh

- Phase 1 tạo parent có provenance đủ để carry; phần lỗi trở thành mandatory rewrite thay vì sửa mờ trên canonical.
- Phase 2 R3 review đủ `491/491`, fresh recheck `80/80`, zero unresolved.
- Combined provenance audit sạch; canonical `14.706` hàng được merge nguyên tử; runtime QA artifact được build ngoài game live.
- Full regression cuối: `63 PASS`, một live-CDP opt-in skip.

## Sai lầm tổng quát và sửa bắt buộc

| Failure | Root cause | Quy tắc mới |
|---|---|---|
| Phase-2 R1 có `943/981` challenge không giải được | Hidden target hash không suy ra từ prompt; model bị buộc đoán preimage | Challenge correct target phải byte-derivable từ visible prompt source và host phải verify độc lập trước arm |
| Phase-2 R2 chết ở whitespace-only donor | `keep_identity` spacer có target đúng là blank, xung đột gate `rewritten` nonblank | `source.strip()` phải nonempty ở builder, authorizer và independent host verifier |
| Recheck v2 không chạy trong PowerShell | Quoted executable đứng đầu command bị parse như expression; allowlist lại khóa exact bytes | Chạy exact receiver-shell probe trước arm; mọi retry dùng host-private epoch mới, không sửa authorization cũ |
| UTF-8 có thể hỏng qua Windows default codec | Hook subprocess thiếu `-X utf8`; byte tiếng Việt có thể thành surrogate | Mọi semantic-hook/controller command Windows dùng `python -X utf8`; command generator và regression cùng kiểm |
| Auditor đòi đúng ba lifecycle events | Một prestart recheck bị reject hợp lệ tạo thêm arm/reset | Chọn epoch theo exact authorization path; chỉ bỏ qua retry epoch khi chứng minh zero semantic write và zero commit |
| Native write lặp trước một commit bị báo corruption | Tool retry byte-identical/idempotent tạo hai authorize/readback pairs | Chỉ collapse exact duplicate cùng auth/conversation/batch/prompt/payload/disk trước một commit; payload khác vẫn fail |
| Full-pass `finalized` bị hiểu gần như final | Fresh recheck là gate riêng nhưng chưa có helper đầu-cuối | Recheck materializer reusable là artifact bắt buộc; full pass không đủ điều kiện merge |
| Builder test hỏng sau canonical merge | Test đọc mutable production canonical thay vì baseline fixture | Builder/regression dùng immutable pre-merge fixture và exact hash; không phụ thuộc lifecycle state hiện tại |
| Acceptance/runtime tooling được viết muộn | Workflow chỉ chuẩn bị translation package, chưa chuẩn bị đường về | Trước dispatch phải có return verifier, atomic acceptance adapter và runtime-copy route hoặc ghi blocker rõ |
| Hermes phải đọc nhiều ledger/file lớn | Thiếu compact receipt và helper chung khi lỗi mới xuất hiện | Receipt-first; full report ở disk; chỉ mở payload/ledger khi compact receipt mismatch hoặc loại lỗi mới |

## Phase 1 sau postmortem

- Ceiling mới là `12`, nhưng cap là package-configured `1..12`; guard, manifest, schedule và controller phải bằng nhau. Nếu provider không nhận wave 12, reject prestart và build run mới với cap thấp hơn; không đổi cap giữa run.
- Worker tạo **preview-grade draft** một lượt: đủ nghĩa, đủ hàng, glossary/xưng hô/context, không source-copy ngoài `keep_identity`; trước khi emit phải làm silent self-review. Đây không phải editorial Phase 2.
- Lease vẫn giới hạn theo bytes và độ khó. V2.5 giữ `23.000` prompt-row bytes/lease và nâng budget wave-12 lên `300.000` bytes; trên corpus PMA, phép đo deterministic là `526` lease / `44` wave thay vì R6 `434` lease / `62` wave-7—giảm `29,0%` vòng coordinator. Đây là corpus metric, không phải cam kết provider; wave 12 bị provider từ chối trước commit thì retire và rebuild cap thấp hơn.
- Sau deterministic acceptance, không tự build demo. Ghi `phase1_accepted_waiting_for_user_direction` và hỏi user chọn `build_demo_patch`, `external_phase2_antigravity`, `hermes_cron_phase2`, hoặc `pause`.
- Demo chỉ là route tùy chọn: build patch đảo ngược được dưới nhãn `PREVIEW_PHASE1_DEMO_NOT_FINAL`, không merge canonical/đưa sang `buildpatch`, rồi ghi `phase1_demo_ready_waiting_for_user_direction` và hỏi lại. Hai route Phase 2 dùng cùng accepted snapshot; route Hermes cron không tạo external Phase-2 package.

## Phase 2 sau postmortem

- Main-only cap `0` giữ nguyên. Không parallelize một corpus final giữa nhiều main agents.
- Full review vẫn 100%; giảm thời gian bằng packet profile, không bằng bỏ row hoặc compact blanket acceptance:
  - mandatory/runtime/explicit-high-risk: `30`;
  - dialogue/lore thường: `60`;
  - short UI: `100`; clean identity UI: `120`;
  - protected-token rows giữ deterministic structural gate; chỉ hạ về high-risk khi markup dày hoặc có evidence;
  - mọi packet còn bị hard-cap theo prompt bytes.
- Fresh recheck gồm all rewritten/runtime/explicit high-risk và stratified >=10% accepted. `keep_identity` là một stratum riêng, nhưng clean identity không tự động thành high-risk toàn bộ; chỉ nâng toàn nhóm khi policy collision/evidence yêu cầu.
- Trên corpus PMA, profile `30/60/100/120` tạo `388` packet thay vì fixed-30 `491`—giảm `21,0%` controller cycles; challenge slots còn `891` thay vì `981` do bớt rounding, nhưng coverage vẫn >=5% từng packet. Đây là regression metric, không phải lý do nới challenge policy.
- Dùng generic `scripts/materialize_guarded_phase2_recheck.py`; chạy exact PowerShell probe trước arm.
- Auditor chấp nhận prestart-rejected epoch và byte-identical retry chỉ theo điều kiện fail-closed đã có regression.

## Token/cost lesson

Không có số token đáng tin để công bố cho run lịch sử. Bằng chứng cho thấy phần lãng phí lớn phía Hermes là forensic lặp lại, custom glue và đọc full artifacts vào chat—not translation. Vì vậy tối ưu đúng là:

1. chuẩn bị helper đường về trước dispatch;
2. compact receipt cho build/prepare/status/accept;
3. một targeted RED/GREEN cho mỗi failure class;
4. full suite đúng một lần ở mỗi release boundary;
5. không poll và không yêu cầu user báo `đã gửi`.

## Những gì cố ý không đổi

- Phase 2 review 100%, challenge, fresh recheck, main-only cap `0`, exact-key provenance và atomic canonical write.
- Không dùng script để tạo language decisions.
- Không chia cùng một package/run cho hai máy active cùng lúc.
- Runtime artifact vẫn engine-specific; không tạo abstraction giả cho import/repack.
