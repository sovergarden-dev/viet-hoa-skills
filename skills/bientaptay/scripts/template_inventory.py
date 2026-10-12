"""Select template source files, excluding generated build/cache artifacts."""
from pathlib import Path

EXCLUDED = {'bin', 'obj', '__pycache__', '.git', '.venv'}

def template_files(root: Path):
    root = Path(root)
    return sorted(p for p in root.rglob('*')
                  if p.is_file()
                  and not any(part.lower() in EXCLUDED for part in p.relative_to(root).parts[:-1])
                  and p.suffix.lower() not in {'.pyc', '.pyo'})
