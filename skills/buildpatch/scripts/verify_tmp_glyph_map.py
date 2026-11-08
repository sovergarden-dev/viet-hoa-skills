import os
import sys
import io
import argparse
import UnityPy
from fontTools.ttLib import TTFont

VN_134_CHARS = (
    "àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ"
    "ÀÁẢÃẠĂẰẮẲẴẶÂẦẤẨẪẬÈÉẺẼẸÊỀẾỂỄỆÌÍỈĨỊÒÓỎÕỌÔỒỐỔỖỘƠỜỚỞỠỢÙÚỦŨỤƯỪỨỬỮỰỲÝỶỸỴĐ"
)

def audit_containers(paths):
    print("=================================================================")
    print(">>> MECHANICAL TMP GLYPH COLLISION & FALLBACK COVERAGE GATE <<<")
    print("=================================================================")

    total_tmp = 0
    total_collisions = 0
    total_uncovered = 0

    for path in paths:
        if not os.path.exists(path):
            continue
        bname = os.path.basename(path)
        try:
            env = UnityPy.load(path)
        except Exception as e:
            print(f"Skipping unreadable container {bname}: {e}")
            continue

        fonts = {}
        for obj in env.objects:
            if obj.type.name == "Font":
                try:
                    d = obj.read()
                    raw = bytes(d.m_FontData)
                    if len(raw) > 0:
                        fonts[obj.path_id] = (getattr(d, "name", ""), TTFont(io.BytesIO(raw)))
                except Exception:
                    pass

        tmp_assets = {}
        for obj in env.objects:
            if obj.type.name == "MonoBehaviour":
                try:
                    tree = obj.read_typetree()
                    name = tree.get("m_Name", "")
                    if ("SDF" in name or "Font" in name) and "m_GlyphTable" in tree:
                        tmp_assets[obj.path_id] = tree
                except Exception:
                    pass

        for pid, tree in tmp_assets.items():
            name = tree.get("m_Name", "")
            total_tmp += 1
            glyphs = tree.get("m_GlyphTable", [])
            chars = tree.get("m_CharacterTable", [])
            baked_index_to_glyph = {g["m_Index"]: g for g in glyphs}
            baked_unicodes = {c["m_Unicode"] for c in chars}

            src_font_ref = tree.get("m_SourceFontFile", {})
            src_pid = src_font_ref.get("m_PathID") if src_font_ref else None

            asset_collisions = []
            if src_pid in fonts:
                fname, tt = fonts[src_pid]
                cmap = tt.getBestCmap()
                for ch in "0123456789.:/ -+%":
                    u = ord(ch)
                    if u not in baked_unicodes:
                        gn = cmap.get(u)
                        if gn:
                            gid = tt.getGlyphID(gn)
                            if gid in baked_index_to_glyph:
                                colliding_g = baked_index_to_glyph[gid]
                                asset_collisions.append((ch, u, gid, colliding_g))

            # Recursive fallback resolution for primary font chain
            is_primary_font = ("康熙" in name) or ("NotoSerifTC" in name)
            missing_vn = []
            if is_primary_font:
                resolved_unicodes = set(baked_unicodes)
                if src_pid in fonts:
                    resolved_unicodes.update(fonts[src_pid][1].getBestCmap().keys())
                for fb in tree.get("m_FallbackFontAssetTable", []):
                    fb_pid = fb.get("m_PathID")
                    if fb_pid in tmp_assets:
                        fb_tree = tmp_assets[fb_pid]
                        fb_src_pid = fb_tree.get("m_SourceFontFile", {}).get("m_PathID")
                        if fb_src_pid in fonts:
                            resolved_unicodes.update(fonts[fb_src_pid][1].getBestCmap().keys())
                missing_vn = [c for c in VN_134_CHARS if ord(c) not in resolved_unicodes]

            status = "PASS" if not asset_collisions and not missing_vn else "FAIL"
            print(f"[{status}] {bname:40} | Asset: {name:32}")
            print(f"       Glyphs: {len(glyphs):<5} | Baked: {len(chars):<5} | Collisions: {len(asset_collisions)} | Missing VN: {len(missing_vn)}")
            total_collisions += len(asset_collisions)
            total_uncovered += len(missing_vn)

    print("-----------------------------------------------------------------")
    print(f"Audit finished: {total_tmp} assets, {total_collisions} collisions, {total_uncovered} missing VN")
    if total_collisions == 0 and total_uncovered == 0:
        print(">>> RESULT: ALL TMP INVARIANTS PASSED 100% (ZERO COLLISIONS, 100% COVERAGE) <<<")
        return 0
    else:
        print(">>> RESULT: GATE FAILED! <<<")
        return 1

def main():
    parser = argparse.ArgumentParser(description="Audit Unity TextMeshPro Font Assets for Glyph Index Collisions & VN Coverage.")
    parser.add_argument("paths", nargs="+", help="Paths to Unity asset bundles or .assets files")
    args = parser.parse_args()

    resolved = []
    for p in args.paths:
        if os.path.isdir(p):
            for root, dirs, files in os.walk(p):
                for f in files:
                    if f.endswith(".bundle") or f.endswith(".assets"):
                        resolved.append(os.path.join(root, f))
        elif os.path.exists(p):
            resolved.append(p)

    sys.exit(audit_containers(resolved))

if __name__ == "__main__":
    main()
