import importlib.util
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location('installer', Path(__file__).resolve().parents[1] / 'install_bientaptay.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class RecoveryTests(unittest.TestCase):
    def test_config_restore_is_attempted_even_when_source_rollback_fails(self):
        events = []
        class Transaction:
            def rollback(self):
                events.append('source')
                raise PermissionError('source locked')
        def restore(state):
            events.append(('config', state))
        with self.assertRaises(BaseExceptionGroup) as caught:
            m.rollback_install(Transaction(), restore, {'saved': b'old'})
        self.assertEqual(events, ['source', ('config', {'saved': b'old'})])
        self.assertIsInstance(caught.exception.exceptions[0], PermissionError)

    def test_extra_steps_run_even_after_earlier_failures(self):
        events = []
        class Transaction:
            def rollback(self):
                events.append('source')
                raise PermissionError('source locked')
        def restore(state):
            events.append('config')
            raise OSError('config locked')
        def app_dir():
            events.append('app')
        with self.assertRaises(BaseExceptionGroup) as caught:
            m.rollback_install(Transaction(), restore, {}, extra=(app_dir,))
        self.assertEqual(events, ['source', 'config', 'app'])
        self.assertEqual(len(caught.exception.exceptions), 2)

    def test_extra_step_failure_is_reported(self):
        class Transaction:
            def rollback(self):
                pass
        def bad():
            raise OSError('app locked')
        with self.assertRaises(BaseExceptionGroup) as caught:
            m.rollback_install(Transaction(), lambda state: None, {}, extra=(bad,))
        self.assertEqual([str(e) for e in caught.exception.exceptions], ['app locked'])

    def test_both_failures_are_preserved(self):
        class Transaction:
            def rollback(self):
                raise PermissionError('source locked')
        def restore(state):
            raise OSError('config locked')
        with self.assertRaises(BaseExceptionGroup) as caught:
            m.rollback_install(Transaction(), restore, {})
        self.assertEqual([str(e) for e in caught.exception.exceptions], ['source locked', 'config locked'])
