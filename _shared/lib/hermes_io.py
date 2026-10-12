"""Unified I/O, Atomic Transactions, File Locking, and Canonical Merge Library.

Contract: CANONICAL-INVARIANTS-V1
Version: 1.0.0
License: MIT
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

CONTRACT_VERSION = "1.0.0"
LOCK_RELATIVE_PATH = Path(".hermes") / "locks" / "canonical.lock"


class LockAcquisitionError(Exception):
    """Raised when file lock acquisition fails or encounters incompatible protocol."""


class InvariantViolationError(Exception):
    """Raised when canonical merge, atomic write, or key integrity check violates invariants."""


# -----------------------------------------------------------------------------
# 1. Atomic Write Protocol [INV-ATOM]
# -----------------------------------------------------------------------------

def atomic_write(path: Path | str, content: str | bytes, encoding: str = "utf-8") -> int:
    """Writes content to a temporary sibling file in the same directory and replaces atomically.
    
    Guarantees:
    - Same-filesystem atomic rename via os.replace (prevents cross-drive EXDEV error).
    - Temporary file is synced before replace to prevent zero-byte corruptions on crash.
    """
    target = Path(path).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    
    # Create temp sibling file directly in the same directory
    prefix = f".tmp.{os.getpid()}."
    is_bytes = isinstance(content, bytes)
    mode = "wb" if is_bytes else "w"
    
    with tempfile.NamedTemporaryFile(
        mode=mode,
        dir=target.parent,
        prefix=prefix,
        suffix=".tmp",
        delete=False,
        encoding=None if is_bytes else encoding,
        newline="" if not is_bytes else None
    ) as tmp:
        tmp_path = Path(tmp.name)
        if is_bytes:
            tmp.write(content)
        else:
            tmp.write(content)
        tmp.flush()
        os.fsync(tmp.fileno())

    # Atomic replace
    os.replace(tmp_path, target)
    return target.stat().st_size


# -----------------------------------------------------------------------------
# 2. Unified Cross-Process Lock Protocol [INV-LOCK]
# -----------------------------------------------------------------------------

class CanonicalLock:
    """Cross-process byte-range lock adhering to <project>/.hermes/locks/canonical.lock."""

    def __init__(
        self,
        project_dir: Path | str,
        owner: str = "hermes_worker",
        timeout: float = 10.0,
        non_blocking: bool = False
    ) -> None:
        self.project_dir = Path(project_dir).resolve()
        self.lock_file = self.project_dir / LOCK_RELATIVE_PATH
        self.owner = owner
        self.timeout = timeout
        self.non_blocking = non_blocking
        self.fd: Optional[int] = None
        self._acquired = False

    def __enter__(self) -> CanonicalLock:
        self.acquire()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.release()

    def acquire(self) -> bool:
        """Acquires lock with OS-level byte-range locking and protocol verification."""
        self.lock_file.parent.mkdir(parents=True, exist_ok=True)
        start_time = time.time()

        while True:
            try:
                # Open or create lock file in read/write mode
                self.fd = os.open(str(self.lock_file), os.O_RDWR | os.O_CREAT, 0o666)
                
                # Pre-extend lock file to at least 1 byte if empty (required for msvcrt.locking stability)
                if os.fstat(self.fd).st_size == 0:
                    os.write(self.fd, b"\x00")
                    os.fsync(self.fd)
                os.lseek(self.fd, 0, os.SEEK_SET)

                # Apply OS-specific lock on sentinel lock file
                if sys.platform == "win32":
                    import msvcrt
                    # Lock first byte (0) with LK_NBLCK (non-blocking)
                    msvcrt.locking(self.fd, msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    flags = fcntl.LOCK_EX | (fcntl.LOCK_NB if self.non_blocking else 0)
                    fcntl.flock(self.fd, flags)

                # Lock granted: write metadata sidecar atomically
                meta = {
                    "version": CONTRACT_VERSION,
                    "pid": os.getpid(),
                    "owner": self.owner,
                    "acquired_at": time.time(),
                }
                meta_file = self.project_dir / LOCK_RELATIVE_PATH.parent / "canonical.lock.json"
                meta_bytes = json.dumps(meta, indent=2).encode("utf-8")
                atomic_write(meta_file, meta_bytes)

                self._acquired = True
                return True

            except (BlockingIOError, OSError) as e:
                if self.fd is not None:
                    try:
                        os.close(self.fd)
                    except OSError:
                        pass
                    self.fd = None

                if self.non_blocking or (time.time() - start_time) >= self.timeout:
                    raise LockAcquisitionError(
                        f"Could not acquire canonical lock at {self.lock_file}: {e} (timed out after {self.timeout}s)"
                    ) from e
                time.sleep(0.1)

    def release(self) -> None:
        """Releases the OS-level lock and closes the file descriptor."""
        if self._acquired and self.fd is not None:
            try:
                if sys.platform == "win32":
                    import msvcrt
                    os.lseek(self.fd, 0, os.SEEK_SET)
                    msvcrt.locking(self.fd, msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(self.fd, fcntl.LOCK_UN)
            except OSError:
                pass
            finally:
                try:
                    os.close(self.fd)
                except OSError:
                    pass
                self.fd = None
                self._acquired = False


# -----------------------------------------------------------------------------
# 3. Exact-Key Matching & Reconcile Protocol [INV-CSV]
# -----------------------------------------------------------------------------

def load_canonical_csv(path: Path | str, encoding: str = "utf-8-sig") -> Tuple[List[Dict[str, str]], List[str]]:
    """Loads CSV and returns list of row dicts and list of header fieldnames."""
    target = Path(path).resolve()
    if not target.exists():
        raise FileNotFoundError(f"Canonical CSV does not exist: {target}")
    
    with open(target, "r", encoding=encoding, newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)
    return rows, fieldnames


def exact_key_merge(
    canonical_rows: List[Dict[str, str]],
    incoming_rows: List[Dict[str, str]],
    key_fields: Tuple[str, ...] = ("domain", "key"),
    target_field: str = "translation_vi",
    status_field: str = "status"
) -> Tuple[List[Dict[str, str]], int, int]:
    """Merges incoming translations into canonical rows strictly by exact composite key.
    
    Invariants enforced:
    - Never overwrites rows marked with 'human_locked' or status == 'human_edited'.
    - Rejects merge if incoming rows contain orphan keys not in canonical set.
    Returns: (merged_rows, updated_count, skipped_locked_count).
    """
    # Build canonical key index
    def make_key(r: Dict[str, str]) -> Tuple[str, ...]:
        return tuple(r.get(k, "").strip() for k in key_fields)

    can_map = {}
    for idx, r in enumerate(canonical_rows):
        k = make_key(r)
        can_map[k] = idx

    # Validate incoming keys
    updated = 0
    skipped_locked = 0
    new_canonical = [dict(r) for r in canonical_rows]

    for inc in incoming_rows:
        k = make_key(inc)
        if k not in can_map:
            raise InvariantViolationError(f"Incoming key {k} is not in the canonical key set [INV-CSV].")

        idx = can_map[k]
        existing = new_canonical[idx]

        # Invariant: preserve human locked entries
        is_human_locked = (
            existing.get("human_locked", "").lower() in ("true", "1") or
            existing.get(status_field, "").strip() == "human_edited"
        )
        if is_human_locked:
            skipped_locked += 1
            continue

        new_val = inc.get(target_field, "")
        if new_val and new_val != existing.get(target_field, ""):
            existing[target_field] = new_val
            if status_field in existing and inc.get(status_field):
                existing[status_field] = inc[status_field]
            updated += 1

    return new_canonical, updated, skipped_locked


# -----------------------------------------------------------------------------
# 4. Checkpoint & Verification Protocol [INV-RB]
# -----------------------------------------------------------------------------

def checkpoint_file(target_file: Path | str, checkpoint_dir: Optional[Path | str] = None) -> Path:
    """Creates an atomic checkpoint of target_file in .checkpoint subdirectory."""
    tgt = Path(target_file).resolve()
    if not tgt.exists():
        raise FileNotFoundError(f"Cannot checkpoint non-existent file: {tgt}")

    ckpt_d = Path(checkpoint_dir).resolve() if checkpoint_dir else tgt.parent / ".checkpoint"
    ckpt_d.mkdir(parents=True, exist_ok=True)
    
    ckpt_path = ckpt_d / f"{tgt.name}.last_valid"
    atomic_write(ckpt_path, tgt.read_bytes())
    return ckpt_path


def restore_checkpoint(target_file: Path | str, checkpoint_dir: Optional[Path | str] = None) -> Path:
    """Restores target_file from its corresponding last_valid checkpoint."""
    tgt = Path(target_file).resolve()
    ckpt_d = Path(checkpoint_dir).resolve() if checkpoint_dir else tgt.parent / ".checkpoint"
    ckpt_path = ckpt_d / f"{tgt.name}.last_valid"
    
    if not ckpt_path.exists():
        raise FileNotFoundError(f"Checkpoint not found for restoration: {ckpt_path}")

    atomic_write(tgt, ckpt_path.read_bytes())
    return tgt


def compute_sha256(path: Path | str) -> str:
    """Computes SHA-256 hash of a file efficiently."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(1024 * 1024):
            h.update(chunk)
    return h.hexdigest()
