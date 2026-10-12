# Vietnamese pronoun audit workflow

Use this for every dialogue-heavy game localization. Vietnamese xưng hô is a consistency system, not a word-by-word translation problem.

## Required files

- `pronoun_rules.csv`
- `pronoun_audit.csv`
- optional `manual_pronoun_fixes.csv`

## `pronoun_rules.csv` schema

```csv
speaker,addressee,scope,vi_speaker,vi_addressee,confidence,notes
```

Example:

```csv
Dr. Eva Rosalene;Dr. Rosalene,Dr. Neil Watts;Dr. Watts,all,tôi,ông,high,Eva nói với Neil
Dr. Neil Watts;Dr. Watts,Dr. Eva Rosalene;Dr. Rosalene,all,tôi,bà,high,Neil nói với Eva
```

## Build speaker/addressee context

Do not trust line order blindly until verified. For each engine, confirm whether NameBox appears before or after the dialogue row.

For each row, derive:

- `speaker`: NameBox paired with the dialogue row.
- `prev_speaker`: previous dialogue speaker.
- `next_speaker`: next dialogue speaker.
- `scene_participants`: speakers appearing in the same event/page/window.
- `addressee_candidate`: usually previous speaker in two-person exchanges, but not always.

## Audit flags

Flag, do not auto-fix:

- speaker uses a pronoun forbidden by `pronoun_rules.csv`
- sudden switch of addressee pronoun inside the same scene
- mixed `ông/bà/anh/cô` in a two-person exchange
- visible control fragments like `t3`, `c[6]`, `w[5]`, `[30]`
- suspicious punctuation imported from English, especially semicolon overuse

## Classification

Every flagged row must be classified:

- `fix`: confirmed wrong pronoun.
- `keep_third_person`: pronoun refers to someone absent, e.g. `ông ấy`, `bà ấy`.
- `keep_idiom`: phrase is not addressee pronoun, e.g. `anh chị em`.
- `needs_context`: cannot decide without scene/playthrough/screenshot.

Never bulk replace all occurrences. Apply exact-key fixes only.

## Patch strategy

1. Write `manual_pronoun_fixes.csv` with exact keys and reasons.
2. Apply fixes by exact `key` only.
3. Rebuild patch.
4. Run audit again.
5. Ship only when no high-risk unclassified rows remain, or document remaining `needs_context` rows.

## Lesson from To the Moon SerenityForge

A naive pass left lines where Rosalene called Neil `bà` and Neil called Eva `ông`. The correct solution was not global replacement; it was a speaker/addressee audit and exact-key manual fixes.
