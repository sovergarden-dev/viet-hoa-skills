# Editor v2 integration — experimental boundary

## Verified implementation

`scripts/editor_handoff_v2.py` builds and validates v2 manifests from explicit per-table mapping and canonical CSV bytes. CLI build publishes no-clobber through a sibling temporary file and hardlink. It does not install the editor. `editor_config` returns a candidate only and requires explicit token patterns for every table ID.

Run from skill directory:

```text
uv run --with jsonschema==4.25.1 python -B -m unittest discover -s scripts/tests -p "test_editor_v2*.py" -v
```

The cross-language test builds a copy of sibling bientaptay Core in a temporary directory. It checks different CSV schemas, identical keys in distinct tables, token rejection, scoped save/readback, unchanged other table, exact backup and stale-manifest rejection after save. This is not WPF or installer acceptance.

## Validation boundary

JSON Schema mapping requires exact core fields, typed optional columns and a unique reference-column list; test it with Draft202012Validator. Schema validation does not verify file contents, path containment, cross-role column collisions, hashes or key scope: always run the Python validator on the actual CSVs. Candidate config declares all accepted states explicitly, including rejected; do not rely on editor defaults. Keep nested input mapping independent of the manifest snapshot.

## Reference evidence

Optional manifest `references` binds each project-level reference CSV by explicit id/label/path/key_column, SHA-256 and row count. CLI build carries plan references; validate rebuilds them from disk and config generation refuses stale reference bytes. Reject duplicate reference IDs/paths, aliasing translation CSVs, escapes and malformed headers/rows. Empty reference CSVs with headers are allowed for fresh glossary/pronoun datasets. This is structural evidence, not glossary/pronoun semantic acceptance; keep their editor-specific validators. Reference source columns inside a translation table are distinct from these external CSV files. Pronoun evidence with a raw key shared by multiple canonical rows is ambiguous: Core rejects it rather than silently collapsing duplicates into a HashSet. Unique raw keys retain compatibility. This is a fail-closed guard, not a new table-qualified evidence format; do not claim qualified multi-table evidence support.

## Remaining production gates

1. Bind editor policy (token patterns, reference columns, notes/speaker/group/protected-token columns, glossary/pronoun references) to handoff evidence. Patterns being present or compiling does not establish semantic correctness; validate positive/negative samples with the actual .NET matcher.
2. Integrate v2 into existing installer, retaining v1 compatibility. Reject stale hashes, duplicate paths and mismatched table mapping before any write. Never reduce multi-table config to its first file.
3. Stage install/update without deleting current source/config first. Hold the shared writer lock; snapshot owned state; preserve reference CSVs and user configuration. Fault injection must prove byte-exact rollback, not only successful build.
4. Exercise fresh install and update on synthetic workspaces using the actual release pipeline. Recheck all canonical/reference hashes and exact receipt.
5. Run WPF smoke with two differently mapped tables, scoped editing and token failure. Only then document production v2 support.

## Do not overclaim

Installer remains v1. CLI result explicitly reports production_installer_supported=false. Core tests do not satisfy installer/GUI gates. No live project migration is authorized by skill maintenance. Do not ask for repeated permission for these already-authorized isolated implementation/test steps; request input only for genuine user choices.
