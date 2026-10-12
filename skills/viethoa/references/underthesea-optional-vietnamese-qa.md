# Underthesea as optional Vietnamese QA for game localization

Session learning: `undertheseanlp/underthesea` is useful for Vietnamese-language QA in a `viethoa` pipeline, but not as an extractor/patcher or final translator.

## What it is good for

Use as an optional QA helper after workbook translation exists:

- `text_normalize(text)`: suggest fixes for malformed Vietnamese accents/Unicode, e.g. `Ðảm baỏ chất lựơng` -> `Đảm bảo chất lượng`.
- `sent_tokenize(text)`: split long lore/codex/note text into sentences for review, batching, and line-wrap checks.
- `word_tokenize(text)`: count/segment Vietnamese words more naturally for line-wrap heuristics and phrase-boundary checks.
- `lang_detect(text)`: heuristic flag for rows that still look English/foreign; unreliable on short UI strings.
- `ner(text)`: weak helper for common Vietnamese entities; not reliable for fantasy names or game terms.
- `translate(text, source_lang='en', target_lang='vi')`: can produce `reference_auto`, but should not be final game text without glossary/style/pronoun review.

## What it does not solve

Do not use underthesea for:

- extracting game formats (`.pak`, `.locres`, `.uasset`, Unity `.assets`, RPG Maker data);
- bypassing encrypted Unreal pak indexes or AES requirements;
- repacking/patching game files;
- guaranteeing preservation of placeholders/control codes/tags;
- resolving speaker/addressee pronouns or lore style.

## Dependency and trust notes

As of the checked repo/PyPI snapshot, `underthesea` is active around version `9.5.0` and requires Python `>=3.10`. Treat the license as repo-sourced (`Apache-2.0`) because PyPI metadata may not expose it consistently.

Core package dependencies include `underthesea_core`, `joblib`, `requests`, `PyYAML`, `huggingface-hub`. Translation uses `VietAI/envit5-translation` and requires heavy optional deps such as `torch` and `transformers`.

Do not make underthesea a required dependency of `viethoa`. Use it behind an optional import:

```python
try:
    from underthesea import text_normalize, sent_tokenize, word_tokenize, lang_detect
except ImportError:
    text_normalize = sent_tokenize = word_tokenize = lang_detect = None
```

## Recommended QA report fields

For each translated row, add/report:

- `normalized_suggestion`
- `normalize_diff`
- `sentence_count`
- `word_count`
- `maybe_english_leftover`
- `maybe_foreign_leftover`
- `qa_note`

Hard failures should still be stdlib/structural checks:

- missing reviewed translation;
- placeholder mismatch;
- tag/control-code mismatch;
- Cyrillic left in target when not expected;
- glossary mismatch.

Underthesea findings should be warnings unless they reveal a structural issue.

## Safe workflow

1. Run normal `viethoa` extraction/build/import validations first.
2. Run underthesea QA on the final or near-final workbook.
3. Write a separate QA CSV/report; do not mutate the source workbook automatically.
4. Auto-apply only if the row has no placeholders/tags/control codes and the diff is a pure Vietnamese accent normalization.
5. Human/LLM review any row with game terms, pronouns, placeholders, or UI layout constraints.

## Practical verdict after Luna Abyss

Underthesea is worth keeping as an optional final QA pass, not as a default dependency. In Luna Abyss it caught one real issue (`Archive Entry List` left as English vertical UI text), but most remaining warnings were false positives, vendor/proper names, short UI labels, or normalization suggestions that still needed human review.

Use it when:
- the project has hundreds/thousands of Vietnamese rows;
- you need a second pass for accent/normalization anomalies;
- you want sentence/word counts for long codex/lore rows;
- you can afford optional setup time.

Skip it when:
- the project is small;
- structural validators already found all target rows clean;
- the environment should stay dependency-light;
- the remaining issue is format/patching, not Vietnamese language quality.

Do not run underthesea repeatedly after every patch. Run it once near final, review the report, then rely on structural readback and screenshot/gameplay QA.

## Example command shape

```bash
python tools/qa_vi_underthesea.py translations_final.csv qa_underthesea_report.csv
```

Keep the script optional. If underthesea is missing, fall back to regex/stdlib checks and report that enhanced Vietnamese NLP QA was skipped.
