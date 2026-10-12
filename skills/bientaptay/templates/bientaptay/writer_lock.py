from __future__ import annotations

import argparse
import msvcrt
import subprocess
import sys
import time
from pathlib import Path
from types import TracebackType
from typing import BinaryIO


LOCK_FILE_NAME = ".bientaptay.writer.lock"


class WriterLockBusy(RuntimeError):
    pass


def lock_path(project: Path) -> Path:
    return project.resolve().parent / LOCK_FILE_NAME


class WriterLock:
    def __init__(self, project: Path) -> None:
        self.path = lock_path(project)
        self._handle: BinaryIO | None = None

    def __enter__(self) -> "WriterLock":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        handle = self.path.open("a+b")
        try:
            handle.seek(0, 2)
            if handle.tell() == 0:
                handle.write(b"\0")
                handle.flush()
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError as exc:
            handle.close()
            raise WriterLockBusy(str(self.path)) from exc
        self._handle = handle
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
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


def build_parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Share the bientaptay project writer lock.")
    commands = root.add_subparsers(dest="command_name", required=True)
    for name in ("probe", "hold", "run"):
        command = commands.add_parser(name)
        command.add_argument("--project", type=Path, required=True)
        if name == "hold":
            command.add_argument("--seconds", type=float, default=30)
        if name == "run":
            command.add_argument("command", nargs=argparse.REMAINDER)
    return root


def main() -> int:
    args = build_parser().parse_args()
    try:
        with WriterLock(args.project) as acquired:
            print(f"LOCKED {acquired.path}", flush=True)
            if args.command_name == "hold":
                time.sleep(max(0, args.seconds))
            elif args.command_name == "run":
                command = list(args.command)
                if command and command[0] == "--":
                    command = command[1:]
                if not command:
                    raise SystemExit("run requires a command after --")
                return subprocess.run(command, check=False).returncode
            return 0
    except WriterLockBusy as exc:
        print(f"LOCK-REFUSED {exc}", flush=True)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
