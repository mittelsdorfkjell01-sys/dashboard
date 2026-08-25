from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.nearshore.contracts import DatasetReference, NearshoreInput
from app.spatial_fields.contracts import FieldManifest


def manifest(layers):
    now = datetime.now(timezone.utc)
    return FieldManifest(
        snapshot_id="fixture-only", provider="fixture", model="test-grid",
        model_run=now, issued_at=now, valid_times=[now],
        coverage={"west": -10, "south": 40, "east": 10, "north": 60},
        zoom_min=0, zoom_max=6, tile_format="lerc", tile_url_template="fixture://{z}/{x}/{y}",
        layers=layers, quality_status="experimental", processing_version="test-v1", attribution=[],
    )


def test_wind_tiles_require_vector_components_together():
    with pytest.raises(ValidationError):
        manifest([{"variable": "wind_u", "unit": "m/s", "encoding": "float32"}])
    result = manifest([
        {"variable": "wind_u", "unit": "m/s", "encoding": "float32"},
        {"variable": "wind_v", "unit": "m/s", "encoding": "float32"},
    ])
    assert {layer.variable for layer in result.layers} == {"wind_u", "wind_v"}


def test_nearshore_refuses_missing_total_wave():
    dataset = DatasetReference(
        key="fixture", version="1", source="tests", licence="test-only",
        horizontal_resolution_m=100, coverage={"fixture": True},
    )
    with pytest.raises(ValidationError):
        NearshoreInput(
            spot_id="spot", valid_at=datetime.now(timezone.utc), offshore_waves={},
            bathymetry=dataset, coastline=dataset, model_configuration={},
        )


def test_public_field_endpoints_are_honestly_disabled(client):
    for layer in ("wind", "waves", "nearshore"):
        response = client.get(f"/weather-fields/{layer}")
        assert response.status_code == 200
        assert response.json()["public"] is False
        assert response.json()["active_manifest"] is None
