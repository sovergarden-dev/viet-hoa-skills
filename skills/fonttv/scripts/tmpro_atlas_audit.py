#!/usr/bin/env python3
"""Read-only geometry audit for exported Unity TMP FontAsset JSON."""
from __future__ import annotations
import argparse,json,sys
from pathlib import Path

def main(argv=None):
 ap=argparse.ArgumentParser(description='Audit TMP atlas geometry'); ap.add_argument('asset',type=Path); ap.add_argument('--output',type=Path); a=ap.parse_args(argv)
 if not a.asset.is_file(): print(json.dumps({'valid':False,'error':'input_not_found'})); return 2
 try:d=json.loads(a.asset.read_text(encoding='utf-8'))
 except Exception as e: print(json.dumps({'valid':False,'error':f'json_error:{type(e).__name__}'})); return 2
 pages=d.get('atlasTextures') or d.get('atlas'); sizes=d.get('atlasSizes') or d.get('atlasSize')
 chars=d.get('characterTable') or d.get('characters')
 if not isinstance(pages,list) or not isinstance(chars,list): print(json.dumps({'valid':False,'error':'missing_characterTable_or_atlasTextures'})); return 1
 if isinstance(sizes,dict): sizes=[sizes]
 if not isinstance(sizes,list): sizes=[]
 bad=[]; rects=[]
 for i,row in enumerate(chars):
  if not isinstance(row,dict): bad.append(f'char_{i}_not_object'); continue
  r=row.get('glyphRect') or row.get('rect')
  page=row.get('atlasIndex',row.get('atlas_page',0))
  if not isinstance(r,dict): bad.append(f'char_{i}_missing_rect'); continue
  try:
   x,y,w,h=(int(r[k]) for k in ('x','y','width','height')); page=int(page)
   if w<=0 or h<=0 or page<0 or page>=len(pages): bad.append(f'char_{i}_invalid_rect_or_page')
   if page<len(sizes):
    s=sizes[page]; W=int(s.get('width',s.get('w',0))); H=int(s.get('height',s.get('h',0)))
    if W and H and (x<0 or y<0 or x+w>W or y+h>H): bad.append(f'char_{i}_out_of_bounds')
   rects.append((page,x,y,w,h,i))
  except (TypeError,ValueError,KeyError): bad.append(f'char_{i}_bad_geometry')
 overlap=0
 for n,a1 in enumerate(rects):
  for b1 in rects[n+1:]:
   if a1[0]!=b1[0]: continue
   _,x,y,w,h,_=a1; _,X,Y,W,H,_=b1
   if max(x,X)<min(x+w,X+W) and max(y,Y)<min(y+h,Y+H): overlap+=1
 result={'schema':'fonttv/tmpro-atlas-audit/v1','valid':not bad,'asset':str(a.asset),'atlas_page_count':len(pages),'character_count':len(chars),'rect_count':len(rects),'invalid_geometry':bad,'overlap_pairs':overlap,'bounds_ok':not any('out_of_bounds' in x for x in bad),'geometry_ok':not bad and overlap==0,'proof_level':'structurally_verified' if not bad and overlap==0 else 'inventory_only'}
 out=json.dumps(result,ensure_ascii=False,indent=2)
 if a.output:a.output.write_text(out+'\n',encoding='utf-8')
 print(out); return 0 if result['geometry_ok'] else 1
if __name__=='__main__':sys.exit(main())
