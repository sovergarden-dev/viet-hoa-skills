#!/usr/bin/env python3
"""Read-only TMP atlas pixel/padding audit for exported JSON + PNG."""
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
try:
 from PIL import Image
except ImportError: Image=None

def main(argv=None):
 ap=argparse.ArgumentParser(description='Audit TMP atlas pixels and padding'); ap.add_argument('asset',type=Path); ap.add_argument('--atlas-dir',type=Path,required=True); ap.add_argument('--padding',type=int,default=1); a=ap.parse_args(argv)
 if Image is None: print(json.dumps({'valid':False,'error':'Pillow_required'})); return 2
 try:d=json.loads(a.asset.read_text(encoding='utf-8'))
 except Exception as e: print(json.dumps({'valid':False,'error':f'json_error:{type(e).__name__}'})); return 2
 pages=d.get('atlasTextures') or d.get('atlas') or []; chars=d.get('characterTable') or d.get('characters') or []; sizes=d.get('atlasSizes') or d.get('atlasSize') or []
 if isinstance(sizes,dict): sizes=[sizes]
 bad=[]; checked=0; clipped=0; padding_fail=0
 images=[]
 for i,name in enumerate(pages):
  p=a.atlas_dir/Path(str(name)).name
  try: im=Image.open(p).convert('RGBA'); images.append(im)
  except Exception: images.append(None); bad.append(f'atlas_{i}_unreadable')
 for i,row in enumerate(chars):
  if not isinstance(row,dict): bad.append(f'char_{i}_not_object'); continue
  r=row.get('glyphRect') or row.get('rect'); page=int(row.get('atlasIndex',row.get('atlas_page',0)))
  if not isinstance(r,dict) or page<0 or page>=len(images): bad.append(f'char_{i}_missing_rect_or_page'); continue
  try:x,y,w,h=[int(r[k]) for k in ('x','y','width','height')]
  except (KeyError,TypeError,ValueError): bad.append(f'char_{i}_bad_rect'); continue
  im=images[page]
  if im is None or min(w,h)<=0: continue
  if x<0 or y<0 or x+w>im.width or y+h>im.height: bad.append(f'char_{i}_out_of_bounds'); continue
  checked+=1; pix=im.load()
  def ink(xx,yy): return pix[xx,yy][3]>0
  edge=any(ink(xx,yy) for xx in range(x,x+w) for yy in range(y,y+h) if xx in (x,x+w-1) or yy in (y,y+h-1))
  if edge: clipped+=1
  p=a.padding
  if x<p or y<p or x+w+p>im.width or y+h+p>im.height: padding_fail+=1
 result={'schema':'fonttv/tmpro-atlas-pixels-audit/v1','valid':not bad,'character_count':len(chars),'atlas_count':len(pages),'rects_checked':checked,'edge_ink_rects':clipped,'padding_failures':padding_fail,'invalid':bad,'padding_requested':a.padding,'pixel_geometry_ok':not bad and clipped==0 and padding_fail==0,'warning':'alpha edge ink is heuristic; transparent glyphs and SDF ink require visual/runtime review'}
 print(json.dumps(result,ensure_ascii=False,indent=2)); return 0 if result['pixel_geometry_ok'] else 1
if __name__=='__main__':sys.exit(main())