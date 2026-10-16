"""Immutable multi-time containers for browser-side point sampling."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import struct
import tempfile
from typing import Iterator


MAGIC = b"SWS1"
PREFIX = struct.Struct("<4sI")


@dataclass(frozen=True)
class SeriesEntry:
    valid_time: str
    payload: bytes


def encode_field_series(entries: list[SeriesEntry], *, z: int, x: int, y: int) -> bytes:
    if not entries:
        raise ValueError("field series requires at least one time tile")
    if len({entry.valid_time for entry in entries}) != len(entries):
        raise ValueError("field series valid times must be unique")
    ordered = sorted(entries, key=lambda entry: entry.valid_time)
    offset = 0
    index = []
    bodies = []
    for entry in ordered:
        index.append(
            {"valid_time": entry.valid_time, "offset": offset, "length": len(entry.payload)}
        )
        bodies.append(entry.payload)
        offset += len(entry.payload)
    header = json.dumps(
        {
            "schema": "swd-field-series-v1",
            "z": z,
            "x": x,
            "y": y,
            "entries": index,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return PREFIX.pack(MAGIC, len(header)) + header + b"".join(bodies)


def decode_field_series(payload: bytes) -> tuple[dict, list[SeriesEntry]]:
    if len(payload) < PREFIX.size:
        raise ValueError("field series is truncated")
    magic, header_size = PREFIX.unpack_from(payload)
    if magic != MAGIC:
        raise ValueError("field series magic is invalid")
    header_end = PREFIX.size + header_size
    if header_end > len(payload):
        raise ValueError("field series header is truncated")
    header = json.loads(payload[PREFIX.size:header_end].decode("utf-8"))
    if header.get("schema") != "swd-field-series-v1":
        raise ValueError("unsupported field series schema")
    body_size = len(payload) - header_end
    entries = []
    previous_end = 0
    for item in header.get("entries", []):
        offset, length = int(item["offset"]), int(item["length"])
        if offset != previous_end or length <= 0 or offset + length > body_size:
            raise ValueError("field series index is invalid")
        start = header_end + offset
        entries.append(SeriesEntry(str(item["valid_time"]), payload[start : start + length]))
        previous_end = offset + length
    if not entries or previous_end != body_size:
        raise ValueError("field series body does not match its index")
    return header, entries


class FieldSeriesBuilder:
    """Disk-backed builder that keeps a full model run out of worker memory."""

    def __init__(self) -> None:
        self._temporary = tempfile.TemporaryDirectory(prefix="swd-field-series-")
        self._root = Path(self._temporary.name)
        self._entries: dict[tuple[int, int, int], list[tuple[str, int]]] = {}

    def append(self, *, z: int, x: int, y: int, valid_time: str, payload: bytes) -> None:
        cell = (z, x, y)
        with (self._root / f"{z}-{x}-{y}.parts").open("ab") as handle:
            handle.write(payload)
        self._entries.setdefault(cell, []).append((valid_time, len(payload)))

    def containers(self) -> Iterator[tuple[tuple[int, int, int], bytes]]:
        for cell in sorted(self._entries):
            z, x, y = cell
            combined = (self._root / f"{z}-{x}-{y}.parts").read_bytes()
            offset = 0
            entries = []
            for valid_time, length in self._entries[cell]:
                entries.append(SeriesEntry(valid_time, combined[offset : offset + length]))
                offset += length
            yield cell, encode_field_series(entries, z=z, x=x, y=y)

    def close(self) -> None:
        self._temporary.cleanup()

