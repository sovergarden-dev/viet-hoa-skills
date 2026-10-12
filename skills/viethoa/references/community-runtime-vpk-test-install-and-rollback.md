# Community runtime VPK: test install and rollback

Use after an encrypted community translation archive has been rebuilt in a workspace and exact decrypt/readback matches the reviewed canonical corpus. This route is for reversible runtime QA, not release packaging.

## Build gate

Before touching the live game:

1. Require canonical `pending == 0` and canonical validator errors `== 0`.
2. Preserve rows marked `needs_context`; report them honestly rather than silently promoting them.
3. Rebuild the archive with the exact loader contract: signature/version, record count, sentinel record, table offsets, key/IV derivation, cipher mode, padding, UTF-8 encoding, NUL convention, and escaped line-break marker.
4. Decrypt the emitted archive and compare every source/target pair against canonical values in exact order. Whole-file parse success is insufficient.
5. Record original archive, rebuilt archive, executable, and plugin SHA-256 values.

## Hash-guarded test installer

Implement one small CLI with `status`, `install`, and `uninstall` actions.

### `install`

- Bind to the canonical executable and live archive paths.
- Refuse before writes unless executable hash, live-original hash, payload hash, and expected plugin hash all match.
- If a backup already exists, require its hash to equal the expected original; never overwrite an unknown backup.
- Copy the original to a workspace backup using a sibling temporary file, flush + `fsync`, verify hash, then `os.replace`.
- Install the reviewed payload using the same atomic-copy procedure.
- Verify the live payload hash after installation. On verification failure, restore the verified backup immediately and report failure.
- Persist an install-state JSON with paths, hashes, timestamp, and ownership.

### `uninstall`

- Require the verified original backup.
- Refuse to overwrite if the live archive hash is neither the known test payload nor the known original; another party may have changed it.
- Restore atomically, verify exact original hash, then clear install state.
- Keep the backup unless the release workflow explicitly owns and removes it after successful restore.

### `status`

Report only current live/payload/backup hashes and state-file presence. It must not write.

## Ad-hoc verification

Before offering the installer, exercise the atomic-copy/hash path in an isolated `tempfile.TemporaryDirectory(prefix="hermes-verify-")`. This proves helper behavior without touching the game. Also run `status` against the canonical paths to establish the pre-install state.

## Runtime checkpoint ownership

Do not launch the game automatically. Ask the user to install explicitly, then run the game and capture targeted evidence:

- the originally reported terminology defect;
- another mechanics panel;
- item/Rune/Spell names expected to remain English;
- long dialogue and quest log;
- small labels, Vietnamese diacritics, wrapping, clipping, exposed tokens, and missing glyphs.

Call the artifact `offline structurally verified, pending runtime QA` until those checkpoints pass. A successful decrypt/readback and live-file hash do not prove runtime hook coverage or UI fit.
