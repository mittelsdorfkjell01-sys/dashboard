from __future__ import annotations

import math
import uuid
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest
from geoalchemy2.elements import WKTElement
from sqlalchemy import select

from app.live.cache import InMemoryCache
from app.live.deps import get_cache, get_om_client
from app.main import app
from app.models import (
    Region,
    Spot,
    TideCalculationRun,
    TideEvent,
    TideEventOverride,
    TideProfile,
)
from app.tides import ALGORITHM_VERSION
from app.tides.calculation import (
    CurvePoint,
    calibration_suggestion,
    corrected_time,
    detect_extrema,
    phase_at,
)
from app.tides.rollout import bootstrap_europe_profiles


class _UnavailableMarineClient:
    def fetch_marine(self, lat, lon, days=7):
        return {"timezone": "GMT", "hourly": {"time": [], "sea_level_height_msl": []}}


@pytest.fixture(autouse=True)
def _local_tide_provider():
    """Never let a tide endpoint test reach an external weather provider."""

    previous_client = app.dependency_overrides.get(get_om_client)
    previous_cache = app.dependency_overrides.get(get_cache)
    app.dependency_overrides[get_om_client] = lambda: _UnavailableMarineClient()
    app.dependency_overrides[get_cache] = lambda: InMemoryCache()
    yield
    if previous_client is None:
        app.dependency_overrides.pop(get_om_client, None)
    else:
        app.dependency_overrides[get_om_client] = previous_client
    if previous_cache is None:
        app.dependency_overrides.pop(get_cache, None)
    else:
        app.dependency_overrides[get_cache] = previous_cache


