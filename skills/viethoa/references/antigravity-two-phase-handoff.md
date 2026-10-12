# Antigravity two-phase host-guarded handoff

Baseline hiện hành:

```text
AGY-VIETHOA-HANDOFF/2.5-TWO-PHASE-DRAFT12-PREVIEW-FINAL0-GUARDED
contract_version=2.5.1
semantic_authorization=agy-semantic-origin-authorization/v3
phase2_response=agy-explicit-review/v2
```

Mục tiêu: Antigravity làm toàn bộ dịch thuật và Language/Semantic QA; Hermes chỉ sở hữu corpus, deterministic acceptance, import/repack/runtime và final merge. Baseline này sửa lỗ hổng của `2.2|2.3`: prompt cấm script không đủ khi host vẫn cho `run_command` hoặc file writer tạo `accepted_ids` hàng loạt.

Không hệ thống kỹ thuật nào chứng minh tuyệt đối một model đã “suy nghĩ sâu”. Baseline `2.5` giữ ba bằng chứng của `2.4`—native semantic origin, challenge chống blanket acceptance và explicit full-corpus review + recheck—đồng thời nâng Phase 1 thành preview-grade draft với cap cấu hình tối đa `12`, thêm checkpoint để user chọn route tiếp theo và chuẩn hóa multi-host/recheck helper. Case evidence: `promise-mascot-agency-two-phase-postmortem.md`.

## Kiến trúc

```text
Phase 0 policy lock (trong preflight Phase 1)
  ↓
Phase 1 Parallel Preview-grade Draft — one main + package cap 1..12
  ↓ one Phase-1 return ZIP
Hermes immutable acceptance + accepted draft snapshot
  ↓
state=phase1_accepted_waiting_for_user_direction
  ↓ ask user; choose exactly one
  ├─ build_demo_patch → phase1_demo_ready_waiting_for_user_direction → ask again
  ├─ external_phase2_antigravity → fresh Phase-2 ZIP + host-only authorization
  ├─ hermes_cron_phase2 → deterministic Hermes full-corpus review, no external Phase-2 package
  └─ pause → preserve accepted snapshot/receipts

External route only:
Phase 2 Main-only Final Language & Semantic Review — cap 0
       ↓ one Phase-2 final ZIP
Hermes envelope + host-origin + challenge + recheck gates
       ↓
canonical transaction → runtime/release
```

Phase 1 chứng minh draft coverage; Phase 2 mới tạo candidate ngôn ngữ final. Structural/runtime preview PASS không chứng minh wording final.

Mọi lease/packet bind exact `(package_id,run_id,phase,batch_or_lease_id,prompt_sha256,input_payload_sha256,parent_phase_sha256)`; mismatch reject whole envelope.

## Hai host guards độc lập

### 1. Subagent phase control

Một phase-aware cap hook fail closed:

```text
idle_main_only
  limit=0, reserved=0

phase1_parallel_draft
  1<=limit<=12
  exact package/run/manifest/authorization
  one bound main conversation
  exact allowed lease map

phase2_main_only_final
  limit=0, reserved=0
  invoke_subagent|send_message|manage_subagents denied
```

Phase-1 arming JSON gồm exact `package_id`, `run_id`, `manifest_sha256`, package-configured `1<=max_subagents<=12`, `{lease_id,lease_sha256}`. Manifest, schedule, host authorization và controller wave limit phải bằng nhau; default là `12`. Nếu provider từ chối wave 12 trước semantic commit, retire run và build fresh package với cap thấp hơn—không đổi cap giữa run. Worker marker:

```text
AGY_LEASE_V1::<package_id>::<run_id>::<lease_id>::<lease_sha256>
```

Pinned Phase-1 controller phải đưa cả `lease_sha256` và complete `invocation_marker` vào exact current prompt; main coordinator copy marker byte-for-byte sang worker description. Vì semantic guard cấm đọc schedule/auth, prompt thiếu một trong hai field là package-tool hard stop trước semantic work, không được đoán hash.

Bắt buộc global cap, exact configured `N/(N+1)` boundary tới hard ceiling `12/13`, no nested worker, exact lease/hash, idempotence chỉ cùng step+lease, post/error/fully-idle release, transition fail khi `reserved>0`.

### 2. Semantic-origin guard

Cả Phase 1 và Phase 2 phải arm riêng bằng host-only sidecar:

