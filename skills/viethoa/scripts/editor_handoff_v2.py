"""Read-only v2 contract prototype. Not connected to production installer."""
from __future__ import annotations
import csv
from copy import deepcopy
import hashlib
import io
from pathlib import Path
import json

SCHEMA='viethoa/canonical-editor-handoff/v2'
FIELDS={'key_column','source_column','target_column','state_column'}

def digest(value):
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,separators=(',',':')).encode('utf-8')).hexdigest()

def build(workspace, project_id, tables, *, references=None):
    root=Path(workspace).resolve(strict=True)
    if not isinstance(project_id,str) or not project_id.strip() or not isinstance(tables,list) or not tables:
        raise ValueError('project_id and nonempty tables required')
    ids=set(); paths=set(); files=[]; aggregate=[]
    for table in tables:
        if not isinstance(table, dict):
            raise ValueError('each table must be an object')
        tid=table.get('translation_id'); domain=table.get('domain'); rel=table.get('path')
        if not all(isinstance(x,str) and x.strip() for x in (tid,domain,rel)):
            raise ValueError('table identity/path required')
        if tid.casefold() in ids:
            raise ValueError('duplicate translation_id')
        candidate=Path(rel)
        if candidate.is_absolute() or '..' in candidate.parts:
            raise ValueError('relative contained path required')
        path=(root/candidate).resolve()
        if not path.is_relative_to(root):
            raise ValueError('path escapes workspace')
        identity=str(path).casefold()
        if identity in paths:
            raise ValueError('duplicate canonical path')
        ids.add(tid.casefold()); paths.add(identity)
        mapping=table.get('mapping')
        optional = {'notes_column', 'speaker_column', 'group_column', 'protected_tokens_column'}
        if not isinstance(mapping, dict) or not FIELDS <= set(mapping) or set(mapping) - FIELDS - optional - {'reference_columns'}:
            raise ValueError('explicit mapping columns required; unknown mapping field')
        columns = [v for k, v in mapping.items() if k != 'reference_columns']
        reference_columns = mapping.get('reference_columns', [])
        if not isinstance(reference_columns, list):
            raise ValueError('reference_columns must be a list')
        columns += reference_columns
        if not all(isinstance(v, str) and v.strip() for v in columns) or len(set(columns)) != len(columns):
            raise ValueError('mapping columns must be nonempty and distinct')
        raw=path.read_bytes()
        reader=csv.DictReader(io.StringIO(raw.decode('utf-8-sig'),newline=''))
        headers=reader.fieldnames or []
        if len(set(headers))!=len(headers) or not set(columns)<=set(headers):
            raise ValueError('duplicate or missing header')
        keys=set()
        for row in reader:
            if None in row or any(v is None for v in row.values()):
                raise ValueError('malformed CSV row')
            state = row[mapping['state_column']]
            if state not in {'pending', 'translated', 'reviewed', 'needs_context', 'rejected'}:
                raise ValueError('unknown canonical state; normalize via project policy first')
            source = row[mapping['source_column']]
            target = row[mapping['target_column']]
            whitespace_identity = bool(source) and source.isspace() and target == source
            if state in {'translated', 'reviewed'} and not target.strip() and not whitespace_identity:
                raise ValueError('accepted state requires target or exact nonempty whitespace identity')
            key=row[mapping['key_column']]
            if not key.strip() or key in keys:
                raise ValueError('blank or duplicate key within table')
            keys.add(key)
        if not keys:
            raise ValueError('canonical table must contain at least one row')
        pairs=sorted((domain,k) for k in keys)
        aggregate.extend((tid,domain,k) for k in keys)
        entry = dict(translation_id=tid,path=rel,domain=domain,mapping=deepcopy(mapping),sha256=hashlib.sha256(raw).hexdigest(),row_count=len(keys),key_set_sha256=digest(pairs))
        if 'editor_policy' in table:
            policy = table['editor_policy']
            if not isinstance(policy, dict) or set(policy) != {'token_pattern'} or not isinstance(policy['token_pattern'], str) or not policy['token_pattern'].strip():
                raise ValueError('editor_policy requires explicit nonempty token_pattern')
            entry['editor_policy'] = dict(policy)
        files.append(entry)
    result = dict(schema=SCHEMA,project_id=project_id,editor_identity=dict(identity_columns=['translation_id','domain','key'],stable_key_scope='(translation_id,domain,key)'),files=files,aggregate_key_set_sha256=digest(sorted(aggregate)))
    if references is not None:
        if not isinstance(references, list):
            raise ValueError('references must be a list')
        result['references'] = []
        reference_ids = set()
        for reference in references:
            if not isinstance(reference, dict):
                raise ValueError('reference must be an object')
            fields = ('id', 'label', 'path', 'key_column')
            if not all(isinstance(reference.get(k), str) and reference[k].strip() for k in fields):
                raise ValueError('reference id/label/path/key_column required')
            rid = reference['id'].casefold()
            rel = Path(reference['path'])
            if rid in reference_ids or rel.is_absolute() or '..' in rel.parts:
                raise ValueError('duplicate reference id or invalid path')
            path = (root / rel).resolve()
            identity = str(path).casefold()
            if not path.is_relative_to(root) or identity in paths:
                raise ValueError('reference path escapes workspace or aliases another CSV')
            reference_ids.add(rid); paths.add(identity)
            raw = path.read_bytes()
            reader = csv.DictReader(io.StringIO(raw.decode('utf-8-sig'), newline=''), strict=True)
            headers = reader.fieldnames or []
            if not headers or len(set(headers)) != len(headers) or any(not h.strip() for h in headers) or reference['key_column'] not in headers:
                raise ValueError('invalid reference headers')
            count = 0
            for row in reader:
                if None in row or any(v is None for v in row.values()):
                    raise ValueError('malformed reference row')
                count += 1
            result['references'].append(dict((k, reference[k]) for k in fields) | dict(sha256=hashlib.sha256(raw).hexdigest(), row_count=count))
    return result

