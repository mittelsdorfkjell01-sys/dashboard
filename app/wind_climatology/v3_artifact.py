"""Deterministic compressed storage for the V3 variant cube."""

from __future__ import annotations

import gzip
import hashlib
import json


def encode_cube(cube: dict) -> tuple[bytes, str]:
    raw = json.dumps(cube, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    blob = gzip.compress(raw, compresslevel=9, mtime=0)
    return blob, hashlib.sha256(blob).hexdigest()


def decode_cube(blob: bytes) -> dict:
    return json.loads(gzip.decompress(blob))
