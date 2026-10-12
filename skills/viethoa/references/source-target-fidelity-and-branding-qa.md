# Source–target fidelity and branding QA

Use after merging community patches, external translations, or batch output, especially when runtime screenshots reveal text whose length or meaning differs from the canonical English.

## Core rule

Structural validity is necessary but not semantic proof. Exact keys, valid tokens, non-empty targets, and clean import/readback can all pass while a translation from another row has been attached to the wrong key.

## Required audit

1. **Lock canonical source by stable key.** Treat returned `source`, context, and row order as untrusted metadata. Merge only `translation_vi` by exact key.
2. **Search attribution/branding corpus-wide:** team names, `translated by`, `translation by`, `Việt hóa bởi`, URLs, handles, and known old signatures. Report every key and distinguish original game credits from translator-added text.
3. **Compare source–target semantics, not only residual English.** Flag:
   - long source with very short target;
   - short source with very long target;
   - target that appears to answer or describe a neighboring source;
   - identical target reused across unrelated sources;
   - task, dialogue, title, and description fields whose function differs.
4. **Length ratio is triage, not a verdict.** For prose source length ≥35–45 characters, investigate ratios roughly below 0.35 or above 2.8. Exempt legal text, acronyms, intentional names, markup-heavy rows, and languages with expected compression.
5. **Prioritize high-risk origins:** newly translated DLC, externally translated batches, manually recovered candidates, and rows previously involved in key mismatch/recovery.
6. **Translate flagged rows directly from canonical source**, preserving protected tokens, tags, escapes, and line breaks. Require `candidate.keys == flagged_keys` and semantic review before merge.
7. **Re-run the same audit after fixes.** A clean structural validator alone is not enough.

## Proper nouns and technical terms

- Apply glossary preservation only when the canonical source contains the protected term or a documented alias such as `QC` for `Quantum Computer`.
- Match case-insensitively and account for capitalization/plural variants.
- Never globally replace a Vietnamese phrase when the source does not contain the corresponding protected term. Such residual text may be evidence of wrong-row attachment, which requires retranslating the whole row.
- For franchise terms, preserve grammatical number where meaningful: `Alter` versus `Alters`.

## Branding edits

- Remove an old translator signature by restoring that key's canonical English source unless the user requests replacement text there.
- Put a requested handle only in the exact UI key the user identified. Example: replacing the main-menu `Credits` label changes a navigation label, not the credits content itself.
- Verify runtime placement with screenshots. A string-table match does not prove the intended visual location.
- Audit assets separately: logos or attribution baked into textures, movies, splash images, or widgets will not appear in `.locres` searches.

## Release gate

Before rebuilding:

- no unauthorized old attribution remains in localization text;
- requested branding appears only at approved keys;
- all semantic-mismatch candidates are reviewed or explicitly deferred;
- canonical validator passes;
- import/export readback has zero mismatches for all importable rows;
- artifact is marked `pending runtime QA` until screenshots confirm placement and meaning.
