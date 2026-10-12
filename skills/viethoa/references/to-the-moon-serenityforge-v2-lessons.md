# To the Moon SerenityForge v2.x lessons

Date: 2026-07-06

## 1. Unity asset size validation is mandatory

A UI patch built from the wrong UnityPy save path produced tiny `.assets` files and crashed at Unity startup.

Bad sizes seen:

```text
main resources.assets: ~493 KB
minisode1 resources.assets: ~276 KB
minisode2 sharedassets2.assets: ~134 KB
```

Safe sizes for this project were around:

```text
main resources.assets: ~145 MB
minisode1 resources.assets: ~63 MB
minisode2 sharedassets2.assets: ~66 MB
```

Rule: after every Unity `.assets` rebuild, compare output size against the last known-good patch/original. If a file shrinks by orders of magnitude, do not ship it even if `zipfile.testzip()` passes.

## 2. UI/menu text is not limited to dialogue tables

The tabs and menu text came from:

- `Terms_Loc`: `Characters`, `Notes`, `Items`, `Description:`, `Save`, `Load`, `Options`, `Exit Game`, options text, character descriptions.
- `Items_Loc`: item names, item descriptions, notes shown as inventory entries.
- `Actors_Loc`: character names.

Do not translate only visible screenshot strings. Scan all related UI tables and build a full mapping for terms/items/notes/characters.

## 3. Newline wrapping

Actual newline in TextAsset dialogue was accepted by the game and prevented font auto-shrink. A literal `\n` should not be assumed safe.

Pitfall: do not put pause control code `\.` at the start of a wrapped line; in this game it rendered as a visible `.` before the next word.

Safe pattern:

```text
Line 1,
Line 2
```

Unsafe pattern:

```text
Line 1,
\.Line 2
```

## 4. Dynamic-protagonist pronouns

Some scenes let the player choose Eva or Neil, but the same English text keys can be reused. A fixed Vietnamese `chú` breaks when Eva is selected; fixed `cô` breaks when Neil is selected.

Handling rules:

- If the line is definitely spoken by Eva/Rosalene to children: use `cô/cháu`.
- If definitely spoken by Neil/Watts to children: use `chú/cháu`.
- If the same choice text may be selected by either lead: use neutral `tôi` where natural.
- If children address both leads together: `cô chú` can be correct.
- Do not convert `cô ấy/ông ấy/bà ấy/anh ta` unless it is truly direct address.

## 5. Pronoun audit must be context-classified

An automated grep for `ông/bà/anh/cô/chú` produces many false positives. Classify each flagged row before editing:

- `fix`
- `keep_third_person`
- `keep_idiom`
- `keep_dynamic_neutral`
- `needs_context`

Exact-key fixes are safe; global replacement is not.

## 6. Foundational docs to consult

For this user, `viethoa` should consult these documents when available:

```text
C:\Users\<user>\Desktop\Hướng dẫn Việt hóa game – README tổng hợp theo engine và phương pháp.md
C:\Users\<user>\Desktop\dich.md
```

They establish the methodology: engine-aware workflow, reference-language use for xưng hô, glossary/style/pronoun files, and QA for font/wrap/UI.
