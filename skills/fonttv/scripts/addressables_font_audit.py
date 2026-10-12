#!/usr/bin/env python3
"""Read-only audit for exported Unity Addressables font dependency JSON."""
from __future__ import annotations
import argparse,json,sys
from pathlib import Path

def main(argv=None):
 ap=argparse.ArgumentParser(description='Audit Addressables font dependency graph'); ap.add_argument('manifest',type=Path); a=ap.parse_args(argv)
 if not a.manifest.is_file(): print(json.dumps({'valid':False,'error':'input_not_found'})); return 2
 try:d=json.loads(a.manifest.read_text(encoding='utf-8'))
 except Exception as e: print(json.dumps({'valid':False,'error':f'json_error:{type(e).__name__}'})); return 2
 nodes=d.get('nodes'); edges=d.get('edges');
 if not isinstance(nodes,list) or not isinstance(edges,list): print(json.dumps({'valid':False,'error':'requires_nodes_edges'})); return 1
 ids={n.get('id') for n in nodes if isinstance(n,dict)}; bad=[]; incoming={i:0 for i in ids}; outgoing={i:0 for i in ids}
 for i,e in enumerate(edges):
  if not isinstance(e,dict): bad.append(f'edge_{i}_not_object'); continue
  s,t=e.get('from'),e.get('to')
  if s not in ids: bad.append(f'edge_{i}_missing_from')
  else: outgoing[s]+=1
  if t not in ids: bad.append(f'edge_{i}_missing_to')
  else: incoming[t]+=1
 roots=[n.get('id') for n in nodes if isinstance(n,dict) and n.get('type')=='FontAsset']
 missing_root=[x for x in roots if outgoing.get(x,0)==0]
 orphan=[x for x in ids if incoming.get(x,0)==0 and x not in roots]
 result={'schema':'fonttv/addressables-font-audit/v1','valid':not bad,'node_count':len(nodes),'edge_count':len(edges),'fontasset_roots':roots,'fontassets_without_dependencies':missing_root,'orphan_nodes':orphan,'invalid_edges':bad,'graph_ok':not bad and not missing_root,'proof_level':'structurally_verified' if not bad and not missing_root else 'inventory_only','warning':'export graph proof does not prove Addressables catalog/runtime load identity'}
 print(json.dumps(result,ensure_ascii=False,indent=2)); return 0 if result['graph_ok'] else 1
if __name__=='__main__':sys.exit(main())