# Unity Addressables `ru`-slot Vietnamese build: serialized StringTables

## Proven extraction/build pattern

A Unity Localization Addressables build may have 45 English tables and a technically selected `ru` locale with different table names. Treat the `ru` runtime tables as authoritative for patching—not the English table names.

### Target-table aliases observed

Use stable entry IDs, but map source names to actual target `ru` table names when inspection proves the relationship:

```python
aliases = {
    "EquipmentName": "EquipmentShared",
    "SettingsMenu": "SettingsPage",
    "StartMenu": "Menu",
}
target_table = aliases.get(source_table, source_table)
```

Then perform a second extraction from all `ru` tables to find target-only rows. In this case the target-only rows were `Menu`, `SettingsPage`, and `EquipmentShared`. Those rows supersede overlapping English-derived translations because the target table is what loads at runtime.

Release criterion: every player-visible row in selected `ru` tables is Vietnamese. Do not count only English-table rows.

## Safe UnityPy write behavior

Most serialized `MonoBehaviour` StringTables can be saved with:

```python
data.set_object_reader(obj)
data.save()
obj.assets_file.mark_changed()
```

Two table types can contain managed-reference metadata which UnityPy's generated wrapper cannot serialize (`TypeError: 'UnknownObject' object is not subscriptable`). Do not abandon the build or raw-patch bytes. Use a targeted typetree fallback for the affected object:

```python
tree = obj.read_typetree()
for entry in tree["m_TableData"]:
    if (table, str(entry["m_Id"])) in translations:
        entry["m_Localized"] = translations[(table, str(entry["m_Id"]))]
obj.save_typetree(tree)
obj.assets_file.mark_changed()
```

Use this only for the affected table(s); preserve all other typetree fields and managed-reference metadata untouched.

## QA requirements

1. Verify each output CSV has reviewed status and non-empty Vietnamese.
2. Compare token multisets exactly: placeholders (`{0}`), rich-text tags (`[b]`, `[/b]`), and literal serialized newlines (`\\n`).
3. Preserve source storage semantics: if the source stores a literal `\\n`, normalize any physical newline in translation back to literal `\\n` before import.
4. Reject Cyrillic text in final `vietnamese` cells.
5. Write bundle only to workspace patch folder, reload with UnityPy, and compare every target `(table, entry ID)` value exactly.
6. Record source/patch hashes and sizes. A rewritten Unity bundle may grow substantially; structural reload plus launch smoke test is required before treating it as valid.
7. Use a reversible installer: SHA-256 guard against expected source build, backup as `.vi-original`, then replace one locale bundle only; uninstaller restores and validates the original hash.
8. Do not package an installer whose payload and live target share the same extracted relative path. Use a dedicated `payload/` directory for installer input, or ship a manual copy-over package; run install/uninstall in a disposable sandbox before release.

## Visual caveat

A headless Unity launch (`-batchmode -nographics -quit`) can prove startup compatibility, but cannot prove locale selection, Vietnamese glyph coverage, wrapping, clipping, or image-based language labels. Keep the package marked test-only until graphical screenshots cover language selection, menus, tooltips, and long descriptions.
