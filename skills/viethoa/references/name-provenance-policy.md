# Canonical-name provenance policy

Use this reference whenever a game, term, character, place, faction, item, skill, title, or branded name could have an original-country form and a later English localization.

## Rule

The source country's authorial/original-market canonical form wins for creator-authored names. English localization is evidence for meaning and identity only; it cannot silently replace that form. A project must record the game origin, primary authorial language, evidence, and each resolved or unresolved name decision before bulk translation.

This is not a mechanical "country equals spelling" rule. Country discovers the creator's primary source, while the **entity's own provenance** decides the display form:

1. Explicit user lock or exact glossary lock wins.
2. Creator/publisher's original-market official form wins, including a creator-published Latin spelling.
3. If no official Latin form exists, use a documented native-source/national romanization convention declared by the project.
4. A Vietnamese convention such as Hán–Việt is valid only when the project records the original characters, the convention, scope, and evidence.
5. A foreign/Latin name deliberately used in an original-language work keeps its established canonical spelling; do not mechanically romanize it through the game's language.
6. A later English localization is reference-only unless it is proven to be the original/creator-published form.
7. Missing evidence or source/English collision is `needs_review` in the ledger and `needs_context` in a candidate. Never guess or bulk replace.

## Project artifacts

Create these before the first bulk packet:

- `name-provenance-policy.json`: project origin country, primary authorial language, origin evidence, declared romanization rule, ledger path, and audit status.
- `name-provenance-ledger.csv`: one row per locked, collided, or unresolved proper name. Keep it separate from the glossary so its evidence is inspectable.

Use `templates/name-provenance-policy.json` and `templates/name-provenance-ledger.csv`. Validate with:

```text
python <viethoa-skill-root>/scripts/audit_name_provenance.py --policy <policy.json> --ledger <ledger.csv>
```

Before release, require no unresolved rows and a completed corpus audit:

```text
python <viethoa-skill-root>/scripts/audit_name_provenance.py --policy <policy.json> --ledger <ledger.csv> --require-resolved --require-complete
```

`audit_status=complete` means a human/semantic audit compared the entire release corpus's candidate proper names against native source, glossary, and source-country evidence. The script checks artifact integrity; it cannot infer every name from arbitrary game data.

## Language-specific defaults

- **Japanese-origin / Japanese authorial names:** creator-published Latin spelling first. Otherwise romanize the Japanese source using the project-declared standard; default is Modified Hepburn without macrons. Do not replace it with an English localized pun or alternate name.
- **Chinese-language projects:** retain original characters as evidence. Use a project-declared canonical Vietnamese convention (for example, evidence-backed Hán–Việt in a wuxia corpus) or an official creator form. Do not substitute an English localization or mechanically force Pinyin/Hán–Việt without scope evidence.
- **Korean and other non-Latin scripts:** creator-published Latin spelling first; otherwise use a documented national/project romanization standard. English localization is not a fallback.
- **English-origin projects:** English is normally the authorial form, so existing English proper names remain unless the ledger proves a different creator canonical form.

## Regression examples

| Source / context | Correct canonical decision | Why |
| --- | --- | --- |
| Japanese game: `イキルカ・シヌカ・ハムレット` | `Ikiruka Shinuka Hamlet` | `イキルカ・シヌカ` is Japanese authorial wording rendered from Japanese source; `Hamlet` is an established foreign/Latin name. English `Toby Notoby Hamlet` is reference-only. |
| Taiwanese Traditional-Chinese wuxia: `唐門` | project-locked `Đường Môn` | Original characters plus an evidence-backed project Hán–Việt convention; not English `Tang-Man`. |
| English-origin game: `Mortal Shell` | `Mortal Shell` | English is the creator's original branded form. |

## Worker and handoff gate

Put policy and the relevant ledger rows into every worker/external prompt. The model may translate surrounding prose but cannot choose a proper-name form absent from the ledger. Record the new row and review it first; a context state is safer than an English fallback. Freeze policy and ledger hashes in handoff manifests. Never change past canonical rows through a blind search/replace: audit exact keys, create a receipt, then make a scoped transaction.

## Existing-project migration

Do not rewrite an existing canonical corpus just because this policy is new. At the next translation, review, external handoff, import, or release action: pause any writer; record the project's country/language/evidence; create and validate the policy + ledger; add `name_provenance` status to project state; then audit exact affected keys. Keep `audit_status` non-complete until all release-scope proper-name collisions have evidence. A release/build gate must fail closed while that audit remains pending. This applies even when the translation count is already zero-pending.
