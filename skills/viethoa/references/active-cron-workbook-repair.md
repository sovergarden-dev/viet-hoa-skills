# Active cron + canonical localization workbook

## Problem

A cron worker can rewrite the shared CSV while a manual status check, validator, or repair reads it. This can yield transient token mismatches, stale totals, or a repair that the next tick overwrites.

## Read-only status protocol

A progress/error check must not pause a healthy atomic writer.

1. Read live cron state by verified job ID and workspace; never use a stale name, project-state snapshot or model-pin receipt as live state.
2. Read execution history, lifecycle state, active packet/candidate/journal and latest receipt. Parse timezone-aware timestamps and normalize to UTC before sorting/comparing; ISO strings with different offsets are not lexicographically ordered.
3. Hash one canonical byte snapshot. Trust totals only when the hash matches the latest receipt/manifest, or an in-flight commit journal binds it as the verified post-replace hash.
4. If snapshots disagree, retry after the current tick boundary. Do not merge counts/timestamps from different snapshots and do not pause merely to make a status report easier.

## Mutating repair protocol

1. Pause the exact verified job. Pause prevents new dispatch; it does not kill a run already holding `fire_claim`.
2. Read execution/claim ownership and wait until no execution, active packet, candidate, journal or writer lock is in flight. Do not restart/kill the owner.
3. Checkpoint the canonical and repair only exact full keys under one deterministic transaction, preserving protected tokens and intentional `<br>` count.
4. Run the canonical validator, atomically replace, reload and run the same validator again against persisted bytes.
5. Let `bientaptay` reload only after the persisted validation is clean.
6. In a `finally` path, resume the same verified job unless the user explicitly paused it, `pending == 0`, or a deterministic hard gate exists. Read back `enabled=true/state=scheduled`; a forgotten resume is a lifecycle failure.

## Why

Atomic status reads avoid needless downtime. Pause is required for mutation, not observation. The final readback distinguishes a durable repair from a transient writer state, and the resume readback prevents a diagnostic session from silently stopping translation. Do not infer token errors from an ad-hoc regex; import the canonical validator's matcher.
