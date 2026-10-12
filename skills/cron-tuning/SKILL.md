---
name: cron-tuning
description: Use when starting or tuning translation cron workers.
version: 1.5.0
contract_version: "1.0.0"
---

# Translation cron tuning

Apply at FIRST creation, not only after slow runs. Scope is the requested project. Historical evidence does not authorize modifying unrelated jobs.

## Safety

Preserve full keys, source, tokens, glossary/name policy, validator, checkpoint, OS lock, single writer, atomic commit and readback. Structural acceptance is not semantic review. Live game assets stay read-only. Pin authorized route/model/effective settings: no unattended Sol; Terra/Luna/5.4 default approved families, others require explicit permission. Never reduce reasoning/review or change model silently for speed.

Preparation-only authorization does not permit translation probes. Use approved fixtures or report calibration awaiting authorization. Keep benchmark candidates outside canonical until normal writer acceptance.

## First-launch gate

1. Discover scheduler semantics (completion-relative vs wall-clock), actual timeout layers, overlap handling, lock, durable heartbeat, quotas and shared queue. Never assume a universal timeout or schedule.
2. Fingerprint route/model/effective effort/output cap, worker/prompt/validator versions, language pair, domain and source-length distribution. Historical settings are seeds, not optimal defaults.
3. Select bounded authorized representative source: short UI, dialogue, long and token-heavy text. Preserve context/scene boundaries. Limit both rows and serialized input/output budgets. Set request, cost and elapsed-time ceilings before probing.
4. Compare conservative seed and adjacent batch sizes, one variable at a time. Seek at least three comparable observations per candidate as an initial heuristic, not statistical assurance; interleave baseline/candidate to expose drift. Stop escalation at cliff, timeout, truncation or quality regression.
5. Measure queue, staging, provider, validation, commit/readback, pacing and scheduler idle separately. Optimize unique accepted rows per end-to-end wall time including failures/waits; also report source volume, rejected/unresolved counts, token usage if available, sample size, median and observed tails. Do not present tiny-sample P95 as reliable.
6. Choose fastest stable configuration passing unchanged structural AND project language-review gates. Weak evidence means provisional plus explicit recheck trigger, not fabricated optimum.
7. Before unattended launch test two-process lock contention (no second send/writer), crash recovery on copies, stale candidate rejection, budget exit and completion cleanup. Verify effective route, not labels.
8. Create via supported scheduler tools and read back exact ID, schedule, workspace, route and state. Verify first authorized commits and idle gaps from receipts/canonical readback. Created is not live-verified.

## Continuous execution

Prefer deterministic no-agent stage/model/validate/commit/readback where project contract permits. No skill/history/web preload per packet. A frequent cron can be recovery launcher, not a universal mandatory schedule. Nonblocking OS lock covers entire worker lifetime; lock-busy exits without duplicate inference.

Continue packets without arbitrary sleep when quota permits. Use measured pacing and Retry-After, not fixed 0.5–1 second sleeps. Derive session budget from actual timeouts and measured request/validation/commit reserve. Do not start a packet without finishing reserve. JSONL progress does NOT renew scheduler claims: verify durable heartbeat binding separately.

Shared single-flight provider requires existing shared lane and measured queue time/fairness; no parallel competing benchmarks or bypass. Do not silently replace older per-tick contracts with continuous execution.

## Failure handling

- Proven pre-send retry-safe: bounded backoff/jitter and persisted retry budget.
- Post-send timeout/disconnect or sent_unconfirmed: quarantine and read-only reconciliation; never auto-replay. HTTP 503 alone does not prove unprocessed.
- Auth/billing/quota/config blocker: stop/report, no endless retry storm or unauthorized fallback.
- Candidate rejection: preserve raw response and validator findings. Never extract JSON by first/last brace or silently repair. Only explicitly supported/tested single outer fence unwrapping; duplicate fields, multiple objects and trailing prose fail closed. Live workers that still slice first brace to last brace stay untouched until that project is the requested scope. New workers must not copy them.
- Commit failure: reconcile transaction before new inference; close owned Windows reader handles, never weaken atomic-write gates.
- Stalled / deadlock prevention: if pending row count remains completely unchanged across consecutive ticks (e.g. 3 consecutive attempts with 0 accepted rows), the worker must NOT spin indefinitely in an infinite loop. Isolate unprogressing rows to quarantine or mark `needs_context`/`rejected` with specific validator diagnostic, or trigger self-pause with reason `stalled_validation`. Never allow a tiny set of failing rows to keep the cron job ticking forever.
- Format tokens vs translatable prose: validator regexes must NOT match bracketed UI labels or subtitle cues (`[LOCKED]`, `[NEW]`, `[mumbling]`) as immutable format tokens; over-broad regexes reject legitimate translations (`[ĐÃ KHÓA]`, `[lẩm bẩm]`). Whitespace-only rows must not be silently stripped/dropped; preserve byte-exact via an explicit validator-approved identity rule and normal state transition, not unconditional done.

