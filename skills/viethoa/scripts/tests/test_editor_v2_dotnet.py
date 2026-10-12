"""Cross-language handoff integration; synthetic CSVs, actual editor Core."""
import importlib.util
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPT=Path(__file__).resolve().parents[1]/'editor_handoff_v2.py'
SKILLS=SCRIPT.parents[3]
CORE=SKILLS/'software-development/bientaptay/templates/bientaptay/src/BienTapTay.Core'

@unittest.skipUnless(shutil.which('dotnet') and CORE.is_dir(),'dotnet and companion editor Core required')
class DotnetBoundaryTests(unittest.TestCase):
    def test_generated_multitable_config_in_real_core(self):
        spec=importlib.util.spec_from_file_location('v2',SCRIPT)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            (root/'a.csv').write_text('id,en,vi,status\nx,Hello {0},Chào {0},translated\nevidence-only,Context,Ngữ cảnh,reviewed\n',encoding='utf-8')
            (root/'b.csv').write_text('key,original,target,state\nx,World,Thế giới,reviewed\n',encoding='utf-8')
            tables=[dict(translation_id='dialogue',path='a.csv',domain='dialogue',mapping=dict(key_column='id',source_column='en',target_column='vi',state_column='status')),dict(translation_id='ui',path='b.csv',domain='ui',mapping=dict(key_column='key',source_column='original',target_column='target',state_column='state'))]
            (root/'glossary.csv').write_text('term,translation,type,context,status\nHello,Xin chào,term,,reviewed\n', encoding='utf-8')
            (root/'pronouns.csv').write_text('speaker,self_reference,address_form,notes,status,evidence_keys\nNarrator,tôi,bạn,Ngữ cảnh thử nghiệm,reviewed,evidence-only\n', encoding='utf-8')
            manifest=module.build(root,'synthetic',tables, references=[dict(id='glossary', label='Thuật ngữ', path='glossary.csv', key_column='term'), dict(id='pronouns', label='Xưng hô', path='pronouns.csv', key_column='speaker')])
            config=module.editor_config(root,manifest,token_patterns={'dialogue':r'\{[0-9]+\}','ui':r'\{[0-9]+\}'})
            app=root/'bientaptay';app.mkdir()
            config_path=app/'project.json';config_path.write_text(json.dumps(config),encoding='utf-8')
            copied=root/'Core'
            shutil.copytree(CORE,copied,ignore=shutil.ignore_patterns('bin','obj'))
            runner=root/'Runner';runner.mkdir()
            (runner/'Runner.csproj').write_text('<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup><OutputType>Exe</OutputType><TargetFramework>net8.0</TargetFramework><ImplicitUsings>enable</ImplicitUsings></PropertyGroup><ItemGroup><ProjectReference Include="../Core/BienTapTay.Core.csproj" /></ItemGroup></Project>',encoding='utf-8')
            (runner/'Program.cs').write_text('''using BienTapTay.Core;
var config = ProjectConfig.Load(args[0]);
if (!config.Statuses.Contains("rejected")) throw new Exception("handoff state rejected missing from config");
var files = config.GetTranslationFiles();
if (config.References.Count != 2) throw new Exception("reference count");
var reference = config.References[0];
if (reference.Id != "glossary" || reference.KeyColumn != "term") throw new Exception("reference mapping");
var glossary = CsvTableStore.Open(config.Resolve(reference.Path), reference.KeyColumn, reference.Id);
if (glossary.Rows.Count != 1) throw new Exception("glossary count");
glossary.Validate();
var glossaryBytes = File.ReadAllBytes(config.Resolve(reference.Path));
glossary.Rows[0]["translation"] = "";
bool glossaryRejected = false;
try { glossary.Save(); } catch (ReferenceValidationException) { glossaryRejected = true; }
if (!glossaryRejected || !glossaryBytes.SequenceEqual(File.ReadAllBytes(config.Resolve(reference.Path))))
    throw new Exception("invalid glossary save changed disk");
glossary.ReloadFromDisk();
glossary.Validate();
if (files.Count != 2) throw new Exception("table count");
var a = CanonicalStore.Open(config.ForTranslationFile(files[0]));
var b = CanonicalStore.Open(config.ForTranslationFile(files[1]));
var pronounReference = config.References.Single(r => r.Id == "pronouns");
var pronouns = CsvTableStore.Open(config.Resolve(pronounReference.Path), pronounReference.KeyColumn,
    pronounReference.Id, a.Rows.Select(r => r.Key).Concat(b.Rows.Select(r => r.Key)));
pronouns.Validate();
var ambiguousPronouns = CsvTableStore.Open(config.Resolve(pronounReference.Path), pronounReference.KeyColumn,
    pronounReference.Id, new[] { "evidence-only", "evidence-only" });
bool ambiguousRefused = false;
try { ambiguousPronouns.Validate(); } catch (ReferenceValidationException) { ambiguousRefused = true; }
if (!ambiguousRefused) throw new Exception("ambiguous cross-table evidence accepted");
var pronounBytes = File.ReadAllBytes(config.Resolve(pronounReference.Path));
foreach (var invalidField in new[] { "evidence_keys", "status", "self_reference" })
{
    pronouns.Rows[0][invalidField] = invalidField == "evidence_keys" ? "missing-key" : "";
    bool refused = false;
    try { pronouns.Save(); } catch (ReferenceValidationException) { refused = true; }
    if (!refused || !pronounBytes.SequenceEqual(File.ReadAllBytes(config.Resolve(pronounReference.Path))))
        throw new Exception("invalid pronoun save changed disk: " + invalidField);
    pronouns.ReloadFromDisk();
}
pronouns.Validate();
if (a.Rows[0].Key != "x" || b.Rows[0].Key != "x") throw new Exception("scoped key");
if (a.ValidateTarget(a.Rows[0], "Chào").Length == 0) throw new Exception("lost token accepted");
if (a.ValidateTarget(a.Rows[0], "Chào {0}").Length != 0) throw new Exception("valid token rejected");
if (b.ValidateTarget(b.Rows[0], "Thế giới").Length != 0) throw new Exception("UI rejected");
if (args.Length > 1 && args[1] == "save")
{
    var untouched = File.ReadAllBytes(config.ForTranslationFile(files[1]).ResolvedCanonicalPath);
    a.Rows[0].Target = "Xin chào {0}";
    a.Save();
    var reopened = CanonicalStore.Open(config.ForTranslationFile(files[0]));
    if (reopened.Rows[0].Target != "Xin chào {0}") throw new Exception("save readback");
    if (!untouched.SequenceEqual(File.ReadAllBytes(config.ForTranslationFile(files[1]).ResolvedCanonicalPath)))
        throw new Exception("other table mutated");
    var snapshot = File.ReadAllBytes(config.ForTranslationFile(files[0]).ResolvedCanonicalPath);
    reopened.Rows[0].Target = "Missing token";
    bool rejected = false;
    try { reopened.Save(); } catch (CanonicalValidationException) { rejected = true; }
    if (!rejected || !snapshot.SequenceEqual(File.ReadAllBytes(config.ForTranslationFile(files[0]).ResolvedCanonicalPath)))
        throw new Exception("invalid save changed disk");
    Console.WriteLine("V2_SCOPED_SAVE_OK");
}
Console.WriteLine("V2_CORE_BOUNDARY_OK");
''',encoding='utf-8')
            before={p:p.read_bytes() for p in (root/'a.csv',root/'b.csv',root/'glossary.csv',root/'pronouns.csv')}
            result=subprocess.run(['dotnet','run','--project',str(runner/'Runner.csproj'),'-c','Release','--',str(config_path)],capture_output=True,text=True,encoding='utf-8',timeout=120)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            self.assertIn('V2_CORE_BOUNDARY_OK',result.stdout)
            for p,data in before.items(): self.assertEqual(p.read_bytes(),data)
            saved=subprocess.run(['dotnet','run','--no-build','--project',str(runner/'Runner.csproj'),'-c','Release','--',str(config_path),'save'],capture_output=True,text=True,encoding='utf-8',timeout=120)
            self.assertEqual(saved.returncode,0,saved.stdout+saved.stderr)
            self.assertIn('V2_SCOPED_SAVE_OK',saved.stdout)
            self.assertEqual((root/'pronouns.csv').read_bytes(),before[root/'pronouns.csv'])
            self.assertEqual((root/'glossary.csv').read_bytes(),before[root/'glossary.csv'])
            self.assertEqual((root/'b.csv').read_bytes(),before[root/'b.csv'])
            self.assertEqual((root/'a.csv.bientaptay.bak').read_bytes(),before[root/'a.csv'])
            with self.assertRaises(ValueError): module.validate(root,manifest)

if __name__=='__main__': unittest.main()
