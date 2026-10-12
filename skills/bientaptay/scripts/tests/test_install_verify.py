import ast
import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / 'install_bientaptay.py'
spec = importlib.util.spec_from_file_location('installer', SCRIPT)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def build(root: Path):
    app = root / 'bientaptay'
    (app / 'app').mkdir(parents=True)
    canonical = root / 'a.csv'
    canonical.write_text('key,source\nx,Hello\ny,World\n', encoding='utf-8')
    config = app / 'project.json'
    config.write_text(json.dumps({'canonicalPath': '../a.csv'}), encoding='utf-8')
    exe = app / 'app' / 'BienTapTay.exe'
    exe.write_bytes(b'MZ-synthetic-executable')
    receipt = {
        'schema': 'bientaptay-install/v3', 'app_version': m.APP_VERSION,
        'canonical_unchanged': True, 'translation_files_unchanged': True,
        'reference_files_unchanged': True, 'text_row_count': 2,
        'executable': str(exe), 'executable_sha256': hashlib.sha256(exe.read_bytes()).hexdigest(),
    }
    (app / 'install-receipt.json').write_text(json.dumps(receipt), encoding='utf-8')
    before = m.sha256(canonical)
    inventory = m.translation_inventory(config, root.resolve())
    return app, canonical, config, exe, before, inventory


class VerifyInstallResultTests(unittest.TestCase):
    def run_verify(self, mutate=None):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            app, canonical, config, exe, before, inventory = build(root)
            if mutate:
                mutate(app, canonical, exe)
            return m.verify_install_result(canonical, before, inventory, config, root, app, exe)

    def test_valid_result_passes(self):
        receipt, inventory = self.run_verify()
        self.assertEqual(receipt['text_row_count'], 2)
        self.assertEqual(len(inventory), 1)

    def test_tampered_executable_hash_is_rejected(self):
        def mutate(app, canonical, exe):
            exe.write_bytes(b'MZ-tampered')
        with self.assertRaises(SystemExit):
            self.run_verify(mutate)

    def test_changed_canonical_is_rejected(self):
        def mutate(app, canonical, exe):
            canonical.write_text('key,source\nx,Changed\ny,World\n', encoding='utf-8')
        with self.assertRaises(SystemExit):
            self.run_verify(mutate)

    def test_string_false_flag_is_rejected(self):
        def mutate(app, canonical, exe):
            path = app / 'install-receipt.json'
            data = json.loads(path.read_text(encoding='utf-8'))
            data['canonical_unchanged'] = 'false'
            path.write_text(json.dumps(data), encoding='utf-8')
        with self.assertRaises(SystemExit):
            self.run_verify(mutate)

    def test_corrupt_receipt_is_rejected(self):
        def mutate(app, canonical, exe):
            (app / 'install-receipt.json').write_text('{not json', encoding='utf-8')
        with self.assertRaises(SystemExit):
            self.run_verify(mutate)


class CommitOrderTests(unittest.TestCase):
    def test_verification_runs_inside_try_before_commit(self):
        tree = ast.parse(SCRIPT.read_text(encoding='utf-8'))
        main = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'main')

        def calls(node, name):
            return [c for c in ast.walk(node) if isinstance(c, ast.Call)
                    and (getattr(c.func, 'id', None) == name or getattr(c.func, 'attr', None) == name)]

        commits = calls(main, 'commit')
        self.assertEqual(len(commits), 1)
        guarded = [t for t in ast.walk(main) if isinstance(t, ast.Try)
                   and any(calls(s, 'verify_install_result') for s in t.body)]
        self.assertEqual(len(guarded), 1)
        handler_names = [ast.dump(h.type) for h in guarded[0].handlers if h.type]
        self.assertTrue(any('BaseException' in name for name in handler_names))
        verify_line = calls(guarded[0], 'verify_install_result')[0].lineno
        self.assertLess(verify_line, commits[0].lineno)
        self.assertFalse(any(calls(s, 'commit') for s in guarded[0].body))


if __name__ == '__main__':
    unittest.main()
