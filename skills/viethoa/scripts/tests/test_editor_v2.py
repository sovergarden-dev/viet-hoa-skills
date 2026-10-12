import importlib.util
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / 'editor_handoff_v2.py'

class ContractTests(unittest.TestCase):
    def test_roundtrip_and_stale_second_table(self):
        spec=importlib.util.spec_from_file_location('v2',SCRIPT)
        m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for name in ('a','b'):
                (root/(name+'.csv')).write_text('key,source,target,state\nk,Hello,Xin chào,translated\n',encoding='utf-8')
            tables=[dict(translation_id=n,path=n+'.csv',domain=n,mapping=dict(key_column='key',source_column='source',target_column='target',state_column='state')) for n in ('a','b')]
            manifest=m.build(root,'test',tables)
            self.assertEqual(m.validate(root,manifest),manifest)
            (root/'b.csv').write_text('key,source,target,state\nk,Changed,,pending\n',encoding='utf-8')
            with self.assertRaises(ValueError): m.validate(root,manifest)
    def test_escape_and_duplicate_path(self):
        spec=importlib.util.spec_from_file_location('v2',SCRIPT)
        m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            with self.assertRaises(ValueError): m.build(root,'test',[dict(translation_id='x',path='../outside.csv',domain='x',mapping={})])

class ConfigTests(unittest.TestCase):
    def test_per_table_mapping_and_stale_refusal(self):
        spec=importlib.util.spec_from_file_location('v2',SCRIPT)
        m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            (root/'a.csv').write_text('id,en,vi,status\nx,Hello,,pending\n',encoding='utf-8')
            tables=[dict(translation_id='dialogue',path='a.csv',domain='dialogue',mapping=dict(key_column='id',source_column='en',target_column='vi',state_column='status'))]
            manifest=m.build(root,'project',tables)
            with self.assertRaises(ValueError): m.editor_config(root,manifest)
            policy={'dialogue': r'\{[0-9]+\}'}
            config=m.editor_config(root,manifest,token_patterns=policy)
            self.assertEqual(config['translationFiles'][0]['tokenPattern'],policy['dialogue'])
            with self.assertRaises(ValueError):
                m.editor_config(root,manifest,token_patterns={'wrong': 'x'})
            table=config['translationFiles'][0]
            self.assertEqual(table['keyColumn'],'id')
            self.assertEqual(table['sourceFields'][0]['column'],'en')
            self.assertEqual(table['path'],'../a.csv')
            self.assertEqual(config['canonicalPath'],'../a.csv')
            self.assertFalse((root/'bientaptay').exists())
            (root/'a.csv').write_text('changed',encoding='utf-8')
            with self.assertRaises(ValueError): m.editor_config(root,manifest)

class StrictInputTests(unittest.TestCase):
    def test_malformed_table_objects_rejected(self):
        spec=importlib.util.spec_from_file_location('v2',SCRIPT)
        m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
        with tempfile.TemporaryDirectory() as tmp:
            for value in (None, [], 'table', 1, True):
                with self.subTest(value=value), self.assertRaises(ValueError):
                    m.build(Path(tmp), 'test', [value])

    def test_empty_csv_table_rejected(self):
        spec=importlib.util.spec_from_file_location('v2',SCRIPT)
        m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root/'empty.csv').write_text('key,source,target,state\n', encoding='utf-8')
            table = dict(translation_id='empty', path='empty.csv', domain='ui',
                         mapping=dict(key_column='key', source_column='source', target_column='target', state_column='state'))
            with self.assertRaises(ValueError):
                m.build(root, 'test', [table])

    def test_duplicate_path_rejected(self):
        spec=importlib.util.spec_from_file_location('v2',SCRIPT)
        m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            (root/'a.csv').write_text('key,source,target,state\nk,Hello,,pending\n',encoding='utf-8')
            row=dict(translation_id='a',path='a.csv',domain='a',mapping=dict(key_column='key',source_column='source',target_column='target',state_column='state'))
            with self.assertRaises(ValueError): m.build(root,'test',[row,dict(row,translation_id='b')])
    def test_unknown_state_rejected(self):
        spec=importlib.util.spec_from_file_location('v2',SCRIPT)
        m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            (root/'a.csv').write_text('key,source,target,state\nk,Hello,,definitely_finished\n',encoding='utf-8')
            row=dict(translation_id='a',path='a.csv',domain='a',mapping=dict(key_column='key',source_column='source',target_column='target',state_column='state'))
            with self.assertRaises(ValueError): m.build(root,'test',[row])

class WhitespaceTests(unittest.TestCase):
    def test_exact_whitespace_identity_allowed_but_changed_whitespace_rejected(self):
        spec=importlib.util.spec_from_file_location('v2',SCRIPT)
        m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            csv=root/'a.csv'
            table=dict(translation_id='a',path='a.csv',domain='a',mapping=dict(key_column='key',source_column='source',target_column='target',state_column='state'))
            csv.write_text('key,source,target,state\nk,  ,  ,reviewed\n',encoding='utf-8')
            self.assertEqual(m.build(root,'test',[table])['files'][0]['row_count'],1)
            csv.write_text('key,source,target,state\nk,  , ,reviewed\n',encoding='utf-8')
            with self.assertRaises(ValueError): m.build(root,'test',[table])
            csv.write_text('key,source,target,state\nk,Hello, ,reviewed\n',encoding='utf-8')
            with self.assertRaises(ValueError): m.build(root,'test',[table])