```text
schema=agy-semantic-origin-authorization/v3
contract=AGY-VIETHOA-HANDOFF/2.5-TWO-PHASE-DRAFT12-PREVIEW-FINAL0-GUARDED
exact package/run/phase/manifest
absolute extracted package/work/controller/prompt/response paths
controller + phase-schedule SHA-256
exact single-command allowlist
response schema
Phase-2 host-private overlay path/hash
Phase-2 challenge ID → SHA-256(correct target UTF-8)
```

Final authorization và actual Phase-2 challenge overlay nằm ngoài immutable package/work roots để tránh self-hash/path vòng tròn và challenge leakage. ZIP/schedule chỉ khai báo `challenge_slots >= max(1, ceil(5% × real rows))`; tuyệt đối không chứa actual challenge ID, row hoặc target. Trước materialize/arm, host `prepare_guarded_handoff_host.py` phải độc lập kiểm overlay lấp exact slot count, challenge ID unique, prompt row là corrupted `keep_identity`, và `expected_target_sha256 == SHA-256(prompt_row.source UTF-8)` với derivation `prompt_source_keep_identity`; không được chỉ tin package-pinned materializer. Compact receipt ghi `challenge_count` và `prompt_derivable_challenge_count`, hai số phải bằng nhau. Hermes materialize overlay + auth sau extraction, arm cả hai host guards, rồi mới gửi task/prompt đầu tiên cho Antigravity. Antigravity không có pre-arm turn và không tạo, sửa hoặc đọc auth/overlay/state/event ledger.

Khi guard active:

- `run_command` Phase 1 chỉ allow exact package-pinned `verify|init|wave|select|commit|status|finalize`; legacy `next` không được authorize. Phase 2 giữ `next|commit|status|finalize`. `CommandLine` và `Cwd` phải byte-exact; `Cwd` là package root trong allowlist, không phải Antigravity project root. Continuation phải đưa một parseable JSON args object thay vì command/CWD rời nhau. Không newline, chain, redirection, `python -c|-m`, renamed flag/path hoặc helper;
- Trước first semantic tool call, host phải render một bootstrap prompt riêng từ authorization đã materialize, nằm ngoài package/work roots. Prompt đó phải expose exact JSON args cho `wave|select|commit|finalize`, exact current prompt/response paths và worker-wrapper contract; offline test từng args bằng cùng matcher guard. Coordinator gọi `wave` trước, vì chưa có `current/prompt.json` để đọc. Không dùng package README/skill như bootstrap context. Actual canonical wave wrapper phải nằm dưới receiver single-view budget; coordinator đọc đúng một lần, không `ContentOffset`/pagination rồi mới copy nested prompts;
- `view_file` chỉ allow exact `current/prompt.json`; `grep_search|find_by_name|list_dir` và đọc auth/overlay/schedule/state/ledger đều bị deny;
- `write_to_file` chỉ allow direct overwrite exact `current/response.json`; không gửi `ArtifactMetadata` vì field đó chuyển Antigravity sang artifact-only path mode và bác work-root filesystem path;
- `replace_file_content|multi_replace_file_content|edit_file|create_file|delete_file|move_file|rename_file|apply_patch` bị deny;
- direct payload phải là một bare UTF-8 JSON object hợp lệ, exact field set, prompt row order và prompt hash. Minified hoặc pretty-printed đều hợp lệ; BOM, code fence, prose và duplicate key bị bác. Raw payload vẫn byte-exact native worker evidence; controller mới canonicalize JSON serialization, còn prompt/state vẫn dùng sorted-key canonical;
- first semantic tool call bind main conversation; khác conversation bị deny;
- PostToolUse phải luôn emit đúng `{}` theo Antigravity proto; nó không có quyền trả `decision`. Khi readback lỗi, guard giữ `readback=false` để PreToolUse của `commit` fail closed;
- disk response chỉ hợp lệ khi byte-exact bằng canonical payload hoặc bằng payload cộng đúng một LF do native writer thêm. Event chain phải ghi riêng `payload_sha256`, `native_lf_sha256`, actual `disk_sha256` và `normalization=exact|append_lf`; BOM, CRLF, khoảng trắng hay nhiều LF đều bị bác;
- exact duplicate PreToolUse cho cùng conversation/batch/prompt/payload trước một PostToolUse được dedupe idempotently; payload khác không được ghi đè receipt đang chờ readback;
- `commit` bind actual `disk_sha256` đã readback, không so nhầm disk hash với payload hash; prompt hoặc disk bytes đổi sau readback đều bị deny;
- Phase-2 `finalize` chỉ được guard ghi event/allow đúng một lần khi pinned controller state chứng minh `next_packet_index == commit_count == packet_count`, `active_packet_id=null` và `finalized=false`; premature/idempotent finalize bị deny trước event vì package-pinned provenance auditor yêu cầu exact một finalize sau commit cuối;
- Phase-2 bootstrap phải đặt exact `agy-explicit-review/v2` top-level/accepted/rewritten/needs-context contract trước command block và giữ đủ ngắn để schema anchor sống qua context compaction; nếu một write bị reject, dừng ngay, cấm probe schema variants;
- controller hash drift sau arm fail closed.

