import importlib.util
import tempfile
import unittest
from pathlib import Path

SCRIPT=Path(__file__).resolve().parents[1]/'template_inventory.py'

class InventoryTests(unittest.TestCase):
    def test_generated_files_excluded_and_source_preserved(self):
        spec=importlib.util.spec_from_file_location('inventory',SCRIPT)
        m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            names=['src/App/Main.cs','src/App/bin/Release/app.exe','src/App/obj/assets.json','__pycache__/x.pyc','writer_lock.py','tests/test_core.py']
            for name in names:
                p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('fixture',encoding='utf-8')
            self.assertEqual([p.relative_to(root).as_posix() for p in m.template_files(root)],['src/App/Main.cs','tests/test_core.py','writer_lock.py'])

if __name__=='__main__': unittest.main()
