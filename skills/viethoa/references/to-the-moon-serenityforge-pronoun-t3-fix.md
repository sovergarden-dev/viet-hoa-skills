# To the Moon SerenityForge: pronoun rules and `\t3` escape fix

Date: 2026-07-05

## Symptoms found in Minisode 1 QA

- Visible `t3` appeared before dialogue text, e.g. `t3'Neil...`.
- Eva/Rosalene sometimes called Neil/Watts with the wrong gendered pronoun.
- Neil/Watts sometimes called Eva/Rosalene with the wrong gendered pronoun.
- Some Vietnamese dialogue overused semicolons `;` where a comma reads naturally.

## Root causes

1. Control code `\t3` must be escaped as `\\t3` in the serialized CSV/TextAsset path, same family as `\\c[]`, `\\w[]`, `\\oi[]`, `\\.`.
2. Translation batches drifted because there was only a glossary, not a relation-specific pronoun rule file.
3. Old reference translations can be useful, but cannot be trusted blindly for speaker/addressee in remaster rows.

## Added file

Create and maintain:

`pronoun_rules.csv`

Recommended columns:

```csv
speaker,addressee,scope,vi_speaker,vi_addressee,notes
```

Rules used for this project:

```text
Eva/Rosalene -> Neil/Watts: tôi/ông
Neil/Watts -> Eva/Rosalene: tôi/bà
Eva -> Roxie: tôi/cô
Roxie -> Eva: tôi/cô
Roxie -> Neil: tôi/ông
Neil -> Roxie: tôi/cô
Johnny nhỏ <-> River nhỏ: tớ/cậu
```

## Fix pattern

Before rebuilding the patch:

1. Load final review CSV.
2. Escape leading/control `\t3` to `\\t3`.
3. Run a pronoun consistency pass by speaker/addressee, not by isolated text.
4. Replace semicolons in Vietnamese prose unless the source/meaning explicitly needs a strong break.
5. Rebuild TextAsset patch and run validation.
6. Rebuild final zip.

## Release package after fix

`To_the_Moon_SerenityForge_VietHoa_v1.5-pronoun-t3-act.zip`

SHA256:

`4959b804033e23764e3cd987aa5855dbff4509aa89d29565d07c8db77f798617`

## QA points

- Minisode 1 first Rosalene line must not show `t3`.
- Rosalene -> Neil uses `ông`, not `anh` or `bà`.
- Neil -> Rosalene uses `bà`, not `ông`.
- Banter punctuation should read naturally with commas unless a semicolon is deliberate.
