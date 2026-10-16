from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from app.spatial_fields.contracts import BoundingBox
from app.tides.geocorrection import ConstituentCorrection, interpolate_constituent_correction
from app.tides.marine_field import (
    MarineAttribution,
    MarineFieldManifest,
    MarineVariableDefinition,
)
from app.tides.service import _normalized_hourly_series
from app.tides.station_import import evidence_hash
from app.tides.stations import ProviderObservation


def test_marine_field_contract_requires_datum_for_metric_levels():
    with pytest.raises(ValidationError, match="explicit model datum"):
        MarineVariableDefinition(name="tide_elevation_model_m", unit="m")


def test_marine_field_contract_accepts_safe_normalized_tide_publication():
    start = datetime(2026, 10, 13, tzinfo=timezone.utc)
    manifest = MarineFieldManifest(
        publication_id="fes-2022b-20261013",
        provider="AVISO+",
        model="FES2022b",
        model_run=start,
        published_at=start,
        valid_times=[start, start + timedelta(hours=1)],
        coverage=BoundingBox(west=-30, south=25, east=45, north=72),
        variables=[MarineVariableDefinition(name="tide_level_normalized", unit="1")],
        wet_mask_version="v1",
        quality_status="candidate",
        field_template="/{valid_time}/{z}/{x}/{y}.webp",
        series_template="/series/{z}/{x}/{y}.json",
        processing_version="1",
        attribution=[MarineAttribution(
            provider="AVISO+", text="FES2022b", url="https://www.aviso.altimetry.fr/", licence="provider terms"
        )],
    )
    assert manifest.contract_version == "marine-field-v1"


def test_geocorrection_is_basin_gated_and_wraps_phase_angles():
    corrections = [
        ConstituentCorrection(1.1, 359, 1, "north_sea", 10, True),
        ConstituentCorrection(0.9, 1, 1, "north_sea", 10, True),
        ConstituentCorrection(4.0, 180, 20, "baltic", 1, True),
    ]
    ratio, phase = interpolate_constituent_correction(
        corrections, target_basin="north_sea", max_water_path_km=100
    ) or (None, None)
    assert ratio == pytest.approx((1.1 * 0.9) ** 0.5)
    assert phase == pytest.approx(0, abs=0.01)


def test_normalized_series_starts_at_current_instant_and_covers_hours():
    start = datetime(2026, 10, 13, 10, 23, tzinfo=timezone.utc)
    events = [
        {"event_type": "low", "time": start - timedelta(hours=2)},
        {"event_type": "high", "time": start + timedelta(hours=4)},
        {"event_type": "low", "time": start + timedelta(hours=10)},
    ]
    series = _normalized_hourly_series(events, start=start, end=start + timedelta(hours=3))
    assert series[0]["time"] == start
    assert all(0 <= point["level_normalized"] <= 1 for point in series)


def test_station_evidence_hash_is_deterministic_for_raw_key_order():
    now = datetime(2026, 10, 13, tzinfo=timezone.utc)
    common = dict(
        provider="test", provider_station_id="s1", provider_sensor_id="s1:w",
        observed_at=now, value_m=1.2, unit="m", vertical_datum=None,
        quality_status="raw",
    )
    assert evidence_hash(ProviderObservation(**common, raw={"a": 1, "b": 2})) == evidence_hash(
        ProviderObservation(**common, raw={"b": 2, "a": 1})
    )
