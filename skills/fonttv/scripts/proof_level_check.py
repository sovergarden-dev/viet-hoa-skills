#!/usr/bin/env python3
"""Read-only check: which proof level does a fonttv manifest actually justify?

Reads a manifest (schema ``fonttv/manifest/v1``, see templates/) and computes,
per font consumer, the highest level its evidence supports:

  inventory_only < structurally_verified < mapping_verified
  < archive_verified < runtime_verified < release_verified

Every level needs artifacts (path + SHA-256): output font, gate reports,
archive readback, screenshots, rights evidence, release reports, sign-off
records. A status the manifest merely declares is never evidence.

Without --verify-files only the internal consistency of the declared hashes
is checked (``evidence_mode: declared_only``): the result is reported as
``declared_consistent_level`` and ``justified_proof_level`` stays at
``inventory_only``, so any higher claim fails. With --verify-files ROOT every
artifact that a level depends on is re-hashed. For route B/C, ``mapping_verified``
additionally re-executes ``custom_encoding_audit.py`` on the output font with the
pinned adapter. Hashing the stored report is ``report_file_rehashed``; it is not
``semantic_reexecution``. A missing, unreadable or mismatching file is an ERROR
and the level is not reached.

Exit codes: 0 claim justified, 1 overclaim or manifest errors, 2 input error.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

from custom_encoding_audit import canonical_inventory, semantic_digest

SCHEMA = "fonttv/manifest/v1"
LEVELS = ["inventory_only", "structurally_verified", "mapping_verified",
          "archive_verified", "runtime_verified", "release_verified"]
ROUTES = {"A_unicode_opentype", "B_custom_encoding", "C_engine_atlas"}
ENCODED_ROUTES = {"B_custom_encoding", "C_engine_atlas"}
CHANGES = {"new", "remapped", "modified", "preserved", "unchanged"}
STRUCTURAL_GATES = ("coverage", "outline_ink", "metrics", "structural_validator")
MAPPING_GATES = ("semantic_mapping", "preservation_diff")
NOT_APPLICABLE_OK = {"shaping", "preservation_diff"}
WAIVABLE = {"metrics"}
WAIVER_FIELDS = ("reason", "approved_by", "scope")
HELPER_SCHEMAS = {"fonttv/custom-encoding-audit/v1", "fonttv/audit/v2", "fonttv/shaping/v2"}
IDENTITY_POLICY = "fonttv/identity-evidence/v2"
ADAPTER_PROTOCOL = "fonttv-adapter/v1"
SHA_RE = re.compile(r"^[0-9a-f]{64}$")
AUDIT_SCRIPT = Path(__file__).resolve().parent / "custom_encoding_audit.py"


def is_sha(value) -> bool:
    return isinstance(value, str) and bool(SHA_RE.match(value.lower()))


def low(value) -> str:
    return value.lower() if isinstance(value, str) else ""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class Checker:
    def __init__(self, manifest: dict, root: Path | None):
        self.m, self.root = manifest, root
        self.verify = root is not None
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.rehashed: list[str] = []
        self.mapping_sha: str | None = None
        self.semantic_reexecution = False
        self.adapter_reexecuted = False
        self.reexecution: dict | None = None
        self._rerun_cache: dict[tuple, dict] = {}
        self.receipts: list[dict] = []

    def artifact(self, where: str, rel, declared, blockers: list[str]) -> tuple[bool, Path | None]:
        """An evidence file needs a path and a SHA-256; with --verify-files it must exist and match."""
        if not isinstance(rel, str) or not rel.strip():
            blockers.append(f"{where}: artifact path missing")
            return False, None
        if not is_sha(declared):
            blockers.append(f"{where}: sha256 missing or invalid")
            return False, None
        if not self.verify:
            return True, None
        path = Path(rel) if Path(rel).is_absolute() else self.root / rel
        try:
            actual = sha256_file(path)
        except OSError as exc:
            self.errors.append(f"{where}: {rel} missing or unreadable ({type(exc).__name__})")
            blockers.append(f"{where}: file missing")
            return False, None
        if actual != declared.lower():
            self.errors.append(f"{where}: {rel} hashes to {actual}, manifest declares {declared.lower()}")
            blockers.append(f"{where}: hash mismatch")
            return False, None
        self.rehashed.append(rel)
        return True, path

    def check_contract(self, blockers: list[str]) -> bool:
        enc = self.m.get("encoding") or {}
        ok, _ = self.artifact("encoding/mapping_source", enc.get("mapping_source"), enc.get("mapping_sha256"), blockers)
        self.mapping_sha = low(enc.get("mapping_sha256")) if ok else None
        return ok

    def check_report(self, where: str, path: Path | None, gate: str, entry: dict, out_hash: str,
                     route: str, blockers: list[str]) -> bool:
        if not self.verify or path is None:
            return True
        semantic_b = gate == "semantic_mapping" and route in ENCODED_ROUTES
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = None
        schema = data.get("schema") if isinstance(data, dict) else None
        if schema not in HELPER_SCHEMAS:
            if semantic_b:
                self.errors.append(f"{where}: semantic_mapping report must be custom_encoding_audit.py JSON")
                blockers.append(f"{where}: report content not verifiable")
                return False
            self.warnings.append(f"{where}: report format not parsed; only its hash was verified")
            return True
        problems = []
        if entry.get("status") == "PASS" and data.get("verdict") != "PASS":
            problems.append(f"report verdict is {data.get('verdict')!r}")
        if schema == "fonttv/custom-encoding-audit/v1":
            inputs, inventory = data.get("inputs") or {}, data.get("inventory") or {}
            if low(inputs.get("font_sha256")) != out_hash:
                problems.append("report did not hash the output font itself (inputs.font_sha256)")
            if low(inventory.get("declared_font_sha256")) != out_hash:
                problems.append("inventory.declared_font_sha256 is not the output")
            if inventory.get("font_hash_matches") is not True or inventory.get("adapter_input_matches") is not True \
                    or inventory.get("binding_status") != "PASS":
                problems.append("inventory/adapter not bound to the output bytes (pre-binding or failed report)")
            if data.get("identity_evidence_policy") != IDENTITY_POLICY:
                problems.append(f"identity evidence policy must be {IDENTITY_POLICY}")
            execution = data.get("adapter_execution") or {}
            if data.get("inventory_origin") != "adapter_executed" or data.get("records_rederived") is not True:
                problems.append("records were not re-derived by a hash-pinned adapter in the audit run "
                                "(external inventory is a declaration)")
            elif not (is_sha(execution.get("script_sha256")) and execution.get("invocation_id")
                      and execution.get("exit_code") == 0 and is_sha(execution.get("generated_inventory_sha256"))
                      and execution.get("input_unchanged") is True and execution.get("protocol") == ADAPTER_PROTOCOL):
                problems.append("adapter_execution lacks script hash, invocation id, exit 0, output hash or unchanged input")
            if semantic_b:
                if data.get("proof_level") != "mapping_verified":
                    problems.append(f"report proof_level is {data.get('proof_level')!r}")
                if low((data.get("inputs") or {}).get("mapping_sha256")) != self.mapping_sha:
                    problems.append("report was produced with a different mapping table")
        elif low(data.get("sha256")) != out_hash:
            problems.append("report audited different font bytes")
        if semantic_b and schema != "fonttv/custom-encoding-audit/v1":
            problems.append("semantic_mapping on route B/C needs custom_encoding_audit.py output")
        if problems:
            self.errors += [f"{where}: {p}" for p in problems]
            blockers.append(f"{where}: report content contradicts the gate")
            return False
        return True

    def gate_ok(self, font: dict, name: str, gate: str, out_hash: str, route: str, blockers: list[str]) -> bool:
        entry = font["_gates"].get(gate)
        where = f"{name}/{gate}"
        if entry is None:
            blockers.append(f"{where}: missing")
            return False
        status = entry.get("status")
        if status == "NOT_APPLICABLE":
            allowed = gate in NOT_APPLICABLE_OK and bool(entry.get("reason"))
            if gate == "preservation_diff" and font.get("change") != "new":
                allowed = False
            if gate == "shaping" and font.get("engine_shapes") is not False:
                allowed = False
            if not allowed:
                blockers.append(f"{where}: NOT_APPLICABLE not allowed here")
            return allowed
        if status == "WAIVED":
            missing = [k for k in WAIVER_FIELDS if not str(entry.get(k) or "").strip()]
            if gate not in WAIVABLE or missing or entry.get("approver_type") != "human":
                blockers.append(f"{where}: waiver not allowed or missing {missing or ['approver_type=human']}")
                return False
        elif status != "PASS":
            blockers.append(f"{where}: {status or 'no status'}")
            return False
        if low(entry.get("font_sha256")) != out_hash:
            blockers.append(f"{where}: measured on {entry.get('font_sha256')!r}, not the output bytes")
            return False
        ok, path = self.artifact(f"{where} report", entry.get("report"), entry.get("report_sha256"), blockers)
        if not ok:
            return False
        if gate == "semantic_mapping" and route in ENCODED_ROUTES:
            if not self.mapping_sha:
                blockers.append(f"{where}: encoding contract (mapping_source + mapping_sha256) not established")
                return False
            if low(entry.get("mapping_sha256")) != self.mapping_sha:
                blockers.append(f"{where}: gate mapping_sha256 does not match the manifest encoding contract")
                return False
        if gate == "semantic_mapping" and route in ENCODED_ROUTES and self.verify:
            if not self.semantic_matches_rerun(font, path, blockers):
                return False
        if not self.check_report(where, path, gate, entry, out_hash, route, blockers):
            return False
        if status == "WAIVED":
            self.warnings.append(f"{where}: WAIVED by {entry['approved_by']} ({entry['scope']}): {entry['reason']}")
        return True

    def semantic_matches_rerun(self, font: dict, report_path: Path | None, blockers: list[str]) -> bool:
        """Mapping proof requires the cached rerun's semantic result, plus a stored report with the same digest."""
        where = f"{font.get('name') or 'font'}/semantic reexecution"
        receipt = font.get("_rerun") or {}
        if receipt.get("semantic_status") != "PASS":
            blockers.append(f"{where}: rerun semantic_result is {receipt.get('semantic_status')!r}")
            return False
        if report_path is None:
            blockers.append(f"{where}: stored report missing")
            return False
        try:
            stored = json.loads(report_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            blockers.append(f"{where}: stored report is not JSON")
            return False
        if semantic_digest(stored) != receipt.get("semantic_digest"):
            self.errors.append(f"{where}: stored report semantic digest differs from the rerun (stale or tampered report)")
            blockers.append(f"{where}: stored report semantic digest differs from the rerun")
            return False
        return True

    def ensure_rerun(self, font: dict, out_hash: str, blockers: list[str]) -> dict:
        """Run the audit once per input set. Structural and semantic gates share that result."""
        where = f"{font.get('name') or 'font'}/adapter reexecution"
        enc = self.m.get("encoding") or {}
        audit = font.get("semantic_audit") or {}
        evidence = font.get("identity_evidence", enc.get("identity_evidence") or [])
        adapter_path = font["adapter_path"] if "adapter_path" in font else enc.get("adapter_path")
        adapter_sha = font["adapter_sha256"] if "adapter_sha256" in font else enc.get("adapter_sha256")
        key = (
            out_hash, self.mapping_sha or "", low(adapter_sha),
            tuple((item.get("type"), low(item.get("sha256"))) for item in evidence if isinstance(item, dict)),
            low(audit.get("corpus_sha256")), low(audit.get("encoded_sha256")), low(audit.get("allowlist_sha256")),
            low(audit.get("generated_inventory_sha256")),
        )
        if key in self._rerun_cache:
            return self._rerun_cache[key]
        receipt = {"adapter_reexecuted": False, "semantic_reexecution": False, "structural_status": None,
                   "semantic_status": None, "semantic_digest": None, "exit_code": None, "adapter_sha256": None,
                   "font_sha256": None, "mapping_sha256": None, "proof_level": None, "verdict": None}
        ok, script = self.artifact(f"{where}/adapter", adapter_path, adapter_sha, blockers)
        if not ok or script is None:
            blockers.append(f"{where}: encoding.adapter_path + adapter_sha256 are required; "
                            "a stored report is not structural proof on an encoded route")
            self._rerun_cache[key] = receipt
            return receipt
        mapping = enc.get("mapping_source")
        mapping_path = Path(str(mapping)) if Path(str(mapping)).is_absolute() else self.root / str(mapping)
        font_path = Path(font["output_path"]) if Path(str(font.get("output_path"))).is_absolute() else self.root / str(font.get("output_path"))
        cmd = [sys.executable, str(AUDIT_SCRIPT), "--mapping", str(mapping_path),
               "--adapter-script", str(script), "--adapter-sha256", low(adapter_sha),
               "--font-file", str(font_path)]
        for index, item in enumerate(evidence):
            if not isinstance(item, dict):
                blockers.append(f"{where}: identity_evidence[{index}] must be an object")
                self._rerun_cache[key] = receipt
                return receipt
            ok, ev_path = self.artifact(f"{where}/identity_evidence[{index}]", item.get("path"), item.get("sha256"), blockers)
            if not ok or ev_path is None:
                self._rerun_cache[key] = receipt
                return receipt
            kind = item.get("type")
            if not isinstance(kind, str) or not kind.strip():
                blockers.append(f"{where}: identity_evidence[{index}] needs a type")
                self._rerun_cache[key] = receipt
                return receipt
            cmd += ["--identity-evidence", f"{kind}={ev_path}"]
        for flag, name in (("--text", "corpus"), ("--encoded", "encoded"), ("--allowlist", "allowlist")):
            if f"{name}_path" not in audit and f"{name}_sha256" not in audit:
                continue
            ok, extra = self.artifact(f"{where}/{name}", audit.get(f"{name}_path"), audit.get(f"{name}_sha256"), blockers)
            if not ok or extra is None:
                self._rerun_cache[key] = receipt
                return receipt
            cmd += [flag, str(extra)]
        generated = None
        if "generated_inventory_path" in audit or "generated_inventory_sha256" in audit:
            ok, generated = self.artifact(f"{where}/generated_inventory", audit.get("generated_inventory_path"),
                                          audit.get("generated_inventory_sha256"), blockers)
            if not ok or generated is None:
                self._rerun_cache[key] = receipt
                return receipt
        try:
            proc = subprocess.run(cmd, capture_output=True, timeout=120, check=False)
        except subprocess.TimeoutExpired:
            blockers.append(f"{where}: audit rerun exceeded 120s")
            self._rerun_cache[key] = receipt
            return receipt
        receipt["adapter_reexecuted"] = True
        receipt["exit_code"] = proc.returncode
        try:
            rerun = json.loads(proc.stdout.decode("utf-8"))
        except ValueError:
            blockers.append(f"{where}: rerun did not return JSON (exit {proc.returncode})")
            self._rerun_cache[key] = receipt
            return receipt
        receipt.update({
            "semantic_reexecution": True,
            "verdict": rerun.get("verdict"),
            "proof_level": rerun.get("proof_level"),
            "adapter_sha256": (rerun.get("adapter_execution") or {}).get("script_sha256"),
            "font_sha256": (rerun.get("inputs") or {}).get("font_sha256"),
            "mapping_sha256": (rerun.get("inputs") or {}).get("mapping_sha256"),
            "rerun_report_sha256": hashlib.sha256(proc.stdout).hexdigest(),
            "semantic_digest": semantic_digest(rerun),
            "inventory_canonical_sha256": rerun.get("inventory_canonical_sha256"),
            "structural_status": (rerun.get("structural_result") or {}).get("status"),
            "semantic_status": (rerun.get("semantic_result") or {}).get("status"),
        })
        if low(receipt["font_sha256"]) != out_hash:
            blockers.append(f"{where}: rerun hashed different font bytes")
            receipt["structural_status"] = "FAIL"
        if self.mapping_sha and low(receipt["mapping_sha256"]) != self.mapping_sha:
            blockers.append(f"{where}: rerun used a different mapping table")
            receipt["structural_status"] = "FAIL"
        if low(receipt["adapter_sha256"]) != low(adapter_sha):
            blockers.append(f"{where}: rerun adapter hash does not match the pin")
            receipt["structural_status"] = "FAIL"
        if generated is not None:
            try:
                saved = json.loads(generated.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                blockers.append(f"{where}: generated inventory is not JSON")
                receipt["structural_status"] = "FAIL"
            else:
                if canonical_inventory(saved) != rerun.get("inventory_canonical_sha256"):
                    self.errors.append(f"{where}: generated inventory canonical form differs from the adapter rerun")
                    blockers.append(f"{where}: generated inventory canonical form differs")
                    receipt["structural_status"] = "FAIL"
        if receipt["structural_status"] != "PASS":
            blockers.append(f"{where}: rerun structural_result is {receipt['structural_status']!r} "
                            f"(exit {proc.returncode}, verdict {rerun.get('verdict')!r})")
        self._rerun_cache[key] = receipt
        return receipt

    def font_level(self, font: dict, route: str) -> tuple[str | None, list[str]]:
        name = font.get("name") or font.get("consumer") or "<unnamed font>"
        blockers: list[str] = []
        gates = font.get("gates") or []
        font["_gates"] = {g.get("gate"): g for g in gates if isinstance(g, dict)}
        if len(font["_gates"]) != len(gates):
            self.errors.append(f"{name}: duplicate or malformed gate entries")
        if not is_sha(font.get("input_sha256")):
            self.errors.append(f"{name}: input_sha256 missing; no baseline")
            return None, ["no baseline"]
        out_hash = low(font.get("output_sha256"))
        if not is_sha(out_hash):
            return "inventory_only", ["output_sha256 missing"]
        change = font.get("change")
        if change not in CHANGES:
            self.errors.append(f"{name}: change must be one of {sorted(CHANGES)}")
        if change in ("preserved", "unchanged") and out_hash != low(font["input_sha256"]):
            self.errors.append(f"{name}: change={change} but output hash differs from input")
        semantic = font["_gates"].get("semantic_mapping", {})
        if route in ENCODED_ROUTES and change in ("preserved", "unchanged"):
            if semantic.get("status") != "PASS" or low(semantic.get("font_sha256")) != out_hash:
                self.errors.append(f"{name}: kept original bytes without a semantic_mapping PASS on those bytes "
                                   "(record presence is not mapping correctness)")

        level = "inventory_only"
        output_ok, _ = self.artifact(f"{name}/output", font.get("output_path"), out_hash, blockers)
        if not output_ok:
            return level, blockers
        if route in ENCODED_ROUTES and self.verify:
            receipt = self.ensure_rerun(font, out_hash, blockers)
            font["_rerun"] = receipt
            self.receipts.append({"name": name, **{k: receipt[k] for k in (
                "adapter_reexecuted", "semantic_reexecution", "exit_code", "adapter_sha256",
                "font_sha256", "mapping_sha256", "semantic_digest", "structural_status", "semantic_status")}})
            if receipt.get("structural_status") != "PASS":
                return level, blockers
        structural = STRUCTURAL_GATES + (("shaping",) if route == "A_unicode_opentype" else ())
        if not all([self.gate_ok(font, name, g, out_hash, route, blockers) for g in structural]):
            return level, blockers
        level = "structurally_verified"
        contract_ok = route not in ENCODED_ROUTES or self.mapping_sha is not None
        if not contract_ok:
            blockers.append("encoding contract: mapping_source + mapping_sha256 required for route B/C")
        mapping_ok = all([self.gate_ok(font, name, g, out_hash, route, blockers) for g in MAPPING_GATES])
        if not (contract_ok and mapping_ok):
            return level, blockers
        level = "mapping_verified"

        archive = font.get("archive") or {}
        readback = low(archive.get("readback_sha256"))
        if not archive.get("container") or not archive.get("readback_method"):
            blockers.append("archive: container and readback_method required")
            return level, blockers
        if not is_sha(readback):
            blockers.append("archive: readback_sha256 required")
            return level, blockers
        if readback != out_hash:
            self.errors.append(f"{name}: bytes read back from the live container differ from the audited output")
            blockers.append("archive: readback hash mismatch")
            return level, blockers
        readback_ok, _ = self.artifact(f"{name}/archive readback", archive.get("readback_path"), readback, blockers)
        if archive.get("container_path") and self.verify:
            self.artifact(f"{name}/archive container (metadata)", archive.get("container_path"),
                          archive.get("container_sha256_after"), [])
        if not readback_ok:
            return level, blockers
        level = "archive_verified"

        runtime = font.get("runtime") or {}
        shots = runtime.get("screenshots") or []
        build_id = (self.m.get("build") or {}).get("build_id")
        if not runtime.get("build_id") or not shots:
            blockers.append("runtime: build_id and screenshots required")
            return level, blockers
        if build_id and runtime["build_id"] != build_id:
            blockers.append(f"runtime: build_id {runtime['build_id']!r} is not the manifest build {build_id!r}")
            return level, blockers
        shots_ok = True
        for index, shot in enumerate(shots):
            where = f"{name}/screenshot[{index}]"
            if not isinstance(shot, dict) or low(shot.get("font_sha256")) != out_hash:
                blockers.append(f"{where}: font_sha256 must equal the output")
                shots_ok = False
                continue
            ok, _ = self.artifact(where, shot.get("path"), shot.get("sha256"), blockers)
            shots_ok = shots_ok and ok
        if not shots_ok:
            return level, blockers
        if runtime.get("reviewer_type") != "human":
            blockers.append("runtime: review by a human is required; AI review only triages")
            return level, blockers
        if runtime.get("verdict") != "PASS":
            blockers.append(f"runtime: verdict {runtime.get('verdict')!r}")
            return level, blockers
        return "runtime_verified", blockers

    def release_blockers(self, fonts: list[dict]) -> list[str]:
        blockers: list[str] = []
        rights, release = self.m.get("rights") or {}, self.m.get("release") or {}
        if rights.get("modification") != "verified":
            blockers.append("rights.modification not verified")
        if rights.get("redistribution") not in ("verified", "not_distributed"):
            blockers.append("rights.redistribution not verified")
        self.artifact("rights/evidence", rights.get("evidence"), rights.get("evidence_sha256"), blockers)
        for key in ("clean_install", "rollback"):
            item = release.get(key)
            if not isinstance(item, dict) or item.get("status") != "PASS":
                blockers.append(f"release.{key}: PASS object with report required")
                continue
            self.artifact(f"release/{key}", item.get("report"), item.get("report_sha256"), blockers)
        outputs = {low(f.get("output_sha256")) for f in fonts}
        signed, roles = set(), set()
        for index, s in enumerate(release.get("signoff") or []):
            if not isinstance(s, dict) or s.get("reviewer_type") != "human":
                continue
            ok, _ = self.artifact(f"release/signoff[{index}]", s.get("record"), s.get("record_sha256"), blockers)
            if ok:
                signed |= {low(h) for h in s.get("sha256") or []}
                roles.add(s.get("role"))
        if not outputs <= signed:
            blockers.append("human sign-off records must cover every output sha256")
        elif len(roles) < 2:
            self.warnings.append("only one sign-off role; Vietnamese reader + typography reviewer recommended")
        return blockers

    def run(self) -> dict:
        m = self.m
        if m.get("schema") != SCHEMA:
            raise ValueError(f"schema must be {SCHEMA}")
        fonts = m.get("fonts")
        if not isinstance(fonts, list) or not fonts or not all(isinstance(f, dict) for f in fonts):
            raise ValueError("fonts must be a non-empty list of objects")
        contract_blockers: list[str] = []
        needs_contract = any((f.get("route") or m.get("route")) in ENCODED_ROUTES for f in fonts)
        if needs_contract:
            self.check_contract(contract_blockers)
        per_font, levels = [], []
        for font in fonts:
            route = font.get("route") or m.get("route")
            if route not in ROUTES:
                self.errors.append(f"{font.get('name')}: route must be one of {sorted(ROUTES)}")
                route = "B_custom_encoding"
            level, blockers = self.font_level(font, route)
            if route in ENCODED_ROUTES:
                blockers = contract_blockers + blockers
            font.pop("_gates", None)
            receipt = font.get("_rerun") or {}
            per_font.append({
                "name": font.get("name"), "consumer": font.get("consumer"), "route": route,
                "level": level, "blockers": blockers,
                "adapter_reexecuted": bool(receipt.get("adapter_reexecuted")),
                "semantic_reexecution": bool(receipt.get("semantic_reexecution")),
                "reexecution": {k: receipt.get(k) for k in (
                    "exit_code", "adapter_sha256", "font_sha256", "mapping_sha256", "semantic_digest",
                    "structural_status", "semantic_status", "verdict", "proof_level")} if receipt else None,
            })
            levels.append(level)
        justified = None if any(level is None for level in levels) else min(levels, key=LEVELS.index)
        release_blockers: list[str] = []
        if justified == "runtime_verified":
            release_blockers = self.release_blockers(fonts)
            if not release_blockers:
                justified = "release_verified"
        declared_level = justified
        if not self.verify and justified is not None:
            justified = "inventory_only"
        claimed = m.get("claimed_proof_level")
        overclaim = False
        if claimed is not None:
            if claimed not in LEVELS:
                self.errors.append(f"claimed_proof_level {claimed!r} is not a known level")
            elif justified is None or LEVELS.index(claimed) > LEVELS.index(justified):
                overclaim = True
                self.errors.append(f"claimed {claimed} but evidence supports {justified}")
        if m.get("status") == "APPROVED" and justified != "release_verified":
            self.errors.append("status APPROVED requires release_verified")
        encoded = [row for row in per_font if row["route"] in ENCODED_ROUTES]
        all_adapter = bool(encoded) and all(row["adapter_reexecuted"] for row in encoded)
        all_semantic = bool(encoded) and all(row["semantic_reexecution"] for row in encoded)
        if not self.verify:
            self.warnings.append("--verify-files not given: only the internal consistency of declared hashes was "
                                 "checked; no artifact was read and no adapter was reexecuted, so justified_proof_level "
                                 "is capped at inventory_only")
        verdict = "FAIL" if self.errors else "PASS"
        return {
            "schema": "fonttv/proof-level-check/v1",
            "tool": "proof_level_check.py",
            "project": m.get("project"),
            "status": m.get("status"),
            "evidence_mode": "files_rehashed" if self.verify else "declared_only",
            "report_file_rehashed": self.verify,
            "semantic_reexecution": all_semantic,
            "adapter_reexecuted": all_adapter,
            "semantic_reexecution_for_all_encoded_fonts": all_semantic,
            "adapter_reexecuted_for_all_encoded_fonts": all_adapter,
            "reexecution": per_font[0]["reexecution"] if len(per_font) == 1 else None,
            "reexecutions": [row["reexecution"] for row in per_font if row["reexecution"]],
            "rehashed_artifacts": len(self.rehashed),
            "claimed_proof_level": claimed,
            "justified_proof_level": justified,
            "declared_consistent_level": declared_level,
            "overclaim": overclaim,
            "per_font": per_font,
            "release_blockers": release_blockers,
            "errors": self.errors,
            "warnings": self.warnings,
            "verdict": verdict,
            "exit_code": 0 if verdict == "PASS" else 1,
        }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Compute the proof level a fonttv manifest justifies")
    ap.add_argument("manifest", type=Path)
    ap.add_argument("--verify-files", type=Path, metavar="ROOT", help="re-hash every artifact relative to ROOT")
    ap.add_argument("--output", type=Path)
    a = ap.parse_args(argv)
    try:
        if a.verify_files is not None and not a.verify_files.is_dir():
            raise ValueError(f"--verify-files root is not a directory: {a.verify_files}")
        manifest = json.loads(a.manifest.read_text(encoding="utf-8"))
        if not isinstance(manifest, dict):
            raise ValueError("manifest must be a JSON object")
        result = Checker(manifest, a.verify_files).run()
    except (OSError, ValueError) as exc:
        result = {"schema": "fonttv/proof-level-check/v1", "verdict": "INPUT_ERROR", "exit_code": 2,
                  "error": f"{type(exc).__name__}: {exc}"}
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if a.output:
        a.output.write_text(text + "\n", encoding="utf-8")
    sys.stdout.buffer.write((text + "\n").encode("utf-8"))
    return result["exit_code"]


if __name__ == "__main__":
    sys.exit(main())
