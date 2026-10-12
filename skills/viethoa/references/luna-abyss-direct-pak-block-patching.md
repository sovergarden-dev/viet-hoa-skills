# Luna Abyss: direct pak compressed-block patching

Use when patch-pak overrides of cooked Unreal DataTable assets crash, but zlib payload blocks are readable and the user has explicitly approved direct edits to a disposable install.

## Problem signal

Patch pak with carved/repacked `TooltipTable.uasset` / `.uexp` crashed with errors such as:

```text
DataTable /Game/LunaAbyssGame/Text/Tables/TooltipTable.TooltipTable: Serial size mismatch
EXCEPTION_ACCESS_VIOLATION reading address 0xffffffffffffffff
```

Cause: the override file shape did not match the original cooked asset split/serialization. Do not keep trying to override partial carved assets.

## Working approach

1. Keep stable locres patch pak for `Game.locres`.
2. For DataTable/Codex/Tooltip strings, patch the original pak's compressed zlib blocks in place.
3. Decompress the contiguous zlib blocks that contain the asset payload.
4. Parse Unreal `FString` values:
   - positive length: ANSI bytes including null
   - negative length: UTF-16LE chars including null
5. Patch only existing UTF-16 language slots, keeping the same `FString` character count and padding with spaces.
6. Recompress each modified block to a zlib stream no larger than the original compressed block length.
7. Write the recompressed bytes back at the original pak offset. Pad with zeros to the original compressed block length if needed.
8. Verify by reading the pak back, decompressing the patched blocks, and checking key Vietnamese strings.

## Slot strategy

For Vietnamese with accents, do not patch `_En` if it is ANSI. Use an existing UTF-16 language slot such as `_Ru`/`_Fr`, then include Vietnamese `Game.locres` under the same culture folder (`ru`, `ru-RU`, `fr`, etc.). If needed, tell the tester to select that language in-game.

## Portable installer packaging

If the user asks for a ZIP that can be extracted into the game folder, do not ship the full 8GB pak. Package:

```text
INSTALL_VI.bat
INSTALL_VI.ps1
_vi_patch/manifest.json
_vi_patch/blocks/block_<n>_<offset>_<length>.bin
LunaAbyss/Content/Paks/pakchunk99-WindowsNoEditor_P.pak
README_VI.txt
```

The installer opens `LunaAbyss/Content/Paks/LunaAbyss-WindowsNoEditor.pak` read/write and writes each block at the manifest offset. Explain that extraction alone cannot modify bytes inside the pak unless shipping the full pak.

## Safety policy

Default: backup original blocks before writing.

If the user explicitly grants direct original-pak edits on a disposable test install and says no backup, respect it. Recovery path is Steam Verify Integrity plus deleting `pakchunk99-WindowsNoEditor_P.pak`.

## Verification checklist

- Decompression succeeds for every written block.
- Patched block size equals original compressed block length.
- Key Vietnamese strings are found after re-decompression.
- Game boots.
- Test screenshots cover:
  - Options difficulty tooltip
  - Bách Khoa/Codex location entry
  - Bách Khoa/Codex memory entry