Host ghi append-only hash-chain ngoài package/workspace: authorization hash, conversation, step, batch, prompt hash, payload hash, readback và command. Final acceptance đối chiếu chain với transcript, response files, controller ledger và final target snapshot.

Hai guard global của một Antigravity profile chỉ có một active package/run. Ngay trước khi user gửi bootstrap, đọc cả hai status: nếu package/run khác đang active hoặc semantic `main_conversation_id` đã bind, không reset/arm run mới; giữ hàng đợi đến khi run kia dừng, hoặc dùng profile/host tách biệt. Re-check này phải xảy ra sau mọi background/other-workspace activity, không chỉ lúc host preparation.

Maintenance/update guard phải pin active semantic guard bằng template, khôi phục hook nếu mất/tamper, kiểm `SCHEMA`, `AUTH_SCHEMA`, `CONTRACT`, hook matchers và inactive/armed state. Default ngoài run là `subagent idle_main_only` + `semantic inactive`.

## Phase 1 — Parallel Preview-grade Draft

### Lease và scope

- Toàn exact release corpus xuất hiện đúng manifest count.
- `keep_identity` bằng exact expected source bytes.
- Mọi row cần dịch có target không rỗng.
- `review_action=translated|provisional_needs_context`.
- `provisional_needs_context` vẫn cần draft trung tính, faithful; không bịa giới tính/quan hệ/cốt truyện.
- Lease union đúng full corpus, pairwise disjoint, mỗi ID đúng một lần, source/input/prompt hash riêng.

