# Unity Addressables serialized StringTable extraction and safe target-slot patching

## Discovery pattern

Some Unity Localization games store each locale as one Addressables asset bundle containing serialized `MonoBehaviour` StringTables rather than CSV `TextAsset` files.

Inspect each bundle structurally with UnityPy:

- identify `MonoBehaviour` objects;
- read `m_Name`, `m_LocaleId.m_Code`, and `m_TableData`;
- key source rows as `table base name + m_Id`;
- use the English table as source where it exists, and retain other locales only as context.

Do not infer runtime platform from an Addressables directory label. A Windows install may load bundles below `StandaloneOSX`; prove loading through the catalog and bundle inventory.

## Completeness trap: target-only tables

A locale can contain tables absent in English. Do a second extraction from the target technical locale (`ru` in this case) and compare table names/entry IDs. Translate target-only rows separately; typical examples are menu, settings, and equipment-component tables.

Release criterion is not merely `all English rows translated`: it is `all player-visible rows in the selected runtime locale translated`.

## Slot approach

When no `vi` locale is registered, preserve `en` and use an existing Unicode locale slot such as `ru` only after proving:

1. the locale is selectable by the game;
2. its bundle contains all relevant StringTables;
3. its font/UI path can render Vietnamese;
4. every target-slot row is Vietnamese before release.

Do not ship mixed Vietnamese/Russian or English fallback in the technical target slot.

## UnityPy write verification

For a write proof:

1. Modify exactly one known target-locale entry in a workspace copy.
2. Call `data.set_object_reader(obj)`, `data.save()`, and mark the owning assets file changed.
3. Save to `patch_files/`, never the live game path.
4. Reload the emitted bundle with UnityPy and assert the exact changed entry value.
5. Record source/output sizes. UnityPy serialization can substantially increase bundle size even when reload succeeds; treat that as an artifact to verify with a real game launch, not proof of corruption or safety.

Do not distribute a patched bundle until structural reload and in-game startup/UI screenshots pass.
