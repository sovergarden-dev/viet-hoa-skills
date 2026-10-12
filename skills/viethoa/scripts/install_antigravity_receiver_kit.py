from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        with temporary.open("wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()
    if path.read_bytes() != data:
        raise RuntimeError(f"atomic readback mismatch: {path}")


def read_object(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError(f"{label} unreadable: {path}") from error
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object")
    return value


def require_idle_destination(config: Path) -> None:
    cap_path = config / "hooks/subagent_cap_state.json"
    if cap_path.exists():
        cap = read_object(cap_path, "destination subagent state")
        reservations = cap.get("reservations")
        if cap.get("mode") != "idle_main_only" or cap.get("max_subagents") != 0 or reservations not in ({}, None):
            raise ValueError("destination subagent guard is active; retire the run before installing")
    semantic_path = config / "hooks/semantic_response_guard_state.json"
    if semantic_path.exists():
        semantic = read_object(semantic_path, "destination semantic state")
        if semantic.get("mode") != "inactive" or semantic.get("pending_response") is not None:
            raise ValueError("destination semantic guard is active; retire the run before installing")


def command(python: Path, script: Path, mode: str) -> str:
    executable = str(python.resolve())
    if any(character.isspace() for character in executable):
        raise ValueError("receiver Python path must be whitespace-free for Antigravity hooks")
    if any(character in executable for character in '"\'`;&|<>(){}'):
        raise ValueError("receiver Python path contains unsafe shell characters")
    return f"{executable} -X utf8 {script.resolve()} {mode}"


def hook_entry(matcher: str, command_line: str) -> dict[str, Any]:
    return {
        "matcher": matcher,
        "hooks": [{"type": "command", "command": command_line, "timeout": 5}],
    }


def generated_hooks(config: Path, python: Path) -> dict[str, Any]:
    cap = config / "hooks/subagent_cap.py"
    semantic = config / "hooks/semantic_response_guard.py"
    cap_pre = command(python, cap, "pre")
    semantic_pre = command(python, semantic, "pre")
    return {
        "subagent-phase-control": {
            "PreToolUse": [hook_entry(name, cap_pre) for name in ("invoke_subagent", "send_message", "manage_subagents")],
            "PostToolUse": [hook_entry("invoke_subagent", command(python, cap, "post"))],
            "Stop": [{"type": "command", "command": command(python, cap, "stop"), "timeout": 5}],
        },
        "semantic-response-origin": {
            "PreToolUse": [
                hook_entry(name, semantic_pre)
                for name in (
                    "run_command", "write_to_file", "replace_file_content", "multi_replace_file_content",
                    "edit_file", "create_file", "delete_file", "move_file", "rename_file", "apply_patch",
                    "view_file", "grep_search", "find_by_name", "list_dir",
                )
            ],
            "PostToolUse": [hook_entry("write_to_file", command(python, semantic, "post"))],
        },
    }


def backup_existing(paths: list[Path], backup_root: Path) -> list[str]:
    copied: list[str] = []
    for path in paths:
        if not path.is_file():
            continue
        relative = path.anchor.replace(":", "") + path.as_posix().replace(":", "")
        destination = backup_root / relative.lstrip("/")
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, destination)
        copied.append(str(path))
    return copied


def merge_settings(destination: Path, portable: dict[str, Any]) -> bytes:
    current = read_object(destination, "destination config") if destination.exists() else {}
    current_settings = current.get("userSettings")
    if not isinstance(current_settings, dict):
        current_settings = {}
    incoming = portable.get("userSettings")
    if not isinstance(incoming, dict):
        raise ValueError("portable settings missing userSettings")
    current["userSettings"] = {**current_settings, **incoming}
    return (json.dumps(current, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def install(args: argparse.Namespace) -> dict[str, Any]:
    bundle = Path(args.bundle_root).resolve()
    target_home = Path(args.target_home).resolve()
    receiver_python = Path(args.python).resolve()
    manifest = read_object(bundle / "receiver-kit-manifest.json", "receiver kit manifest")
    files = manifest.get("files")
    if not isinstance(files, dict) or not files:
        raise ValueError("receiver kit manifest file map missing")
    for relative, descriptor in files.items():
        if not isinstance(relative, str) or not isinstance(descriptor, dict):
            raise ValueError("receiver kit manifest descriptor malformed")
        path = (bundle / relative).resolve()
        try:
            path.relative_to(bundle)
        except ValueError as error:
            raise ValueError("receiver kit member escapes bundle root") from error
        if not path.is_file() or descriptor.get("sha256") != sha256_bytes(path.read_bytes()) or descriptor.get("size") != path.stat().st_size:
            raise ValueError(f"receiver kit member hash/size mismatch: {relative}")

    gemini = target_home / ".gemini"
    config = gemini / "config"
    require_idle_destination(config)
    destinations = {
        "receiver/GEMINI.md": gemini / "GEMINI.md",
        "receiver/skills/dichgame/SKILL.md": config / "skills/dichgame/SKILL.md",
        "receiver/hooks/subagent_cap.py": config / "hooks/subagent_cap.py",
        "receiver/hooks/semantic_response_guard.py": config / "hooks/semantic_response_guard.py",
    }
    if args.apply_settings:
        destinations["receiver/config.json"] = config / "config.json"
    hooks_path = config / "hooks.json"
    backup_paths = list(destinations.values()) + [hooks_path]
    stamp = datetime.now().strftime("%Y%m%dT%H%M%S")
    backup_root = target_home / "Antigravity-backups/receiver-kit" / stamp
    backups = backup_existing(backup_paths, backup_root)

    installed: dict[str, str] = {}
    for relative, destination in destinations.items():
        source = bundle / relative
        if relative == "receiver/config.json":
            payload = merge_settings(destination, read_object(source, "portable config"))
        else:
            payload = source.read_bytes()
        atomic_write(destination, payload)
        installed[str(destination)] = sha256_bytes(payload)

    hooks = read_object(hooks_path, "destination hooks") if hooks_path.exists() else {}
    hooks.update(generated_hooks(config, receiver_python))
    hooks_payload = (json.dumps(hooks, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    atomic_write(hooks_path, hooks_payload)
    installed[str(hooks_path)] = sha256_bytes(hooks_payload)

    for script in (config / "hooks/subagent_cap.py", config / "hooks/semantic_response_guard.py"):
        result = subprocess.run(
            [str(receiver_python), "-X", "utf8", "-B", str(script), "--self-test"],
            text=True, capture_output=True, check=False,
        )
        if result.returncode:
            raise RuntimeError(f"receiver hook self-test failed: {script}: {(result.stderr or result.stdout).strip()}")

    receipt = {
        "schema": "agy-receiver-kit-install-receipt/v1",
        "status": "installed_idle_receiver_config",
        "contract": manifest.get("contract"),
        "target_home": str(target_home),
        "python": str(receiver_python),
        "settings_applied": bool(args.apply_settings),
        "installed": installed,
        "backup_root": str(backup_root) if backups else None,
        "backed_up": backups,
        "active_authorization_imported": False,
        "history_or_account_session_imported": False,
    }
    receipt_path = config / "receiver-kit-install-receipt.json"
    atomic_write(receipt_path, (json.dumps(receipt, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    return receipt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Install a sanitized Antigravity localization receiver kit.")
    parser.add_argument("--bundle-root", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--target-home", type=Path, default=Path.home())
    parser.add_argument("--python", type=Path, default=Path(sys.executable))
    parser.add_argument("--apply-settings", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = install(args)
        print(json.dumps({
            "status": result["status"],
            "contract": result["contract"],
            "receipt": str(Path(args.target_home).resolve() / ".gemini/config/receiver-kit-install-receipt.json"),
        }, ensure_ascii=False, sort_keys=True))
        return 0
    except (OSError, UnicodeError, ValueError, RuntimeError, json.JSONDecodeError) as error:
        print(f"FAIL: {type(error).__name__}: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
