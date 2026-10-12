"""Read-only CSV handoff validation/generation. Paths are workspace-relative."""
import argparse
import csv
import hashlib
import io
import json
from pathlib import Path, PureWindowsPath

SCHEMA = 'viethoa/canonical-editor-handoff/v1'

def require(ok, message):
    if not ok:
        raise ValueError(message)

def pairs(items):
    result = {}
    for k, v in items:
        require(k not in result, 'duplicate JSON field')
        result[k] = v
    return result

def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'), object_pairs_hook=pairs)

def text(value):
    return isinstance(value, str) and bool(value.strip())

def snapshot(workspace, item, ident):
    raw = item['path']
    require(text(raw), 'empty path')
    rel = Path(raw)
    require(not rel.is_absolute() and not PureWindowsPath(raw).drive and '..' not in raw.replace('\\', '/').split('/'), 'unsafe path')
    path = (workspace / rel).resolve()
    require(path.is_relative_to(workspace.resolve()) and path.is_file(), 'file missing or outside workspace')
    data = path.read_bytes()
    reader = csv.reader(io.StringIO(data.decode('utf-8-sig'), newline=''), strict=True)
    header = next(reader, [])
    require(header and all(text(x) for x in header) and len(set(header)) == len(header), 'invalid CSV header')
    columns = [v for k,v in ident.items() if k.endswith('_column')]
    require(all(c in header for c in columns), 'missing mapped column')
    keys = set()
    editor_keys = set()
    for values in reader:
        require(len(values) == len(header), 'ragged CSV row')
        row = dict(zip(header, values))
        key = row[ident['key_column']]
        domain = row[ident['domain_column']] if 'domain_column' in ident else item['domain']
        require(text(key) and text(domain), 'empty identity')
        require((domain,key) not in keys, 'duplicate full key')
        # ponytail: WPF indexes one keyColumn; refuse cross-domain collisions until composite identity is supported.
        require(key not in editor_keys, 'editor key collision across domains')
        keys.add((domain,key)); editor_keys.add(key)
    require(keys, 'empty corpus')
    digest = hashlib.sha256(json.dumps(sorted(keys), ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()
    return {'sha256': hashlib.sha256(data).hexdigest(), 'row_count': len(keys), 'key_set_sha256': digest}

def validate(path, workspace, generate=False):
    data = load(path)
    require(isinstance(data,dict) and set(data)=={'schema','project_id','canonical_identity','files'}, 'invalid envelope')
    require(data['schema']==SCHEMA and text(data['project_id']), 'invalid schema/project')
    ident = data['canonical_identity']
    needed = {'key_column','source_column','target_column','state_column','stable_key_scope'}
    require(isinstance(ident,dict) and needed <= set(ident) and set(ident)<=needed|{'domain_column','protected_tokens_column'}, 'invalid mapping fields')
    require(ident['stable_key_scope']=='(domain,key)', 'invalid scope')
    columns = [v for k,v in ident.items() if k.endswith('_column')]
    require(all(text(v) for v in columns) and len(set(columns))==len(columns), 'invalid or overlapping columns')
    require(isinstance(data['files'],list) and data['files'], 'empty files')
    ids=set(); paths=set()
    for item in data['files']:
        required={'id','path','domain','sha256','row_count','key_set_sha256'}
        require(isinstance(item,dict) and set(item)==required, 'invalid file fields')
        require(all(text(item[k]) for k in ['id','path','domain']), 'invalid file identity')
        require(item['id'].casefold() not in ids, 'duplicate file id'); ids.add(item['id'].casefold())
        resolved=str((Path(workspace)/item['path']).resolve()).casefold()
        require(resolved not in paths, 'duplicate file path'); paths.add(resolved)
        actual=snapshot(Path(workspace),item,ident)
        if generate:
            item.update(actual)
        else:
            require(type(item['row_count']) is int, 'row_count must be integer')
            require(all(item[k]==v for k,v in actual.items()), 'stale hash/count/key set')
    return data

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest'); parser.add_argument('--workspace',required=True)
    args=parser.parse_args()
    try:
        data=validate(args.manifest,args.workspace)
        print(json.dumps({'valid':True,'file_count':len(data['files'])}))
    except (ValueError,OSError,UnicodeError,csv.Error,TypeError,KeyError) as exc:
        print(json.dumps({'valid':False,'error':str(exc)})); raise SystemExit(1)