class PolicyBindingTests(unittest.TestCase):
    def test_policy_is_bound_and_override_rejected(self):
        spec=importlib.util.spec_from_file_location('v2',SCRIPT)
        m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            (root/'a.csv').write_text('key,source,target,state\nk,Hello,,pending\n',encoding='utf-8')
            table=dict(translation_id='a',path='a.csv',domain='a',mapping=dict(key_column='key',source_column='source',target_column='target',state_column='state'),editor_policy={'token_pattern': r'\{[0-9]+\}'})
            manifest=m.build(root,'test',[table])
            self.assertEqual(manifest['files'][0]['editor_policy'],table['editor_policy'])
            self.assertEqual(m.editor_config(root,manifest)['translationFiles'][0]['tokenPattern'],table['editor_policy']['token_pattern'])
            with self.assertRaises(ValueError):
                m.editor_config(root,manifest,token_patterns={'a':'different'})
            for invalid in ([], 'pattern', 7, True):
                with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                    m.editor_config(root,manifest,token_patterns=invalid)

class OptionalColumnsTests(unittest.TestCase):
    def test_optional_mapping_preserved_and_missing_column_refused(self):
        spec=importlib.util.spec_from_file_location('v2',SCRIPT)
        m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            (root/'a.csv').write_text('key,source,target,state,notes,speaker,reference\nk,Hello,,pending,,Narrator,Bonjour\n',encoding='utf-8')
            mapping=dict(key_column='key',source_column='source',target_column='target',state_column='state',notes_column='notes',speaker_column='speaker',reference_columns=['reference'])
            table=dict(translation_id='a',path='a.csv',domain='a',mapping=mapping,editor_policy={'token_pattern':r'\{[0-9]+\}'})
            manifest=m.build(root,'test',[table])
            config=m.editor_config(root,manifest)['translationFiles'][0]
            self.assertEqual(config['notesColumn'],'notes')
            self.assertEqual(config['speakerColumn'],'speaker')
            self.assertEqual([x['column'] for x in config['sourceFields']],['source','reference'])
            mapping['reference_columns'].append('later_change')
            self.assertEqual(manifest['files'][0]['mapping']['reference_columns'], ['reference'])
            mapping['reference_columns'].pop()
            mapping['notes_column']='absent'
            with self.assertRaises(ValueError): m.build(root,'test',[table])

class PublishTests(unittest.TestCase):
    def test_invalid_plan_root_returns_json_error_without_output(self):
        import json
        import subprocess
        import sys
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan, output = root/'plan.json', root/'handoff.json'
            for value in (None, [], 'plan', 1, True):
                with self.subTest(value=value):
                    plan.write_text(json.dumps(value), encoding='utf-8')
                    result = subprocess.run([sys.executable, str(SCRIPT), 'build', '--workspace', str(root),
                                             '--plan', str(plan), '--output', str(output)], capture_output=True, text=True)
                    self.assertEqual(result.returncode, 2, result.stderr)
                    self.assertEqual(json.loads(result.stdout)['result'], 'error')
                    self.assertNotIn('Traceback', result.stderr)
                    self.assertFalse(output.exists())
                    self.assertEqual(list(root.glob('.handoff-*')), [])

    def test_publish_validate_and_no_clobber(self):
        import json
        import subprocess
        import sys
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            csv=root/'a.csv'
            csv.write_text('key,source,target,state\nk,Hello,,pending\n',encoding='utf-8')
            plan=root/'plan.json'
            plan.write_text(json.dumps(dict(project_id='test',tables=[dict(translation_id='a',path='a.csv',domain='a',mapping=dict(key_column='key',source_column='source',target_column='target',state_column='state'))])),encoding='utf-8')
            out=root/'handoff.json'
            cmd=[sys.executable,str(SCRIPT),'build','--workspace',str(root),'--plan',str(plan),'--output',str(out)]
            first=subprocess.run(cmd,capture_output=True)
            self.assertEqual(first.returncode,0,first.stderr)
            self.assertTrue(out.is_file())
            baseline=out.read_bytes()
            second=subprocess.run(cmd,capture_output=True)
            self.assertNotEqual(second.returncode,0)
            self.assertEqual(out.read_bytes(),baseline)
            verify=[sys.executable,str(SCRIPT),'validate','--workspace',str(root),'--manifest',str(out)]
            self.assertEqual(subprocess.run(verify,capture_output=True).returncode,0)
            csv.write_text('key,source,target,state\nk,Changed,,pending\n',encoding='utf-8')
            self.assertNotEqual(subprocess.run(verify,capture_output=True).returncode,0)

if __name__=='__main__': unittest.main()
