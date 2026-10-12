import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

# Add _shared/lib to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "_shared" / "lib"))
import hermes_io


class TestHermesIO(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp_dir.name)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_atomic_write_creates_file_and_replaces_cleanly(self) -> None:
        target = self.workspace / "test_file.txt"
        size = hermes_io.atomic_write(target, "Hello Atomic Write!")
        self.assertTrue(target.exists())
        self.assertEqual(target.read_text(encoding="utf-8"), "Hello Atomic Write!")
        self.assertEqual(size, target.stat().st_size)

        # Overwrite atomically
        hermes_io.atomic_write(target, "Overwritten Content")
        self.assertEqual(target.read_text(encoding="utf-8"), "Overwritten Content")

    def test_canonical_lock_acquire_and_release(self) -> None:
        lock = hermes_io.CanonicalLock(self.workspace, owner="test_worker", timeout=2.0)
        try:
            acquired = lock.acquire()
            self.assertTrue(acquired)
            self.assertTrue(lock.lock_file.exists())

            # Read metadata from sidecar .lock.json (not locked sentinel file)
            meta_file = self.workspace / hermes_io.LOCK_RELATIVE_PATH.parent / "canonical.lock.json"
            self.assertTrue(meta_file.exists())
            import json
            data = json.loads(meta_file.read_text(encoding="utf-8"))
            self.assertEqual(data["owner"], "test_worker")
            self.assertEqual(data["version"], hermes_io.CONTRACT_VERSION)
        finally:
            lock.release()
        self.assertFalse(lock._acquired)

    def test_canonical_lock_concurrent_conflict(self) -> None:
        lock1 = hermes_io.CanonicalLock(self.workspace, owner="worker_1", timeout=1.0)
        lock2 = hermes_io.CanonicalLock(self.workspace, owner="worker_2", timeout=0.2, non_blocking=True)
        try:
            lock1.acquire()
            # Worker 2 attempts non-blocking acquire
            with self.assertRaises(hermes_io.LockAcquisitionError):
                lock2.acquire()
        finally:
            lock1.release()

        # Worker 2 should now succeed
        try:
            acquired = lock2.acquire()
            self.assertTrue(acquired)
        finally:
            lock2.release()

    def test_exact_key_merge_preserves_human_locked(self) -> None:
        canonical = [
            {"domain": "UI", "key": "btn_start", "translation_vi": "Bắt đầu", "status": "reviewed", "human_locked": "false"},
            {"domain": "UI", "key": "btn_save", "translation_vi": "Lưu game", "status": "human_edited", "human_locked": "true"},
            {"domain": "Dialog", "key": "line_01", "translation_vi": "Xin chào", "status": "pending", "human_locked": "false"},
        ]
        incoming = [
            {"domain": "UI", "key": "btn_start", "translation_vi": "Khởi đầu", "status": "translated"},
            {"domain": "UI", "key": "btn_save", "translation_vi": "Lưu đè bậy", "status": "translated"},
            {"domain": "Dialog", "key": "line_01", "translation_vi": "Chào bạn", "status": "translated"},
        ]

        merged, updated, skipped = hermes_io.exact_key_merge(canonical, incoming)
        self.assertEqual(updated, 2)
        self.assertEqual(skipped, 1)

        by_key = {f"{r['domain']}::{r['key']}": r for r in merged}
        self.assertEqual(by_key["UI::btn_start"]["translation_vi"], "Khởi đầu")
        self.assertEqual(by_key["UI::btn_save"]["translation_vi"], "Lưu game")  # Preserved!
        self.assertEqual(by_key["Dialog::line_01"]["translation_vi"], "Chào bạn")

    def test_exact_key_merge_rejects_orphan_keys(self) -> None:
        canonical = [
            {"domain": "UI", "key": "btn_ok", "translation_vi": "Đồng ý"}
        ]
        incoming = [
            {"domain": "UI", "key": "btn_unknown_phantom", "translation_vi": "Lạ"}
        ]
        with self.assertRaises(hermes_io.InvariantViolationError):
            hermes_io.exact_key_merge(canonical, incoming)

    def test_checkpoint_and_restore(self) -> None:
        target = self.workspace / "sample.csv"
        hermes_io.atomic_write(target, "original,data\n1,one\n")
        ckpt = hermes_io.checkpoint_file(target)
        self.assertTrue(ckpt.exists())

        # Corrupt target
        hermes_io.atomic_write(target, "corrupted,data\n")
        self.assertEqual(target.read_text(encoding="utf-8"), "corrupted,data\n")

        # Restore
        restored = hermes_io.restore_checkpoint(target)
        self.assertEqual(restored.read_text(encoding="utf-8"), "original,data\n1,one\n")


if __name__ == "__main__":
    unittest.main()
