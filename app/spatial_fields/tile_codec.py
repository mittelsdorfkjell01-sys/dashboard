"""Deterministic phase-0 binary codec for paired u/v field tiles."""

from __future__ import annotations

from dataclasses import dataclass
import gzip
import hashlib
import json
import struct
from typing import Literal

import numpy as np

from app.spatial_fields.contracts_v2 import WIND_COMPONENT_SCALE_MS_V2


MAGIC = b"SWF2"
PREFIX = struct.Struct("<4sI")


@dataclass(frozen=True)
class TileVariable:
    name: str
    scale: float = WIND_COMPONENT_SCALE_MS_V2
    offset: float = 0.0
    nodata: int = -32768


@dataclass(frozen=True)
class DecodedFieldTile:
    header: dict
    arrays: dict[str, np.ndarray]


def _quantize(values: np.ndarray, variable: TileVariable) -> np.ndarray:
    source = np.asarray(values, dtype=np.float64)
    finite = np.isfinite(source)
    quantized = np.full(source.shape, variable.nodata, dtype="<i2")
    if finite.any():
        scaled = np.rint((source[finite] - variable.offset) / variable.scale)
        if (scaled < -32767).any() or (scaled > 32767).any():
            raise ValueError(f"{variable.name} exceeds int16 quantization range")
        quantized[finite] = scaled.astype("<i2")
    return quantized


def _compress(payload: bytes, compression: Literal["none", "gzip", "brotli"]) -> bytes:
    if compression == "none":
        return payload
    if compression == "gzip":
        return gzip.compress(payload, compresslevel=9, mtime=0)
    try:
        import brotli  # type: ignore[import-not-found]
    except ImportError as exc:
        raise RuntimeError("brotli compression requires the optional brotli package") from exc
    return brotli.compress(payload, quality=9)


def _decompress(payload: bytes, compression: Literal["none", "gzip", "brotli"]) -> bytes:
    if compression == "none":
        return payload
    if compression == "gzip":
        return gzip.decompress(payload)
    try:
        import brotli  # type: ignore[import-not-found]
    except ImportError as exc:
        raise RuntimeError("brotli decompression requires the optional brotli package") from exc
    return brotli.decompress(payload)


def encode_field_tile(
    arrays: dict[str, np.ndarray],
    *,
    metadata: dict,
    variables: tuple[TileVariable, ...],
    compression: Literal["none", "gzip", "brotli"] = "none",
) -> bytes:
    names = tuple(variable.name for variable in variables)
    has_vector_pair = any(
        set(pair).issubset(names)
        for pair in (("wind_u", "wind_v"), ("wave_u", "wave_v"))
    )
    if len(names) != len(set(names)) or not has_vector_pair:
        raise ValueError("tiles require a unique paired wind or wave vector")
    if set(arrays) != set(names):
        raise ValueError("tile arrays must exactly match declared variables")
    shapes = {np.asarray(array).shape for array in arrays.values()}
    if len(shapes) != 1:
        raise ValueError("all tile variables must share one shape")
    shape = shapes.pop()
    if len(shape) != 2 or min(shape) < 2:
        raise ValueError("tile arrays must be two-dimensional")

    header = {
        "schema": "swd-field-tile-v2",
        "width": shape[1],
        "height": shape[0],
        "layout": "planar",
        "byte_order": "little",
        "variables": [
            {
                "name": variable.name,
                "dtype": "int16",
                "scale": variable.scale,
                "offset": variable.offset,
                "nodata": variable.nodata,
            }
            for variable in variables
        ],
        **metadata,
    }
    header_bytes = json.dumps(
        header, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")
    body = b"".join(
        _quantize(arrays[variable.name], variable).tobytes(order="C")
        for variable in variables
    )
    return _compress(PREFIX.pack(MAGIC, len(header_bytes)) + header_bytes + body, compression)


def decode_field_tile(
    payload: bytes,
    *,
    compression: Literal["none", "gzip", "brotli"] = "none",
) -> DecodedFieldTile:
    raw = _decompress(payload, compression)
    if len(raw) < PREFIX.size:
        raise ValueError("field tile is truncated")
    magic, header_size = PREFIX.unpack_from(raw)
    if magic != MAGIC:
        raise ValueError("field tile magic is invalid")
    header_end = PREFIX.size + header_size
    if header_end > len(raw):
        raise ValueError("field tile header is truncated")
    header = json.loads(raw[PREFIX.size:header_end].decode("utf-8"))
    if header.get("schema") != "swd-field-tile-v2":
        raise ValueError("unsupported field tile schema")
    width, height = int(header["width"]), int(header["height"])
    cell_count = width * height
    expected_size = header_end + cell_count * 2 * len(header["variables"])
    if len(raw) != expected_size:
        raise ValueError("field tile payload size does not match its header")
    arrays: dict[str, np.ndarray] = {}
    offset = header_end
    for variable in header["variables"]:
        stored = np.frombuffer(raw, dtype="<i2", count=cell_count, offset=offset).reshape(
            height, width
        )
        offset += cell_count * 2
        decoded = stored.astype(np.float64) * float(variable["scale"]) + float(
            variable["offset"]
        )
        decoded[stored == int(variable["nodata"])] = np.nan
        arrays[str(variable["name"])] = decoded
    return DecodedFieldTile(header=header, arrays=arrays)


def sha256_hex(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()
