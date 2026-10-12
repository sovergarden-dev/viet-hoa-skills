# To the Moon SerenityForge v1.1 lessons

## What changed after first in-game QA

User tested the v1.0 ZIP in-game and found:
- Control codes showed literally: `c[6]`, `c[0]`, `w[5]`, `[30]`.
- Many dialogue lines displayed extra `.` before text.
- Some choices were still English: `Push it by hand`, `Find a branch`, `Abort mission and go home`.
- Act title cards still showed English: `Act 1` and quote text.
- A literal/joke translation `Cucumbers...` -> `Dưa leo...` was semantically wrong in context.

## Durable fixes

### Unity CSV/TextAsset escaping

When patching Unity `TextAsset` CSV localization tables, keep runtime control codes double-escaped in the CSV cell:

```text
\.      pause
\|      wait/continue
\c[6]   color start
\c[0]   color reset
\w[5]   wait
\oi[30] icon/item injection
\v[187] variable
```

In Python strings this often means the workbook/final cell must contain two literal backslashes before runtime codes. Validate after CSV write and after UnityPy reload. Bad symptoms in-game:
- `\c[6]text\c[0]` written with one slash may render as `c[6]textc[0]`.
- `\w[5]` written with one slash may render as `w[5]`.
- `\oi[30]` written wrong may render as `[30]` or broken item text.
- `\.` written wrong may render as visible `.` rather than a pause.

Use a validation pass that searches for single-escaped control codes and fixes them before building the patch.

### Dialogue choices are not `ShowText`

Initial extraction regex only captured `ShowText`/`NameBox`, so choices were missed. For Unity/RPG Maker-like SerenityForge tables also extract keys containing:

```text
DialogueChoice
ChangeActorName
```

Skip empty `ChangeActorName` rows, but review all visible `DialogueChoice` rows.

### Act title cards

`Act1`, `Act2`, `Act3`, and quote card assets appear in Unity `Texture2D`/resource metadata and may not live in the same `TextAsset` CSV tables as dialogue. Dump and inspect title/quote assets separately. Do not patch blindly.

Recommended Vietnamese act labels for readability and literary tone:

```text
Act 1 -> Hồi 1
Act 2 -> Hồi 2
Act 3 -> Hồi 3
```

For title-card quotes, preserve speaker voice and meaning, not literal phrasing. Example candidate for Act 1:

```text
“I never told anyone, but… I’ve always thought they were lighthouses.”
-> “Em chưa từng nói với ai, nhưng… em luôn nghĩ chúng là những ngọn hải đăng.”
```

Confirm pronoun choice with the user because the title card is prominent.

### Literal joke phrases

Do not translate surreal euphemisms literally when Vietnamese result is nonsensical. Example:

```text
Cucumbers... We don't have time for this fluff.
BAD: Dưa leo... Chúng ta không có thời gian...
BETTER: Khỉ thật... Chúng ta không có thời gian...
```

`What the cucumber...?!` should be treated as a comic minced oath, e.g. `Cái quái gì vậy...?!`, unless the game intentionally references actual cucumbers.

## Release discipline

After in-game QA fixes:
1. Update workbook first.
2. Rebuild TextAsset patch.
3. Reload patched assets and validate exact cell equality.
4. Rebuild ZIP with a new version, e.g. `v1.1`.
5. Ask for screenshots of early scenes, choices, item popups, and act cards before calling it final.
