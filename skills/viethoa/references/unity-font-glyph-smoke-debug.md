# Unity UI Vietnamese glyph smoke debugging

## Trigger

Vietnamese strings reload correctly from localization assets but runtime shows tofu squares (`□`) only for accented glyphs.

## Gates before changing fonts

1. Inspect the installed `resources.assets` hash and byte size. Confirm it equals the patch manifest hash; a successful installer message is not proof the file remains installed.
2. Verify any `.viet_backup` exists and is the expected original hash.
3. Capture a Steam-runtime screenshot after restarting the game. A clone launched outside Steam can fail `SteamAPI_Init()` and is not enough for UI proof.
4. Audit embedded font cmap coverage for the exact Vietnamese alphabet. Coverage in a TTF is necessary but not sufficient for Unity runtime rendering.

## Asset investigation

- Inventory all `Font` objects and extract `m_FontData` to audit cmap with `fontTools.ttLib.TTFont`.
- Determine the actual UI renderer path. In this Unity 2020 IL2CPP game, ordinary menu labels are `UnityEngine.UI.Text`; language/script assets may be TMP and are a separate path.
- Scan **all** `.assets`, `sharedassets*`, and `level*` files for font PPtr references. Do not assume the first `resources.assets` hit is the active scene/menu asset.
- Decode `UnityEngine.UI.Text` through the DummyDll type tree. Change only `m_FontData.m_Font` if a write proof is needed; raw PPtr replacement is not proof of intended field semantics.

## Critical pitfall

Changing a `UI.Text` font pointer from a legacy font to a dynamic font can serialize and reload correctly yet still render tofu at runtime. Unity may depend on the target font's runtime rendering mode, material/atlas state, or another menu asset. Do not claim a font fix from structural validation alone.

## Proof requirements for a font fix

- Preserve every unrelated raw Unity object payload before saving.
- Object inventory changes match an explicit whitelist.
- Reload every changed `UI.Text.m_FontData.m_Font` field.
- Confirm the installed hash after using the installer.
- Steam runtime screenshot shows target strings without `□`, including menu labels, values, and confirmation dialogs.
- Check clipping/line breaks after switching the font.

## Session evidence

`Perfect DOS VGA 437` lacked 102 Vietnamese characters; `Roboto-Regular`, Roboto Slab variants, Noto Sans KR, and Noto Sans had full cmap coverage. Repointing 82 `UI.Text` objects from the legacy font to Roboto serialized/reloaded correctly but did not remove runtime tofu. Continue with full asset/scene reference scan rather than producing more blind font patches.
