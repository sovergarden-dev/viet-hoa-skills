# To the Moon SerenityForge v1 Lessons

## What went wrong after first release ZIP

User tested the patch in-game and screenshots showed:
- control tags rendered visibly: `c[6]`, `c[0]`, `w[5]`, `[30]`
- extra visible dots before words where pause tags were under-escaped
- missed choice-menu text such as `Push it by hand`, `Find a branch`, `Abort mission and go home`
- missed title/card text such as `Act 1`
- mistranslation: `Cucumbers...` was rendered literally as `Dưa leo...` though context needed an expletive/interjection.

## Root cause

Unity localization `TextAsset.m_Script` is a CSV table consumed by the game runtime. In the CSV cell, runtime escape codes need doubled backslashes in stored text. A workbook string that visually contains `\c[6]` may serialize into the asset as `\c[6]`; the game then treats the backslash as CSV-level escaping/loses it and displays `c[6]`. Final asset validation must check runtime-intended escaping, not only cell equality.

## Durable fixes

1. Before rebuilding a Unity TextAsset patch, normalize final translations:
   - `(?<!\\)\\(c|w|oi|p|v)\[` -> `\\\\<code>[`
   - `(?<!\\)\\([.|])` -> `\\\\.` / `\\\\|`
   - explicitly audit `\\v[...]` because Python can turn it into vertical-tab if literal strings were mishandled.
2. Do not treat bare `[number]` as automatically bad; classify it by source. It may be part of `\\oi[30]`, `\\v[187]`, etc. Check the prefix.
3. Validate both ways:
   - reload patch and compare CSV cells to workbook
   - scan generated TextAssets for visible-bad patterns: `(?<!\\)\\c\[`, `(?<!\\)\\w\[`, `(?<!\\)\\oi\[`, `(?<!\\)\\[.|]`, vertical-tab chars.
4. Extract more than `ShowText` rows. Choice/menu/title cards can live under other keys or tables. After screenshots show English remains, search all TextAsset tables (`Maps_Loc`, `CommonEvents_Loc`, `Terms_Loc`, `Items_Loc`, `Actors_Loc`) for the exact English strings and add them to workbook/patch scope.
5. Screenshot QA is mandatory before final community release. Treat user screenshots as validation failures and rebuild a new version (`v1.1`, etc.), not as minor cosmetic notes.

## Translation note

`Cucumbers...` / `What the cucumber...` in To the Moon is a joke/expletive substitute. Do not translate literally as `Dưa leo`. Use natural Vietnamese expletive/interjection, e.g. `Khỉ thật...` or `Cái quái gì vậy...?!` depending context.