Worker chỉ author một lease, không ghi shared state và không nested delegation. Phase 1 dùng **atomic wave**: exact `wave` ghi một `agy-semantic-wave/v1` wrapper chứa tối đa package-configured `1..12` nested prompt cùng `prompt_sha256_by_batch`; coordinator tạo đúng một worker entry cho mỗi nested prompt; trường `Prompt` là JSON `agy-phase1-worker-invocation/v1` chứa `instructions` có `DO NOT CALL TOOLS`, `expected_prompt_sha256` khớp `prompt_sha256_by_batch`, `response_schema=agy-phase1-draft/v2` và nested prompt nguyên vẹn. Sau đó phát ONE native `invoke_subagent` call containing exactly every staged worker entry. Sau khi toàn wave trả về, exact `select` phục hồi từng staged prompt để direct-write/commit tuần tự; chỉ gọi wave mới khi staged bằng zero. Legacy `next` và rolling refill bị cấm. Final wave có thể ít hơn. Do not invoke one worker and wait trước khi launch full wave. Builder giữ mỗi lease trong prompt-byte cap; default v2.5 là `23.000` prompt-row bytes/lease và `300.000` budgeted bytes/wave-12. Không được đạt wave 12 bằng cách phình dialogue lease hoặc bỏ context. Phase 1 là **preview-grade draft** một lượt: trước khi emit JSON, worker làm silent self-review ngay trong authoring response về fidelity, omission/addition, natural Vietnamese, glossary/xưng hô, tokens/newlines, residual source và UI fit. Không gọi thêm reviewer agent hay cross-lease polish; meticulous editorial pass vẫn thuộc Phase 2. Raw worker tool result là evidence bất biến và main coordinator phải direct-write byte-exact native worker result vào raw path, không transliterate, normalize, reserialize, sửa schema/row/câu chữ hoặc thay byte. Raw phải là một bare UTF-8 JSON object hợp lệ; minified hoặc pretty-printed đều được, nhưng BOM, code fence, prose và duplicate key bị bác. Controller được phép **deterministic envelope normalization** duy nhất: raw object phải có exact `schema,batch_id,prompt_sha256,rows`; controller canonicalize JSON formatting và có thể đổi top-level worker-copy schema `agy-semantic-prompt/v1` sang `agy-phase1-draft/v2`, archive raw thành `raw-response.json`, normalized response và receipt `agy-phase1-envelope-normalization/v1`. Receipt ghi `changed_fields=json_format|schema` và khóa `target_utf8_sha256_by_handoff_id`; mọi target UTF-8 bytes, ID, order, action, note và row field phải giữ nguyên. Mismatch khác retry exact lease. Trước first `select` của mỗi atomic wave, semantic guard phải thấy một exact wave reservation cho toàn staged lease set trong subagent event ledger. Trước mọi raw write, guard phải tìm payload byte-exact trong native child transcript có exact invocation marker; append-only event ghi `native_worker_conversation_id`. Không có exact wave reservation hoặc native worker transcript thì deny; checkpoint không thể cấp quyền main dịch trực tiếp. `RECOVERABLE_SEQUENCE` (wave wrapper/write-before-SELECT hoặc thiếu exact full-wave reservation) phải tự chạy lại đúng WAVE/SELECT mà không stop/report. `RECOVERABLE_WORKER_RETRY` retry đúng một selected lease bằng fresh worker. Legacy `current prompt fields missing` khi current schema là `agy-semantic-wave/v1` được xử lý như `RECOVERABLE_SEQUENCE`. Non-recoverable denied write is a hard stop. Do not dump worker payloads hoặc translation rows trong blocker report; chỉ báo IDs, hashes, counts và exact non-recoverable reason. Controller commit-time structural gate bắt buộc reject source-copy, edge whitespace, protected-token, locked-term và physical-newline mismatch; post-final acceptance vẫn chạy nhưng chỉ legacy package thiếu gate mới tạo Phase-1 rework remainder. Controller là writer duy nhất của queue/snapshot/ledger/ZIP. Phase 1 là preview-grade draft một lượt có silent self-review trong cùng response; editorial second pass/cross-lease polishing thuộc Phase 2.

### Response v2

```json
{
  "schema":"agy-phase1-draft/v2",
  "batch_id":"<exact lease>",
  "prompt_sha256":"<exact raw prompt SHA-256>",
  "rows":[
    {
      "handoff_id":"<exact id>",
      "translation_vi":"<nonblank draft>",
      "review_action":"translated",
      "notes":""
    }
  ]
}
```

Rows đúng input order. Cấm wildcard/range/positional repair/default fill và script-generated target. Hermes acceptance phải match direct-write payload với exact native worker result trong transcript; host direct-write receipt một mình chưa chứng minh worker origin.

### Phase-1 completion

- full exact coverage, no missing/extra/duplicate/foreign key;
- source/token/newline/schema/encoding/policy parity;
- raw prompt/worker response hashes và native provider/model evidence;
- subagent reservations + semantic-origin event chain + controller ledger;
- disk response bytes đúng một trong hai normalization được host pin: exact payload hoặc payload cộng một LF; payload hash, disk hash và controller commit hash liên kết byte-exact;
- zero blank required target;
- ZIP CRC/checksum/filename sạch;
- `reserved=0` trước khi return; sau Hermes acceptance, host owner disarm về `idle_main_only` + semantic `inactive` trong lúc chờ user chọn route.

Return một ZIP rồi stop. Hermes nhận/accept, ghi `phase1_accepted_waiting_for_user_direction` và hỏi user chọn đúng một route: `build_demo_patch`, `external_phase2_antigravity`, `hermes_cron_phase2`, hoặc `pause`. Không tự build demo hoặc tự chọn Phase 2. Nếu user chọn demo, build artifact có thể gỡ bỏ, thu runtime feedback, ghi `phase1_demo_ready_waiting_for_user_direction` rồi hỏi lại; demo không khóa route Phase 2 sau đó.

## Hermes Phase-1 acceptance và preview