def _curve(start: datetime, hours: int = 36, step_minutes: int = 10):
    return [
        CurvePoint(
            start + timedelta(minutes=index * step_minutes),
            math.cos(2 * math.pi * (index * step_minutes) / (12.42 * 60)),
        )
        for index in range(hours * 60 // step_minutes)
    ]


def test_extrema_are_stable_and_chronological_across_year_boundary():
    events = detect_extrema(_curve(datetime(2026, 12, 31, 12, tzinfo=timezone.utc)))
    assert len(events) >= 4
    assert all(a.time < b.time for a, b in zip(events, events[1:]))
    assert all(a.event_type != b.event_type for a, b in zip(events, events[1:]))
    assert any(event.time.year == 2027 for event in events)


def test_correction_order_is_global_then_event_specific():
    raw = datetime(2026, 8, 6, 12, tzinfo=timezone.utc)
    assert corrected_time(
        raw, "high", global_offset_minutes=10,
        high_offset_minutes=-4, low_offset_minutes=20,
    ) == raw + timedelta(minutes=6)
    assert corrected_time(
        raw, "low", global_offset_minutes=10,
        high_offset_minutes=-4, low_offset_minutes=20,
    ) == raw + timedelta(minutes=30)


def test_calibration_suggestion_is_robust_to_outlier():
    result = calibration_suggestion([
        ("high", 18), ("high", 20), ("high", 22), ("high", 180),
        ("low", -11), ("low", -9),
    ])
    assert result["high"]["offset_minutes"] == 21
    assert result["high"]["count"] == 4
    assert result["low"]["offset_minutes"] == -10


def test_phase_uses_surrounding_events():
    now = datetime(2026, 8, 6, 12, tzinfo=timezone.utc)
    phase, position = phase_at([
        ("low", now - timedelta(hours=3)),
        ("high", now + timedelta(hours=3)),
    ], now)
    assert phase == "rising"
    assert position == pytest.approx(0.5)


def test_utc_instants_render_across_european_dst_jump():
    berlin = ZoneInfo("Europe/Berlin")
    before = datetime(2026, 3, 29, 0, 30, tzinfo=timezone.utc).astimezone(berlin)
    after = datetime(2026, 3, 29, 1, 30, tzinfo=timezone.utc).astimezone(berlin)
    assert before.strftime("%H:%M %z") == "01:30 +0100"
    assert after.strftime("%H:%M %z") == "03:30 +0200"


@pytest.fixture
def tide_spot(db):
    suffix = uuid.uuid4().hex[:8]
    region = Region(
        slug=f"tide-region-{suffix}", name=f"Tide Region {suffix}",
        normalized_name=f"tide region {suffix}", country="DE", status="published",
    )
    db.add(region)
    db.flush()
    spot = Spot(
        slug=f"tide-spot-{suffix}", name=f"Tide Spot {suffix}",
        normalized_name=f"tide spot {suffix}", region_id=region.id,
        location=WKTElement("POINT(8.5 54.5)", srid=4326),
        sports=["surf"], water_type=["sea"], bottom_type=["sand"],
        level=["advanced"], water_character=["welle_klein"], style=[],
        status="published",
    )
    db.add(spot)
    db.commit()
    yield spot
    db.delete(spot)
    db.flush()
    db.delete(region)
    db.commit()


def test_publishing_needs_a_reviewed_anchor_and_a_finished_calculation(client, tide_spot):
    """The admin gate refuses to publish before the anchor is reviewed and the
    FES calculation has succeeded."""
    created = client.get(f"/admin/spots/{tide_spot.id}/tide")
    assert created.status_code == 200
    refused = client.patch(f"/admin/spots/{tide_spot.id}/tide", json={
        "enabled": True,
        "public_enabled": True,
        "timezone": "Europe/Berlin",
    })
    assert refused.status_code == 422, refused.text


def test_public_tides_fail_closed_and_hide_admin_notes(anon_client, client, db, tide_spot):
    """Second line of defence: even with the published flag forced on in the
    database, an unreviewed, uncalculated profile serves nothing — and the
    internal note never reaches the public payload."""
    created = client.get(f"/admin/spots/{tide_spot.id}/tide")
    assert created.status_code == 200
    noted = client.patch(f"/admin/spots/{tide_spot.id}/tide", json={
        "enabled": True,
        "timezone": "Europe/Berlin",
        "note": "interne fachliche Notiz",
    })
    assert noted.status_code == 200, noted.text

    # Set the flag past the admin gate on purpose: the public read must stand
    # on its own, not on the write path having been careful.
    db.expire_all()
    profile = db.scalar(select(TideProfile).where(TideProfile.spot_id == tide_spot.id))
    profile.public_enabled = True
    db.commit()

    response = anon_client.get(f"/spots/{tide_spot.id}/tides")
    assert response.status_code == 200
    assert response.json()["available"] is False
    assert "interne fachliche Notiz" not in response.text


def test_public_tides_use_modelled_sea_level_when_fes_is_unavailable(anon_client, tide_spot):
    class CurrentMarineClient:
        def fetch_marine(self, lat, lon, days=7):
            start = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0) - timedelta(hours=18)
            count = 11 * 24
            return {
                "timezone": "GMT",
                "hourly": {
                    "time": [(start + timedelta(hours=i)).isoformat() for i in range(count)],
                    "sea_level_height_msl": [
                        round(0.7 * math.sin(2 * math.pi * i / 12.42), 3)
                        for i in range(count)
                    ],
                },
            }

    app.dependency_overrides[get_om_client] = lambda: CurrentMarineClient()
    app.dependency_overrides[get_cache] = lambda: InMemoryCache()

    response = anon_client.get(f"/spots/{tide_spot.id}/tides?days=10")
    assert response.status_code == 200
    body = response.json()
    assert body["available"] is True
    assert body["product_type"] == "modelled_sea_level"
    assert body["datum"] == "mean_sea_level"
    assert body["navigational"] is False
    assert body["current_level_m"] is not None
    assert body["events"]
    assert body["source_name"] == "Open-Meteo Marine"


