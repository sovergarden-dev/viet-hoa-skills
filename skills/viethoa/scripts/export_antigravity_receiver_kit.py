from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import zipfile
from pathlib import Path
from typing import Any

BASELINE = "AGY-VIETHOA-HANDOFF/2.5-TWO-PHASE-DRAFT12-PREVIEW-FINAL0-GUARDED"
SCHEMA = "agy-portable-receiver-kit/v1"
PORTABLE_SETTINGS = {
    "artifactReviewMode", "autoExecutionPolicy", "browserJsExecutionPolicy",
    "disableAgenticFeaturesOutsideAllowlist", "enableTerminalSandbox",
    "messageDeliveryStrategy", "nonWorkspaceFileAccessPolicy", "remoteAgent",
    "sandboxAllowNetwork", "use1PAutocomplete", "useAiCredits",
    "autoContinueOnMaxGeneratorInvocations",
}
SECRET_BYTES = (
    re.compile(rb"AIza[0-9A-Za-z_-]{20,}"),
    re.compile(rb"gh[opusr]_[0-9A-Za-z]{20,}"),
    re.compile(rb"sk-[0-9A-Za-z_-]{20,}"),
    re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
)
README = """ANTIGRAVITY RECEIVER KIT — VIỆT HÓA

1. Cài Antigravity bằng official installer: https://antigravity.google/download
2. Mở ứng dụng một lần và đăng nhập tài khoản thủ công. Không sao chép cookie, keyring hoặc account/session từ máy cũ.
3. Cài Python vào đường dẫn không có khoảng trắng.
4. Giải nén kit, rồi chạy:
   python -B install_receiver_kit.py --apply-settings
5. Mở Antigravity, tạo Project mới và trỏ tới thư mục package/work của đúng dự án.
6. Chạy self-test/host preparation của package trước khi arm. Mỗi package/run chỉ có one active authoring host.

Kit chỉ chứa global rule, skill dichgame, hai guard ở trạng thái code-only và settings allowlist. Kit không chứa app binary, project, conversation/history, browser profile, account/session, MCP secrets, authorization, state hoặc event ledger. Trên máy đích phải materialize authorization mới theo absolute paths mới.
"""


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_object(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError(f"{label} unreadable: {path}") from error
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object")
    return value


def sanitize_config(path: Path) -> bytes:
    value = read_object(path, "Antigravity config")
    settings = value.get("userSettings")
    if not isinstance(settings, dict):
        settings = {}
    portable = {key: settings[key] for key in sorted(PORTABLE_SETTINGS & settings.keys())}
    return (json.dumps({"userSettings": portable}, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def ensure_safe(relative: str, payload: bytes) -> None:
    if any(pattern.search(payload) for pattern in SECRET_BYTES):
        raise ValueError(f"credential-like bytes rejected from receiver kit: {relative}")
    if re.search(rb"(?i)[a-z]:[/\\]users[/\\][^/\\\s\"']+", payload):
        raise ValueError(f"source user path rejected from receiver kit: {relative}")
    if re.search(rb"(?i)/(?:home|users)/[^/\s\"']+", payload):
        raise ValueError(f"source home path rejected from receiver kit: {relative}")


def deterministic_zip(path: Path, files: dict[str, bytes]) -> None:
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for relative in sorted(files):
                info = zipfile.ZipInfo(relative, (1980, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o100644 << 16
                archive.writestr(info, files[relative])
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()
    with zipfile.ZipFile(path) as archive:
        if archive.testzip() is not None or archive.namelist() != sorted(files):
            raise RuntimeError("receiver kit ZIP readback failed")


def build(args: argparse.Namespace) -> dict[str, Any]:
    gemini = Path(args.gemini_root).resolve()
    output = Path(args.output).resolve()
    skill_root = Path(__file__).resolve().parents[1]
    sources = {
        "receiver/GEMINI.md": gemini / "GEMINI.md",
        "receiver/skills/dichgame/SKILL.md": gemini / "config/skills/dichgame/SKILL.md",
        "receiver/hooks/subagent_cap.py": gemini / "config/maintenance/subagent_cap.template.py",
        "receiver/hooks/semantic_response_guard.py": gemini / "config/maintenance/semantic_response_guard.template.py",
        "install_receiver_kit.py": skill_root / "scripts/install_antigravity_receiver_kit.py",
    }
    if any(not path.is_file() for path in sources.values()) or not (gemini / "config/config.json").is_file():
        raise ValueError("portable receiver source files are incomplete")
    files = {relative: path.read_bytes() for relative, path in sources.items()}
    files["receiver/config.json"] = sanitize_config(gemini / "config/config.json")
    files["README_MIGRATION_VI.txt"] = README.encode("utf-8")
    for relative, payload in files.items():
        ensure_safe(relative, payload)
    if BASELINE.encode("utf-8") not in files["receiver/GEMINI.md"] or BASELINE.encode("utf-8") not in files["receiver/skills/dichgame/SKILL.md"]:
        raise ValueError("receiver rules/skill do not use the current baseline")

    descriptors = {
        relative: {"size": len(payload), "sha256": sha256_bytes(payload)}
        for relative, payload in sorted(files.items())
    }
    manifest = {
        "schema": SCHEMA,
        "contract": BASELINE,
        "state": "safe_config_only_no_auth_or_history",
        "files": descriptors,
        "excluded": [
            "application binaries and updater", "account/session and cookies", "MCP config and secrets",
            "projects and absolute paths", "conversations/history/brain", "browser profile",
            "active authorization/state/event ledgers", "cache/log/crash data",
        ],
        "destination_requires_fresh_authorization": True,
        "one_active_authoring_host_per_package_run": True,
    }
    files["receiver-kit-manifest.json"] = (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    deterministic_zip(output, files)
    raw = output.read_bytes()
    return {
        "status": "exported_safe_receiver_kit",
        "contract": BASELINE,
        "output": str(output),
        "size": len(raw),
        "sha256": sha256_bytes(raw),
        "file_count": len(files),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export sanitized Antigravity receiver configuration without app/account/history state.")
    parser.add_argument("--gemini-root", type=Path, default=Path.home() / ".gemini")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        print(json.dumps(build(args), ensure_ascii=False, sort_keys=True))
        return 0
    except (OSError, UnicodeError, ValueError, RuntimeError, json.JSONDecodeError, zipfile.BadZipFile) as error:
        print(f"FAIL: {type(error).__name__}: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
