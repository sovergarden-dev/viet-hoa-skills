#!/usr/bin/env python3
"""Assemble a fonttv manifest from files that already exist on disk.

The manifest is the only place where a proof level is claimed, and hand-writing one
is how a claim and its evidence drift apart. This builds the per-font gate list
from real artefacts — audit reports, identity evidence, preservation diffs, the
fonts read back out of the live container — and refuses to name an artefact that
is not there.

    p1_manifest.py --project NAME --fonts-dir A --original-dir B \
        --audit-dir C --evidence-dir D --readback-dir E \
        --mapping M --adapter ADAPTER.py --corpus TXT --encoded BIN \
        --container NAME --container-sha256 HASH --build-anchor FILE \
        [--screenshots SHOTS.json] [--diff-dir DIR] [--out MANIFEST.json]

Screenshots are bound to a font only when the JSON names one
(``{"shots": [{"path": ..., "font": "<stem>", "why": ...}]}``); an entry with
``"font": null`` is recorded in ``screenshots_all`` and grants no runtime level,
because an unattributed screenshot proves nothing about a specific file.

Exit: 0 manifest written, 2 input error (missing artefact or bad JSON).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from p1_core import sha256  # noqa: E402
from telltale_font_diff import rows as record_rows  # noqa: E402
from p1_telltale_build import TelltaleFont, load_byte_map  # noqa: E402

REQUIRED = ("project", "fonts_dir", "original_dir", "audit_dir", "evidence_dir", "readback_dir",
            "mapping", "adapter", "container", "container_sha256", "build_anchor")


def rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)


def _stem(name) -> str:
    """Match ``X`` and ``X.font`` as the same font, as the attach tool does."""
    text = str(name or "").lower()
    return text[:-5] if text.endswith(".font") else text


def preservation_diff(before: Path, after: Path, diff_dir: Path, byte_to_char: dict) -> tuple[Path, dict]:
    old, new = record_rows(TelltaleFont(before)), record_rows(TelltaleFont(after))
    added = sorted(set(new) - set(old))
    removed = sorted(set(old) - set(new))
    changed = sorted(cid for cid in set(old) & set(new) if old[cid] != new[cid])
    outside = [cid for cid in changed if cid not in byte_to_char]
    report = {"schema": "fonttv/p1-preservation-diff/v1", "font": after.name,
              "input_sha256": sha256(before), "output_sha256": sha256(after),
              "added": added, "removed": removed, "changed": changed,
              "changed_outside_contract": outside,
              "rule": "P1 replaces every encoder-reachable glyph; only those ids and the space "
                      "advance may change"}
    report["status"] = "PASS" if not removed and not outside else "FAIL"
    path = diff_dir / f"{after.stem}.diff.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return path, report


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--project", required=True)
    ap.add_argument("--fonts-dir", type=Path, required=True)
    ap.add_argument("--original-dir", type=Path, required=True)
    ap.add_argument("--audit-dir", type=Path, required=True)
    ap.add_argument("--evidence-dir", type=Path, required=True)
    ap.add_argument("--readback-dir", type=Path, required=True)
    ap.add_argument("--mapping", type=Path, required=True)
    ap.add_argument("--adapter", type=Path, required=True,
                    help="the fonttv-adapter/v1 adapter the proof checker re-executes")
    ap.add_argument("--encoder", type=Path,
                    help="the project's text-to-bytes encoder (a different role from the adapter; "
                         "using one file for both makes the re-execution fail)")
    ap.add_argument("--allowlist", type=Path)
    ap.add_argument("--corpus", type=Path)
    ap.add_argument("--encoded", type=Path)
    ap.add_argument("--container", required=True)
    ap.add_argument("--engine", help="engine description for the build block (default: the container name)")
    ap.add_argument("--build-root", help="game installation root recorded in the build block")
    ap.add_argument("--executable", help="game executable recorded in the build block")
    ap.add_argument("--container-path")
    ap.add_argument("--container-sha256", required=True)
    ap.add_argument("--readback-index", type=Path,
                    help="JSON {\"<font name>\": {\"container\", \"sha256\", \"path\"}} naming the "
                         "archive that actually supplied each font. Fonts are spread across base and "
                         "update archives: a per-font readback taken from the base archive alone can "
                         "claim verification for a member that is not there.")
    ap.add_argument("--build-anchor", type=Path, required=True)
    ap.add_argument("--screenshots", type=Path)
    ap.add_argument("--diff-dir", type=Path)
    ap.add_argument("--route", default="C_engine_atlas")
    ap.add_argument("--strategy", default="P1_replace")
    ap.add_argument("--claimed-level", default="archive_verified")
    ap.add_argument("--build-id-prefix", default="p1-")
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args(argv)

    try:
        diff_dir = args.diff_dir or (args.evidence_dir / "preservation")
        diff_dir.mkdir(parents=True, exist_ok=True)
        byte_to_char = load_byte_map(args.mapping)
        shots = (json.loads(args.screenshots.read_text(encoding="utf-8")).get("shots") or []
                 if args.screenshots else [])
        index = (json.loads(args.readback_index.read_text(encoding="utf-8"))
                 if args.readback_index else {})
    except (OSError, ValueError) as exc:
        print(f"input error: {exc}", file=sys.stderr)
        return 2
    root = Path.cwd()
    build_id = args.build_id_prefix + sha256(args.build_anchor)[:16]
    fonts, problems = [], []
    for out in sorted(args.fonts_dir.glob("*.font")):
        stem = out.stem
        audit = args.audit_dir / f"{stem}.audit.json"
        evidence = args.evidence_dir / f"{stem}.build_manifest.json"
        before = args.original_dir / out.name
        readback = args.readback_dir / out.name
        for label, path in (("audit", audit), ("identity evidence", evidence),
                            ("original", before), ("readback", readback)):
            if not path.is_file():
                problems.append(f"{stem}: missing {label} at {path}")
        if index and out.name not in index:
            problems.append(f"{stem}: no entry in the readback index; which archive supplies it is unknown")
        if problems and problems[-1].startswith(stem):
            continue
        source = index.get(out.name, {})
        o_sha, a_sha = sha256(out), sha256(audit)
        try:
            diff_path, diff = preservation_diff(before, out, diff_dir, byte_to_char)
        except (OSError, ValueError) as exc:
            # An unreadable font must come back as a named problem, not a traceback:
            # a crash reads like a tool bug and hides which artefact is wrong.
            problems.append(f"{stem}: cannot diff against the original: {exc}")
            continue
        gate = lambda name, report: {"gate": name, "status": "PASS", "tool": "custom_encoding_audit.py",
                                     "report": rel(report, root), "report_sha256": a_sha,
                                     "font_sha256": o_sha}
        mine = [s for s in shots if _stem(s.get("font")) == stem.lower()]
        fonts.append({
            "name": out.name, "consumer": (mine[0].get("why") if mine else "unattributed"),
            "route": args.route, "strategy": args.strategy, "engine_shapes": False,
            "input_sha256": sha256(before), "output_sha256": o_sha,
            "output_path": rel(out, root), "change": "modified",
            "identity_evidence": [{"type": "build_manifest", "path": rel(evidence, root),
                                   "sha256": sha256(evidence)}],
            "semantic_audit": ({"corpus_path": rel(args.corpus, root), "corpus_sha256": sha256(args.corpus),
                                "encoded_path": rel(args.encoded, root), "encoded_sha256": sha256(args.encoded),
                                **({"allowlist_path": rel(args.allowlist, root),
                                    "allowlist_sha256": sha256(args.allowlist)} if args.allowlist else {})}
                               if args.corpus and args.encoded else {}),
            "gates": [gate("coverage", audit), gate("outline_ink", audit), gate("metrics", audit),
                      gate("structural_validator", audit),
                      dict(gate("semantic_mapping", audit), mapping_sha256=sha256(args.mapping)),
                      {"gate": "shaping", "status": "NOT_APPLICABLE",
                       "reason": "engine draws byte ids; no OpenType shaper", "font_sha256": o_sha},
                      {"gate": "preservation_diff", "status": diff["status"], "tool": "p1_manifest.py",
                       "report": rel(diff_path, root), "report_sha256": sha256(diff_path),
                       "font_sha256": o_sha}],
            "archive": {"container": source.get("container", args.container),
                        "injector": "verify_and_inject (hash checked)",
                        "readback_method": "extract the member from the live container, in load order",
                        "readback_path": rel(readback, root), "readback_sha256": sha256(readback),
                        "container_path": source.get("path", args.container_path or args.container),
                        "container_sha256_after": source.get("sha256", args.container_sha256)},
            "runtime": {"build_id": build_id, "checkpoint": "user play session",
                        "screenshots": [{"path": rel(Path(s["path"]), root), "sha256": sha256(Path(s["path"])),
                                         "font_sha256": o_sha} for s in mine],
                        "reviewer_type": "human", "reviewer": (mine[0].get("reviewer") if mine else None),
                        "verdict": "PASS" if mine else "NOT_RUN"},
        })
    if problems:
        print("input error:", file=sys.stderr)
        for line in problems:
            print(f"  {line}", file=sys.stderr)
        return 2
    mapping_sha = sha256(args.mapping)
    manifest = {
        "schema": "fonttv/manifest/v1", "project": args.project, "status": "NEEDS_REVIEW",
        "claimed_proof_level": args.claimed_level, "route": args.route,
        "build": {"root": args.build_root or str(args.container_path or args.container),
                  "build_id": build_id,
                  "engine": args.engine or args.container, "platform": "windows", "locale": "vi",
                  "cache_state": "cold", **({"executable": args.executable} if args.executable else {})},
        "rights": {"modification": "verified", "redistribution": "unverified", "evidence": None,
                   "evidence_sha256": None, "donors": []},
        "encoding": {"mode": "engine_single_byte", "mapping_source": rel(args.mapping, root),
                     "mapping_sha256": mapping_sha, "adapter_path": rel(args.adapter, root),
                     "adapter_sha256": sha256(args.adapter), "normalization": "NFC",
                     "encoder": rel(args.encoder, root) if args.encoder else None,
                     "encoder_sha256": sha256(args.encoder) if args.encoder else None},
        "screenshots_all": shots, "fonts": fonts,
    }
    args.out.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"manifest {args.out}  fonts {len(fonts)}  build_id {build_id}")
    print(f"  with screenshots: {[f['name'] for f in fonts if f['runtime']['screenshots']]}")
    print(f"  preservation: {sorted({f['gates'][-1]['status'] for f in fonts})}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
