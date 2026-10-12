# Unity TextAsset HTML dialogue route

## Recognition

Some Unity narrative games store full scripts as `TextAsset` HTML in `resources.assets`. Typical rows are:

```html
<li class="character">Mick</li>
<li class="id">(Mick2-BCDXX)</li>
<li class="dialogue">Hey, sorry about, y'know...</li>
```

The `id` plus neighboring `character`/`dialogue` rows provide stable translation context. Extract structurally with an HTML parser, not a raw-string scan.

## Safe asset probe

1. Inventory every `TextAsset` with UnityPy and write decoded copies to a workspace.
2. Identify the runtime source candidate by name and content; script dumps can include alternate/legacy/full variants. Do not translate every duplicate dump.
3. Parse `li`/`p` content and retain `path_id`, asset name, sequential row key, CSS class, source text, and adjacent speaker/ID context.
4. Keep original `resources.assets` untouched. Copy it to the workspace for serialization proof.

## UnityPy save pitfall and proof

`env.file.save()` returns serialized bytes. Passing an output pathname to it may not write that file. Save explicitly:

```python
asset_copy.write_bytes(env.file.save())
```

Then reload the generated file with UnityPy and assert the altered `TextAsset` field is present. Also compare output size against the original; a plausible full-size file plus reload assertion is the minimum structural proof before translation/import.

A field mutation pattern:

```python
data = obj.read()
data.m_Script = updated_html
data.save()
asset_copy.write_bytes(env.file.save())
```

This proves serialization, not game runtime loading. Install only a separately generated copy/patch for the subsequent smoke test.
