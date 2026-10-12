# Unity IL2CPP: UnityPy full-object rewrite proof for opaque MonoBehaviour edits

## Problem

`Environment.save()` writes changed asset files, but an IL2CPP asset containing opaque `MonoBehaviour` objects can reload with the edited field while many untouched objects have empty raw payloads. A superficially successful one-field reload is therefore not enough.

## Safe copy-only proof

1. Copy the target `.assets` into workspace. Never use the live game file.
2. Load it with UnityPy and enumerate all objects.
3. Before editing, explicitly retain every object raw payload:

```python
objects = list(env.objects)
for obj in objects:
    obj.set_raw_data(bytes(obj.get_raw_data()))
```

4. Decode only the intended object with the recovered `TypeTreeNode`; edit one existing target-locale field; call `obj.save_typetree(tree, node)`.
5. `env.save(out_path=...)`, then reload the emitted file with a fresh environment.
6. Compare source/copy object inventory `(path_id, type, raw_size, sha256(raw))`.

Pass criteria:
- copy asset byte size matches source when stream layout requires it;
- object count matches;
- only expected edited `path_id` values differ;
- every edited field reloads exact expected text;
- copy companion `.resS` exists and matches source when present.

## Why this matters

In a Unity 2020 IL2CPP `resources.assets` test, a naive one-object save produced a 1.35 MB asset from a 46.55 MB source and left many `MonoBehaviour` payloads empty. The full-object raw-data retention route preserved 8,243 objects and changed only the intended DialogueDatabase object.

## Scope

This proves serializer structure, not runtime loading. Still perform an isolated game-copy smoke test before packaging. Use this pattern for opaque IL2CPP assets where UnityPy cannot safely preserve untouched data by default.
