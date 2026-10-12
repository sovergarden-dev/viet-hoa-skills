# BlackSpace `.paloc`: current-build reconciliation and external handoff

Use for Crimson Desert–style Pearl Abyss BlackSpace archives where localization is one `.paloc` inside a `.pamt` + `.paz` group, especially when a community patch replaces a language slot.

## Discovery and safe extraction

1. Read the Steam app manifest and lock App ID, build ID, depot manifest, executable hash, game root, language groups and workspace before writes.
2. Copy only the target `.pamt`/`.paz` pair into the workspace; hash both. Never experiment on the live archive.
3. Parse PAMT first to identify the exact internal path, compressed/original sizes, archive index and flags.
4. Some PALOC entries marked LZ4 still require filename-derived ChaCha20 decryption before LZ4 decompression even when a generic extractor does not label them encrypted. If raw LZ4 fails, test the documented deterministic basename-derived decryption on the copy, then LZ4; accept only exact original size and structurally valid PALOC.
5. PALOC observed schema: file header, then repeated `u32 pad`, `u32 key_len`, UTF-8 key, `u32 text_len`, UTF-8 text, `u32 index`. Require full-file consumption, valid UTF-8, bounded lengths and unique stable keys.

## Community language-slot audit

Community launchers may leave a manifest and numbered backups under a private backup directory. Read that manifest to map each backup blob to its original relative path; copy current override and original backups into the workspace before analysis.

Compare three stable-key maps:

- current authoritative English;
- original same-build secondary language (useful for register/context);
- installed community Vietnamese override.

Report current count, parseable override count, intersection, missing current keys, override-only stale keys, common rows equal to English, rows equal to original secondary language, and structural parse failure offset/remaining bytes. A corrupt or truncated community PALOC is reference-only: never append to it or treat its row order as authoritative. Rebuild from current English stable keys.

## External handoff construction

Create one self-contained ZIP with:

- `manifest.json` containing build, batch ID, source/canonical hashes, exact row count, sorted key-set hash, hashes of every member, one output format and one expected filename;
- `batch.csv` keyed by stable key with source, secondary-language reference, bounded neighboring context, old community Vietnamese as untrusted reference, protected tokens, blank target/state;
- prompt, glossary, style/xưng-hô guide, output schema and example.

Do not include game binaries or private absolute paths. If the provider cannot handle the full corpus, split only into manifest-declared exact-key subsets and require keyed outputs; never split or merge positionally.

The prompt must say that old community text is non-authoritative and may be outdated/corrupt. Set `external_handoff_in_flight` with batch ID and key-set hash, blocking overlapping autonomous writers. On receipt, treat output as untrusted and run envelope, structural, token and semantic validation before atomic merge.

## Proper-term policy for RPG data

Default to English not only for general proper nouns and technical terms but explicitly for character/place/faction/race names, lore/franchise terms, skill/ability names, item names, weapons, armor, equipment, materials and named systems. Translate only when the glossary explicitly approves a natural Vietnamese rendering that preserves in-game recognizability. Do not use blind substring replacement for short terms.
