"""Mechanical GUI chassis gate for native patch installers. Read-only."""
from __future__ import annotations

import argparse
import json
import re
import struct
import sys
from pathlib import Path

SCHEMA = "buildpatch/installer-gui-layout/v1"
CLIENT = (1024, 576)
PHASE = 0.045
SIGNATURE = "Syrin.online"


def fail(message: str) -> None:
    raise ValueError(message)


def rect(item: dict, *keys: str) -> tuple[int, int, int, int]:
    try:
        x, y, w, h = (int(item[k]) for k in keys)
    except (KeyError, TypeError, ValueError) as exc:
        fail(f"invalid rect: {exc}")
    if w < 1 or h < 1 or x < 0 or y < 0:
        fail("rect out of range")
    return x, y, w, h


def inside(child: tuple[int, int, int, int], parent: tuple[int, int, int, int]) -> bool:
    cx, cy, cw, ch = child
    px, py, pw, ph = parent
    return cx >= px and cy >= py and cx + cw <= px + pw and cy + ch <= py + ph


def overlap(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> bool:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    return ax < bx + bw and ax + aw > bx and ay < by + bh and ay + ah > by


def abs_control(control: dict, safes: dict[str, tuple[int, int, int, int]]) -> tuple[int, int, int, int]:
    box = rect(control, "x", "y", "w", "h")
    parent = control.get("parent")
    if not parent:
        return box
    if parent not in safes:
        fail(f"unknown parent {parent}")
    px, py, _, _ = safes[parent]
    return box[0] + px, box[1] + py, box[2], box[3]


def validate_layout(data: dict) -> list[str]:
    if data.get("schema") != SCHEMA:
        fail("schema must be buildpatch/installer-gui-layout/v1")
    client = data.get("client") or {}
    if (client.get("w"), client.get("h")) != CLIENT:
        fail("client must be 1024x576")
    frame = (0, 0, *CLIENT)
    protected = [rect(item, "x", "y", "w", "h") for item in data.get("protected") or []]
    if not protected:
        fail("protected rectangles required")
    safes = {}
    for item in data.get("safe") or []:
        box = rect(item, "x", "y", "w", "h")
        if not inside(box, frame):
            fail(f"safe zone outside client: {item.get('name')}")
        safes[str(item.get("name") or "")] = box
    if not safes:
        fail("safe rectangles required")
    controls = data.get("controls") or {}
    for name in ("install", "uninstall", "signature", "build"):
        if name not in controls:
            fail(f"missing control {name}")
    placed = {name: abs_control(ctrl, safes) for name, ctrl in controls.items()}
    for name, box in placed.items():
        if not inside(box, frame):
            fail(f"{name} outside 1024x576")
        if not any(inside(box, safe) for safe in safes.values()):
            fail(f"{name} outside every safe zone")
        if any(overlap(box, zone) for zone in protected):
            fail(f"{name} intersects protected artwork")
        if box[3] < 14:
            fail(f"{name} shorter than 14px")
    install, uninstall = placed["install"], placed["uninstall"]
    if abs(install[1] - uninstall[1]) > 2:
        fail("Cài and Gỡ must share the same Y")
    left, right = sorted((install, uninstall), key=lambda b: b[0])
    gap = right[0] - (left[0] + left[2])
    if gap < 0 or gap > 24:
        fail("Cài and Gỡ must sit adjacent with a 0-24px gap")
    sig = placed["signature"]
    if sig[0] < 744 or sig[1] < 496:
        fail("Syrin.online must sit in the bottom-right of 1024x576")
    if sig[0] + sig[2] > 1016 or sig[1] + sig[3] > 568:
        fail("signature overflows the 8px outer margin")
    build = placed["build"]
    if controls["build"].get("parent") and build[2] < 120:
        fail("build metadata cell must be a fixed width, not AutoSize")
    locked = data.get("locked") or {}
    if locked.get("rainbow_phase") != PHASE:
        fail("rainbow phase must be 0.045")
    if locked.get("signature_text") != SIGNATURE:
        fail("signature text must be Syrin.online")
    install_label = str(locked.get("install_label") or "")
    uninstall_label = str(locked.get("uninstall_label") or "")
    if "cài" not in install_label.casefold() or "gỡ" not in uninstall_label.casefold():
        fail("labels must remain Cài / Gỡ")
    return ["layout_ok"]


def png_size(path: Path) -> tuple[int, int]:
    data = path.read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n" or data[12:16] != b"IHDR":
        fail("screenshot must be a PNG with IHDR")
    return struct.unpack(">II", data[16:24])


def scan_screenshot(path: Path) -> list[str]:
    width, height = png_size(path)
    allowed = {(1024, 576), (1280, 720), (1536, 864)}
    if (width, height) not in allowed:
        fail(f"screenshot {width}x{height} is not 1024x576 at 100/125/150% DPI")
    return ["screenshot_ok"]


def scan_csharp(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    compact = re.sub(r"\s+", "", text)
    findings = []
    if not re.search(r"ClientSize\s*=\s*new(?:\s*Size)?\s*\(\s*1024\s*,\s*576\s*\)", text):
        findings.append("missing ClientSize 1024,576")
    if "FormBorderStyle.None" not in compact:
        findings.append("missing FormBorderStyle.None")
    if "ShowInTaskbar=true" not in compact:
        findings.append("missing ShowInTaskbar=true")
    if "WS_MINIMIZEBOX" not in text and "0x20000" not in compact and "0x00020000" not in compact:
        findings.append("missing native taskbar minimize")
    if "Cursor.SizeAll" in compact:
        findings.append("Cursor.SizeAll is forbidden on parent surfaces")
    if not re.search(r"(phase\s*\+=\s*\.?045f?|_phase\s*\+\s*0\.045f?|0\.045f?)", text):
        findings.append("rainbow phase must be 0.045")
    if SIGNATURE not in text:
        findings.append("missing Syrin.online signature")
    if re.search(r"AutoSize\s*=\s*true", text) and re.search(r"build|STEAM BUILD|recommended_steam_build", text, re.I):
        if not re.search(r"SetBounds\([^)]+\d+\s*,\s*\d+\s*,\s*1[2-9]\d", text):
            findings.append("build metadata must use a fixed right-aligned cell")
    return findings


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("layout")
    parser.add_argument("--csharp")
    parser.add_argument("--screenshot", help="Compiled GUI PNG at 100/125/150%% DPI")
    args = parser.parse_args(argv)
    try:
        data = json.loads(Path(args.layout).read_text(encoding="utf-8"))
        notes = validate_layout(data)
        if args.csharp:
            csharp = scan_csharp(Path(args.csharp))
            if csharp:
                fail("; ".join(csharp))
            notes.append("csharp_ok")
        if args.screenshot:
            notes.extend(scan_screenshot(Path(args.screenshot)))
        print(json.dumps({"valid": True, "notes": notes}))
        return 0
    except (ValueError, OSError, json.JSONDecodeError, TypeError, KeyError) as exc:
        print(json.dumps({"valid": False, "error": str(exc)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
