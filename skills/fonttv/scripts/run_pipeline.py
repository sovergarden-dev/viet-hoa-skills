#!/usr/bin/env python3
"""Run a font pipeline as an ordered list of steps and stop at the first failure.

Rounds of this work were driven by five or six hand-typed commands, and a step
that was forgotten looked exactly like a step that passed. This harness takes
the steps from a JSON file, refuses to continue after the first non-zero exit,
and writes one receipt with every command, exit code and the tail of its output.

    run_pipeline.py --plan PLAN.json [--json RECEIPT.json] [--dry-run]

PLAN.json:
{
  "schema": "fonttv/pipeline-plan/v1",
  "root": "tests/fixtures/sample_project",
  "python": "python",
  "steps": [
    {"name": "build",  "argv": ["scripts/p1_replace_pipeline.py"], "expect": 0},
    {"name": "audit",  "argv": ["scripts/fonttv_v9_audit.py"],     "expect": 0, "allow": [0]},
    {"name": "proof",  "argv": [".../proof_level_check.py", "reports/p1_manifest.json"],
     "expect": 0, "tail": 20}
  ]
}

``expect`` defaults to 0. ``allow`` lists acceptable exit codes when a step is
informational. Nothing runs with ``--dry-run``, which prints the resolved
command lines so the plan can be reviewed before it touches anything.

Exit: 0 every step as expected, 1 a step failed, 2 plan error.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

SCHEMA = "fonttv/pipeline-plan/v1"


def load_plan(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema") != SCHEMA:
        raise ValueError(f"{path}: schema must be {SCHEMA}")
    steps = data.get("steps")
    if not isinstance(steps, list) or not steps:
        raise ValueError(f"{path}: 'steps' must be a non-empty list")
    for index, step in enumerate(steps):
        if not isinstance(step, dict) or not step.get("name") or not isinstance(step.get("argv"), list):
            raise ValueError(f"{path}: step[{index}] needs 'name' and 'argv'")
    return data


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--plan", type=Path, required=True)
    ap.add_argument("--json", type=Path)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    try:
        plan = load_plan(args.plan)
    except (OSError, ValueError) as exc:
        print(f"plan error: {exc}", file=sys.stderr)
        return 2
    root = Path(plan.get("root") or ".").resolve()
    python = plan.get("python") or sys.executable
    receipt = {"schema": "fonttv/pipeline-receipt/v1", "plan": str(args.plan),
               "root": str(root), "dry_run": bool(args.dry_run), "steps": []}
    def resolve(value: str) -> str:
        """Only rewrite a real relative path that exists under root.

        Resolving every argument turned flags into paths (`<root>/--font`) and the
        first real run stopped on exit 2. Steps run with cwd=root, so anything left
        alone still resolves the way the child process expects.
        """
        if value.startswith("-") or Path(value).is_absolute():
            return value
        candidate = root / value
        return str(candidate) if candidate.exists() else value

    for step in plan["steps"]:
        argv = [str(a) for a in step["argv"]]
        # A step is either a script path or python flags (`-c ...`); both need the
        # interpreter. Only prefixing ".py" made an inline check try to execute "-c".
        if argv[0].endswith(".py") or argv[0].startswith("-"):
            argv = [python] + argv
        cmd = [resolve(a) for a in argv]
        allowed = step.get("allow") or [step.get("expect", 0)]
        print(f"$ {' '.join(cmd)}", flush=True)
        if args.dry_run:
            receipt["steps"].append({"name": step["name"], "argv": cmd, "exit_code": None, "status": "DRY_RUN"})
            continue
        proc = subprocess.run(cmd, cwd=str(root), capture_output=True, text=True, errors="replace")
        tail = "\n".join((proc.stdout or "").splitlines()[-int(step.get("tail", 12)):])
        print(tail)
        status = "PASS" if proc.returncode in allowed else "FAIL"
        receipt["steps"].append({"name": step["name"], "argv": cmd, "exit_code": proc.returncode,
                                 "status": status, "allowed": allowed,
                                 "stdout_tail": tail, "stderr_tail": (proc.stderr or "")[-800:]})
        if status == "FAIL":
            print(f"\nSTOP: {step['name']} exited {proc.returncode}, allowed {allowed}")
            receipt["stopped_at"] = step["name"]
            receipt["all_pass"] = False
            if args.json:
                args.json.write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
            return 1
    receipt["all_pass"] = all(s["status"] in ("PASS", "DRY_RUN") for s in receipt["steps"])
    if args.json:
        args.json.write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nPIPELINE_ALL_PASS = {receipt['all_pass']} ({len(receipt['steps'])} steps)")
    return 0 if receipt["all_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