1. Lưu exact ZIP bytes/hash trước extract.
2. Verify CRC, duplicates, symlink/traversal/private paths, checksums và pinned tools.
3. Verify package/run/manifest/auth/lease/prompt/input/source/policy/token bindings.
4. Recompute exact ID/key union/order/source/tokens từ canonical.
5. Correlate native worker responses → direct-write host events → committed evidence → final snapshot.
6. Whole-envelope/provenance mismatch reject toàn return, không fuzzy repair. Nếu envelope/provenance sạch, dùng `accept_guarded_phase1_snapshot.py` để phân loại deterministic: `direct_phase2_eligible=true` là route mặc định sang full-corpus Phase 2 với exact remainder thành mandatory Phase-2 rewrite; không dựng Phase-1 rework package. Chỉ reissue exact Phase-1 remainder khi receipt false vì target không thể carry an toàn, như blank/non-string target, stale source-token declaration hoặc Unicode corruption. Phase-2 host guard/controller phải deny `accepted|needs_context` và structurally validate every mandatory rewrite.
7. Tạo accepted target snapshot + `phase1-acceptance-parent.json`; không merge canonical final hoặc set `reviewed`.
8. Native-worker retry có thể làm số `authorize_direct_response/readback/commit-command` lớn hơn số controller commits. Chỉ chấp nhận khi từng attempt thừa gắn cùng exact batch/prompt, có controller failure cụ thể trong main transcript, raw/disk hash của attempt thừa không xuất hiện trong commit chain, retry có fresh native reservation/transcript, và mỗi final commit vẫn map one-to-one tới một native payload/readback. Malformed/quota/non-byte-exact failures trước semantic authorization không được tính là commit.
9. `accept_guarded_phase1_snapshot.py` chỉ dùng khi canonical parent là corpus translation-new cùng row count, mọi row `state=pending` và target blank. Với QA/retranslation subset lấy từ canonical đã có target trong `community_vi_reference`, không tạo canonical giả để qua gate; dùng acceptance purpose-built bind package input `domain,key,source,community_vi_reference` về exact canonical key/source/target/hash, lưu candidate/flags/parent riêng và giữ canonical bất biến. Case-only glossary variant có thể là Phase-2 review flag nếu casefold obligation vẫn đủ; không auto-rewrite capitalization.

Chỉ build Preview khi user chọn `build_demo_patch`. Preview lấy accepted snapshot làm parent, namespace:

```text
PREVIEW_PHASE1_DEMO_NOT_FINAL
PRIVATE_TEST_ONLY
NOT_FOR_RELEASE
```

Preview kiểm import/repack/boot/locale/font/glyph/wrap/layout/rollback. Nó dùng exact accepted snapshot, tạo copyable/reversible demo artifact riêng và ghi runtime feedback theo exact handoff ID. Nó không merge canonical final, không đổi Phase-2 parent, không public/share/promote và không giao `buildpatch`.

## Phase 2 — Main-only final review

Host preflight phải đồng thời đọc:

```text
subagent: mode=phase2_main_only_final, limit=0, reserved=0
semantic: mode=phase2_main_only_final, exact package/run/manifest/auth
active guard/template hashes equal package guard snapshot hash
```

Input chỉ từ canonical source/reference/context, Hermes-accepted Phase-1 target và user demo runtime feedback nếu route demo đã chạy. Không expose worker identity/action/reason/confidence. Full schedule dùng reverse/different deterministic order. Full review vẫn 100%; giảm wall time bằng packet profile precomputed, không bỏ row hay compact blanket acceptance: mandatory/runtime/explicit-high-risk `30`, dialogue/lore thường `60`, short UI `100`, clean identity UI `120`, với hard prompt-byte cap cho mọi packet. Protected-token rows vẫn qua deterministic structural gate; chỉ hạ chúng về packet high-risk khi markup dày hoặc có explicit risk evidence, không mặc định làm nhỏ toàn corpus.

### Explicit response v2

Một decision object cho mỗi prompt row đúng thứ tự:

```json
{
  "schema":"agy-explicit-review/v2",
  "batch_id":"p2-00001",
  "prompt_sha256":"<exact raw prompt SHA-256>",
  "decisions":[
    {
      "handoff_id":"<id>",
      "action":"accepted",
      "review_codes":["source_fidelity","context_fit","natural_vi"],
      "notes":""
    },
    {
      "handoff_id":"<id>",
      "action":"rewritten",
      "translation_vi":"<new target>",
      "reason_codes":["wrong_key_target"],
      "notes":""
    },
    {
      "handoff_id":"<id>",
      "action":"needs_context",
      "question":"<specific question>"
    }
  ]
}
```

