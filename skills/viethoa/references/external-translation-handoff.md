# External translation handoff

Dùng cho Plan 2. Hermes chuẩn bị translation-only data bất biến; Antigravity làm toàn bộ ngôn ngữ. Mọi return là untrusted tới khi Hermes tự kiểm exact bytes, semantic origin, challenge và recheck evidence.

## Baseline hiện hành

```text
AGY-VIETHOA-HANDOFF/2.5-TWO-PHASE-DRAFT12-PREVIEW-FINAL0-GUARDED
contract_version=2.5.1
semantic_authorization=agy-semantic-origin-authorization/v3
phase2_response=agy-explicit-review/v2
```

`2.3`, `2.2` và `2.0|2.1` chỉ audit artifact lịch sử. Không sửa manifest/checksum hoặc relabel legacy package.

## Phase 1 và checkpoint chọn route

1. **Phase 1 Parallel Preview-grade Draft:** one main coordinator, package-configured cap `1..12` (default `12`), exact disjoint leases, native worker responses, silent self-review trong cùng authoring pass, one deterministic writer, một return ZIP.
2. **Hermes acceptance:** preserve raw bytes, validate envelope/source/token/policy/lease/semantic origin và tạo accepted target snapshot. Ghi `phase1_accepted_waiting_for_user_direction`.
3. **Hỏi user chọn đúng một route:** `build_demo_patch`, `external_phase2_antigravity`, `hermes_cron_phase2`, hoặc `pause`. Không tự chọn demo hoặc backend Phase 2.
4. **Demo route:** build reversible `PREVIEW_PHASE1_DEMO_NOT_FINAL`, thu runtime feedback, ghi `phase1_demo_ready_waiting_for_user_direction`, rồi hỏi lại.
5. **External Phase 2 route:** cap 0, full corpus reverse/different order, one native explicit decision per row, deterministic challenge mỗi packet, mandatory fresh recheck, một final ZIP.
6. **Hermes cron Phase 2 route:** review 100% corpus từ cùng accepted snapshot bằng deterministic cron lifecycle; không tạo hoặc arm external Phase-2 package.

Resume chỉ cùng immutable `(package_id,run_id,phase)` và verified ledger. Rejected attempts không overwrite.

## Identity và immutable binding

Canonical identity là exact `(domain,key)`. Nếu receiver cần one-field ID, dùng opaque deterministic `handoff_id` one-to-one manifest-pinned. Cấm drop domain, bare-key collision, positional/source-only/suffix/fuzzy merge.

Mọi lease/packet bind package/run/phase/batch, raw prompt/input hashes và parent phase hash. Manifest khóa build/source/target, canonical/key/order/source snapshots, policy/glossary/token/tool/schema/schedule hashes, expected return filename và host modes.

## Host enforcement

Hai guards cùng bắt buộc:

- `subagent_cap.py`: Phase 1 exact cap/lease/bound conversation; Phase 2 cap 0; nested/message/manage deny.
- `semantic_response_guard.py`: exact controller command allowlist; chỉ native `write_to_file` exact response path; canonical v2 schema/order/prompt hash; PostToolUse readback; conversation binding; commit receipt; append-only external event chain.

Package pins guard snapshot SHA-256. Maintenance guard pins active/template bytes, hook matchers, `SCHEMA`, `AUTH_SCHEMA`, `CONTRACT` qua restart/update. Default không run: subagent `idle_main_only`; semantic `inactive`.

Host semantic auth v3 và actual Phase-2 challenge overlay là sidecars materialized ngoài package/work roots sau extraction và trước khi Antigravity nhận task. Auth bind roots/controller/schedule/overlay hashes, prompt/response paths và commands. ZIP schedule chỉ mang hidden `challenge_slots`; actual IDs/rows/targets không được xuất hiện trong ZIP. Antigravity không có pre-arm turn và không tự tạo/sửa/đọc auth, overlay, hook, guard, state hoặc event ledger.

## Phase-1 outbound/return

Core:

```text
project-manifest.json
START-HERE.md
PHASE1-RULES.md
handoff-id-map.csv
glossary.csv
english-policy.csv
token-profile.json
draft-evidence-schema.json
TRANSLATION-PROMPT.txt
input/full-corpus.csv
schedule/phase1.json
host/phase1-host-authorization.json
host/semantic-authoring-authorization.template.json
tools/controller.py
tools/finalizer.py
tools/semantic_response_guard.py
tools/materialize_semantic_authorization_v3.py
tools/validate_two_phase_handoff_package.py
skill/game-translation-contributor/SKILL.md
checksums.sha256
```

Worker output `agy-phase1-draft/v2` exact-partitions one lease in input order. Required target nonblank. Main direct-writes raw worker result unchanged; scripts cannot generate/fill/repair language. Finalizer requires full exact coverage, clean structure, native worker result↔direct-write↔commit evidence, ledger, `reserved=0`, one ZIP. Phase-1 output không canonical-final eligible.

