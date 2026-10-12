import importlib.util
import shutil
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "template_swap.py"
spec = importlib.util.spec_from_file_location("template_swap", SCRIPT)
swap = importlib.util.module_from_spec(spec)
spec.loader.exec_module(swap)


def snapshot(root: Path) -> dict[str, bytes]:
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


class TemplateSwapTests(unittest.TestCase):
    def fixture(self, tmp: str):
        base = Path(tmp)
        template = base / "template"
        app = base / "app"
        for rel, text in {"src/a.cs": "new-a", "src/b.cs": "new-b", "tests/t.py": "new-t", "README.md": "new-readme"}.items():
            path = template / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
        for rel, text in {"src/a.cs": "old-a", "src/stale.cs": "old-stale", "tests/t.py": "old-t", "data/glossary.csv": "keep", "project.json": "keep-config"}.items():
            path = app / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
        files = sorted(p for p in template.rglob("*") if p.is_file())
        return template, app, files

    def test_success_replaces_owned_trees_and_preserves_user_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            template, app, files = self.fixture(tmp)
            swap.swap_template(app, template, files)
            after = snapshot(app)
            self.assertEqual(after["src/a.cs"], b"new-a")
            self.assertNotIn("src/stale.cs", after)
            self.assertEqual(after["data/glossary.csv"], b"keep")
            self.assertEqual(after["project.json"], b"keep-config")
            self.assertFalse((app / ".template-staging").exists())
            self.assertFalse((app / ".template-previous").exists())

    def test_copy_failure_leaves_previous_tree_byte_identical(self):
        with tempfile.TemporaryDirectory() as tmp:
            template, app, files = self.fixture(tmp)
            before = snapshot(app)
            calls = []

            def flaky(source, destination):
                calls.append(source)
                if len(calls) == 3:
                    raise OSError("disk full")
                shutil.copyfile(source, destination)

            with self.assertRaises(swap.SwapError):
                swap.swap_template(app, template, files, copy=flaky)
            self.assertEqual(snapshot(app), before)
            self.assertFalse((app / ".template-staging").exists())
            self.assertFalse((app / ".template-previous").exists())

    def test_failure_after_first_tree_swapped_restores_all(self):
        with tempfile.TemporaryDirectory() as tmp:
            template, app, files = self.fixture(tmp)
            before = snapshot(app)
            import os
            real = os.replace
            seen = {"count": 0}

            def failing_replace(src, dst):
                seen["count"] += 1
                if seen["count"] == 4:
                    raise PermissionError("locked")
                return real(src, dst)

            swap.os.replace = failing_replace
            try:
                with self.assertRaises(swap.SwapError):
                    swap.swap_template(app, template, files)
            finally:
                swap.os.replace = real
            self.assertEqual(snapshot(app), before)

    def test_open_transaction_rolls_back_after_later_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            template, app, files = self.fixture(tmp)
            before = snapshot(app)
            transaction = swap.begin_swap(app, template, files)
            self.assertEqual((app / "src/a.cs").read_bytes(), b"new-a")
            self.assertTrue((app / ".template-previous").is_dir())
            transaction.rollback()
            self.assertEqual(snapshot(app), before)
            transaction.rollback()
            self.assertEqual(snapshot(app), before)
            with self.assertRaises(swap.SwapError):
                transaction.commit()

    def test_commit_after_success_discards_previous(self):
        with tempfile.TemporaryDirectory() as tmp:
            template, app, files = self.fixture(tmp)
            transaction = swap.begin_swap(app, template, files)
            transaction.commit()
            self.assertFalse((app / ".template-previous").exists())
            self.assertEqual((app / "src/a.cs").read_bytes(), b"new-a")
            with self.assertRaises(swap.SwapError):
                transaction.commit()

    def test_snapshot_restore_recovers_changed_and_created_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            existing = base / "project.json"
            created = base / "data" / "glossary.csv"
            existing.write_bytes(b"original-config")
            state = swap.snapshot_files([existing, created])
            existing.write_bytes(b"changed")
            created.parent.mkdir()
            created.write_bytes(b"new")
            swap.restore_files(state)
            self.assertEqual(existing.read_bytes(), b"original-config")
            self.assertFalse(created.exists())
            self.assertFalse(existing.with_name("project.json.restore-tmp").exists())

    def test_rollback_failure_can_retry_without_deleting_restored_files(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as tmp:
            template, app, files = self.fixture(tmp)
            before = snapshot(app)
            transaction = swap.begin_swap(app, template, files)
            real = swap.os.replace
            calls = 0
            def fail_second(source, destination):
                nonlocal calls
                calls += 1
                if calls == 2:
                    raise PermissionError('restore locked')
                return real(source, destination)
            with patch.object(swap.os, 'replace', side_effect=fail_second):
                with self.assertRaises(PermissionError):
                    transaction.rollback()
            self.assertFalse(transaction.closed)
            self.assertTrue(transaction.previous.exists())
            transaction.rollback()
            self.assertEqual(snapshot(app), before)
            self.assertTrue(transaction.closed)

    def test_commit_is_refused_after_partial_rollback(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as tmp:
            template, app, files = self.fixture(tmp)
            before = snapshot(app)
            transaction = swap.begin_swap(app, template, files)
            with patch.object(swap.os, 'replace', side_effect=PermissionError('locked')):
                with self.assertRaises(PermissionError):
                    transaction.rollback()
            with self.assertRaises(swap.SwapError):
                transaction.commit()
            self.assertTrue(transaction.previous.exists())
            transaction.rollback()
            self.assertEqual(snapshot(app), before)

    def test_commit_cleanup_failure_is_visible_and_retryable(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as tmp:
            template, app, files = self.fixture(tmp)
            transaction = swap.begin_swap(app, template, files)
            real = swap.shutil.rmtree
            def locked(path, **kwargs):
                if Path(path) == transaction.previous:
                    if kwargs.get('ignore_errors'):
                        return
                    raise PermissionError('cleanup locked')
                return real(path, **kwargs)
            with patch.object(swap.shutil, 'rmtree', side_effect=locked):
                with self.assertRaises(PermissionError):
                    transaction.commit()
            self.assertFalse(transaction.closed)
            with self.assertRaises(swap.SwapError):
                transaction.rollback()
            transaction.commit()
            self.assertTrue(transaction.closed)
            self.assertFalse(transaction.previous.exists())
            self.assertEqual((app / 'src/a.cs').read_bytes(), b'new-a')

    def test_template_cannot_replace_user_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            template, app, files = self.fixture(tmp)
            malicious = template / 'data' / 'glossary.csv'
            malicious.parent.mkdir()
            malicious.write_bytes(b'replacement')
            before = snapshot(app)
            with self.assertRaises(swap.SwapError):
                swap.begin_swap(app, template, files + [malicious])
            self.assertEqual(snapshot(app), before)
            self.assertFalse((app / '.template-staging').exists())

    def test_snapshot_refuses_directory_instead_of_treating_it_as_absent(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / 'project.json'
            target.mkdir()
            (target / 'keep.txt').write_bytes(b'keep')
            with self.assertRaises(swap.SwapError):
                swap.snapshot_files([target])
            self.assertEqual((target / 'keep.txt').read_bytes(), b'keep')

    def test_restore_preserves_existing_restore_tmp(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / 'project.json'
            target.write_bytes(b'old')
            state = swap.snapshot_files([target])
            target.write_bytes(b'new')
            sentinel = target.with_name('project.json.restore-tmp')
            sentinel.write_bytes(b'user-owned')
            swap.restore_files(state)
            self.assertEqual(target.read_bytes(), b'old')
            self.assertEqual(sentinel.read_bytes(), b'user-owned')

    def test_restore_failure_keeps_current_file_and_cleans_owned_temp(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / 'project.json'
            target.write_bytes(b'old')
            state = swap.snapshot_files([target])
            target.write_bytes(b'new')
            with patch.object(swap.os, 'replace', side_effect=PermissionError('locked')):
                with self.assertRaises(PermissionError):
                    swap.restore_files(state)
            self.assertEqual(target.read_bytes(), b'new')
            self.assertEqual(list(Path(tmp).iterdir()), [target])
            swap.restore_files(state)
            self.assertEqual(target.read_bytes(), b'old')

    def test_restore_attempts_remaining_files_after_one_failure(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as tmp:
            a, b = Path(tmp) / 'a.json', Path(tmp) / 'b.json'
            a.write_bytes(b'old-a'); b.write_bytes(b'old-b')
            state = swap.snapshot_files([a, b])
            a.write_bytes(b'new-a'); b.write_bytes(b'new-b')
            real = swap.os.replace
            def locked(source, destination):
                if destination == a:
                    raise PermissionError('a locked')
                return real(source, destination)
            with patch.object(swap.os, 'replace', side_effect=locked):
                with self.assertRaises(BaseExceptionGroup):
                    swap.restore_files(state)
            self.assertEqual(a.read_bytes(), b'new-a')
            self.assertEqual(b.read_bytes(), b'old-b')
            swap.restore_files(state)
            self.assertEqual(a.read_bytes(), b'old-a')

    def test_restore_refuses_directory_created_at_missing_file_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / 'project.json'
            state = swap.snapshot_files([target])
            target.mkdir()
            (target / 'keep').write_bytes(b'keep')
            with self.assertRaises(swap.SwapError):
                swap.restore_files(state)
            self.assertEqual((target / 'keep').read_bytes(), b'keep')

    def test_dir_backup_restores_replaced_tree_and_discards_on_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            live = Path(tmp) / 'app'
            (live / 'sub').mkdir(parents=True)
            (live / 'BienTapTay.exe').write_bytes(b'old-exe')
            (live / 'sub' / 'x.dll').write_bytes(b'old-dll')
            before = snapshot(live)
            backup = swap.DirBackup(live)
            shutil.rmtree(live)
            live.mkdir()
            (live / 'BienTapTay.exe').write_bytes(b'new-exe')
            backup.restore()
            self.assertEqual(snapshot(live), before)
            self.assertFalse(backup.path.exists())
            backup = swap.DirBackup(live)
            backup.discard()
            self.assertFalse(backup.path.exists())
            self.assertEqual(snapshot(live), before)

    def test_dir_backup_of_missing_dir_removes_new_tree_on_restore(self):
        with tempfile.TemporaryDirectory() as tmp:
            live = Path(tmp) / 'app'
            backup = swap.DirBackup(live)
            live.mkdir()
            (live / 'BienTapTay.exe').write_bytes(b'new')
            backup.restore()
            self.assertFalse(live.exists())

    def test_dir_backup_refuses_stale_backup_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            live = Path(tmp) / 'app'
            live.mkdir()
            stale = Path(tmp) / '.app.installer-backup'
            stale.mkdir()
            with self.assertRaises(swap.SwapError):
                swap.DirBackup(live)
            self.assertTrue(stale.is_dir())

    def test_dir_backup_restore_is_retryable_after_failure(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as tmp:
            live = Path(tmp) / 'app'
            live.mkdir()
            (live / 'a.bin').write_bytes(b'old')
            before = snapshot(live)
            backup = swap.DirBackup(live)
            shutil.rmtree(live)
            live.mkdir()
            (live / 'a.bin').write_bytes(b'new')
            with patch.object(swap.os, 'replace', side_effect=PermissionError('locked')):
                with self.assertRaises(PermissionError):
                    backup.restore()
            self.assertTrue(backup.path.exists())
            backup.restore()
            self.assertEqual(snapshot(live), before)
            self.assertFalse(backup.path.exists())

    def test_installer_lock_excludes_second_installer_and_releases(self):
        import subprocess, sys
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            child = (
                "import importlib.util,sys\n"
                "from pathlib import Path\n"
                f"spec=importlib.util.spec_from_file_location('s', r'{SCRIPT}')\n"
                "m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)\n"
                "try:\n"
                "    with m.InstallerLock(Path(sys.argv[1])): print('ACQUIRED')\n"
                "except m.SwapError: print('BUSY')\n"
            )
            def probe():
                return subprocess.run([sys.executable, '-c', child, str(workspace)],
                                      capture_output=True, text=True).stdout.strip()
            with swap.InstallerLock(workspace):
                self.assertEqual(probe(), 'BUSY')
                with self.assertRaises(swap.SwapError):
                    with swap.InstallerLock(workspace):
                        pass
            self.assertEqual(probe(), 'ACQUIRED')
            self.assertFalse((workspace / '.bientaptay.installer.lock').exists())

    def test_same_lock_object_reentry_is_refused_without_losing_handle(self):
        with tempfile.TemporaryDirectory() as tmp:
            lock = swap.InstallerLock(Path(tmp))
            with lock:
                original = lock._handle
                with self.assertRaises(swap.SwapError):
                    lock.__enter__()
                self.assertIs(lock._handle, original)
                self.assertFalse(original.closed)
            self.assertTrue(original.closed)

    def test_unfinished_prior_update_is_refused_untouched(self):
        with tempfile.TemporaryDirectory() as tmp:
            template, app, files = self.fixture(tmp)
            (app / ".template-previous").mkdir()
            before = snapshot(app)
            with self.assertRaises(swap.SwapError):
                swap.swap_template(app, template, files)
            self.assertEqual(snapshot(app), before)
            self.assertTrue((app / ".template-previous").is_dir())


if __name__ == "__main__":
    unittest.main()
