# DragonSword: Awakening — custom PAK extraction and runtime table override

Use when an Unreal game has encrypted/custom legacy `.pak` files, QuickBMS can extract them, and a standard override PAK appears structurally valid but has no runtime effect.

## Proven build

- Steam App ID: `4570720`
- Build ID: `24350519`
- Engine family: UE5; game-specific evidence identifies UE 5.3.
- Shipping executable and every source PAK must be hashed before reuse on another build.

This is case evidence, not a universal route. Revalidate all hashes and behavior after any update.

## Discovery sequence

1. **Do not equate `repak` failure with a wrong AES key.** DragonSword uses a custom PAK index. A locally recovered key may be correct while generic `repak info/list` still fails.
2. Use the current `UE4_specific_scripts` bundle and select:
   ```text
   unreal_tournament_4_0.4.27e_dragon_sword.bms
   ```
   Require QuickBMS `0.12` and `quickbms_4gb_files.exe`.
3. Prove the key by listing a small PAK first. Completion evidence is plausible paths, nonzero file count, `Entries ignored: 0` where applicable, and successful listing across the intended source PAKs.
4. List all PAKs before extracting. Keep raw per-PAK lists and a reduced candidate report.

## Avoid the server-XML false route

The game contains readable server-side XML tables under:

```text
DS/Content/__GeneratedGameData__/Server/XML/GameData/String*.xml
```

They mirror localization content and are useful references, but they are not the authoritative client runtime tables for the tested UI. A structurally correct override of these XML files produced no runtime change.

The authoritative client files for the tested build are JSON-formatted `.table` files in `pakchunk108-WindowsClient.pak`:

```text
DS/Content/Design/GameData/StringData_en.table
DS/Content/Design/GameData/StringQuestData_en.table
DS/Content/Design/GameData/StringReminiscenceData_en.table
DS/Content/Design/GameData/StringSceneData_en.table
```

Before choosing a source, search for an exact full runtime sentence and its stable ID. Do not test a generic label such as `Confirm`: repeated labels can occur under many IDs and cannot identify the active table.

## Stable-key tracer test

1. Capture a runtime sentence from a reproducible screen.
2. Search every candidate table for the exact sentence.
3. Confirm its stable envelope, e.g.:
   ```text
   table: StringData_en.table
   ID: 3000009
   field: SourceString
   ```
4. Change one conspicuous same-length character inside that exact record. Keep JSON byte length unchanged for the tracer when practical.
5. Parse the modified table and assert:
   - exact target ID exists once;
   - only the intended field changed;
   - byte length is unchanged;
   - changed-byte count matches expectation.
6. Pack one-file override with standard UE V11 and mount point `../../../`.
7. Unpack the exact generated PAK and require byte-for-byte equality with the modified source.

Structural pack/unpack proof is not runtime proof.

## Correct mod installation path

DragonSword loads standard override PAKs from:

```text
DS/Content/Paks/~mods/
```

Putting the same PAK directly in `DS/Content/Paks/` produced no override. Create `~mods` when absent. Use a high-priority filename such as:

```text
pakchunk999-WindowsClient_P.pak
```

Hash the installed copy against the generated artifact before asking for runtime QA.

## Runtime proof gate

- User fully exits and restarts the game through Steam.
- User reproduces the exact screen tied to the stable-key tracer.
- Screenshot must visibly contain the deliberate marker.
- Read the screenshot exactly, including case. A normal `cutscenes` does not prove a marker `cutsceneS`.
- After proof, remove the tracer PAK before translation packaging.

Only then mark the route `runtime_verified`.

## Runtime screenshot feedback loop

A successful runtime mount does not prove terminology consistency or visual polish. For every screenshot checkpoint:

1. Transcribe every visible string and resolve each issue to an exact stable key before editing.
2. Treat feature names as proper terms when UI/help uses them as system nouns. For DragonSword, keep `Karma` everywhere; do not mix `Karma`, `Nghiệp`, `Nghiệp lực`, `Nghiệp quả`, or `Nghiệp chướng`.
3. Correct terminology only when the canonical source contains that term or a documented alias. Use boundary-aware matching; never replace Vietnamese words corpus-wide without source association.
4. Audit capitalization of standalone UI labels separately (`Hero` → `Anh hùng`, `Awaken` → `Thức tỉnh`). Do not impose title case on prose.
5. For branding, distinguish title-screen menu, pause/in-game menu, and confirmation-button contexts. Source labels `Exit` and `Quit` may be mapped opposite to intuition; identify the exact visual key by screenshot plus context/Memo and verify with a second screenshot. Replace only the proven key, then assert the signature occurs exactly once and every other exit/quit key remains unchanged.
6. For capitalization feedback, inventory every exact standalone source label producing the visible lowercase target (`Rune`, `Dodge`, `Raid`, `Bond`, etc.). Fix all source-equivalent UI labels, not only the screenshot instance; keep prose untouched.
7. Rebuild, unpack and compare the exact payload; require a second screenshot for every corrected screen.

Add screenshot-proven terminology and branding keys to the project regression corpus before release.

## Why direct QuickBMS reimport failed

The extracted `.table`/XML payloads are chunked. Even a one-byte same-length edit can recompress a 64 KiB chunk larger than its original compressed slot. QuickBMS `-r` then correctly refuses the write. `REIMPORT2` is incompatible with this script because its TOC/index uses `MEMORY_FILE` and chunked `Append` operations.

Do not force a larger chunk; that corrupts the archive. Build an additive override PAK instead.

## Completion criteria

- [ ] Correct build and source hashes recorded.
- [ ] Custom script lists real paths with the supplied key.
- [ ] Exact runtime sentence resolves to one `(table, ID, field)`.
- [ ] Modified table parses and changed-object whitelist is exact.
- [ ] Generated PAK unpacks byte-identically.
- [ ] Installed under `Paks/~mods/` with matching hash.
- [ ] Screenshot visibly proves the tracer marker.
- [ ] Tracer PAK removed before translation begins.
