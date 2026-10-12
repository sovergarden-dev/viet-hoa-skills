# Unattended model routing and prompt budgets

Load when configuring, repairing, benchmarking or reporting an unattended translation worker that calls an LLM through a bridge.

## Separate roles

A high-capability interactive reviewer is not implicitly the right unattended translator.

- Declare an explicit `background-translation` request role.
- Declare a project allowlist and pin exactly one provider/model for a production worker.
- Enforce the allowlist twice: in the runner before provider/network resolution and in the bridge before upstream selection. Both checks fail closed.
- Keep interactive consultation routing separate. Do not infer an unattended model from CDP UI evidence, a reviewer E2E, or a similarly named model on another provider.
- Never silently retry a failed packet with another model, another provider, higher reasoning, Fast/service tier, or a smaller semantic payload.

For the user's Postman policy: `gpt-5.6-sol` is consultation-only. Unattended translation may use only `gpt-5.6-terra`, `gpt-5.6-luna`, or `gpt-5.4`; production changes still require an exact bridge mapping capture and a like-for-like benchmark before they replace the current pin.

## Route proof

Before enabling or resuming a worker, read and compare all four layers:

1. Scheduler job: `provider`, `model`, no-agent/script mode and Fast/service-tier setting.
2. Runner: pinned model, role marker, request model and pre-network allowlist assertion.
3. Bridge: model mapping for the role, selected upstream model and no semantic slim-retry path.
4. Commit receipt: provider, model, request role, API mode, Fast/service-tier, request/response hashes and canonical commit hash.

The four layers must agree. A missing, divergent or unproven mapping pauses the worker; never use a text label alone as evidence.

Report consultation and translation separately, for example:

```text
Consultation: Postman CDP / GPT-5.6 Sol / advisory only
Translation packet: p / gpt-5.6-terra / background-translation
```

## Prompt budget

The prompt budget protects source fidelity; it is not permission to truncate.

1. Render the full candidate prompt from an immutable staged packet.
2. Remove only declared optional references in a fixed order. Preserve authoritative source, exact `(domain,key)`, protected tokens and context fields required by the contract.
3. If a multi-row packet still exceeds the bridge limit, restage only the largest ordered prefix of complete rows before any model request.
4. Re-read the persisted restage and require same packet ID, candidate path, canonical SHA-256, ordered-key SHA-256 and exact selected source rows.
5. If one complete row cannot fit, stop deterministically with its exact key. Increase a measured bridge budget or obtain a dedicated structured segmentation design; do not split/trim source ad hoc.
6. Background requests never use bridge fallback that retries a slimmed prompt. An upstream failure leaves canonical unchanged for bounded recovery.
7. Classify operational errors separately from candidate errors: `postman_manual_lane_busy` means an external interactive lane collision and must not trigger fallback or prompt changes; timeout is transport failure; source/token/newline mismatch is quarantined model output. Keep the original receipt and verify a later clean packet before claiming recovery.
8. A rising `needs_context` count is not translation progress. Report `translated`, `needs_context`, `pending_nonblank`, and `pending_blank_source` separately; investigate domain concentration before tuning throughput or changing model.

## Benchmark before a production swap

Use disjoint, representative packets with the same packet construction and exact prompts. Generate candidates without canonical merge until every candidate passes structural gates. Compare latency distribution, valid-envelope rate, source/token/newline failures, correction rate, `needs_context` rate and independent language QA. Promote only at a clean packet boundary after user-approved model pin change; retain receipts and rollback to the prior pin if post-change proof regresses.
