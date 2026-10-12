#!/usr/bin/env python3
"""Repository Hygiene, Path Sanitization, and Security Audit Tool.

Checks:
1. No absolute machine paths (C:/Users/rurus, G:/AI/hermes, D:/SteamLibrary)
2. No leaked tokens (gho_, personal auth tokens)
3. No internal email domains (@bot.cue.im, @cue.im)
4. No binary game assets or compiled artifacts (*.bundle, *.dll, *.assets, *.pyc)
5. File size limits (warn if single file > 1MB)
6. SKILL.md token budget (< 15KB per skill)

Usage:
  python tools/check_hygiene.py [--fix]
"""

import os
import re
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
SKILLS_DIR = ROOT_DIR / "skills"

DISALLOWED_PATTERNS = [
    (r"c:[/\\]users[/\\]rurus", "<USER_HOME>", "Absolute user home path"),
    (r"g:[/\\]ai[/\\]hermes", "<PROJECT_ROOT>", "Absolute hermes dev workspace"),
    (r"d:[/\\]steamlibrary", "<STEAM_ROOT>", "Absolute steam library path"),
    (r"[\w\.-]+@(bot\.cue\.im|cue\.im)", "<REDACTED_EMAIL>", "Internal bot email"),
    (r"gho_[a-zA-Z0-9_]{30,}", "<GITHUB_TOKEN_REDACTED>", "Leaked GitHub token"),
    # C26 Dogfood isolation barrier: prevent internal game project names from leaking into public repo
    (r"\b(?:Well_Dweller|Third_Crisis|Neon_Night_18|Bo_Teal_Lotus|Apocalypse_with_Femboy)\b", "<INTERNAL_GAME_NAME>", "Internal commercial game workspace leakage"),
]

BANNED_EXTENSIONS = {".pyc", ".dll", ".bundle", ".assets", ".exe", ".pak", ".ucas", ".utoc"}
MAX_FILE_SIZE_BYTES = 1024 * 1024  # 1 MB


# Files allowed to declare disallowed patterns as part of security/scanner definitions
ALLOWLIST_SCANNER_FILES = {
    "lint_skill_package.py",
    "check_hygiene.py",
}


def scan_file(path: Path) -> list[tuple[str, str]]:
    issues = []
    
    # 1. Extension check
    if path.suffix.lower() in BANNED_EXTENSIONS:
        issues.append(("BANNED_EXTENSION", f"File extension '{path.suffix}' is disallowed in git."))
        return issues

    # 2. Size check
    sz = path.stat().st_size
    if sz > MAX_FILE_SIZE_BYTES:
        issues.append(("FILE_SIZE_EXCEEDED", f"Size {sz:,} bytes exceeds 1MB limit."))

    # 3. Content pattern check (skip known scanner definitions)
    if path.name in ALLOWLIST_SCANNER_FILES:
        return issues

    try:
        content = path.read_text(encoding="utf-8", errors="ignore")
        for regex, _, desc in DISALLOWED_PATTERNS:
            matches = re.findall(regex, content, flags=re.IGNORECASE)
            if matches:
                issues.append(("LEAKED_PATH_OR_SECRET", f"{desc} found ({len(matches)} occurrences)"))
    except Exception as e:
        issues.append(("READ_ERROR", str(e)))

    return issues


def sanitize_file(path: Path) -> int:
    """Replaces disallowed machine paths with portable placeholders."""
    try:
        content = path.read_text(encoding="utf-8")
        original = content
        for regex, replacement, _ in DISALLOWED_PATTERNS:
            content = re.sub(regex, replacement, content, flags=re.IGNORECASE)
        if content != original:
            path.write_text(content, encoding="utf-8")
            return 1
    except Exception:
        pass
    return 0


def main() -> int:
    do_fix = "--fix" in sys.argv
    print(f"=== Running Hygiene & Security Audit on {ROOT_DIR} ===")

    total_files = 0
    total_issues = 0
    files_fixed = 0

    # Scan the entire repository root (excluding .git)
    for path in ROOT_DIR.rglob("*"):
        if not path.is_file() or ".git" in path.parts:
            continue
        total_files += 1

        issues = scan_file(path)
        if issues:
            rel = path.relative_to(ROOT_DIR)
            for code, msg in issues:
                total_issues += 1
                print(f"  [{code:20}] {rel}: {msg}")

            if do_fix:
                if sanitize_file(path):
                    files_fixed += 1

    # Check SKILL.md sizes
    print("\n=== SKILL.md Size & Budget Audit ===")
    for skill_dir in SKILLS_DIR.iterdir():
        if not skill_dir.is_dir():
            continue
        skill_md = skill_dir / "SKILL.md"
        if skill_md.exists():
            sz = skill_md.stat().st_size
            status = "OK (< 15KB)" if sz <= 15360 else "WARN (> 15KB - needs trimming)"
            print(f"  {skill_dir.name:15}: {sz:6,} bytes | {status}")

    print(f"\nAudit complete: {total_files} files scanned, {total_issues} issues found.")
    if do_fix:
        print(f"Sanitization applied: {files_fixed} files sanitized.")

    return 1 if total_issues > 0 and not do_fix else 0


if __name__ == "__main__":
    sys.exit(main())
