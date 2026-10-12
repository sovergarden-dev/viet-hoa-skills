# External QA handoff for encrypted community VPK corpora

Use when a Unity IL2CPP runtime plugin loads an encrypted community translation archive and the user wants corpus-wide QA through Notion AI or another external service.

## Recover the translation corpus safely

1. Inspect the managed loader/plugin to recover the container contract rather than guessing from the `.vpk` extension. Resolve header fields, entry table, verification value, key derivation, IV derivation, cipher/mode/padding, and string-pool offsets.
2. Keep the installed archive read-only. Export stable synthetic keys such as `vpk-000001`, English source, community Vietnamese, blank QA target, state, category, and notes.
3. Some archives contain a non-translation sentinel as entry zero. Prove this from decoded offsets/content; exclude it from the canonical corpus only after evidence.
4. Validate row count, unique keys, UTF-8 decoding, source/target association, and archive hash. Never raw-patch variable-length encrypted content.

## External handoff at large scale

A service may claim a full 15k-row result while the downloaded attachment is truncated. Trust the received bytes, not the service summary.

- Manifest fixes one output format and filename, canonical hash, exact row count, ordered key list/key-set hash, and file hashes.
- Include `batch.csv`, prompt, style/proper-noun policy, locked-English glossary, protected tokens, neighboring context, schema, and example output.
- Keep the canonical writer paused and record `external_handoff_in_flight` with the exact key-set hash.
- For large files, proactively split by exact stable-key subsets if the provider has attachment/export limits. Each subset records first/last key, exact count, unique key set, and output filename. Never split or rejoin by physical row position.

## Receipt gate

1. Copy incoming files unchanged under `incoming/<batch_id>/` and hash them.
2. Parse each as UTF-8-SIG CSV. Verify exact header, subset count, unique keys, first/last key, immutable metadata, and subset order.
3. Verify the union of subsets equals the manifest key set and order exactly. A file ending mid-row, blank state, or incomplete key union is an envelope rejection; canonical remains untouched.
4. If the complete envelope is valid, classify rows independently:
   - accept only `translated` rows with nonblank target, exact protected-token multiset, matching physical/literal newline structure, no corruption, and no source-association drift;
   - reject `needs_context` and every structurally suspect row into one stable-key `remainder.csv` with semicolon-separated reasons.
5. Checkpoint canonical, merge accepted rows by key only, write a sibling temp file, `fsync`, `os.replace`, reload, and run the canonical validator. Restore the checkpoint on any failure.
6. Report submitted states, accepted merged, unique rejected rows, occurrence counts by overlapping reason, before/after hashes, checkpoint, remainder hash, and validator result. Keep the external lock until the remainder is resolved.

## Important edge cases

- A service can restore most tokens but introduce one extra closing rich-text tag; token equality must reject that row even if it reads correctly.
- Literal `\\n` and physical CRLF/newline are not interchangeable without proof of the runtime parser. Keep mismatches in `needs_context`.
- Proper-noun replacement must be boundary-aware. Generic words that are also Rune/skill names (`Fish`, `Arrow`, `Leap`, `Whirl`) must not be globally replaced.
- An automated 100% scan plus sampled review is not equivalent to hand-review. Preserve `needs_context` and describe the evidence level honestly.

## Deliverables

- immutable incoming copies and SHA-256 hashes;
- envelope report;
- canonical checkpoint;
- atomic partial-merge receipt report;
- stable-key remainder for manual/external follow-up;
- canonical validator output.
