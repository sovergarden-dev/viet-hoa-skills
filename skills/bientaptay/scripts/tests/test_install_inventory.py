import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location('installer', Path(__file__).resolve().parents[1] / 'install_bientaptay.py')
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)

class InventoryTests(unittest.TestCase):
    def test_alias_paths_cannot_double_count_same_csv(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            (root / 'a.csv').write_text('key,source\nx,Hello\n', encoding='utf-8')
            config = root / 'project.json'
            config.write_text(json.dumps({'translationFiles': [
                {'id': 'a', 'path': 'a.csv'}, {'id': 'b', 'path': './a.csv'}
            ]}), encoding='utf-8')
            before = (root / 'a.csv').read_bytes()
            with self.assertRaises(SystemExit):
                installer.translation_inventory(config, root)
            self.assertEqual((root / 'a.csv').read_bytes(), before)

    def test_inventory_rejects_duplicate_headers(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            (root / 'a.csv').write_text('key,source,source\nx,Hello,Other\n', encoding='utf-8')
            config = root / 'project.json'
            config.write_text(json.dumps({'canonicalPath': 'a.csv'}), encoding='utf-8')
            with self.assertRaises(SystemExit):
                installer.translation_inventory(config, root)

    def test_inventory_rejects_ragged_rows(self):
        for row in ('x,Hello,extra', 'x'):
            with self.subTest(row=row), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp).resolve()
                (root / 'a.csv').write_text('key,source\n' + row + '\n', encoding='utf-8')
                config = root / 'project.json'
                config.write_text(json.dumps({'canonicalPath': 'a.csv'}), encoding='utf-8')
                with self.assertRaises(SystemExit):
                    installer.translation_inventory(config, root)

    def test_distinct_csvs_are_counted_separately(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            for name in ('a', 'b'):
                (root / (name + '.csv')).write_text('key,source\nx,Hello\n', encoding='utf-8')
            config = root / 'project.json'
            config.write_text(json.dumps({'translationFiles': [
                {'id': name, 'path': name + '.csv'} for name in ('a', 'b')
            ]}), encoding='utf-8')
            rows = installer.translation_inventory(config, root)
            self.assertEqual([row['row_count'] for row in rows], [1, 1])
