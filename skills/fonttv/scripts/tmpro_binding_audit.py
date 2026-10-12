#!/usr/bin/env python3
"""Read-only audit for exported TMP FontAsset/material binding JSON."""
from __future__ import annotations
import argparse,json,sys
from pathlib import Path

def main(argv=None):
 ap=argparse.ArgumentParser(description='Audit TMP atlas/material/shader binding'); ap.add_argument('asset',type=Path); ap.add_argument('--output',type=Path); a=ap.parse_args(argv)
 if not a.asset.is_file(): print(json.dumps({'valid':False,'error':'input_not_found'})); return 2
 try:d=json.loads(a.asset.read_text(encoding='utf-8'))
 except Exception as e: print(json.dumps({'valid':False,'error':f'json_error:{type(e).__name__}'})); return 2
 pages=d.get('atlasTextures') or d.get('atlas')
 mats=d.get('materials') or d.get('materialTable')
 bindings=d.get('materialBindings') or d.get('bindings')
 if not isinstance(pages,list) or not isinstance(mats,list) or not isinstance(bindings,list):
  print(json.dumps({'valid':False,'error':'requires_atlasTextures_materials_materialBindings'})); return 1
 bad=[]; seen=set()
 for i,b in enumerate(bindings):
  if not isinstance(b,dict): bad.append(f'binding_{i}_not_object'); continue
  try: page=int(b.get('atlasIndex',b.get('atlas_page',-1))); mi=int(b.get('materialIndex',b.get('material',-1)))
  except (TypeError,ValueError): bad.append(f'binding_{i}_bad_index'); continue
  if page<0 or page>=len(pages): bad.append(f'binding_{i}_atlas_out_of_range')
  if mi<0 or mi>=len(mats): bad.append(f'binding_{i}_material_out_of_range')
  shader=b.get('shader')
  if not isinstance(shader,str) or not shader.strip(): bad.append(f'binding_{i}_missing_shader')
  tex=b.get('texture') or b.get('mainTexture')
  if not isinstance(tex,str) or not tex.strip(): bad.append(f'binding_{i}_missing_texture')
  seen.add(page)
 unused=sorted(set(range(len(pages)))-seen)
 result={'schema':'fonttv/tmpro-binding-audit/v1','valid':not bad,'atlas_count':len(pages),'material_count':len(mats),'binding_count':len(bindings),'bound_atlas_pages':sorted(seen),'unused_atlas_pages':unused,'invalid':bad,'binding_ok':not bad and not unused,'proof_level':'structurally_verified' if not bad and not unused else 'inventory_only','warning':'JSON binding proof does not prove Unity serialized material or runtime shader identity'}
 out=json.dumps(result,ensure_ascii=False,indent=2)
 if a.output:a.output.write_text(out+'\n',encoding='utf-8')
 print(out); return 0 if result['binding_ok'] else 1
if __name__=='__main__':sys.exit(main())