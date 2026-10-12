# Unity IL2CPP encrypted localization files

## Trigger

Use when a Unity IL2CPP game ships a readable localization source such as `Lang.json`, but runtime screenshots prove that editing it has no effect and a same-purpose high-entropy file such as `Lang.BenFox` exists.

## Evidence-first workflow

1. Do not blame fonts or cache. Record the patched readable file hash, obtain a fresh runtime screenshot, and confirm the selected locale still shows old text.
2. Restore the ineffective readable-file patch before changing direction.
3. Inspect the opaque file without modifying it:
   - Record SHA-256 and size.
   - Check entropy and whether length is block-aligned.
   - Search IL2CPP metadata for its exact filename, loader messages, path fields, and encryption-related game classes.
4. Dump IL2CPP metadata/code with Il2CppDumper. If its .NET target is older than the installed runtime, `DOTNET_ROLL_FORWARD=Major` can run it without installing another runtime.
5. In `dump.cs`, locate the game-specific service and RVAs, for example fields like `secretKey`/`key` and methods such as `Encrypt`/`Decrypt`. Do not infer the algorithm from entropy alone.
6. Inspect `stringliteral.json` for key material and localization filenames. Correlate literals with constructor/encrypt/decrypt disassembly.
7. Prove the format by decrypting the original and parsing the full payload. For AES-CBC formats, the common container is:
   - first 16 bytes: IV;
   - remaining bytes: ciphertext;
   - PKCS#7 padding;
   - key exactly as represented by the recovered managed string encoding.
8. Validate against structure, not a readable prefix alone:
   - complete decrypt succeeds;
   - padding removes cleanly;
   - UTF-8 decode succeeds;
   - JSON/CSV parses;
   - locale names and entry counts are plausible;
   - stable keys match the canonical workbook.
9. Build the translated payload from the decrypted runtime file, not from an older readable companion. Replace only the proven locale slot and preserve all other language records and unknown/null records.
10. Encrypt with a fresh IV. Immediately decrypt the generated artifact independently and assert exact translated entries, protected tokens, parseability, and counts.
11. Install only after confirming the game is closed. Refuse unknown source hashes, create a sibling backup, copy the payload, and verify source/target hashes. Never launch the game automatically when the user owns runtime testing.

## Important pitfalls

- A readable `Lang.json` may be an editor/export artifact while runtime loads `Lang.BenFox`.
- High entropy plus 16-byte alignment suggests block encryption but does not identify AES, key derivation, mode, IV placement, or padding.
- CBC decryption with the correct key but wrong IV can make every block after the first look valid. Treat this as evidence that the first ciphertext block may actually be an IV; prove it by stripping the first 16 bytes and completing padding/parse validation.
- Comparing encrypted size directly with a different readable companion can mislead because runtime and readable files may contain different locale counts or revisions.
- Never publish a payload based only on successful encryption. Require decrypt-after-encrypt round-trip and a user-supplied runtime screenshot.

## Runtime-test ownership

Prepare and validate offline. The user launches the game, selects the target locale, and supplies screenshots. If the screenshot still shows the old locale, compare the live target hash and exact runtime source path before another patch attempt.