- `accepted` giữ current target byte-exact và có ít nhất ba distinct allowed `review_codes`;
- `rewritten` nonblank, khác target cũ, có reason cụ thể;
- `needs_context` không bịa target;
- cấm `accepted_ids`, omission default, ranges, wildcards, generated lists, duplicate/extra/out-of-order IDs;
- final yêu cầu zero unresolved.

Review 100% corpus trên fidelity, omission/addition, wrong-key target, natural Vietnamese, glossary/proper noun/xưng hô, consistency, punctuation/newline/token, residual English/CJK, UI fit và runtime findings.

### Deterministic challenge

Mỗi packet khai báo `challenge_slots >= max(1, ceil(5% × real rows))`, nhưng actual challenge không nằm trong ZIP. Sau extraction và trước khi Antigravity nhận task, Hermes tạo host-private overlay từ một clean `keep_identity` real row **ngoài packet hiện tại**, với `current_translation_vi == source`, rồi làm hỏng current target bằng target-swap, truncation hoặc xóa protected token. Exact correct target phải suy ra byte-exact từ chính prompt: `SHA-256(prompt_row.source UTF-8) == expected_target_sha256`; không được dùng hidden free-translation gold vì đó là bài toán preimage SHA-256 bất khả thi cho model. Challenge donor source bắt buộc `source.strip()` nonempty: whitespace-only keep_identity/layout-spacer rows không được làm donor vì guard cấm rewritten target blank; chúng vẫn là real rows hợp lệ và được `accepted` khi target hiện tại đúng source. Donor có thể tái dùng ở packet khác nhưng không lặp trong cùng packet. ID giả phải là lowercase hex cùng exact width với real `handoff_id`, không prefix/marker và không trùng release corpus; target-swap không được trùng target đang hiện trong packet. Overlay bind full prompt row, parent ID, corruption kind, `expected_target_derivation=prompt_source_keep_identity` và expected target hash.

Host-only authorization v3 bind exact schedule + overlay hashes và lưu `challenge_id → SHA-256(correct target UTF-8)`. Guard xác nhận prompt real rows đúng schedule, challenge rows byte-equal overlay, rồi chỉ allow action `rewritten` với exact target hash. `accepted`, `needs_context`, wrong rewrite hoặc challenge leakage đều fail trước commit. Với `keep_identity`, target phải bằng source byte-for-byte, gồm cả edge whitespace; cấm trim hoặc thêm một dấu cách. Donor dấu câu khó phân biệt bằng mắt phải có `identity_expected_codepoints` và `identity_expected_utf8_hex` suy ra trực tiếp từ source trong prompt; bootstrap yêu cầu đóng JSON string ngay sau byte cuối. Literal `\u2026\u2026\u2026\u3002` (`………。`) vẫn là identity control thật và vẫn bị validator kiểm byte-exact, nhưng bị loại khỏi pool challenge rewrite vì Antigravity cố định thêm `U+0020` khi rewrite challenge. Challenge write bị guard bác là whole-run hard stop: lưu receipt, reset sau khi chứng minh không commit, rồi build package/run ID mới từ parent sạch; không correction retry trong cùng conversation vì lỗi guard đã làm lộ tín hiệu challenge.

### Fresh recheck

Sau full pass, schedule bắt buộc fresh prompts không expose prior action/reason cho union:

- toàn bộ rewritten real rows;
- toàn bộ runtime/high-risk rows;
- stratified deterministic sample tối thiểu `10%` accepted real rows theo domain/content class/translation policy. Clean `keep_identity` là stratum riêng nhưng không tự động biến toàn bộ identity corpus thành high-risk; chỉ recheck toàn nhóm khi policy collision, deterministic inconsistency hoặc runtime evidence yêu cầu.

