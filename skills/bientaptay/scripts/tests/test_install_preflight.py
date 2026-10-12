import importlib.util
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / 'install_bientaptay.py'
spec = importlib.util.spec_from_file_location('installer', SCRIPT)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class LockedPreflightTests(unittest.TestCase):
    def test_inputs_changed_since_validation_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            canonical, handoff, config = [root / n for n in ('a.csv', 'handoff.json', 'project.json')]
            canonical.write_bytes(b'key,source\na,Hello\n')
            handoff.write_bytes(b'{}')
            config.write_bytes(b'{"original":true}')
            expected = {p: m.sha256(p) for p in (canonical, handoff, config)}
            m.verify_preflight_inputs(expected)
            for path in expected:
                original = path.read_bytes()
                path.write_bytes(original + b' ')
                with self.subTest(path=path), self.assertRaises(SystemExit):
                    m.verify_preflight_inputs(expected)
                path.write_bytes(original)
            config.unlink()
            with self.assertRaises(SystemExit):
                m.verify_preflight_inputs(expected)

    def test_config_created_after_preflight_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = Path(tmp) / 'project.json'
            m.verify_preflight_inputs({config: None})
            config.write_bytes(b'{}')
            with self.assertRaises(SystemExit):
                m.verify_preflight_inputs({config: None})
