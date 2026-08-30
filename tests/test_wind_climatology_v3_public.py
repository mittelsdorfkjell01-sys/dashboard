"""Public, read-only V3 weekly reliability contract (Phase 5)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from geoalchemy2.elements import WKTElement

from app.config import Settings
from app.models import (
    Region,
    Spot,
    SpotWeatherProfile,
    SpotWeatherSector,
    WindClimatologyCell,
    WindClimatologyV3Run,
    WindClimatologyV3Variant,
)
from app.wind_climatology.v3_artifact import encode_cube
from app.wind_climatology.v3_engine import ALGORITHM_VERSION


def _week(week: int, *, reliability=60.0, sample_years=19, successful_years=12, quality="high"):
    return {
        "week": week,
        "sample_years": sample_years,
        "successful_years": successful_years,
        "reliability_percent": reliability,
        "probability_at_least_1_day": 80.0,
        "probability_at_least_2_days": reliability,
        "probability_at_least_3_days": 30.0,
        "median_usable_days": 2.0,
        "median_session_hours": 9.0,
        "p25_session_hours": 5.0,
        "p75_session_hours": 14.0,
        "median_longest_session": 4.0,
        "quality_status": quality,
    }


def _cube_value(min_wind_kn, max_wind_kn, direction_mode, weeks):
    return {"min_wind_kn": min_wind_kn, "max_wind_kn": max_wind_kn, "direction_mode": direction_mode, "weeks": weeks}


@pytest.fixture
def v3_spot(db):
    suffix = uuid.uuid4().hex[:8]
    region = Region(
        slug=f"v3-region-{suffix}", name=f"V3 Region {suffix}",
        normalized_name=f"v3 region {suffix}", country="DE", status="published",
    )
    db.add(region)
    db.flush()
    spot = Spot(
        slug=f"v3-spot-{suffix}", name=f"V3 Spot {suffix}",
        normalized_name=f"v3 spot {suffix}", region_id=region.id,
        location=WKTElement("POINT(8.5 54.5)", srid=4326),
        sports=["wind"], water_type=["sea"], bottom_type=["sand"],
        level=["advanced"], water_character=["welle_klein"], style=[],
        status="published",
    )
    db.add(spot)
    db.flush()
    cell = WindClimatologyCell(spot_id=spot.id, spot_lat=54.5, spot_lon=8.5, requested_lat=54.5, requested_lon=8.5, actual_lat=54.5, actual_lon=8.5)
    db.add(cell)
    db.commit()
    yield spot, cell
    db.delete(spot)
    db.flush()
    db.delete(region)
    db.commit()


def _add_active_run(db, spot, cell, *, variants: dict[tuple[int, int | None, str], list[dict]]):
    run = WindClimatologyV3Run(
        spot_id=spot.id, cell_id=cell.id, start_year=2006, end_year=2025,
        algorithm_version=ALGORITHM_VERSION, config_hash=uuid.uuid4().hex,
        status="ready", is_active=True, activated_at=datetime.now(timezone.utc),
    )
    db.add(run)
    db.flush()
    for (min_kn, max_kn, mode), weeks in variants.items():
        blob, digest = encode_cube(_cube_value(min_kn, max_kn, mode, weeks))
        db.add(WindClimatologyV3Variant(run_id=run.id, min_wind_kn=min_kn, max_wind_kn=max_kn, direction_mode=mode, payload_blob=blob, payload_sha256=digest, payload_bytes=len(blob)))
    db.commit()
    return run


def _default_weeks(**overrides):
    return [_week(week, **overrides) for week in range(1, 53)]


def _enable_public(monkeypatch, *, allowlist=None):
    settings = Settings(
        wind_climatology_v3_public_enabled=True,
        wind_climatology_v3_public_spot_ids=[str(item) for item in allowlist] if allowlist else [],
    )
    monkeypatch.setattr("app.wind_climatology.v3_service.get_settings", lambda: settings)


def _disable_public(monkeypatch):
    settings = Settings(wind_climatology_v3_public_enabled=False)
    monkeypatch.setattr("app.wind_climatology.v3_service.get_settings", lambda: settings)


def test_flag_off_hides_v3_even_with_ready_active_run(anon_client, db, v3_spot, monkeypatch):
    spot, cell = v3_spot
    _add_active_run(db, spot, cell, variants={(15, 20, "all"): _default_weeks()})
    _disable_public(monkeypatch)
    response = anon_client.get(f"/spots/{spot.id}/wind-climatology-v3")
    assert response.status_code == 404


def test_flag_on_no_active_run_returns_404(anon_client, db, v3_spot, monkeypatch):
    spot, _ = v3_spot
    _enable_public(monkeypatch)
    response = anon_client.get(f"/spots/{spot.id}/wind-climatology-v3")
    assert response.status_code == 404


def test_pilot_allowlist_excludes_non_listed_spots(anon_client, db, v3_spot, monkeypatch):
    spot, cell = v3_spot
    _add_active_run(db, spot, cell, variants={(15, 20, "all"): _default_weeks()})
    _enable_public(monkeypatch, allowlist=[uuid.uuid4()])
    response = anon_client.get(f"/spots/{spot.id}/wind-climatology-v3")
    assert response.status_code == 404


def test_pilot_allowlist_admits_listed_spot(anon_client, db, v3_spot, monkeypatch):
    spot, cell = v3_spot
    _add_active_run(db, spot, cell, variants={(15, 20, "all"): _default_weeks()})
    _enable_public(monkeypatch, allowlist=[spot.id])
    response = anon_client.get(f"/spots/{spot.id}/wind-climatology-v3")
    assert response.status_code == 200


def test_default_window_returns_exactly_52_weeks_and_public_shape(anon_client, db, v3_spot, monkeypatch):
    spot, cell = v3_spot
    _add_active_run(db, spot, cell, variants={(15, 20, "all"): _default_weeks()})
    _enable_public(monkeypatch)
    response = anon_client.get(f"/spots/{spot.id}/wind-climatology-v3")
    assert response.status_code == 200
    body = response.json()
    assert len(body["weeks"]) == 52
    assert body["selection"] == {"min_wind_kn": 15, "max_wind_kn": 20, "direction_mode": "all"}
    assert body["default_window"] == {"min_wind_kn": 15, "max_wind_kn": 20}
    assert body["attribution"] == "Open-Meteo / ERA5"
    assert body["period"] == [2006, 2025]
    assert body["direction"]["usable_available"] is False
    week_one = body["weeks"][0]
    assert week_one["week"] == 1
    assert set(week_one) == {
        "week", "date_range", "sample_years", "successful_years", "reliability_percent",
        "reliability_low_percent", "reliability_high_percent",
        "probability_at_least_1_day", "probability_at_least_2_days", "probability_at_least_3_days",
        "median_usable_days", "median_session_hours", "p25_session_hours", "p75_session_hours",
        "median_longest_session", "quality_status",
    }
    # no internal fields ever leak
    for forbidden in ("error", "warnings", "config_hash", "run_id", "cache_key"):
        assert forbidden not in body


def test_no_internal_error_or_warning_data_in_response_text(anon_client, db, v3_spot, monkeypatch):
    spot, cell = v3_spot
    run = _add_active_run(db, spot, cell, variants={(15, 20, "all"): _default_weeks()})
    run.error = "secret provider stacktrace"
    run.warnings = ["internal warning detail"]
    db.commit()
    _enable_public(monkeypatch)
    response = anon_client.get(f"/spots/{spot.id}/wind-climatology-v3")
    assert response.status_code == 200
    assert "secret provider stacktrace" not in response.text
    assert "internal warning detail" not in response.text


def test_invalid_window_bounds_are_rejected(anon_client, db, v3_spot, monkeypatch):
    spot, cell = v3_spot
    _add_active_run(db, spot, cell, variants={(15, 20, "all"): _default_weeks()})
    _enable_public(monkeypatch)
    assert anon_client.get(f"/spots/{spot.id}/wind-climatology-v3?min_wind_kn=4").status_code == 422
    assert anon_client.get(f"/spots/{spot.id}/wind-climatology-v3?min_wind_kn=20&max_wind_kn=15").status_code == 422


def test_open_upper_window_reports_null_max(anon_client, db, v3_spot, monkeypatch):
    spot, cell = v3_spot
    _add_active_run(db, spot, cell, variants={(30, None, "all"): _default_weeks()})
    _enable_public(monkeypatch)
    response = anon_client.get(f"/spots/{spot.id}/wind-climatology-v3?min_wind_kn=30&open_upper=true")
    assert response.status_code == 200
    assert response.json()["selection"] == {"min_wind_kn": 30, "max_wind_kn": None, "direction_mode": "all"}


def test_usable_mode_without_reviewed_directions_is_rejected(anon_client, db, v3_spot, monkeypatch):
    spot, cell = v3_spot
    _add_active_run(db, spot, cell, variants={(15, 20, "all"): _default_weeks()})
    _enable_public(monkeypatch)
    response = anon_client.get(f"/spots/{spot.id}/wind-climatology-v3?direction_mode=usable")
    assert response.status_code == 422


def test_usable_mode_available_with_reviewed_directions_and_description(anon_client, db, v3_spot, monkeypatch):
    spot, cell = v3_spot
    profile = SpotWeatherProfile(spot_id=spot.id, reviewed_at=datetime.now(timezone.utc), active=True)
    db.add(profile)
    db.flush()
    db.add(SpotWeatherSector(profile_id=profile.id, start_deg=247.5, end_deg=315.0, enabled=True))
    db.commit()
    _add_active_run(db, spot, cell, variants={
        (15, 20, "all"): _default_weeks(),
        (15, 20, "usable"): _default_weeks(reliability=45.0, successful_years=9),
    })
    _enable_public(monkeypatch)
    response = anon_client.get(f"/spots/{spot.id}/wind-climatology-v3?direction_mode=usable")
    assert response.status_code == 200
    body = response.json()
    assert body["direction"]["usable_available"] is True
    assert body["direction"]["description"] == "WSW bis NW"
    assert body["direction"]["selected_mode"] == "usable"


def test_variant_missing_for_requested_window_returns_404(anon_client, db, v3_spot, monkeypatch):
    spot, cell = v3_spot
    _add_active_run(db, spot, cell, variants={(15, 20, "all"): _default_weeks()})
    _enable_public(monkeypatch)
    response = anon_client.get(f"/spots/{spot.id}/wind-climatology-v3?min_wind_kn=10&max_wind_kn=15")
    assert response.status_code == 404


def test_active_run_stays_available_while_a_refresh_is_in_flight(anon_client, db, v3_spot, monkeypatch):
    spot, cell = v3_spot
    _add_active_run(db, spot, cell, variants={(15, 20, "all"): _default_weeks()})
    pending = WindClimatologyV3Run(
        spot_id=spot.id, cell_id=cell.id, start_year=2006, end_year=2025,
        algorithm_version=ALGORITHM_VERSION, config_hash=uuid.uuid4().hex, status="pending", is_active=False,
    )
    db.add(pending)
    db.commit()
    _enable_public(monkeypatch)
    response = anon_client.get(f"/spots/{spot.id}/wind-climatology-v3")
    assert response.status_code == 200
    assert len(response.json()["weeks"]) == 52


def test_failed_run_without_prior_active_falls_back_to_not_found(anon_client, db, v3_spot, monkeypatch):
    spot, cell = v3_spot
    failed = WindClimatologyV3Run(
        spot_id=spot.id, cell_id=cell.id, start_year=2006, end_year=2025,
        algorithm_version=ALGORITHM_VERSION, config_hash=uuid.uuid4().hex, status="failed", is_active=False, error="provider timeout",
    )
    db.add(failed)
    db.commit()
    _enable_public(monkeypatch)
    response = anon_client.get(f"/spots/{spot.id}/wind-climatology-v3")
    assert response.status_code == 404


def test_unpublished_spot_never_serves_v3(anon_client, db, v3_spot, monkeypatch):
    spot, cell = v3_spot
    _add_active_run(db, spot, cell, variants={(15, 20, "all"): _default_weeks()})
    spot.status = "draft"
    db.commit()
    _enable_public(monkeypatch)
    response = anon_client.get(f"/spots/{spot.id}/wind-climatology-v3")
    assert response.status_code == 404


def test_response_is_edge_cacheable_and_carries_an_etag(anon_client, db, v3_spot, monkeypatch):
    spot, cell = v3_spot
    _add_active_run(db, spot, cell, variants={(15, 20, "all"): _default_weeks()})
    _enable_public(monkeypatch)
    response = anon_client.get(f"/spots/{spot.id}/wind-climatology-v3")
    assert response.status_code == 200
    assert "s-maxage" in response.headers.get("cache-control", "")
    assert response.headers.get("etag")


def test_best_season_is_absolute_not_relative_to_a_weak_maximum(anon_client, db, v3_spot, monkeypatch):
    spot, cell = v3_spot
    weak_year_weeks = _default_weeks(reliability=20.0, successful_years=4, quality="limited")
    _add_active_run(db, spot, cell, variants={(15, 20, "all"): weak_year_weeks})
    _enable_public(monkeypatch)
    response = anon_client.get(f"/spots/{spot.id}/wind-climatology-v3")
    assert response.status_code == 200
    assert response.json()["best_season"] is None


def test_best_season_reports_longest_reliable_run(anon_client, db, v3_spot, monkeypatch):
    spot, cell = v3_spot
    weeks = _default_weeks(reliability=20.0, successful_years=4, quality="limited")
    for week in weeks[19:35]:
        week["reliability_percent"] = 70.0
        week["successful_years"] = 14
        week["quality_status"] = "high"
    _add_active_run(db, spot, cell, variants={(15, 20, "all"): weeks})
    _enable_public(monkeypatch)
    response = anon_client.get(f"/spots/{spot.id}/wind-climatology-v3")
    assert response.status_code == 200
    season = response.json()["best_season"]
    assert season is not None
    assert season["start_week"] == 20
    assert season["end_week"] == 35


def test_best_season_wraps_across_december_and_january(anon_client, db, v3_spot, monkeypatch):
    spot, cell = v3_spot
    weeks = _default_weeks(reliability=20.0, successful_years=4, quality="limited")
    for week in weeks[:8] + weeks[48:]:
        week["reliability_percent"] = 70.0
        week["successful_years"] = 14
        week["quality_status"] = "high"
    _add_active_run(db, spot, cell, variants={(15, 20, "all"): weeks})
    _enable_public(monkeypatch)

    season = anon_client.get(f"/spots/{spot.id}/wind-climatology-v3").json()["best_season"]

    assert season["start_week"] == 49
    assert season["end_week"] == 8
    assert season["start_date"].startswith("12-")
    assert season["end_date"].startswith("02-")
