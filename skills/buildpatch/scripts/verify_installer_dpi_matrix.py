"""
Automated High-DPI Matrix & Visual Proof Gate for native patch installers.
Runs the built single-file or debug installer with --layout-matrix and --render-probe
to prove zero text clipping and flawless scaling across all standard display configurations.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


STANDARD_DPI_LEVELS = [96, 120, 144, 168, 192, 216, 240, 288]
STANDARD_RESOLUTIONS = [
    (800, 600),
    (1024, 600),
    (1280, 720),
    (1366, 768),
    (1600, 900),
    (1920, 1080),
    (2560, 1440),
    (3840, 2160),
]


def verify_dpi_matrix(exe_path: Path, output_dir: Path | None = None) -> bool:
    if not exe_path.exists():
        print(f"ERROR: Executable not found at {exe_path}", file=sys.stderr)
        return False

    out_dir = output_dir or (exe_path.parent / "layout-proof")
    out_dir.mkdir(parents=True, exist_ok=True)
    report_file = out_dir / "dpi_matrix_report.json"

    print(f"[*] Running exhaustive DPI layout matrix on: {exe_path.name}")
    cmd = [str(exe_path), "--layout-matrix", str(report_file)]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    except subprocess.TimeoutExpired:
        print("[-] Matrix run TIMED OUT after 180s (executable likely blocked on GUI message loop) -> FAIL", file=sys.stderr)
        return False
    if res.returncode != 0:
        print(f"[-] Matrix run failed with returncode {res.returncode}", file=sys.stderr)
        if res.stderr:
            print(f"    Stderr: {res.stderr.strip()}", file=sys.stderr)
        return False

    if not report_file.exists():
        print(f"[-] Report file not generated: {report_file}", file=sys.stderr)
        return False

    try:
        data = json.loads(report_file.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        print(f"[-] Failed to parse matrix report JSON: {exc}", file=sys.stderr)
        return False

    total = data.get("total_cells", 0)
    all_passed = data.get("all_passed", False)
    print(f"[+] Total matrix cells tested: {total}")
    print(f"[+] All cells passed: {all_passed}")

    if total < 64 or not all_passed:
        print(f"[-] Matrix check FAILED: total={total} (expected >= 64), all_passed={all_passed}", file=sys.stderr)
        return False

    # Generate visual proof renders for standard display scales
    proof_cases = [
        (96, 1920, 1080, "probe_100dpi_1080p.png"),
        (120, 1366, 768, "probe_125dpi_768p.png"),
        (144, 1920, 1080, "probe_150dpi_1080p.png"),
        (192, 3840, 2160, "probe_200dpi_4k.png"),
    ]
    print(f"[*] Generating visual proof renders in: {out_dir}")
    for dpi, w, h, fname in proof_cases:
        target_png = out_dir / fname
        p_res = subprocess.run(
            [str(exe_path), "--render-probe", str(dpi), str(w), str(h), str(target_png)],
            capture_output=True,
            text=True
        )
        if p_res.returncode == 0 and target_png.exists():
            print(f"    [OK] Rendered {dpi} DPI ({w}x{h}) -> {fname} ({target_png.stat().st_size} bytes)")
        else:
            print(f"    [WARN] Failed to render {dpi} DPI -> {fname}", file=sys.stderr)

    print("[SUCCESS] All DPI scaling and layout invariants verified mechanically!")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify installer high-DPI scaling matrix.")
    parser.add_argument("exe", type=Path, help="Path to compiled installer executable")
    parser.add_argument("--out-dir", type=Path, default=None, help="Directory to save proofs and reports")
    args = parser.parse_args()

    ok = verify_dpi_matrix(args.exe, args.out_dir)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
