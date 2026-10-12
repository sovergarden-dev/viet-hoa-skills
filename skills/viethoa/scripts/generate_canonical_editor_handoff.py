"""Generate canonical-editor-handoff/v1 from an explicit CSV mapping."""
from __future__ import annotations
import argparse, csv, hashlib, json, sys
from pathlib import Path

SCHEMA='viethoa/canonical-editor-handoff/v1'
def sha256(p):
 h=hashlib.sha256();
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''): h.update(b)
 return h.hexdigest()
def main():
 p=argparse.ArgumentParser()
 p.add_argument('--workspace',required=True);p.add_argument('--canonical',required=True);p.add_argument('--output',required=True)
 p.add_argument('--project-id',required=True);p.add_argument('--key-column',required=True);p.add_argument('--source-column',required=True)
 p.add_argument('--target-column',required=True);p.add_argument('--state-column',required=True);p.add_argument('--domain',required=True)
 p.add_argument('--domain-column');p.add_argument('--protected-tokens-column')
 a=p.parse_args(); w=Path(a.workspace).resolve(); c=(w/a.canonical).resolve()
 if not c.is_file() or not c.is_relative_to(w): raise SystemExit('canonical must be an existing file inside workspace')
 with c.open(encoding='utf-8-sig',newline='') as f:
  r=csv.DictReader(f); h=list(r.fieldnames or []); rows=list(r)
 cols=[a.key_column,a.source_column,a.target_column,a.state_column]+([a.domain_column] if a.domain_column else [])+([a.protected_tokens_column] if a.protected_tokens_column else [])
 if not h or any(x not in h for x in cols) or len(set(cols))!=len(cols): raise SystemExit('invalid or overlapping CSV columns')
 keys=[]; seen=set(); seen_keys=set()
 for row in rows:
  key=row[a.key_column]; domain=row[a.domain_column] if a.domain_column else a.domain
  if not key.strip() or not domain.strip() or (domain,key) in seen or key in seen_keys: raise SystemExit('empty or colliding canonical identity')
  seen.add((domain,key)); seen_keys.add(key); keys.append((domain,key))
 if not keys: raise SystemExit('canonical is empty')
 keyhash=hashlib.sha256(json.dumps(sorted(keys),ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
 ident={'key_column':a.key_column,'source_column':a.source_column,'target_column':a.target_column,'state_column':a.state_column,'stable_key_scope':'(domain,key)'}
 if a.domain_column: ident['domain_column']=a.domain_column
 if a.protected_tokens_column: ident['protected_tokens_column']=a.protected_tokens_column
 data={'schema':SCHEMA,'project_id':a.project_id,'canonical_identity':ident,'files':[{'id':'canonical','path':c.relative_to(w).as_posix(),'domain':a.domain,'sha256':sha256(c),'row_count':len(keys),'key_set_sha256':keyhash}]}
 out=Path(a.output); out.parent.mkdir(parents=True,exist_ok=True)
 with out.open('x',encoding='utf-8') as f: json.dump(data,f,ensure_ascii=False,indent=2);f.write('\n')
 print(json.dumps({'generated':True,'output':str(out),'row_count':len(keys)}))
if __name__=='__main__': main()