def test_europe_bootstrap_is_bounded_private_and_idempotent(db, tide_spot):
    preview = bootstrap_europe_profiles(db, apply=False, limit=1000)
    assert any(item["spot_id"] == str(tide_spot.id) for item in preview["planned"])
    assert db.scalar(select(TideProfile).where(TideProfile.spot_id == tide_spot.id)) is None

    applied = bootstrap_europe_profiles(db, apply=True, limit=1000)
    assert applied["queued"] >= 1
    profile = db.scalar(select(TideProfile).where(TideProfile.spot_id == tide_spot.id))
    assert profile is not None
    assert profile.enabled is True
    assert profile.public_enabled is False
    run_count = len(list(db.scalars(select(TideCalculationRun).where(
        TideCalculationRun.spot_id == tide_spot.id,
        TideCalculationRun.status == "queued",
    ))))
    assert run_count == 1

    second = bootstrap_europe_profiles(db, apply=True, limit=1000)
    assert second["pending"] >= 1
    assert len(list(db.scalars(select(TideCalculationRun).where(
        TideCalculationRun.spot_id == tide_spot.id,
        TideCalculationRun.status == "queued",
    )))) == run_count


def test_admin_tide_permissions_and_offset_validation(anon_client, curator_client, tide_spot):
    assert anon_client.get(f"/admin/spots/{tide_spot.id}/tide").status_code == 401
    assert curator_client.get(f"/admin/spots/{tide_spot.id}/tide").status_code == 200
    response = curator_client.patch(f"/admin/spots/{tide_spot.id}/tide", json={
        "global_offset_minutes": 999,
    })
    assert response.status_code == 422


def test_public_events_return_only_after_review_and_calculation(client, anon_client, db, tide_spot):
    profile = db.scalar(select(TideProfile).where(TideProfile.spot_id == tide_spot.id))
    if profile is None:
        client.get(f"/admin/spots/{tide_spot.id}/tide")
        db.expire_all()
        profile = db.scalar(select(TideProfile).where(TideProfile.spot_id == tide_spot.id))
    profile.enabled = True
    profile.public_enabled = True
    profile.timezone = "Europe/Berlin"
    profile.anchor_status = "reviewed"
    profile.quality_status = "reviewed_anchor"
    profile.calculation_status = "ready"
    profile.last_calculated_at = datetime.now(timezone.utc)
    now = datetime.now(timezone.utc)
    for index, kind in enumerate(("low", "high", "low", "high")):
        at = now + timedelta(hours=index * 3 - 2)
        db.add(TideEvent(
            spot_id=tide_spot.id, profile_version=profile.version,
            cycle_key=f"{kind}:{at.isoformat()}", event_type=kind,
            raw_time=at, corrected_time=at, relative_height=float(index),
            uncertainty_minutes=30, calculated_at=now,
            model_name="FES2022b", model_version="2022b",
        ))
    db.commit()
    response = anon_client.get(f"/spots/{tide_spot.id}/tides")
    assert response.status_code == 200
    body = response.json()
    assert body["available"] is True
    assert body["timezone"] == "Europe/Berlin"
    assert body["quality"] == "reviewed_anchor"
    assert body["events"]


def test_coordinate_change_invalidates_anchor_and_publication(db, tide_spot):
    from app.tides.service import get_or_create_profile, invalidate_for_coordinates

    profile = get_or_create_profile(tide_spot.id, db=db, actor="test")
    profile.enabled = True
    profile.public_enabled = True
    profile.automatic_anchor = WKTElement("POINT(8.51 54.51)", srid=4326)
    profile.anchor_status = "reviewed"
    db.commit()
    invalidate_for_coordinates(tide_spot.id, db=db, actor="test")
    db.commit()
    db.refresh(profile)
    assert profile.public_enabled is False
    assert profile.automatic_anchor is None
    assert profile.manual_anchor is None
    assert profile.anchor_status == "needs_review"
    assert profile.calculation_status == "queued"


