import importlib.util
from pathlib import Path
import unittest
from unittest.mock import Mock

P = Path(__file__).resolve().parents[2] / 'templates/pause_when_finished.py'
spec = importlib.util.spec_from_file_location('completion', P)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class CompletionTests(unittest.TestCase):
    def test_incomplete_counts_fail_closed(self):
        self.assertFalse(m.corpus_finished({'total': 2, 'accepted': 2}))
    def test_full_counts(self):
        c = dict(total=2, accepted=2, pending=0, rejected=0, needs_review=0, needs_context=0)
        self.assertTrue(m.corpus_finished(c))
        for key in c:
            bad = dict(c); bad[key] = True
            self.assertFalse(m.corpus_finished(bad))
        c['needs_context'] = 1
        self.assertFalse(m.corpus_finished(c))
    def test_api_pause_readback(self):
        api = Mock()
        api.get_job.side_effect = [{'id':'x','enabled':True}, {'id':'x','enabled':False,'state':'paused','next_run_at':'retained'}]
        self.assertEqual(m.pause_finished_job('x', reason='complete', scheduler=api), 'paused')
        api.pause_job.assert_called_once_with('x', reason='complete')
    def test_missing_id_no_pause(self):
        api=Mock(); api.get_job.return_value=None
        self.assertEqual(m.pause_finished_job('x',reason='complete',scheduler=api),'missing')
        api.pause_job.assert_not_called()
    def test_failed_readback(self):
        api=Mock(); api.get_job.return_value={'id':'x','enabled':True,'state':'scheduled'}
        with self.assertRaises(RuntimeError):
            m.pause_finished_job('x',reason='complete',scheduler=api)
    def test_legacy_file_write_refused(self):
        with self.assertRaises(ValueError):
            m.pause_finished_job('x', Path('never-write.json'), reason='complete')

if __name__ == '__main__': unittest.main()
