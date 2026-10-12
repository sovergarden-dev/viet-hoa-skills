"""Read-only diagnostic; fingerprints describe installation baseline, not save authorization."""
import argparse
import hashlib
import json
from pathlib import Path
from validate_canonical_editor_handoff import load, validate


def status(project, handoff, workspace):
    project, handoff, workspace = Path(project).resolve(), Path(handoff).resolve(), Path(workspace).resolve()
    if not project.is_relative_to(workspace) or not handoff.is_relative_to(workspace):
        return 'path_mismatch'
    config, manifest = load(project), load(handoff)
    if not isinstance(config, dict) or not isinstance(manifest, dict):
        return 'invalid_input'
    if len(manifest.get('files', [])) != 1 or config.get('translationFiles'):
        return 'unsupported_multitable'
    if config.get('handoffSchema') != manifest.get('schema') or config.get('handoffSha256') != hashlib.sha256(handoff.read_bytes()).hexdigest():
        return 'stale_handoff'
    item, mapping = manifest['files'][0], manifest['canonical_identity']
    actual = (project.parent / config['canonicalPath']).resolve()
    expected = (workspace / item['path']).resolve()
    if actual != expected or not actual.is_relative_to(workspace):
        return 'path_mismatch'
    fields = {'keyColumn':'key_column', 'targetColumn':'target_column', 'statusColumn':'state_column', 'protectedTokensColumn':'protected_tokens_column'}
    if any(config.get(k) != mapping.get(v) for k,v in fields.items()):
        return 'mapping_mismatch'
    sources = config.get('sourceFields')
    if not isinstance(sources,list) or not sources or sources[0].get('column') != mapping['source_column']:
        return 'mapping_mismatch'
    if not actual.is_file() or hashlib.sha256(actual.read_bytes()).hexdigest() != item['sha256']:
        return 'stale_canonical'
    if config.get('canonicalSha256') != item['sha256'] or config.get('keySetSha256') != item['key_set_sha256']:
        return 'stale_handoff'
    validate(handoff, workspace)
    return 'verified'


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--project',required=True);p.add_argument('--handoff',required=True);p.add_argument('--workspace',required=True)
    a=p.parse_args()
    try:
        result=status(a.project,a.handoff,a.workspace)
    except (ValueError,OSError,KeyError,TypeError,AttributeError):
        result='invalid_input'
    print(json.dumps({'status':result,'read_only':True}))
    raise SystemExit(0 if result=='verified' else 1)
