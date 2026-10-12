# Luna Abyss no-AES Unreal `.locres` build/packaging notes

Use this as a concrete recovery pattern when an Unreal pak has an encrypted index but localization payload blocks are still zlib-compressed and readable.

## What worked

- Confirmed normal pak listing/extraction was blocked by encrypted index and missing AES key.
- Avoided translating raw binary string scans; raw hits mixed FMOD events, asset paths, metadata, and player text.
- Scanned localization-adjacent pak regions for zlib headers and decompressed candidate blocks.
- Identified a valid Unreal localization resource by magic `0x7574140E`.
- Used `akintos/UnrealLocres` instead of hand-writing a full parser:
  - `UnrealLocres.exe export -f csv -o Game_en_from_zlib_locres.csv recovered_block.bin`
  - edit/import CSV
  - `UnrealLocres.exe import -f csv -o Game_vi.locres recovered_block.bin Game_vi_import.csv`
- Built a clean workbook and retained only structurally exported locres rows as source-of-truth.
- Created two install candidates without touching the original pak:
  - loose localization overrides under likely `Content/Localization/Game/<culture>/Game.locres` paths
  - a best-effort patch pak with `repak pack --version V11 --compression Zlib --mount-point "../../../"`

## Important pitfalls

- `UnrealLocres export` writes translated strings back into the CSV `source` column for the new locres; the `target` column can be blank. Compare original-export `source` vs translated-export `source` to verify changes.
- Do not call `.strip()` on translation text in build scripts. It removes intentional trailing newlines and causes false newline-count failures or real layout changes. Only use `.strip()` to test whether a translation is empty, then preserve the raw value.
- Validate placeholders/tags/newline counts before import. Fail hard on mismatch; newline mismatches can break layout or glyph effects.
- For vertical/layout text, preserving the English source is safer than inventing a shorter Vietnamese string with fewer line breaks unless you can reproduce the same layout count.
- Patch-pak file paths are best-effort when the pak index is encrypted. If loose override and patch pak are ignored, ask the user for a clean FModel export or AES/key-derived listing to confirm exact paths.

## Minimal validation pattern

```python
PLACEHOLDER_RE = re.compile(r'\{[^{}]+\}')
TAG_RE = re.compile(r'<[^<>]+>')

def tokens(s):
    return {
        'placeholders': sorted(PLACEHOLDER_RE.findall(s or '')),
        'tags': sorted(TAG_RE.findall(s or '')),
        'crlf': (s or '').count('\n') + (s or '').count('\r'),
    }

vi_raw = row.get('translation_vi') or ''
if vi_raw.strip():
    translations[(key, source)] = vi_raw  # preserve raw newlines
```

## Delivery wording

Be explicit that this is a no-AES best-effort build:
- original pak untouched
- locres is valid and validated
- exact in-pak path cannot be proven without index listing
- user should test loose override/patch pak first, then use FModel guide only if ignored
