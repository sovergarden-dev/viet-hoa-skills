# Mortal Shell II Demo — UE5 locres + UI font fix v4

Session lesson for Unreal Vietnamese localization where `Game.locres` loads correctly but UI drops Vietnamese characters.

## Symptoms

Screenshots showed Vietnamese loaded, but some uppercase/small UI text lost entire characters:

- `BẢN TÓM TẮT` rendered like `BN TÓM TT`
- `THOÁT VỀ MENU CHÍNH` rendered like `THOÁT V MENU CHÍNH`
- `NGHỈ NGƠI TẠI BEACON` rendered like `NGH NGI TI BEACON`
- `SỬ DỤNG GLOOM SIPHON` rendered like `S DNG GLOOM SIPHON`
- `VŨ KHÍ TẦM XA` rendered like `V KHÍ T M XA`

Important diagnosis: subtitles/dialogue could render accents while menu/prompt widgets failed. That means the locres/text is not the root problem; those widgets use a different font asset with missing Vietnamese glyphs.

## Correct workflow

1. Confirm Vietnamese text is present in the target culture locres by exporting the installed pak.
2. Do **not** globally strip accents or convert UI to no-diacritic Vietnamese as the primary fix.
3. Find custom UI font assets in the pak, especially under paths like:
   - `MortalShell2/Content/Sparta/UI/Fonts/*.ufont`
4. Extract candidate `.ufont` files and test glyph coverage for Vietnamese precomposed glyphs (`Ơ/Ư/Ạ/Ả/Ấ/Ầ/Ể/Ử/Ụ...`).
5. Patch only font assets that lack Vietnamese glyphs, then rebuild the pak.
6. Keep a screenshot-driven QA loop. If a specific screen still drops glyphs, identify the other font asset used by that widget and patch that font too.

## Mortal Shell II details

Custom font assets found:

```text
MortalShell2/Content/Sparta/UI/Fonts/Cormorant/*.ufont
MortalShell2/Content/Sparta/UI/Fonts/CrimsonText-*.ufont
MortalShell2/Content/Sparta/UI/Fonts/NotoSans/*.ufont
MortalShell2/Content/Sparta/UI/Fonts/NotoSerif/*.ufont
MortalShell2/Content/Sparta/UI/Fonts/PTSerif/*.ufont
MortalShell2/Content/Sparta/UI/Fonts/Trajan_Pro_Regular.ufont
MortalShell2/Content/Sparta/UI/Fonts/Trajan_Pro_SemiBold.ufont
MortalShell2/Content/Sparta/UI/Fonts/Vollkorn*.ufont
```

Glyph coverage test showed:

- `PTSerif-Regular/Bold/Italic.ufont`: missing 98 Vietnamese precomposed glyphs.
- `Trajan_Pro_Regular.ufont`: missing 98 Vietnamese precomposed glyphs.
- `Cormorant`, `CrimsonText`, `Vollkorn`, `Trajan_Pro_SemiBold`: full coverage for the tested Vietnamese glyph set.

Patch used:

```text
PTSerif-Regular.ufont -> C:\Windows\Fonts\times.ttf
PTSerif-Bold.ufont    -> C:\Windows\Fonts\timesbd.ttf
PTSerif-Italic.ufont  -> C:\Windows\Fonts\timesi.ttf
Trajan_Pro_Regular.ufont -> C:\Windows\Fonts\cambriab.ttf
```

After replacement, glyph missing count for the tested Vietnamese set was `0`.

## `.ufont` wrapper note

These `.ufont` files were raw font bytes wrapped by Unreal with a 4-byte little-endian size prefix and a 4-byte zero tail:

```python
def wrap_font_bytes(font_path: Path) -> bytes:
    data = font_path.read_bytes()
    return len(data).to_bytes(4, 'little') + data + b'\x00\x00\x00\x00'
```

To inspect with `fontTools`, read `ufont_bytes[4:-4]` as the font payload.

## Glyph check snippet

```python
import io
from pathlib import Path
from fontTools.ttLib import TTFont

VI_CHARS = 'ÀÁÂÃÈÉÊÌÍÒÓÔÕÙÚÝàáâãèéêìíòóôõùúýĂăĐđĨĩŨũƠơƯưẠạẢảẤấẦầẨẩẪẫẬậẮắẰằẲẳẴẵẶặẸẹẺẻẼẽẾếỀềỂểỄễỆệỈỉỊịỌọỎỏỐốỒồỔổỖỗỘộỚớỜờỞởỠỡỢợỤụỦủỨứỪừỬửỮữỰựỲỳỴỵỶỷỸỹ'

def missing_vi_glyphs(path: Path) -> str:
    data = path.read_bytes()
    if path.suffix.lower() == '.ufont':
        data = data[4:-4]
    font = TTFont(io.BytesIO(data), fontNumber=0)
    cmap = {}
    for table in font['cmap'].tables:
        cmap.update(table.cmap)
    return ''.join(c for c in VI_CHARS if ord(c) not in cmap)
```

## Text QA decisions from this session

- Keep Vietnamese in the Russian/foreign technical slot when possible; do not overwrite English unless making a separate explicit English-override build.
- Do not leave proper/game terms machine-translated when the user wants them preserved. Lock terms such as `Disciple`, `Sidearm`, `Sester`, `Tarstone`, `Mether`, `Beacon`, `Gloom`, `Resolve`, `Harbinger`, `Shell`, and `Seal` where appropriate.
- Fix wrong MT separately from font issues: e.g. `Disciple` must not become `đệ tử`; `Parry` must not become `tha thứ`; `Fire (Sidearm)` must not become `Lửa (Sidearm)`.

## Packaging note

For this game, loose patch paks did not override in-game even when structurally valid. The working test build used a direct patched `pakchunk0-Windows.pak` with backup/restore scripts and a portable zip for other machines.