def test_failed_worker_run_preserves_existing_events(db, tide_spot):
    from app.config import get_settings
    from app.tides.worker import TideWorker

    class FailingProvider:
        def curve(self, lat, lon, times):
            raise RuntimeError("model unavailable")

    class ValidSelector:
        def validate(self, lat, lon):
            return True, False

    profile = TideProfile(
        spot_id=tide_spot.id, enabled=True, public_enabled=True,
        timezone="Europe/Berlin", automatic_anchor=WKTElement("POINT(8.5 54.5)", srid=4326),
        anchor_status="reviewed", quality_status="reviewed_anchor",
        calculation_status="queued",
    )
    db.add(profile)
    db.flush()
    old_time = datetime.now(timezone.utc) + timedelta(hours=2)
    event = TideEvent(
        spot_id=tide_spot.id, profile_version=profile.version,
        cycle_key=f"high:{old_time.isoformat()}", event_type="high",
        raw_time=old_time, corrected_time=old_time, uncertainty_minutes=30,
        calculated_at=datetime.now(timezone.utc), model_name="FES2022b",
        model_version="2022b", status="valid",
    )
    run = TideCalculationRun(
        spot_id=tide_spot.id, status="queued", model_name="FES2022b",
        model_version="2022b", algorithm_version=ALGORITHM_VERSION,
        profile_version=profile.version, details={"action": "calculate"},
    )
    db.add_all([event, run])
    db.commit()
    worker = TideWorker.__new__(TideWorker)
    worker.settings = get_settings()
    worker.provider = FailingProvider()
    worker.selector = ValidSelector()
    with pytest.raises(RuntimeError, match="model unavailable"):
        worker.process_run(run.id)
    db.expire_all()
    assert db.get(TideEvent, event.id).status == "valid"
    assert db.get(TideCalculationRun, run.id).status == "failed"


def test_single_override_survives_atomic_recalculation(db, tide_spot):
    from app.config import get_settings
    from app.tides.worker import TideWorker

    class HarmonicProvider:
        def curve(self, lat, lon, times):
            origin = datetime(2020, 1, 1, tzinfo=timezone.utc)
            return [
                CurvePoint(
                    at,
                    math.cos(2 * math.pi * ((at - origin).total_seconds() / 60) / (12.42 * 60)),
                )
                for at in times
            ]

    profile = TideProfile(
        spot_id=tide_spot.id, enabled=True, timezone="Europe/Berlin",
        automatic_anchor=WKTElement("POINT(8.5 54.5)", srid=4326),
        anchor_status="reviewed", quality_status="reviewed_anchor",
    )
    db.add(profile)
    db.flush()
    settings = get_settings()
    old_horizon, old_sample = settings.tide_horizon_days, settings.tide_sample_minutes
    settings.tide_horizon_days, settings.tide_sample_minutes = 2, 5
    worker = TideWorker.__new__(TideWorker)
    worker.settings = settings
    worker.provider = HarmonicProvider()
    try:
        today = datetime.now(timezone.utc).date()
        start = datetime.combine(today - timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc)
        times = [start + timedelta(minutes=5 * index) for index in range((4 * 24 * 60 // 5) + 1)]
        raw = detect_extrema(HarmonicProvider().curve(0, 0, times))[1]
        manual = raw.time + timedelta(minutes=17)
        db.add(TideEventOverride(
            spot_id=tide_spot.id, event_type=raw.event_type,
            raw_time=raw.time, original_model_time=raw.time,
            manual_time=manual, difference_minutes=17,
            scope="single", reason="bekannte Referenz", actor="test",
        ))
        db.flush()
        worker._calculate(profile, 54.5, 8.5, db=db)
        db.flush()
        event = db.scalar(select(TideEvent).where(
            TideEvent.spot_id == tide_spot.id, TideEvent.raw_time == raw.time,
        ))
        assert event is not None
        assert event.corrected_time == manual
    finally:
        settings.tide_horizon_days, settings.tide_sample_minutes = old_horizon, old_sample


def test_profile_history_and_rollback_create_new_version(client, tide_spot):
    base = client.get(f"/admin/spots/{tide_spot.id}/tide").json()
    changed = client.patch(f"/admin/spots/{tide_spot.id}/tide", json={
        "high_offset_minutes": 20,
        "correction_reason": "lokale Referenz",
    })
    assert changed.status_code == 200
    assert changed.json()["version"] == base["version"] + 1
    restored = client.post(f"/admin/spots/{tide_spot.id}/tide/rollback", json={
        "version": base["version"],
        "reason": "fachliche Rücknahme",
    })
    assert restored.status_code == 200
    assert restored.json()["version"] == changed.json()["version"] + 1
    assert restored.json()["high_offset_minutes"] == 0
    history = client.get(f"/admin/spots/{tide_spot.id}/tide/history").json()
    assert [item["version"] for item in history[:3]] == [3, 2, 1]