## Bounded recheck

Persist selected config and last-known-good baseline. Recheck source/domain shifts, route/prompt/version drift, throttling or sustained throughput regression. Change batch/pacing only at clean boundaries within approved bounds; revert config on regression, not accepted canonical rows. No autonomous model, quality, concurrency or retry-policy changes.

Reuse existing telemetry. For workers without it, start from `templates/worker_telemetry.py`; it is append-only JSONL and does not write canonical/scheduler state. This skill is a procedure, NOT implemented auto-tuning. If first-run observation is absent, add a tested project-specific implementation before claiming it exists.

## Receipt and completion

Save a compact project receipt: fingerprint, authorization, sample IDs/hashes, configurations/timings, accepted/rejected counts, language review, selection, baseline, budgets, recheck/rollback, job ID and first-run evidence. No secrets.

Pending zero alone is insufficient: account for unresolved/rejected/review scope. A finished translation cron must stop itself cleanly. `no_agent` treats exit 0 and empty stdout as success and schedules the next tick; it does not stop. On the tick where canonical readback shows accepted == total and pending, rejected, and needs_review are all zero, execute completion cleanup.

CRON SELF-REMOVAL HARD INVARIANT (CRITICAL):
- In Hermes scheduler architecture, NEVER rely on the cron subagent's natural LLM turn / prompt instructions to call `cronjob_manage(action="remove")` or `cronjob_manage(action="pause")` on itself!
- Root Cause: When an in-flight cron subagent deletes its own job record mid-run, the background scheduler thread `heartbeat_fire_claim` fails to find the job record in storage on its next heartbeat tick. This trips `lost_ownership.set()` -> logs `Fire claim ownership lost; stale result was discarded` -> marks the execution as failed -> and can leave the job file / scheduler in an inconsistent state or orphaned loop.
- Canonical Mechanism: The worker script (`tools/worker.py` / `cron_completion.py`) itself MUST execute self-removal directly via CLI `hermes cron remove <exact_job_id>` before terminating, followed by an immediate scheduler readback verification (`hermes cron list` asserting `returncode == 0` and 0 matches for the job).
- Idempotent Completion & False-Success Prevention:
  1. Never log `cron_job_removed` unconditionally without checking `res.returncode == 0` and combining `res.stdout + res.stderr` (an already-removed job returns `"Job with ID ... not found"` on stdout/stderr; log that as `cron_job_already_absent` after verifying via `hermes cron list`).
  2. Persist an idempotent completion sentinel (`state/completion_done.json` and `binding["status"] = "completed_and_removed"`) so any overlapping or trailing tick exits immediately without re-running asset importers or CLI calls.
  3. Always attempt cron self-removal even if a post-translation staging importer script throws an error, recording `removed_after_import_error` rather than leaving the cron job spinning in an infinite loop.
- User Preference: The user strictly requires permanent removal (`remove`), NEVER leaving completed jobs in `paused` state.
- Always verify exact job ID from `state/cron_binding.json` before removing; never guess or touch unrelated jobs.

## Historical lessons

Đọc `references/calibration-history.md` khi chọn seed. Batch size thuộc project, không thuộc shared profile; seed không phải optimum.

## Minimality

Reuse lifecycle/metrics/benchmark tools before creating frameworks. Every code change needs a runnable regression check. Add features only for measured bottlenecks; never cut QA to reduce token cost.

## Phạm vi kiểm lại

Docs-only: kiểm contract/link và test helper bị ảnh hưởng; không rebuild/reinstall dự án. Tái dùng evidence chỉ khi input/output hashes, tool/config, build, scope và loại proof khớp. Không gọi skip là PASS. Thay artifact thì kiểm lại gate phụ thuộc; riêng installer EXE đổi byte phải chạy lại exact-EXE suite.
