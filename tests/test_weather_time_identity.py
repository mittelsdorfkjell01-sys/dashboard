"""P0.3: one UTC normalisation path for serving and verification.

Open-Meteo is queried with ``timezone=auto``, so its hourly axis is local-naive.
Serving resolves it through ``provider_time_utc``/``provider_axis_utc`` (local ->
provider zone -> UTC); verification's ``store_forecast_samples`` now uses the same
path. A forecast sample, its observation and ``valid_at`` must reference the same
real UTC instant, and lead buckets must follow from that.
"""

from __future__ import annotations

import uuid
from datetime import datetime

import pytest
from geoalchemy2 import WKTElement

from app.live.weather_contract import provider_axis_utc, provider_time_utc
from app.models import Region, Spot, WeatherForecastSample, WeatherStation
from app.weather.verification import lead_bucket, store_forecast_samples


def _utc(text: str) -> datetime:
    return datetime.fromisoformat(text)


# --- shared normalisation across zones (serving == verification path) ------


def test_berlin_winter_local_is_one_hour_ahead_of_utc():
    (resolved,) = provider_axis_utc(["2026-01-15T12:00"], "Europe/Berlin")
    assert resolved == _utc("2026-01-15T11:00:00+00:00")
    # Serving's single-value helper agrees with the axis helper.
    assert provider_time_utc("2026-01-15T12:00", "Europe/Berlin") == resolved


def test_berlin_summer_local_is_two_hours_ahead_of_utc():
    (resolved,) = provider_axis_utc(["2026-07-01T12:00"], "Europe/Berlin")
    assert resolved == _utc("2026-07-01T10:00:00+00:00")
    assert provider_time_utc("2026-07-01T12:00", "Europe/Berlin") == resolved


def test_utc_zone_is_passed_through_unchanged():
    (resolved,) = provider_axis_utc(["2026-07-01T12:00"], "UTC")
    assert resolved == _utc("2026-07-01T12:00:00+00:00")


def test_spring_forward_axis_is_strictly_monotonic():
    # 2026-03-29: Berlin jumps 02:00 -> 03:00 (02:xx local does not exist).
    axis = provider_axis_utc(
        ["2026-03-29T01:00", "2026-03-29T03:00", "2026-03-29T04:00"], "Europe/Berlin"
    )
    assert axis == [
        _utc("2026-03-29T00:00:00+00:00"),
        _utc("2026-03-29T01:00:00+00:00"),
        _utc("2026-03-29T02:00:00+00:00"),
    ]


def test_fall_back_repeated_local_hour_resolves_to_distinct_utc_instants():
    # 2026-10-25: Berlin falls back, so 02:00 local occurs twice (CEST then CET).
    axis = provider_axis_utc(
        ["2026-10-25T02:00", "2026-10-25T02:00", "2026-10-25T03:00"], "Europe/Berlin"
    )
    assert axis[0] == _utc("2026-10-25T00:00:00+00:00")  # CEST (+2)
    assert axis[1] == _utc("2026-10-25T01:00:00+00:00")  # CET (+1), monotonic
    assert axis[2] == _utc("2026-10-25T02:00:00+00:00")
    assert axis[0] < axis[1] < axis[2]


# --- DB-backed: verification stores the same instant serving would show -----


@pytest.fixture
def sample_spot(db):
    suffix = uuid.uuid4().hex[:8]
    region = Region(slug=f"tz-region-{suffix}", name=f"TZ {suffix}",
                    normalized_name=f"tz {suffix}", country="DE", status="published")
    db.add(region)
    db.flush()
    spot = Spot(slug=f"tz-spot-{suffix}", name=f"TZ Spot {suffix}",
                normalized_name=f"tz spot {suffix}", region_id=region.id,
                location=WKTElement("POINT(13.4 52.5)", srid=4326),
                sports=["wind"], water_type=["sea"], status="published")
    db.add(spot)
    db.flush()
    station = WeatherStation(spot_id=spot.id, provider="dwd", provider_station_id="00123",
                             name="Ref", latitude=52.5, longitude=13.4, active=True,
                             approved=True, representativeness_status="passed")
    db.add(station)
    db.commit()
    yield spot
    db.query(WeatherForecastSample).filter_by(spot_id=spot.id).delete()
    db.query(WeatherStation).filter_by(spot_id=spot.id).delete()
    db.delete(spot)
    db.flush()
    db.delete(region)
    db.commit()


def test_store_forecast_samples_normalises_local_times_and_leads(db, sample_spot):
    issued_at = _utc("2026-07-01T06:00:00+00:00")
    raw = {
        "timezone": "Europe/Berlin",
        "hourly": {
            "time": ["2026-07-01T12:00", "2026-07-01T18:00"],  # local CEST (+2)
            "wind_speed_10m": [8.0, 9.0],
            "wind_direction_10m": [270.0, 280.0],
            "wind_gusts_10m": [11.0, 12.0],
        },
    }
    stored = store_forecast_samples(db, sample_spot.id, raw, ["icon"], issued_at)
    assert stored == 2

    samples = {
        s.valid_at: s
        for s in db.query(WeatherForecastSample).filter_by(spot_id=sample_spot.id).all()
    }
    noon = _utc("2026-07-01T10:00:00+00:00")  # 12:00 CEST -> 10:00Z, NOT 12:00Z
    assert noon in samples
    # Verification maps the Open-Meteo time to the same instant serving would.
    assert provider_time_utc("2026-07-01T12:00", "Europe/Berlin") == noon
    # Lead is computed from the true UTC instant (10:00Z - 06:00Z = 4h -> 0-48h).
    assert samples[noon].lead_hours == 4
    assert lead_bucket(samples[noon].lead_hours) == "0-48h"
