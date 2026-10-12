"""Transactional replacement of the editor source/test trees."""
from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path
from typing import Callable, Iterable

OWNED_TREES = ("src", "tests", "project-tests")


class SwapError(RuntimeError):
    pass


def _remove(path: Path) -> None:
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    elif path.exists() or path.is_symlink():
        path.unlink()


class SwapTransaction:
    def __init__(self, app_root: Path, staging: Path, previous: Path,
                 moved: list[tuple[Path, Path]], installed: list[Path]) -> None:
        self.app_root = app_root
        self.staging = staging
        self.previous = previous
        self.moved = moved
        self.installed = installed
        self.closed = False
        self.rolling_back = False
        self.committing = False

    def commit(self) -> None:
        if self.rolling_back:
            raise SwapError("cannot commit a rollback transaction")
        if self.closed:
            raise SwapError("transaction already closed")
        self.committing = True
        if self.staging.exists():
            shutil.rmtree(self.staging)
        if self.previous.exists():
            shutil.rmtree(self.previous)
        self.closed = True

    def rollback(self) -> None:
        if self.closed:
            return
        if self.committing:
            raise SwapError("commit cleanup started; retry commit, not rollback")
        self.rolling_back = True
        while self.installed:
            live = self.installed[-1]
            _remove(live)
            self.installed.pop()
        while self.moved:
            live, backup = self.moved[-1]
            if not (backup.exists() or backup.is_symlink()):
                raise SwapError(f"rollback backup missing: {backup}")
            os.replace(backup, live)
            self.moved.pop()
        if self.staging.exists():
            shutil.rmtree(self.staging)
        if self.previous.exists():
            shutil.rmtree(self.previous)
        self.closed = True


def snapshot_files(paths: Iterable[Path]) -> dict[Path, bytes | None]:
    state: dict[Path, bytes | None] = {}
    for path in map(Path, paths):
        if path.is_symlink() or (path.exists() and not path.is_file()):
            raise SwapError(f'snapshot requires a regular file or absent path: {path}')
        state[path] = path.read_bytes() if path.is_file() else None
    return state


def restore_files(state: dict[Path, bytes | None]) -> None:
    failures = []
    for path, data in state.items():
        try:
            _restore_file(path, data)
        except Exception as error:
            error.add_note(f'Restore target: {path}')
            failures.append(error)
    if len(failures) == 1 and len(state) == 1:
        raise failures[0]
    if failures:
        raise ExceptionGroup('File recovery incomplete', failures)


def _restore_file(path: Path, data: bytes | None) -> None:
    if path.is_symlink() or (path.exists() and not path.is_file()):
        raise SwapError(f'restore target changed type: {path}')
    if data is None:
        if path.is_file():
            path.unlink()
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix=path.name + '.restore-', dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, 'wb') as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


class InstallerLock:
    """Process-exclusive lock so two installers never mutate one workspace together.

    Separate from the editor WriterLock: release_publish.py takes that one in a
    child process and would block on it if the installer held it.
    """

    NAME = ".bientaptay.installer.lock"

    def __init__(self, workspace: Path) -> None:
        self.path = Path(workspace) / self.NAME
        self._handle = None

    def __enter__(self) -> "InstallerLock":
        import msvcrt
        self.path.parent.mkdir(parents=True, exist_ok=True)
        handle = self.path.open("a+b")
        try:
            handle.seek(0, 2)
            if handle.tell() == 0:
                handle.write(b"\0")
                handle.flush()
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError as error:
            handle.close()
            raise SwapError(f"another installer holds {self.path}") from error
        self._handle = handle
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        import msvcrt
        if self._handle is None:
            return
        try:
            self._handle.seek(0)
            msvcrt.locking(self._handle.fileno(), msvcrt.LK_UNLCK, 1)
        finally:
            self._handle.close()
            self._handle = None
        try:
            self.path.unlink()
        except OSError:
            pass


class DirBackup:
    """Copy-backup of a directory the release pipeline will replace."""

    def __init__(self, live: Path) -> None:
        self.live = Path(live)
        self.path = self.live.parent / f".{self.live.name}.installer-backup"
        if self.path.exists() or self.path.is_symlink():
            raise SwapError(f"unfinished prior backup; inspect {self.path}")
        if self.live.is_symlink() or (self.live.exists() and not self.live.is_dir()):
            raise SwapError(f"backup target must be a real directory: {self.live}")
        self.existed = self.live.is_dir()
        self.closed = False
        if self.existed:
            try:
                shutil.copytree(self.live, self.path)
            except BaseException:
                shutil.rmtree(self.path, ignore_errors=True)
                raise

    def restore(self) -> None:
        if self.closed:
            return
        if self.existed and not self.path.is_dir():
            raise SwapError(f"backup missing, cannot restore: {self.path}")
        if self.live.is_symlink() or (self.live.exists() and not self.live.is_dir()):
            raise SwapError(f"restore target changed type: {self.live}")
        if self.live.exists():
            shutil.rmtree(self.live)
        if self.existed:
            os.replace(self.path, self.live)
        self.closed = True

    def discard(self) -> None:
        if self.closed:
            return
        if self.path.exists():
            shutil.rmtree(self.path)
        self.closed = True


def begin_swap(
    app_root: Path,
    template_root: Path,
    files: Iterable[Path],
    *,
    copy: Callable[[Path, Path], object] = shutil.copyfile,
) -> SwapTransaction:
    app_root = Path(app_root)
    template_root = Path(template_root)
    staging = app_root / ".template-staging"
    previous = app_root / ".template-previous"
    sources = list(files)
    if not sources:
        raise SwapError("template inventory is empty")
    allowed_files = {'Launch-BienTapTay.cmd', 'Launch-Publish.cmd', 'README.md',
                     'release_publish.py', 'release_receipt.py', 'writer_lock.py'}
    for source in sources:
        relative = source.relative_to(template_root)
        if '..' in relative.parts or not relative.parts:
            raise SwapError('invalid template path')
        if relative.parts[0] not in OWNED_TREES and not (
                len(relative.parts) == 1 and relative.name in allowed_files):
            raise SwapError(f'template cannot replace user-owned path: {relative}')
    for leftover in (staging, previous):
        if leftover.exists():
            raise SwapError(f"unfinished prior update; inspect {leftover}")
    app_root.mkdir(parents=True, exist_ok=True)
    moved: list[tuple[Path, Path]] = []
    installed: list[Path] = []
    transaction = SwapTransaction(app_root, staging, previous, moved, installed)
    try:
        for source in sources:
            destination = staging / source.relative_to(template_root)
            destination.parent.mkdir(parents=True, exist_ok=True)
            copy(source, destination)
        previous.mkdir()
        for name in sorted({item.relative_to(template_root).parts[0] for item in sources}):
            live = app_root / name
            if live.exists() or live.is_symlink():
                backup = previous / name
                os.replace(live, backup)
                moved.append((live, backup))
            os.replace(staging / name, live)
            installed.append(live)
    except BaseException as error:
        transaction.rollback()
        if isinstance(error, Exception):
            raise SwapError(f"template update rolled back: {error}") from error
        raise
    return transaction


def swap_template(app_root: Path, template_root: Path, files: Iterable[Path], *,
                  copy: Callable[[Path, Path], object] = shutil.copyfile) -> None:
    begin_swap(app_root, template_root, files, copy=copy).commit()
