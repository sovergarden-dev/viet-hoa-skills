# Unity IL2CPP DialogueDatabase: safe UnityPy write proof requires full object preservation

## Symptom

A one-entry `MonoBehaviour.save_typetree()` + `env.save()` can reload the edited dialogue field while emitting a dangerously small `.assets` file. In the observed Unity 2020 case, the source was 46.55 MB and the output 1.35 MB; many later `MonoBehaviour` objects reloaded as zero-byte payloads.

Do not treat target-field reload alone as an import proof.

## Safe copy-only proof

1. Copy the source asset into `_viet_work/patch/proof_*`; never edit the game install.
2. Load every object and cache `bytes(object.get_raw_data())` keyed by `path_id`.
3. Re-apply each raw object payload with `object.set_raw_data(...)` before serializing the intended `DialogueDatabase` change through the generated type tree.
4. Save the copy, reload it with a fresh `UnityPy` environment, and decode the edited field with the same generated base-class tree.
5. Inventory both source and copy as `(path_id, type, raw byte length, SHA-256(raw))`.
6. Pass only if object count matches, the target field equals the expected Vietnamese string, and exactly the intended `DialogueDatabase:path_id` differs. Do **not** require source and copy to have equal overall byte size: a UTF-8 Vietnamese replacement can legitimately shrink or grow the modified serialized object.

## Observed proof result

- Source/copy: 46,553,632 bytes each.
- Objects: 8,243 each.
- Exactly one changed object: `MonoBehaviour:path_id=6134`.
- Target `Russian` field reloads as `A lô?`.

## Boundary

This establishes a structural serializer route for the DialogueDatabase only. It is not an in-game smoke test, does not prove locale-label selection, and does not authorize release. Legacy I2 source parsing remains extraction-only until it receives an equivalent copy-only serialize/reload/inventory proof.