def validate(workspace, manifest):
    if not isinstance(manifest,dict) or manifest.get('schema')!=SCHEMA:
        raise ValueError('unsupported manifest')
    rebuilt=build(workspace,manifest.get('project_id'),manifest.get('files'), references=manifest.get('references'))
    if rebuilt!=manifest:
        raise ValueError('stale or inconsistent handoff')
    return rebuilt


def editor_config(workspace, manifest, *, token_patterns=None):
    """Return a config candidate only; never install or mutate project files.

    Token/profile/reference configuration still requires the integration layer.
    Do not publish this candidate as an accepted production project.json.
    """
    import os
    checked = validate(workspace, manifest)
    bound = {item['translation_id']: item['editor_policy']['token_pattern']
             for item in checked['files'] if 'editor_policy' in item}
    if token_patterns is None and len(bound) == len(checked['files']):
        token_patterns = bound
    expected_ids = {item['translation_id'] for item in checked['files']}
    if not isinstance(token_patterns, dict) or set(token_patterns) != expected_ids:
        raise ValueError('explicit token pattern required for every exact translation_id')
    if any(token_patterns[key] != value for key, value in bound.items()):
        raise ValueError('token pattern conflicts with handoff policy')
    if any(not isinstance(pattern, str) or not pattern.strip() for pattern in token_patterns.values()):
        raise ValueError('token patterns must be nonempty strings; no implicit regex default')
    root = Path(workspace).resolve()
    tables = []
    for item in checked['files']:
        mapping = item['mapping']
        tables.append(dict(
            id=item['translation_id'], label=item['translation_id'],
            path=os.path.relpath(root / item['path'], root / 'bientaptay').replace('\\', '/'),
            keyColumn=mapping['key_column'],
            sourceFields=[dict(column=c, label=c) for c in [mapping['source_column']] + mapping.get('reference_columns', [])],
            notesColumn=mapping.get('notes_column'), speakerColumn=mapping.get('speaker_column'),
            groupColumn=mapping.get('group_column'), protectedTokensColumn=mapping.get('protected_tokens_column'),
            targetColumn=mapping['target_column'], statusColumn=mapping['state_column'],
            tokenPattern=token_patterns[item['translation_id']]))
    first = tables[0]
    return dict(schemaVersion=1, projectName=checked['project_id'],
                handoffSchema=SCHEMA, canonicalPath=first['path'],
                keyColumn=first['keyColumn'], sourceFields=first['sourceFields'],
                targetColumn=first['targetColumn'], statusColumn=first['statusColumn'],
                statuses=['pending', 'translated', 'reviewed', 'needs_context', 'rejected'],
                references=[dict(id=r['id'], label=r['label'], keyColumn=r['key_column'],
                                 path=os.path.relpath(root / r['path'], root / 'bientaptay').replace('\\', '/'))
                            for r in checked.get('references', [])],
                translationFiles=tables)


def main(argv=None):
    import argparse
    import os
    import tempfile
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['build', 'validate'])
    parser.add_argument('--workspace', required=True, type=Path)
    parser.add_argument('--plan', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--manifest', type=Path)
    args = parser.parse_args(argv)
    temporary = None
    try:
        root = args.workspace.resolve(strict=True)
        if args.action == 'validate':
            if args.manifest is None:
                raise ValueError('--manifest required')
            result = validate(root, json.loads(args.manifest.read_text(encoding='utf-8')))
        else:
            if args.plan is None or args.output is None:
                raise ValueError('--plan and --output required')
            plan = json.loads(args.plan.read_text(encoding='utf-8'))
            if not isinstance(plan, dict):
                raise ValueError('plan must be an object')
            result = build(root, plan.get('project_id'), plan.get('tables'), references=plan.get('references'))
            output = args.output.resolve()
            if not output.is_relative_to(root) or not output.parent.is_dir():
                raise ValueError('output parent must exist within workspace')
            if output.exists():
                raise ValueError('output already exists; no overwrite allowed')
            fd, temporary = tempfile.mkstemp(prefix='.handoff-', suffix='.json', dir=output.parent)
            with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as stream:
                json.dump(result, stream, ensure_ascii=False, indent=2)
                stream.write('\n')
                stream.flush()
                os.fsync(stream.fileno())
            validate(root, result)
            os.link(temporary, output)
            published = json.loads(output.read_text(encoding='utf-8'))
            if published != result:
                raise ValueError('published handoff readback mismatch')
        print(json.dumps({'result': 'verified', 'schema': SCHEMA, 'tables': len(result['files']), 'production_installer_supported': False}))
        return 0
    except (OSError, ValueError, TypeError, KeyError, csv.Error) as exc:
        print(json.dumps({'result': 'error', 'error': str(exc)}))
        return 2
    finally:
        if temporary is not None:
            Path(temporary).unlink(missing_ok=True)


if __name__ == '__main__':
    raise SystemExit(main())
