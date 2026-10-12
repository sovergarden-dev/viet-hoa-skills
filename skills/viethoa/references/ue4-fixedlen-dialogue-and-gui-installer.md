# UE4 dialogue patching, culture isolation, and GUI installer notes

Use this for Unreal Engine game localization when UI/Codex works but dialogue/choices remain in a different pipeline.

## Dialogue tables with per-language columns
- Do not assume dialogue is in `.locres` or the same Codex/Tooltip DataTable.
- Search cooked blocks for dialog table asset paths such as `*/UI/Dialog/CSV/*_Dialog` and struct fields like `DialogText`, `Response1..4`, `Answer1..4`, `enDialogText`, `ruDialogText`.
- If the table has per-language columns, patch only the target culture column (e.g. `ruDialogText`). Never patch `enDialogText` or shared source strings if the user expects English to remain clean.

## Fixed-length FString patching
- In cooked UE4 assets, changing serialized `FString` length fields can trigger `Serialization Error: Corrupt data found` or UE4 access violations even when zlib recompression fits.
- Safer rule for direct DataTable dialogue/name patching: keep the original `FString` length field unchanged, write the target string inside the old character slot, and pad remaining characters with spaces/nulls.
- Validate by readback with `rstrip()` for padded spaces; still fail on Cyrillic/Russian leftovers in target fields.

## Speaker/name fields
- Dialogue text may patch correctly while speaker names stay in a separate table/key (`ru[name]...`). Patch name fields separately, also fixed-length.
- Keep character/speaker names English-ish when requested; fit to old slot caps without changing serialized size.

## Culture isolation
- English must remain untouched when the user asks for Vietnamese only in a technical slot. Avoid hardcoded/global ANSI patches unless they are culture-specific.
- Patch pak locres should not include `en/Game.locres` if English must be pristine.

## Packaging
- For user-facing delivery, a single GUI `.exe` can embed:
  - install payload blocks + patch pak;
  - original compressed blocks for uninstall;
  - background art;
  - author signature/credit text if requested;
  - `Cài Việt hóa` / `Gỡ Việt hóa` buttons.
- The installer should not require being placed perfectly in the game root. First check the EXE folder; if the pak is missing, warn the user, open a folder picker, and accept common choices such as the game root, `LunaAbyss/`, or `LunaAbyss/Content/Paks/`. Validate by finding `LunaAbyss/Content/Paks/LunaAbyss-WindowsNoEditor.pak` before writing.
- Gỡ should restore embedded original blocks and delete the patch pak when possible; otherwise clearly require Steam Verify.

## Reporting
- Be explicit about test-only vs final builds.
- Mention translation batch/API quota interruptions and any fallback use before claiming completion.
