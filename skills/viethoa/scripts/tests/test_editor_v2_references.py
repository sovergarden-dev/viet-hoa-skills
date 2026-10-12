import importlib.util
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / 'editor_handoff_v2.py'
spec = importlib.util.spec_from_file_location('handoff', SCRIPT)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

JSONSCHEMA_AVAILABLE = importlib.util.find_spec('jsonschema') is not None


@unittest.skipUnless(JSONSCHEMA_AVAILABLE, 'jsonschema not installed; run with uv run --with jsonschema')
class ReferenceTests(unittest.TestCase):
    def test_reference_roundtrip_config_and_stale_rejection(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root/'a.csv').write_text('key,source,target,state\nx,Hello,,pending\n', encoding='utf-8')
            ref = root/'glossary.csv'
            ref.write_text('term,translation\nHello,Xin chào\n', encoding='utf-8')
            tables = [dict(translation_id='a', domain='a', path='a.csv', mapping=dict(key_column='key', source_column='source', target_column='target', state_column='state'), editor_policy={'token_pattern': r'\{[0-9]+\}'})]
            refs = [dict(id='glossary', label='Thuật ngữ', path='glossary.csv', key_column='term')]
            manifest = m.build(root, 'test', tables, references=refs)
            self.assertEqual(manifest['references'][0]['row_count'], 1)
            self.assertEqual(m.validate(root, manifest), manifest)
            config = m.editor_config(root, manifest)
            self.assertEqual(config['references'], [dict(id='glossary', label='Thuật ngữ', path='../glossary.csv', keyColumn='term')])
            import json
            import subprocess
            import sys
            from jsonschema import Draft202012Validator
            schema = json.loads((SCRIPT.parents[1]/'templates/canonical-editor-handoff-v2.schema.json').read_text(encoding='utf-8'))
            Draft202012Validator(schema).validate(manifest)
            plan, output = root/'plan.json', root/'handoff.json'
            plan.write_text(json.dumps(dict(project_id='test', tables=tables, references=refs)), encoding='utf-8')
            command = [sys.executable, str(SCRIPT), 'build', '--workspace', str(root), '--plan', str(plan), '--output', str(output)]
            built = subprocess.run(command, capture_output=True, text=True, timeout=30)
            self.assertEqual(built.returncode, 0, built.stderr)
            self.assertEqual(json.loads(output.read_text(encoding='utf-8')), manifest)
            before = ref.read_bytes()
            ref.write_text('term,translation\nHello,"unterminated\n', encoding='utf-8')
            malformed = subprocess.run([sys.executable, str(SCRIPT), 'validate', '--workspace', str(root), '--manifest', str(output)], capture_output=True, text=True, timeout=30)
            self.assertEqual(malformed.returncode, 2, malformed.stderr)
            self.assertEqual(json.loads(malformed.stdout)['result'], 'error')
            self.assertNotIn('Traceback', malformed.stderr)
            ref.write_bytes(before)
            for bad in ([dict(refs[0], path='../outside.csv')], refs*2,
                        [dict(refs[0], key_column='absent')], [dict(refs[0], path='a.csv', key_column='key')]):
                with self.subTest(bad=bad), self.assertRaises(ValueError):
                    m.build(root, 'test', tables, references=bad)
            ref.write_text('term,translation\nHello,Chào\n', encoding='utf-8')
            with self.assertRaises(ValueError):
                m.validate(root, manifest)
            with self.assertRaises(ValueError):
                m.editor_config(root, manifest)
