from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from app.spatial_fields.contracts_v2 import FieldManifestV2, classify_freshness


def manifest_payload() -> dict:
    run = datetime(2026, 1, 1, tzinfo=timezone.utc)
    published = run + timedelta(minutes=20)
    return {
        "publication_id": "icon-eu-20260101T00Z-v2",
        "provider": "Deutscher Wetterdienst",
        "model": "ICON-EU",
        "model_run": run,
        "published_at": published,
        "valid_times": [run, run + timedelta(hours=1)],
        "coverage": {"west": -25, "south": 29, "east": 45, "north": 72},
        "grid": {
            "projection": "regular_ll",
            "grid_type": "regular_ll",
            "rows": 657,
            "columns": 1377,
            "longitude_convention": "-180_180",
            "scanning_mode": {"iScansNegatively": False, "jScansPositively": True},
            "definition": {"iDirectionIncrementInDegrees": 0.0625},
            "coordinates_sha256": "a" * 64,
        },
        "native_resolution": {"approximate_km": 7, "description": "ICON-EU native grid"},
        "display_resolution": {"approximate_km": 14, "description": "phase-0 decimation"},
        "variables": [
            {"name": "wind_u", "semantic": "eastward"},
            {"name": "wind_v", "semantic": "northward"},
        ],
        "quantization": {
            "variables": [
                {"variable": "wind_u", "scale": 0.05},
                {"variable": "wind_v", "scale": 0.05},
            ]
        },
        "compression": "gzip",
        "tile_scheme": {
            "tile_size": 128,
            "overlap": 1,
            "lod": [
                {"source_zoom": 4, "consumer_zoom_min": 0, "consumer_zoom_max": 5, "source_decimation": 1},
                {"source_zoom": 5, "consumer_zoom_min": 6, "consumer_zoom_max": 8, "source_decimation": 1},
            ],
        },
        "processing_version": "phase0.1",
        "quality_status": "candidate",
        "freshness": {
            "status": "fresh",
            "model_run_at": run,
            "source_discovered_at": run + timedelta(minutes=5),
            "processing_started_at": run + timedelta(minutes=10),
            "published_at": published,
            "expected_next_run_at": run + timedelta(hours=6),
            "age_seconds": 1200,
        },
        "attribution": [{
            "provider": "DWD",
            "text": "Contains DWD Open Data",
            "url": "https://opendata.dwd.de/",
            "licence": "GeoNutzV",
        }],
        "field_template": "assets/{valid_time}/{z}/{x}/{y}.swf2.gz",
        "checksums": {"asset_index": "b" * 64},
    }


def test_v2_contract_accepts_complete_vector_publication() -> None:
    manifest = FieldManifestV2.model_validate(manifest_payload())
    assert manifest.contract_version == "weather-field-v2"
    assert manifest.tile_scheme.spatial_interpolation == "bilinear_uv"


@pytest.mark.parametrize("section", ["variables", "quantization"])
def test_v2_contract_requires_paired_uv(section: str) -> None:
    payload = manifest_payload()
    if section == "variables":
        payload[section] = payload[section][:1]
    else:
        payload[section]["variables"] = payload[section]["variables"][:1]
    with pytest.raises(ValidationError, match="wind_u and wind_v|paired"):
        FieldManifestV2.model_validate(payload)


def test_v2_contract_rejects_non_utc_and_template_without_coordinates() -> None:
    payload = manifest_payload()
    payload["published_at"] = datetime(2026, 1, 1)
    with pytest.raises(ValidationError, match="UTC"):
        FieldManifestV2.model_validate(payload)

    payload = manifest_payload()
    payload["field_template"] = "assets/{valid_time}.swf2.gz"
    with pytest.raises(ValidationError, match="valid_time/z/x/y"):
        FieldManifestV2.model_validate(payload)


def test_v2_contract_rejects_inconsistent_vector_quantization() -> None:
    payload = deepcopy(manifest_payload())
    payload["quantization"]["variables"][1]["scale"] = 0.1
    with pytest.raises(ValidationError, match="share scale"):
        FieldManifestV2.model_validate(payload)


def test_non_experimental_contract_rejects_non_frozen_profile() -> None:
    payload = manifest_payload()
    payload["tile_scheme"]["tile_size"] = 256
    with pytest.raises(ValidationError, match="frozen v2 tile geometry"):
        FieldManifestV2.model_validate(payload)


@pytest.mark.parametrize(
    ("age", "status"),
    [(0, "fresh"), (9 * 3600, "fresh"), (9 * 3600 + 1, "delayed"),
     (15 * 3600 + 1, "stale"), (30 * 3600 + 1, "expired")],
)
def test_freshness_thresholds_are_explicit(age: int, status: str) -> None:
    assert classify_freshness(age) == status
