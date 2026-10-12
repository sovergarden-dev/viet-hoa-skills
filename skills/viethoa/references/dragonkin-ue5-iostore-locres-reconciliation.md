# UE5 IoStore game with legacy `.pak` localization sidecar — reconciliation route

## Situation
A UE5 installation may ship large `.utoc`/`.ucas` IoStore payloads while `pakchunk0-Windows.pak` remains a readable V11/Oodle sidecar containing localization and loose Slate/font resources. Do not infer that `.locres` must be extracted from the IoStore payload merely because `.ucas` is present.

## Read-only discovery
1. Record Steam build ID and hashes of `.pak`, `.utoc`, `.ucas` sidecars.
2. Run `repak info` and `repak list` on the base `.pak` first.
3. Search its file list for `Content/Localization/*/<culture>/*.locres`, `.locmeta`, fonts, and plugin locales.
4. If present, extract only the base `.pak` to workspace with `repak unpack`; do not write into the game.
5. Export each current English `.locres` with `UnrealLocres` to canonical CSV.

## Legacy community patch reconciliation
Community `.locres` exports can store Vietnamese in `source` and leave `target` blank because the file itself was built with Vietnamese as the active resource text. Inspect sample rows before deciding which CSV column is the translation.

Reconcile by stable key, not physical order. For each current key:
- carry the legacy Vietnamese value only after protected-token validation;
- mark absent current keys as `new_key_pending`;
- mark legacy rows whose macro/placeholder structure differs as `review_legacy_token_mismatch` and leave `translation_vi` blank;
- include new localization domains such as `Place_Names`, which old patches may omit.

## Unreal `.locres` import/readback traps

- `UnrealLocres export` writes the active localized resource text into CSV column `source` and usually leaves `target` blank. This applies to community-patched locres too; inspect rows before mapping columns.
- Một số bản `UnrealLocres.exe` bỏ qua thư mục trong `-o` và ghi `<basename>.csv` vào process CWD. Chạy mỗi export trong unique empty CWD, snapshot inventory trước/sau, rồi resolve output bằng exact expected basename + newly-created file + parse/hash; không tin requested path hoặc lấy một CSV cũ cùng tên.
- For import, build `key,source,target` where `source` is the **current canonical English text** and `target` is Vietnamese. Putting Vietnamese into `source` imports zero translations.
- Require one-row sentinel proof on an isolated copy before full import, then export the result again and confirm the sentinel moved into exported `source`.
- The serializer may normalize CRLF/CR to LF. Exact full-corpus readback should normalize line endings only; do not normalize other text.
- A UE5 game with IoStore can still keep all `.locres` in the small base `.pak`. Run `repak info/list` on that file before converting tens of GB from `.utoc/.ucas` or escalating to FModel/UEExtractor.
- When matching printf placeholders, `%` is literal unless it starts a syntactically valid directive such as `%s`, `%d`, or `%1$s`. Never let regex consume prose such as `100% of HP` as `% o`; use one tested canonical matcher across every QA helper.
- `repak --path-hash-seed` expects decimal CLI input even when `repak info` prints hex. Convert `0x...` to decimal, then require `repak info` on the output to echo the original hex seed.

## Unreal macro validation
Do not require translated macro arguments to equal English arguments. Validate macro invocation count and syntax, plus markup, real printf placeholders, and escapes. For example, preserve every `{PlayerGender}|gender(...)` invocation, but allow Vietnamese values inside the parentheses. A prior translation can replace a macro invocation with bare `{PlayerGender}`; that is a real review item, not a safe carry-forward.

## Branding/provenance boundary

Search exact prior translator/team names and generic credit phrases across source, canonical workbook, and final readback. Replace only proven non-game branding keys authorized by the user. Do not replace ordinary game-world words that happen to overlap a brand, such as `Forum` in place names or quest text. Record the exact key and verify zero residual prior-brand occurrences after import and package readback.

## Proven checkpoint
A current Dragonkin-style reconciliation produced:
- 8,768 current strings;
- 8,659 safe legacy carry-forwards;
- 44 new `Place_Names` strings;
- 65 macro-token review rows.

Use these only as a pattern, never as expected counts for another build.
