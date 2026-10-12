# Unity legacy `UI.Text` Vietnamese glyph fallback

## Trigger

A Unity Vietnamese patch loads correctly, but menu labels render `□` for Vietnamese diacritics while some text (often TMP headings) renders normally.

## Evidence-first workflow

1. Treat this as font/atlas failure, not encoding or translation failure. Capture an in-game screenshot and list exact broken glyphs.
2. Audit every Unity `Font` asset's embedded `m_FontData` cmap against the complete Vietnamese character set. FontTools can inspect extracted TTF data.
3. Inventory every `MonoBehaviour` raw `PPtr<Font>` reference. Resolve `m_Script` through the owning asset's externals: `UnityEngine.UI.Text` and `TMPro.TMP_FontAsset` have different routes.
4. Before interpreting a screenshot, hash the installed `resources.assets` and compare it to both original and candidate patch. Also verify backup existence. A successful installer message alone does not prove the game is running the patched asset.
5. If legacy UI Text points to a missing-glyph font (e.g. bitmap/DOS font), do **not** assume changing its PPtr to a Unicode font is enough. Dynamic font data, material, and texture/atlas bindings may still cause runtime tofu.
6. Prefer a same-ID replacement proof: preserve all `UI.Text` PPtrs and replace the **legacy font object at its existing `path_id`** with a known-complete font object's serialized typetree/data. Reload it, confirm name/data length, structural object inventory, then run Steam-runtime screenshot QA.
7. Preserve `TMP_FontAsset` objects unless separately audited; a working TMP heading does not validate legacy `UI.Text`.

## Validation gates

- Cmap covers all required Vietnamese glyphs.
- Exact installed asset SHA-256 equals intended patch SHA-256 before runtime QA.
- Expected UI objects/font object only are changed; all object inventory remains intact.
- In-game Steam screenshot confirms no `□` and no layout/visual regression.
- Never call a font patch release-ready from structural validation alone.

## Why pointer replacement can fail

A `UI.Text` PPtr change from a bitmap font to a dynamic font can leave incompatible material/texture state. Replacing the backing font at the original path ID avoids changing widget bindings and is a safer next proof, but still requires runtime visual validation.
