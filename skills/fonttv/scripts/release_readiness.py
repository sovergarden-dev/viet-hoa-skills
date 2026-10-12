#!/usr/bin/env python3
"""What is still missing before this build could be released?

Reads a proof-level report (from proof_level_check.py) plus the manifest it was
produced from, and prints the shortest list of unfinished items, grouped so the
work can be handed out. It computes nothing new on purpose: duplicating the
level rules here is how two tools start disagreeing.

The release bar for a localization patch is **every font at archive_verified or
better, and no release blockers**. That bar is what "the game renders Vietnamese
correctly and never overclaims its evidence" actually needs. Per-font runtime
screenshots are a *higher* tier: a screenshot can only be bound to a font whose
consumer is known, so demanding one per font by default costs hours and proves
nothing new about whether the game works. Turn the strict bar on explicitly with
--require-runtime-evidence when a project wants that dossier.

The proof level reported here is never raised by policy: it stays whatever the
evidence files justify.

    release_readiness.py --proof PROOF.json --manifest MANIFEST.json [--json OUT]
                         [--require-runtime-evidence]

Exit: 0 release bar met, 1 items remain, 2 input error.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

RUNTIME = "runtime_verified"
ARCHIVE = "archive_verified"
SHIP_LEVELS = (ARCHIVE, RUNTIME)
RELEASE_ITEMS = ("rights.evidence", "rights.redistribution", "release.clean_install",
                 "release.rollback", "release.signoff")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--proof", type=Path, required=True)
    ap.add_argument("--manifest", type=Path, required=True)
    ap.add_argument("--json", type=Path)
    ap.add_argument("--require-runtime-evidence", action="store_true",
                    help="strict bar: every font also needs a cited per-font runtime screenshot")
    args = ap.parse_args(argv)
    try:
        proof = json.loads(args.proof.read_text(encoding="utf-8"))
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print(f"input error: {exc}", file=sys.stderr)
        return 2
    level = proof.get("justified_proof_level")
    fonts = manifest.get("fonts") or []
    strict = args.require_runtime_evidence
    bar = "strict_with_runtime" if strict else "blockers_clear_and_fonts_archive_verified"
    print(f"justified proof level: {level}   verdict: {proof.get('verdict')}   "
          f"fonts {len(fonts)}  errors {len(proof.get('errors') or [])}")
    print(f"release bar: {bar}")

    per_font = proof.get("per_font") or []
    below_runtime = [f for f in per_font if f.get("level") != RUNTIME]
    below_ship = [f for f in per_font if f.get("level") not in SHIP_LEVELS]
    if below_runtime and not strict:
        print(f"\n1) per-font runtime evidence missing for {len(below_runtime)} font(s) "
              f"- optional tier, not required by this bar:")
        for row in below_runtime[:12]:
            print(f"   {row['name']:36} {row['level']:18} {', '.join(row['blockers'][:1])}")
        if len(below_runtime) > 12:
            print(f"   ... and {len(below_runtime) - 12} more")
        print("   a screenshot can only be bound to a font whose consumer is known;")
        print("   fonts sharing one source design cannot be separated by any screenshot")

    rights, release = manifest.get("rights") or {}, manifest.get("release") or {}
    todo = []
    if not rights.get("evidence") or not rights.get("evidence_sha256"):
        todo.append("rights.evidence: a LICENSE_AUDIT.md file with its sha256")
    if rights.get("redistribution") not in ("verified", "not_distributed"):
        todo.append(f"rights.redistribution: is {rights.get('redistribution')!r}; say 'not_distributed' "
                    "or record the permission")
    for key in ("clean_install", "rollback"):
        item = release.get(key) or {}
        if item.get("status") != "PASS":
            todo.append(f"release.{key}: a report with status PASS (clean install and rollback)")
    outputs = {str(f.get("output_sha256", "")).lower() for f in fonts}
    signed = set()
    for item in release.get("signoff") or []:
        signed |= {str(h).lower() for h in item.get("sha256") or []}
    if not outputs <= signed:
        todo.append(f"release.signoff: {len(outputs - signed)} output hash(es) without a human sign-off record")
    if below_ship:
        named = ", ".join(f"{r['name']}={r['level']}" for r in below_ship[:6])
        more = f" (+{len(below_ship) - 6} more)" if len(below_ship) > 6 else ""
        todo.append(f"fonts.verified: {len(below_ship)} font(s) below {ARCHIVE}: {named}{more}")
    if strict and below_runtime:
        todo.append(f"fonts.runtime: {len(below_runtime)} font(s) without a cited per-font runtime "
                    f"screenshot (strict bar)")
    if todo:
        print(f"\n2) release blockers ({len(todo)}):")
        for line in todo:
            print(f"   - {line}")
    report = {"schema": "fonttv/release-readiness/v1", "justified_proof_level": level,
              "release_bar": bar,
              "fonts_below_runtime": [row["name"] for row in below_runtime],
              "runtime_evidence_missing": [row["name"] for row in below_runtime],
              "optional_evidence": ([] if strict else
                                    [f"runtime screenshot for {row['name']}" for row in below_runtime]),
              "release_blockers": todo, "ready": not todo}
    if args.json:
        args.json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nREADY_FOR_RELEASE = {report['ready']}")
    return 0 if report["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
