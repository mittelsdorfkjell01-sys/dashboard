import pytest

from app.spatial_fields.series_codec import (
    FieldSeriesBuilder,
    SeriesEntry,
    decode_field_series,
    encode_field_series,
)


def test_series_codec_round_trips_ordered_time_tiles() -> None:
    payload = encode_field_series(
        [SeriesEntry("20261011T03Z", b"later"), SeriesEntry("20261011T00Z", b"first")],
        z=5,
        x=16,
        y=10,
    )

    header, entries = decode_field_series(payload)

    assert (header["z"], header["x"], header["y"]) == (5, 16, 10)
    assert [(entry.valid_time, entry.payload) for entry in entries] == [
        ("20261011T00Z", b"first"),
        ("20261011T03Z", b"later"),
    ]


def test_series_codec_rejects_truncated_body() -> None:
    payload = encode_field_series([SeriesEntry("20261011T00Z", b"tile")], z=4, x=8, y=5)
    with pytest.raises(ValueError, match="index|body"):
        decode_field_series(payload[:-1])


def test_disk_backed_builder_groups_cells_without_mixing_payloads() -> None:
    builder = FieldSeriesBuilder()
    try:
        builder.append(z=4, x=8, y=5, valid_time="20261011T00Z", payload=b"a")
        builder.append(z=4, x=9, y=5, valid_time="20261011T00Z", payload=b"b")
        builder.append(z=4, x=8, y=5, valid_time="20261011T03Z", payload=b"c")
        containers = dict(builder.containers())
    finally:
        builder.close()

    assert [entry.payload for entry in decode_field_series(containers[(4, 8, 5)])[1]] == [b"a", b"c"]
    assert [entry.payload for entry in decode_field_series(containers[(4, 9, 5)])[1]] == [b"b"]
