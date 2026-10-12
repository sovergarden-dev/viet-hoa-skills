# Translation execution modes

Load after preparation is complete and the user authorizes translation. Canonical CSV remains the only source of truth; translation workers never write it directly.

## Default: bounded continuous run

Use a tracked background process or the current session to process many batches in one bounded run. This removes cron startup latency and repeated context loading.

1. Deterministic lifecycle manager recovers/quarantines the inbox, validates canonical, and stages one exact-key packet.
2. The model returns only keyed translation data. Prefer a complete keyed JSON envelope at the LLM boundary; a deterministic writer parses it, verifies exact keys/states/tokens, and emits canonical CSV with Python `csv.writer` before atomic commit. JSON makes truncation and escaping failures easier to reject than model-authored CSV.
3. Continue immediately with the next packet while health gates pass. Reload glossary/style once per run; carry only domain/conversation context needed by the packet.
4. Stop at any hard gate: malformed output, key/source/token mismatch, validator error, stale canonical hash, source drift, repeated model failure, user stop, or cost/time ceiling. When ordinary work is exhausted, route every `needs_context` row with source + secondary reference + current target through a final constrained `context_review`; only rows missing one of those inputs are a manual hard gate.
5. Emit a checkpoint every 5 clean commits or 10 minutes, whichever comes first. A bounded run must have `max_batches` or `max_minutes`; restart from canonical, never from model memory.

Default packet sizing:

- sensitive dialogue/lore or uncertain relationships: 20–40 rows;
- ordinary dialogue with speaker and neighboring context: 40–80 rows;
- short homogeneous UI/system strings: 80–150 rows.

Prefer grouping by domain/conversation/content type over filling a numeric quota. Reduce size after truncation, `needs_context` spikes, inconsistent terminology, or token errors. Increase only after three clean packets of the same class.

Every 5–10 committed packets, run glossary drift, duplicate-source/different-context and xưng-hô consistency audits before continuing. This is the quality checkpoint that permits larger routine packets without treating throughput as review proof.

## Context deferrals before completion

A context deferral is not automatically terminal. When `source`, a secondary-language `reference`, and a current target are non-empty, stage the exact keys in `context_review` after ordinary review. Supply all three fields and accept only `accepted` or `rewritten`; one bounded correction may reject a model that returns `needs_context` again. Preserve a manual hard gate only for rows with missing evidence, and emit their exact keys. Completion requires zero rows in every unresolved state.

## Optional safe concurrency

Parallelize **translation generation only**, never canonical writes.

- Reserve 2–3 disjoint exact-key packets under one immutable canonical snapshot and lease IDs.
- Workers receive the same glossary/style version and cannot stage, merge, or edit canonical.
- A single deterministic commit queue accepts completed packets in manifest order after checking the current source hash and that every key is still `pending`.
- Any stale lease is rejected and regenerated; never remap by row position or suffix.
- Use concurrency for independent UI/domains. Keep connected dialogue and shared-lore passages sequential unless a final cross-packet terminology/xưng-hô review is scheduled.

Start with one worker. Enable two only when the lifecycle regression suite passes and three consecutive packets from each worker commit cleanly. More than three usually increases QA and context costs faster than throughput.

## Cron fallback

Cron is for unattended resumability, not maximum throughput. Use it only when a bounded process cannot stay alive or the user explicitly wants periodic autonomous progress.

### Scheduler contract before launch

- Each tick performs recovery first and at most one commit. `last_status=ok` requires a verified canonical delta, or clean `pending == 0` **and** `needs_context == 0`; staging/candidate creation is not success.
- Do not infer overlap from the schedule string. Prove the runtime's actual interval semantics and inspect execution ownership. An interval shorter than normal batch duration is acceptable only when a durable per-job claim prevents a second worker.
- A process-wide/tick lock serializes scheduler scans, not the full lifetime of a long agent run. With gateway and desktop tickers on one store, the due scan must skip a live `fire_claim` before creating an execution row.
- Heartbeat the claim more frequently than its stale TTL. Regression tests must prove: live claim is not due, refreshed claim remains not due past the original TTL, and an unrefreshed stale claim becomes recoverable.
- Restart every long-lived process that imported changed scheduler code, but never kill the current claim owner mid-packet. Identify owner PID first, replace non-owner/stale processes, then observe at least one crossed due time with zero phantom executions.
- Self-pause only at clean completion or a deterministic hard gate. A context-backed `needs_context` row is not a hard gate until its final `context_review` has been attempted. Transient provider failures fail that tick; they do not justify changing model/provider or silently pausing a healthy pipeline.
- Self-pause is a verified completion state, not a crash. If the user later asks to remove an idle completed job, delete it externally, list/read back that exact job as absent, then atomically clear or retire its lifecycle binding with the retired job ID and timestamp. A future requeue creates and binds a new ID; never reuse stale scheduler metadata.

### Tight cron tool surface

Keep the cron prompt self-contained and load only the toolsets required by its literal lifecycle: normally `terminal`, `file`, and `no_mcp`. Do not attach a large umbrella skill when the prompt already contains the project contract; unrelated references and tools increase context, cost, and model drift. Translation generation must not use helper Python, web/MCP, memory, delegation, or exploratory repair. Any unexpected tool/command result stops the tick.

### Read-only progress evidence

A status check does not pause a healthy atomic writer. Read live cron state, execution history, lifecycle state, active packet/candidate/journal, latest receipt and canonical bytes. Report canonical totals only when its SHA-256 matches the latest committed receipt/manifest, or an in-flight journal proves the post-replace hash. A mismatch is a retry signal, not permission to combine snapshots. Pause only for mutation/repair and follow `active-cron-workbook-repair.md`.

Classify provider failures from exact evidence: isolated `429`, upstream-auth `401`, `503 activity_cost_limit_reached`, TTFB or connection errors fail without canonical write and may recover next tick. Escalate only when failures persist without a later clean commit; never alter an exact provider/model pin or enable fallback implicitly.

## Quality strategy

Do not spend maximum reasoning on every row. Route by risk:

- deterministic reuse only for exact source + equivalent context + identical protected tokens from reviewed translation memory;
- standard model pass for routine UI/system text;
- stronger reasoning or second semantic pass for dialogue, lore, ambiguity, glossary conflicts and `needs_context` candidates;
- corpus-wide consistency QA after each domain and before release.

Automation may flag or reuse; it must not silently turn heuristic output into `reviewed`.

## Minimal proof per commit

```text
before/after canonical SHA-256
exact ordered full-key hash
accepted/rejected counts
pending/state deltas
protected-token result
canonical validator result
archive/quarantine path
```

## Lifecycle regression suite

Before autonomous use, prove: JSON truncation/duplicate-key rejection; CSV comma/quote/physical-newline/BOM roundtrip; exact-key mismatch; committed-orphan recovery; stale/mixed/malformed/incomplete quarantine; token mismatch; rollback after replace; commit-plus-archive idempotence; context-backed deferral reaches final `context_review`; evidence-missing deferral remains manual; and completed-cron retirement clears only the exact externally verified absent ID. A runner exits success only after a verified canonical delta or when all unresolved states are zero with a clean validator.
