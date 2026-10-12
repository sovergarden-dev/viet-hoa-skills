#!/usr/bin/env python3
"""Reference fonttv-adapter/v1 implementation for FTVF, a synthetic test font format.

FTVF exists so the adapter protocol and custom_encoding_audit.py can be tested
against records that are genuinely parsed from bytes. It is not a game format.

FTVF v1 (little-endian):
    0   4s   magic b"FTVF"
    4   H    version (1)
    6   H    record count N
    8   16s  native encoding name, ASCII, NUL-padded ("" = unknown)
    24  N x 32-byte records: <I id, 4f u0 v0 u1 v1, h x_advance, h height, h y_offset, H reserved, I ink_pixels>
The file size must be exactly 24 + 32 * N. ink_pixels 0xFFFFFFFF means "not
measured": the record is emitted with UV only, so ink stays NOT_RUN/UNVERIFIED.

Protocol: python ftvf_reference.py --input FONT --output JSON --invocation-id ID --protocol fonttv-adapter/v1
Exit 0 = inventory written; 3 = unsupported format/version; 1 = corrupt input or protocol misuse.
The adapter never writes to --input and never guesses glyph identity.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path

PROTOCOL = "fonttv-adapter/v1"
HEADER = struct.Struct("<4sHH16s")
RECORD = struct.Struct("<I4fhhhHI")
EXIT_UNSUPPORTED = 3
INK_NOT_MEASURED = 0xFFFFFFFF


def fail(code: int, message: str) -> int:
    sys.stderr.write(message + "\n")
    return code


def parse(data: bytes) -> tuple[str, list[dict]]:
    magic, version, count, native = HEADER.unpack_from(data, 0)
    if version != 1:
        raise NotImplementedError(f"FTVF version {version} not supported")
    if len(data) != HEADER.size + RECORD.size * count:
        raise ValueError(f"size {len(data)} does not match {count} records")
    records = []
    for index in range(count):
        id_, u0, v0, u1, v1, advance, height, y_offset, _reserved, ink = RECORD.unpack_from(data, HEADER.size + RECORD.size * index)
        record = {"id": id_, "uv": [round(u0, 6), round(v0, 6), round(u1, 6), round(v1, 6)],
                  "x_advance": advance, "height": height, "y_offset": y_offset}
        if ink != INK_NOT_MEASURED:
            record["ink_pixels"] = ink
        records.append(record)
    return native.rstrip(b"\0").decode("ascii"), records


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--input", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--invocation-id", required=True)
    ap.add_argument("--protocol", required=True)
    a = ap.parse_args(argv)
    if a.protocol != PROTOCOL:
        return fail(1, f"unsupported protocol {a.protocol!r}")
    data = a.input.read_bytes()
    if len(data) < HEADER.size or data[:4] != b"FTVF":
        return fail(EXIT_UNSUPPORTED, "not an FTVF font (magic mismatch)")
    try:
        native, records = parse(data)
    except NotImplementedError as exc:
        return fail(EXIT_UNSUPPORTED, str(exc))
    except (ValueError, struct.error, UnicodeDecodeError) as exc:
        return fail(1, f"corrupt FTVF: {exc}")
    digest = hashlib.sha256(data).hexdigest()
    adapter = {"name": "ftvf-reference", "version": "1.0.0", "supported": True,
               "capabilities": ["records", "uv", "metrics", "ink"], "input_sha256": digest,
               "inventory_method": "parsed FTVF v1 header and fixed 32-byte records"}
    if native:
        adapter["native_encoding"] = {"name": native, "resolver": "FTVF header native encoding; id decoded as one byte"}
    inventory = {"schema": "fonttv/font-inventory/v1", "font": a.input.name, "sha256": digest, "adapter": adapter,
                 "invocation": {"id": a.invocation_id, "protocol": PROTOCOL}, "lookup": "binary_search", "records": records}
    a.output.write_text(json.dumps(inventory, ensure_ascii=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
