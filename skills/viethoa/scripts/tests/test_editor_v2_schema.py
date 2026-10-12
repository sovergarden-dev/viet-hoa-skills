"""Run with uv run --with jsonschema==4.25.1 python -B -m unittest discover -s scripts/tests -p test_editor_v2_schema.py."""
import importlib.util
import json
import unittest
from pathlib import Path

SCHEMA = Path(__file__).resolve().parents[2] / 'templates/canonical-editor-handoff-v2.schema.json'

JSONSCHEMA_AVAILABLE = importlib.util.find_spec('jsonschema') is not None
if JSONSCHEMA_AVAILABLE:
    from jsonschema import Draft202012Validator


@unittest.skipUnless(JSONSCHEMA_AVAILABLE, 'jsonschema not installed; run with uv run --with jsonschema')
class MappingSchemaTests(unittest.TestCase):
    def test_mapping_contract(self):
        schema = json.loads(SCHEMA.read_text(encoding='utf-8'))
        Draft202012Validator.check_schema(schema)
        validator = Draft202012Validator(schema['properties']['files']['items']['properties']['mapping'])
        valid = dict(key_column='key', source_column='source', target_column='target', state_column='state')
        self.assertTrue(validator.is_valid(valid))
        self.assertTrue(validator.is_valid(dict(valid, notes_column='notes', reference_columns=['reference'])))
        invalid = [dict(a='a', b='b', c='c', d='d'), dict(valid, typo='x'),
                   dict(valid, source_column=''), dict(valid, reference_columns='reference'),
                   dict(valid, reference_columns=['reference', 'reference']), dict(valid, notes_column=None)]
        for candidate in invalid:
            with self.subTest(candidate=candidate):
                self.assertFalse(validator.is_valid(candidate))
