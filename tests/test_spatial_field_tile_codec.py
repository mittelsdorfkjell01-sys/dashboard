import numpy as np
import pytest

from app.spatial_fields.tile_codec import (
    TileVariable,
    decode_field_tile,
    encode_field_tile,
    sha256_hex,
)


VARIABLES = (TileVariable("wind_u"), TileVariable("wind_v"))


def test_tile_codec_round_trip_is_quantized_and_deterministic() -> None:
    arrays = {
        "wind_u": np.array([[1.234, np.nan], [-2.345, 0.0]]),
        "wind_v": np.array([[4.567, 3.0], [2.0, -1.0]]),
    }
    metadata = {"valid_time": "2026-01-01T00:00:00Z", "z": 3, "x": 4, "y": 2}

    first = encode_field_tile(arrays, metadata=metadata, variables=VARIABLES, compression="gzip")
    second = encode_field_tile(arrays, metadata=metadata, variables=VARIABLES, compression="gzip")
    decoded = decode_field_tile(first, compression="gzip")

    assert first == second
    assert sha256_hex(first) == sha256_hex(second)
    assert decoded.header["layout"] == "planar"
    assert decoded.arrays["wind_u"][0, 0] == pytest.approx(1.25)
    assert np.isnan(decoded.arrays["wind_u"][0, 1])
    assert decoded.arrays["wind_v"][0, 0] == pytest.approx(4.55)


def test_tile_codec_rejects_unpaired_and_overflowing_fields() -> None:
    values = np.ones((2, 2))
    with pytest.raises(ValueError, match="paired"):
        encode_field_tile(
            {"wind_u": values},
            metadata={},
            variables=(TileVariable("wind_u"),),
        )
    with pytest.raises(ValueError, match="range"):
        encode_field_tile(
            {"wind_u": values * 2000, "wind_v": values},
            metadata={},
            variables=VARIABLES,
        )


def test_tile_codec_rejects_truncated_payload() -> None:
    values = np.ones((2, 2))
    encoded = encode_field_tile(
        {"wind_u": values, "wind_v": values},
        metadata={},
        variables=VARIABLES,
    )
    with pytest.raises(ValueError, match="size"):
        decode_field_tile(encoded[:-1])
