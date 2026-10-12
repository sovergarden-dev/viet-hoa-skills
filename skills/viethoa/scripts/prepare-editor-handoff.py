"""Generate, validate, publish one editor handoff; same flags as generator."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from validate_canonical_editor_handoff import validate


def main():
    parser = argparse.ArgumentParser(description=__doc__, add_help=False)
    parser.add_argument('--output', required=True)
    parser.add_argument('--workspace', required=True)
    args, remaining = parser.parse_known_args()
    output = Path(args.output).resolve()
    workspace = Path(args.workspace).resolve()
    if not output.is_relative_to(workspace) or not output.parent.is_dir():
        raise ValueError('Output parent must exist inside workspace')
    if output.exists():
        raise FileExistsError('Output already exists; use a new filename')
    with tempfile.TemporaryDirectory(prefix='.editor-handoff-', dir=output.parent) as td:
        staged = Path(td) / 'handoff.json'
        result = subprocess.run([sys.executable, str(Path(__file__).with_name('generate_canonical_editor_handoff.py')),
                                 '--workspace', str(workspace), '--output', str(staged), *remaining],
                                capture_output=True, text=True)
        if result.returncode:
            raise ValueError('Generator refused input: ' + result.stderr.strip())
        data = validate(staged, workspace)
        digest = hashlib.sha256(staged.read_bytes()).hexdigest()
        # Atomic no-clobber publication on the same filesystem; no unsafe copy fallback.
        os.link(staged, output)
        print(json.dumps({'prepared': True, 'schema': data['schema'], 'files': len(data['files']),
                          'handoff_sha256': digest, 'output': str(output)}))


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print(json.dumps({'prepared': False, 'error': str(exc)}))
        raise SystemExit(1)
