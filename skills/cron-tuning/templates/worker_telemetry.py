"""Minimal append-only worker telemetry; no canonical/scheduler writes."""
from __future__ import annotations
import json, time
from pathlib import Path

EVENTS = ("queue_started", "provider_started", "provider_finished", "validation_finished", "commit_finished", "readback_finished")

class Telemetry:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
    def event(self, name: str, *, packet_id: str, ok: bool = True, **extra):
        if name not in EVENTS: raise ValueError(f"unknown_event:{name}")
        row = {"ts": time.time(), "event": name, "packet_id": packet_id, "ok": bool(ok), **extra}
        with self.path.open("a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
    def read(self) -> list[dict]:
        if not self.path.exists(): return []
        rows=[]
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if line.strip(): rows.append(json.loads(line))
        return rows

def durations(rows: list[dict], packet_id: str) -> dict[str, float]:
    ts = {r["event"]: float(r["ts"]) for r in rows if r.get("packet_id") == packet_id}
    pairs = (("queue_to_provider", "queue_started", "provider_started"), ("provider", "provider_started", "provider_finished"), ("validation", "provider_finished", "validation_finished"), ("commit", "validation_finished", "commit_finished"), ("readback", "commit_finished", "readback_finished"))
    return {name: ts[b] - ts[a] for name,a,b in pairs if a in ts and b in ts}
