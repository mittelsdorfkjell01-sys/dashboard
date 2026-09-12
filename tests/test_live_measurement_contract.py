"""P0.1 regression: the three weather products stay separate and consistent.

`current` (model nowcast), `measurement` (station reading) and `forecast` are
distinct products. A measurement must never rewrite `current`, the assembled
model cache must never pin a measurement (so single/batch are order-independent),
the `sources` provenance must survive response validation, and a station import
must invalidate the measurement cache layer.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from app.live.cache import InMemoryCache
from app.live.public_cache import (
    get_public_live,
    get_public_measurement,
    public_measurement_key,
    set_public_live,
)
from app.schemas.live import LiveConditionsRead


def _provenance(source: str) -> dict:
    return {
        "source_type": "model_nowcast",
        "observation_type": "nowcast",
        "source": "model",
        "provider": source,
        "captured_at": datetime(2026, 1, 1, 12, tzinfo=timezone.utc),
        "requested_coordinate": {"latitude": 54.0, "longitude": 8.0},
        "quality_tier": "coordinates",
    }


def _live_payload() -> dict:
    return {
        "spot_id": str(uuid.uuid4()),
        "model": "surfwinddata",
        "models": [],
        "current": {"wind_ms": 10.0, "dir": 270.0},
        "sources": {
            "wind": _provenance("Surfwinddata · Open-Meteo"),
            "air": _provenance("Open-Meteo"),
            "marine": _provenance("Open-Meteo Marine"),
        },
    }


def test_sources_survives_response_validation():
    # Before P0.1 LiveConditionsRead had no `sources` field, so Pydantic silently
    # dropped the provenance the service produced.
    result = LiveConditionsRead.model_validate(_live_payload())
    assert result.sources is not None
    assert result.sources.wind.provider == "Surfwinddata · Open-Meteo"
    assert result.sources.air.source_type == "model_nowcast"
    assert result.sources.marine.observation_type == "nowcast"


def test_model_cache_never_pins_a_station_measurement():
    # Order-independence: regardless of which endpoint warms the cache, the stored
    # product is the model nowcast only — a measurement can never leak into it.
    cache = InMemoryCache()
    spot_id = uuid.uuid4()
    payload = _live_payload()
    payload["measurement"] = {"observation_type": "measurement", "wind_speed_ms": 7.0}
    set_public_live(cache, spot_id, payload, generation="0")
    cached = get_public_live(cache, spot_id, generation="0")
    assert cached is not None
    assert cached["measurement"] is None


def test_station_import_invalidates_the_measurement_cache_layer(db):
    from app.models import Region, Spot, WeatherStation
    from app.weather.observation_worker import persist_batch
    from app.weather.providers.common import normalize_observation
    from geoalchemy2 import WKTElement

    suffix = uuid.uuid4().hex[:8]
    region = Region(slug=f"mc-region-{suffix}", name=f"MC {suffix}",
                    normalized_name=f"mc {suffix}", country="DE", status="published")
    db.add(region)
    db.flush()
    spot = Spot(slug=f"mc-spot-{suffix}", name=f"MC Spot {suffix}",
                normalized_name=f"mc spot {suffix}", region_id=region.id,
                location=WKTElement("POINT(8.5 54.5)", srid=4326),
                sports=["wind"], water_type=["sea"], status="published")
    db.add(spot)
    db.flush()
    station = WeatherStation(spot_id=spot.id, provider="dwd", provider_station_id="00099",
                             name="Ref", latitude=54.5, longitude=8.5, active=True,
                             approved=True, representativeness_status="passed")
    db.add(station)
    db.commit()
    try:
        cache = InMemoryCache()
        # A stale entry in the measurement layer must be dropped by an import.
        cache.set(public_measurement_key(spot.id), {"stale": True}, 1800)
        rows = [normalize_observation(provider="dwd", station_id="00099",
                                      observed_at=datetime.now(timezone.utc),
                                      wind_speed_ms=7.0, wind_direction_deg=180.0,
                                      provider_quality="1")]
        report = persist_batch(db, station, rows, cache=cache, dry_run=False)
        assert report["persisted"] == 1
        # The import invalidates the layer (no hand-rolled, ungated row remains).
        assert cache.get(public_measurement_key(spot.id)) is None
        assert get_public_measurement(cache, spot.id) is None
    finally:
        db.query(WeatherStation).filter_by(spot_id=spot.id).delete()
        db.delete(spot)
        db.flush()
        db.delete(region)
        db.commit()