Hermes stages raw bytes, verifies all bindings, exact union/order/source/tokens and native provenance, then creates accepted target snapshot + `phase1-acceptance-parent.json`. Không merge canonical hoặc set reviewed. Sau đó dừng ở `phase1_accepted_waiting_for_user_direction` và hỏi user chọn route; technical eligibility không phải authorization để tự khởi chạy Phase 2.

## Phase-2 outbound/return

Core:

```text
project-manifest.json
START-HERE.md
PHASE2-RULES.md
handoff-id-map.csv
glossary.csv
english-policy.csv
token-profile.json
decision-evidence-schema.json
TRANSLATION-PROMPT.txt
input/full-corpus-with-draft.csv
schedule/phase2.json
parent/phase1-acceptance-parent.json
runtime/runtime-feedback.csv
host/semantic-authoring-authorization.template.json
tools/controller.py
tools/finalizer.py
tools/expand_explicit_decisions_v2.py
tools/semantic_response_guard.py
tools/materialize_semantic_authorization_v3.py
tools/materialize_phase2_challenge_overlay.py
tools/audit_guarded_phase2_provenance.py
tools/validate_two_phase_handoff_package.py
skill/game-translation-contributor/SKILL.md
checksums.sha256
```

External Phase 2 chỉ được build khi user chọn `external_phase2_antigravity`. Input target chỉ từ Hermes-accepted Phase-1 snapshot; runtime feedback là optional nếu demo đã chạy; không expose worker identity/action/reason/confidence.

Phase 2 reviews 100% real rows. Packet profile: mandatory/runtime/explicit-high-risk `30`, dialogue/lore thường `60`, short UI `100`, clean identity UI `120`, luôn kèm hard prompt-byte cap. Protected-token/markup vẫn qua deterministic structural gate; chỉ dense markup cần gắn explicit high-risk. `agy-explicit-review/v2` có một ordered decision object per row; legacy `accepted_ids`, ranges, wildcard và omission default bị reject. `accepted` cần ≥3 distinct review codes; rewritten cần target mới + reason; final zero unresolved.

Mỗi packet khai báo `challenge_slots >= max(1, ceil(5% × real rows))`; Hermes lấp slot bằng host-private overlay sau extraction. Challenge lấy parent ngoài packet hiện tại, dùng ID lowercase-hex cùng exact width với real IDs và corruption cơ học; correct target là pre-corruption target. Guard xác minh prompt row byte-equal overlay và chỉ allow exact rewrite hash; challenge không vào release snapshot. Sau full pass, controller xuất exact decision index + CSV/receipt; Hermes promote exact CSV bytes ra host-private, tạo recheck schedule bind `parent_full_pass={path,sha256,row_count}`, reset/re-arm guard cùng package/run và giữ nguyên event-chain head. Fresh recheck bắt buộc cho all rewritten, runtime/high-risk và stratified deterministic ≥10% accepted real rows. Pinned provenance auditor phải correlate cả hai guard epochs với packet commits và final snapshot trước acceptance.

## Preview boundary

Preview là route tùy chọn, chỉ build khi user chọn `build_demo_patch`. Nó lấy Hermes-accepted Phase-1 snapshot làm parent và phải ghi:

```text
PREVIEW_PHASE1_DEMO_NOT_FINAL
PRIVATE_TEST_ONLY
NOT_FOR_RELEASE
```

Nó kiểm route/font/playability/rollback, không chứng minh final wording, không merge canonical và không được `buildpatch` promote.

## Export gate Hermes

- exact canonical/source/policy/glossary/token lock;
- phase manifest/schedule/parent and host contracts;
- guard/controller/finalizer/validator/expander/schema self-tests and hashes;
- every Phase-2 packet has challenge; recheck schedule covers required union;
- reopen ZIP, CRC/checksum/no duplicate/symlink/traversal/private/forbidden file;
- validate package and issue external sidecar with ZIP hash/IDs/counts/expected filename;
- materialize host auth and, for Phase 2, private challenge overlay only after exact extraction paths exist; actual challenge data stays outside ZIP/work roots; after full pass use `scripts/materialize_guarded_phase2_recheck.py`, not a project-specific wrapper;
- arm both guards before Antigravity receives its first task; no pre-arm agent turn;
- do not dispatch Phase 1 until user authorizes translation.

## Incoming final gate

1. Preserve raw ZIP/hash.
2. Verify whole envelope/parent/tools/ledger.
3. Verify host event chain no gap/fork and active/template/package guard hashes.
4. Correlate every prompt → native payload → disk response → commit → normalized decision → final target.
5. Verify every challenge exact rewrite, full 100% pass, mandatory fresh rechecks and zero unresolved.
6. Run deterministic source/token/policy/glossary/residual/shape gates.
7. Whole-envelope/provenance/challenge/recheck failure rejects whole run. Partial row merge is allowed only after whole run provenance is clean.
8. Atomic exact-key canonical transaction; final runtime QA before release installer.

`PASS`, `100%`, controller exit code, receipt or model self-report never replaces bytes/hash/count/readback/host-origin evidence.
