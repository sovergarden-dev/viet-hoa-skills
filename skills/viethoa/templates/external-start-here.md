# START HERE — <project> / GUARDED TWO-PHASE / <package-id>

Contract: **AGY-VIETHOA-HANDOFF/2.5-TWO-PHASE-DRAFT12-PREVIEW-FINAL0-GUARDED**.

1. Extract once into a new empty directory. Keep extraction immutable; runtime state belongs in sibling `evidence_work/<package-id>/<run-id>/`.
2. Verify `checksums.sha256`, then wait for the host-side package validator, guarded-host preparation, and arm/readback receipt. During the run, execute only the exact controller commands permitted by the guarded task; the Phase-1 controller has no `preflight` action.

3. Before this agent task begins, Hermes/user must have staged the exact extraction/work paths, materialized host-only `agy-semantic-origin-authorization/v3` and any Phase-2 challenge overlay outside package/work roots, armed both guards, then read back exact package/run/manifest/controller/schedule/overlay hashes. No Antigravity pre-arm turn is permitted.
4. Follow only the phase stated in the user task and guarded current prompt.

## Name provenance

`name-provenance-policy.json` and `name-provenance-ledger.csv` are pinned package inputs and must be materialized into each semantic prompt. For creator-authored proper names, use the source-country/original-market canonical form in the ledger; English localization is reference-only unless the ledger proves it is the creator-published canonical form. Do not substitute an English localization, invent a romanization, or bulk-normalize names. An absent or `needs_review` entry must be returned as the phase's context state, never guessed.

## Hard response rule

During semantic work, never create/run a helper script, `python -c`, shell chain, loop, comprehension, regex substitution or generated identity/action list. `view_file` may read only exact `current/prompt.json`; grep/find/list and auth/overlay/schedule/state/ledger reads are denied. Only a native `write_to_file` call may write exact `current/response.json`; all other writes and every non-allowlisted command must be host-denied. A response without host payload/readback receipt is invalid even if controller says `PASS`.

## Phase 1

- Require subagent and semantic readback for exact `phase1_parallel_draft`, package/run/manifest/controller/work roots.
- Controller selects at most the package-configured `1..12` disjoint exact leases. Every wave provides nested prompts and `prompt_sha256_by_batch`. For each lease, send one `Prompt` containing only a JSON `agy-phase1-worker-invocation/v1` wrapper: unchanged nested prompt, matching `expected_prompt_sha256`, `response_schema=agy-phase1-draft/v2`, and `DO NOT CALL TOOLS` instructions. Workers return one bare valid UTF-8 JSON object with exactly `schema,batch_id,prompt_sha256,rows`; every `rows[]` object has exactly `handoff_id,translation_vi,review_action,notes` (`review_action` is `translated` or `provisional_needs_context`). `target`, `translation`, `status`, `action`, `key`, `source`, and extra row fields are forbidden. Minified or pretty-printed is allowed, but BOM, code fences, prose, and duplicate keys are forbidden. No shared write, nested child or messaging.
- Launch every full wave with ONE native `invoke_subagent` call containing exactly the staged worker entries; default ceiling is twelve and final wave may be smaller. Do not invoke one worker and wait before launching the next.
- Worker returns preview-grade draft `agy-phase1-draft/v2` after one authoring pass. Before emitting JSON it performs a silent self-review for fidelity, omission, natural Vietnamese, glossary/xưng hô, tokens/newlines, residual source and UI fit. The result is one bare valid UTF-8 JSON object; minified or pretty-printed is allowed, while BOM, code fences, prose, and duplicate keys are forbidden. Main direct-writes it unchanged; the controller records deterministic JSON-format normalization, and Phase 2 still owns meticulous editorial review.
- Return one Phase-1 ZIP after exact full draft coverage and `reserved=0`; stop for Hermes acceptance. State becomes `phase1_accepted_waiting_for_user_direction`; Hermes asks the user to choose `build_demo_patch`, `external_phase2_antigravity`, `hermes_cron_phase2`, or `pause`. Demo is optional. No Phase-2 route starts before that choice.

## Phase 2

- Require subagent `phase2_main_only_final,limit=0,reserved=0` and semantic guard armed to the exact new package/run.
- Main reviews 100% IDs in declared reverse/different order.
- Return `agy-explicit-review/v2`: one ordered decision object per row. Legacy `accepted_ids` and omission defaults are invalid.
- ZIP/schedule expose only challenge slot counts. Actual challenge IDs/rows/targets are host-private. Review every prompt row normally; `accepted`, `needs_context` or wrong rewrite on a challenge is rejected before commit.
- Resolve all context issues and complete every rewritten/runtime/high-risk recheck plus stratified 10% accepted recheck.
- Return one final ZIP and stop for Hermes.

Rejected raw responses remain immutable attempts. Resume only the same package/run/verified ledger. Do not patch pinned tools, auth, guard or checksums. Provider `PASS` is not acceptance.
