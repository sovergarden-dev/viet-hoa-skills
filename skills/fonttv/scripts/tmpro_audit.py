#!/usr/bin/env python3
"""Read-only audit for an exported Unity TMP FontAsset JSON."""
from __future__ import annotations
import argparse, hashlib, json, sys
from pathlib import Path

def main(argv=None):
    ap=argparse.ArgumentParser(description='Audit exported TMP FontAsset JSON')
    ap.add_argument('asset', type=Path)
    ap.add_argument('--corpus', type=Path, required=True)
    ap.add_argument('--output', type=Path)
    a=ap.parse_args(argv)
    if not a.asset.is_file() or not a.corpus.is_file():
        print(json.dumps({'valid':False,'error':'input_not_found'})); return 2
    try: d=json.loads(a.asset.read_text(encoding='utf-8'))
    except Exception as e:
        print(json.dumps({'valid':False,'error':f'json_error:{type(e).__name__}'})); return 2
    chars=d.get('characterTable') or d.get('characters')
    atlas=d.get('atlasTextures') or d.get('atlas')
    if not isinstance(chars,list) or not isinstance(atlas,list):
        print(json.dumps({'valid':False,'error':'missing_characterTable_or_atlasTextures'})); return 1
    present=set()
    bad=[]
    for row in chars:
        if not isinstance(row,dict): bad.append('non_object_character'); continue
        cp=row.get('unicode',row.get('codepoint'))
        try: present.add(int(cp))
        except Exception: bad.append('bad_unicode')
    corpus=a.corpus.read_text(encoding='utf-8')
    required={ord(c) for c in corpus if not c.isspace()}
    missing=sorted(required-present)
    result={'schema':'fonttv/tmpro-audit/v1','valid':not bad,'asset':str(a.asset),'sha256':hashlib.sha256(a.asset.read_bytes()).hexdigest(),'character_count':len(chars),'atlas_page_count':len(atlas),'required_codepoints':len(required),'missing_codepoints':[f'U+{x:04X}' for x in missing],'coverage_ok':not missing,'structural_ok':not bad and not missing,'proof_level':'structurally_verified' if not bad and not missing else 'inventory_only','warnings':['characterTable presence is record_present only; glyph identity, ink and runtime binding are NOT_RUN']}
    if not atlas: result['warnings'].append('atlasTextures_empty')
    if d.get('atlasPopulationMode') in ('Dynamic','dynamic'): result['warnings'].append('dynamic_population_requires_runtime_test')
    out=json.dumps(result,ensure_ascii=False,indent=2)
    if a.output: a.output.write_text(out+'\n',encoding='utf-8')
    print(out)
    return 0 if result['structural_ok'] else 1
if __name__=='__main__': sys.exit(main())
