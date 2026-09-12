"""P0.2: corrected forecast snapshots persist with a valid quality tier.

``quality_level`` is constrained to baseline/automatic/calibrated/reviewed. The
publisher used to write "corrected", which the check constraint rejects, so a
genuinely corrected snapshot could never be stored. Quality (pipeline tier) and
correction status must stay separate: the tier stays valid and the correction
status + provenance live in ``snapshot.internal['correction']``.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from geoalchemy2 import WKTElement

from app.forecast.publisher import snapshot_quality_level
from app.models import ForecastSnapshot, Region, Spot

ALLOWED_QUALITY = {"baseline", "automatic", "calibrated", "reviewed"}


# --- pure mapping ----------------------------------------------------------


def test_snapshot_quality_level_never_returns_an_invalid_value():
    assert snapshot_quality_level({"applied": True, "confidence": "ok"}) == "automatic"
    assert snapshot_quality_level({"applied": False}) == "baseline"
    assert snapshot_quality_level(None) == "baseline"
    assert snapshot_quality_level({}) == "baseline"
    # Whatever the input, the value is always a constraint-valid tier, never "corrected".
    for correction in ({"applied": True}, {"applied": False}, {}, None):
        assert snapshot_quality_level(correction) in ALLOWED_QUALITY


# --- DB-backed: a corrected snapshot persists and round-trips --------------


@pytest.fixture
def snapshot_spot(db):
    suffix = uuid.uuid4().hex[:8]
    region = Region(slug=f"sq-region-{suffix}", name=f"SQ Region {suffix}",
                    normalized_name=f"sq region {suffix}", country="DE", status="published")
    db.add(region)
    db.flush()
    spot = Spot(slug=f"sq-spot-{suffix}", name=f"SQ Spot {suffix}",
                normalized_name=f"sq spot {suffix}", region_id=region.id,
                location=WKTElement("POINT(8.5 54.5)", srid=4326),
                sports=["wind"], water_type=["sea"], status="published")
    db.add(spot)
    db.commit()
    yield spot
    db.query(ForecastSnapshot).filter_by(spot_id=spot.id).delete()
    db.delete(spot)
    db.flush()
    db.delete(region)
    db.commit()


def test_corrected_snapshot_persists_with_valid_quality_and_keeps_provenance(db, snapshot_spot):
    correction = {"applied": True, "confidence": "ok"}
    quality = snapshot_quality_level(correction)
    assert quality in ALLOWED_QUALITY and quality != "corrected"

    generated = datetime.now(timezone.utc)
    snapshot = ForecastSnapshot(
        spot_id=snapshot_spot.id,
        generated_at=generated,
        valid_until=generated + timedelta(hours=3),
        consensus_version="family-uv-v1",
        physics_version="wind-v1",
        quality_level=quality,
        fallback_status="open_meteo_transition",
        payload={"correction": correction},
        internal={"correction": {
            "applied": True, "confidence": "ok",
            "consensus_version": "family-uv-v1", "physics_version": "wind-v1",
            "active_sector_versions": [2], "weather_serving_context": "deadbeef",
        }},
        active=False,
    )
    db.add(snapshot)
    db.commit()
    snapshot_id = snapshot.id
    db.expire_all()

    reloaded = db.get(ForecastSnapshot, snapshot_id)
    assert reloaded.quality_level == "automatic"
    # Correction status and provenance survive the round-trip, separate from quality.
    stored = reloaded.internal["correction"]
    assert stored["applied"] is True and stored["confidence"] == "ok"
    assert stored["active_sector_versions"] == [2]
    assert stored["consensus_version"] == "family-uv-v1"
    assert stored["physics_version"] == "wind-v1"
    assert stored["weather_serving_context"] == "deadbeef"
