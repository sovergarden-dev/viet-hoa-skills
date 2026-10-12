"""Independent FTVF writer used to test the reference adapter and adapter-executed audits."""
from __future__ import annotations

import hashlib
import json
import struct
from pathlib import Path

ADAPTERS = Path(__file__).resolve().parent.parent / "adapters"
FTVF_ADAPTER = ADAPTERS / "ftvf_reference.py"
TELLTALE_ADAPTER = ADAPTERS / "telltale_5vsm.py"
NOT_MEASURED = 0xFFFFFFFF


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_sha(path: Path) -> str:
    return sha(path.read_bytes())


def build(records: list[dict], native: str = "cp1252", version: int = 1) -> bytes:
    out = bytearray(struct.pack("<4sHH16s", b"FTVF", version, len(records), native.encode("ascii")))
    for r in records:
        u0, v0, u1, v1 = r.get("uv", (0.1, 0.1, 0.2, 0.2))
        out += struct.pack("<I4fhhhHI", r["id"], u0, v0, u1, v1, r.get("x_advance", 20), r.get("height", 40),
                           r.get("y_offset", 0), 0, r.get("ink_pixels", 100))
    return bytes(out)


def write_evidence(path: Path, font_bytes: bytes, slots: dict, kind: str = "build_manifest") -> Path:
    path.write_text(json.dumps({"schema": "fonttv/glyph-evidence/v1", "type": kind, "font_sha256": sha(font_bytes),
                                "slots": {str(k): v for k, v in slots.items()}}, ensure_ascii=False), encoding="utf-8")
    return path


ASCII = [{"id": ord(c), "x_advance": w, "ink_pixels": 0 if c == " " else 300} for c, w in
         ((" ", 12), ("D", 34), ("a", 26), ("d", 30), ("e", 26), ("u", 27))]
VN_SLOTS = {143: "ệ", 155: "ư", 167: "ạ", 178: "đ", 255: "Đ"}
REMAPPED = ASCII + [{"id": 143, "x_advance": 28, "ink_pixels": 352}, {"id": 155, "x_advance": 30, "ink_pixels": 318},
                    {"id": 167, "x_advance": 27, "ink_pixels": 322}, {"id": 178, "x_advance": 32, "ink_pixels": 344},
                    {"id": 255, "x_advance": 36, "ink_pixels": 402}]
ORIGINAL = ASCII + [{"id": 143, "uv": (0.61, 0.3, 0.61, 0.38), "x_advance": 1, "ink_pixels": 0},
                    {"id": 155, "x_advance": 14, "ink_pixels": 60}, {"id": 167, "x_advance": 22, "ink_pixels": 150},
                    {"id": 178, "uv": (0.72, 0.3, 0.72, 0.38), "x_advance": 17, "ink_pixels": 0},
                    {"id": 255, "x_advance": 26, "ink_pixels": 310}]