Full-pass finalizer xuất exact challenge-free real-decision index và full-pass CSV/receipt. Host dùng reusable `scripts/materialize_guarded_phase2_recheck.py` để copy exact CSV bytes sang path host-private, xác minh SHA-256, tạo fresh overlay/auth/commands và materialize `agy-phase2-recheck-schedule/v1` bind `parent_full_pass={path,sha256,row_count}` cùng selection proof. Semantic guard reset rồi re-arm cùng package/run bằng recheck schedule/overlay/auth mới; reset không xóa event-chain head và conversation phải vẫn là cùng main agent. Recheck có cùng native-direct-write/challenge gates. Sau mỗi commit, guard có thể giữ `pending_response.readback=true` như receipt readback cuối; đây không phải response đang chờ nếu controller đã committed. Chỉ reset sau khi controller `finalized`, `active_packet_id=null`, `current/response.json` không còn, và chain `authorize → readback → commit` đã được audit. Finalizer merge selected decisions vào exact full parent, giữ mọi unselected row byte-equivalent, chứng minh set/order/count/hash và zero unresolved; latest clean recheck decision thắng. Trước acceptance, replay từng archived prompt/response bằng pinned `expand_explicit_decisions_v2.py` hoặc validator tương đương: mọi real `rewritten.translation_vi` phải khác byte-for-byte `current_translation_vi` của đúng prompt. Provenance auditor chain-only không thay gate này. Không script tạo pass-through decisions.

## Phase-2 incoming và merge

1. Stage/hash raw ZIP; verify whole envelope, parent, checksum và pinned tooling.
2. Verify host semantic event chain không gap/fork; exact auth/guard/template hashes; no forbidden mutation/command between arm và finalize.
3. Correlate từng prompt → native write event → disk response → commit ledger → normalized decision → final target.
4. Verify challenge expectations, 100% full pass, all mandatory rechecks và zero unresolved.
5. Run deterministic source/token/policy/glossary/residual/shape gates. Detector không thay language evidence.
6. Whole-envelope/provenance/challenge/recheck failure reject whole run. Partial row acceptance chỉ khi envelope+provenance toàn run sạch và exact rows fail độc lập deterministic gate.
7. Merge bằng one-writer transaction: lock → checkpoint → exact `(domain,key)` join → sibling temp+fsync → `os.replace` → reopen+validator; fail rollback.
8. Runtime final acceptance trước `buildpatch`.

Provider `PASS`, coverage count, receipt hoặc ZIP schema không override host-origin/challenge evidence.

## Package boundaries

Outbound ZIP translation-only; cấm game binary/asset, canonical master, importer/repacker, credential/private path/history. Không hash container ZIP bên trong nó.

Phase 1 core:

```text
project-manifest.json
START-HERE.md
PHASE1-RULES.md
handoff-id-map.csv
glossary.csv
english-policy.csv
token-profile.json
draft-evidence-schema.json
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

Phase 2 replaces schedule/input/parent and adds:

```text
decision-evidence-schema.json
input/full-corpus-with-draft.csv
schedule/phase2.json
parent/phase1-acceptance-parent.json
runtime/runtime-feedback.csv
host/semantic-authoring-authorization.template.json
tools/expand_explicit_decisions_v2.py
tools/semantic_response_guard.py
tools/materialize_semantic_authorization_v3.py
tools/materialize_phase2_challenge_overlay.py
tools/materialize_guarded_phase2_recheck.py
tools/audit_guarded_phase2_provenance.py
```

Manifest descriptors pin controller/finalizer/validator/guard/expander/materializers/auditor/schema/schedule. Reopened ZIP validator must prove every Phase-2 packet has hidden `challenge_slots >= max(1, ceil(5% × real rows))`, schedule leaks no challenge identity/data, real-prompt row hashes are pinned, and recheck policy covers all rewritten/runtime/high-risk + 10% accepted obligations. Host arm proves actual private overlay fills every slot; incoming acceptance runs the pinned auditor across controller evidence, both guard epochs and the final snapshot.

## Blocked conditions

Dừng trước semantic work nếu guard inactive, auth/package/controller hash mismatch, host event ledger unavailable, hook/template differ, unknown mutation tool exists, package tool bug, challenge map empty hoặc recheck schedule thiếu. Không tự patch pinned bytes; trả minimal repro kỹ thuật rồi stop.

## Legacy

`2.4-TWO-PHASE-DRAFT7-FINAL0-GUARDED`, `2.3-TWO-PHASE-DRAFT7-FINAL0`, `2.2-MAIN-ONLY-ONE-SHOT` và `2.0|2.1` chỉ dùng audit immutable artifact đã phát hành. Không mutate/relabel bytes cũ. Run `a581b9ec…` của Hoạt Hiệp Truyện là whole-run rejected/quarantined và không được làm parent, salvage hay resume.
