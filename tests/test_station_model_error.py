from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
import uuid

import pytest

from app.weather.model_error import (
    ModelWindPoint,
    ReviewedStationPhysics,
    StationModelBaseline,
    StationPhysicsSector,
    baseline_from_normalized_values,
    calculate_station_model_error,
    resolve_reviewed_station_physics,
)
from app.weather.catalog import family_for
from app.weather.contracts import ModelFamily
from app.weather.profiles import ResolvedWeatherProfile
from app.weather.vectors import wind_to_uv
from app.forecast.contracts import GridPoint, NormalizedModelValue

OBSERVED_AT = datetime(2026, 9, 13, 12, 30, tzinfo=timezone.utc)
ANALYZED_AT = OBSERVED_AT + timedelta(minutes=5)
RUN_AT = datetime(2026, 9, 13, 6, tzinfo=timezone.utc)


def station(**patch):
    values = {
        "id": uuid.uuid4(),
        "active": True,
        "approved": True,
        "blocked": False,
        "representativeness_status": "passed",
    }
    values.update(patch)
    return SimpleNamespace(**values)


def observation(target_station, *, speed=12.0, direction=270.0, gust=15.0, **patch):
    u_ms, v_ms = wind_to_uv(speed, direction)
    values = {
        "id": uuid.uuid4(),
        "station_id": target_station.id,
        "observed_at": OBSERVED_AT,
        "wind_speed_ms": speed,
        "wind_direction_deg": direction,
        "wind_u_ms": u_ms,
        "wind_v_ms": v_ms,
        "wind_gust_ms": gust,
        "gust_period_seconds": 600,
        "provider_quality": "good",
        "import_status": "accepted",
    }
    values.update(patch)
    return SimpleNamespace(**values)


def point(
    model_id,
    valid_at,
    *,
    speed=10.0,
    direction=270.0,
    gust=12.0,
    run_at=RUN_AT,
    **patch,
):
    u_ms, v_ms = wind_to_uv(speed, direction)
    values = {
        "provider": "official-test-provider",
        "model_id": model_id,
        "dataset_version": "fixture-v1",
        "model_run_id": f"{model_id}:{run_at.isoformat()}",
        "model_run_at": run_at,
        "model_run_quality": "exact",
        "valid_at": valid_at,
        "fetched_at": ANALYZED_AT,
        "latitude": 54.0,
        "longitude": 10.0,
        "grid_distance_km": 1.0,
        "u_ms": u_ms,
        "v_ms": v_ms,
        "gust_ms": gust,
        "source_key": f"fixture:{model_id}",
    }
    values.update(patch)
    return ModelWindPoint(**values)


def baseline(*points, expected=("icon_eu",)):
    return StationModelBaseline(tuple(points), tuple(expected))


def reviewed_physics(*, factor=1.2):
    return ReviewedStationPhysics(
        profile_id=str(uuid.uuid4()),
        version=3,
        physics_version="station-physics-v1",
        reviewed_at=RUN_AT,
        profile=ResolvedWeatherProfile(
            active=True,
            quality_tier="advanced",
            reviewed_at=RUN_AT,
            sectors=(
                StationPhysicsSector(
                    start_deg=0,
                    end_deg=359.999,
                    speed_factor=factor,
                    version=3,
                ),
            ),
        ),
    )


def test_station_physics_is_resolved_only_after_explicit_review():
    record = SimpleNamespace(
        id=uuid.uuid4(),
        active=True,
        status="draft",
        version=2,
        physics_version="station-physics-v1",
        quality_tier="advanced",
        coastal_normal_deg=None,
        reviewed_at=RUN_AT,
        profile={
            "sectors": [
                {
                    "start_deg": 0,
                    "end_deg": 360,
                    "speed_factor": 1.1,
                    "version": 2,
                }
            ]
        },
    )
    assert resolve_reviewed_station_physics(record) is None
    record.status = "reviewed"
    resolved = resolve_reviewed_station_physics(record)
    assert resolved is not None
    assert resolved.version == 2
    assert resolved.profile.sectors[0].speed_factor == pytest.approx(1.1)


def test_direct_model_ids_keep_their_consensus_family():
    assert family_for("gfs-0p25") is ModelFamily.GFS
    assert family_for("icon-eu") is ModelFamily.REGIONAL
    assert family_for("icon-global") is ModelFamily.ICON_GLOBAL


def test_direct_exact_run_values_bridge_into_the_shared_raw_baseline():
    u_ms, v_ms = wind_to_uv(10, 270)
    value = NormalizedModelValue(
        provider="NOAA/NCEP",
        model="gfs-0p25",
        dataset_version="GFS 0.25",
        model_run=RUN_AT,
        valid_at=OBSERVED_AT,
        fetched_at=ANALYZED_AT,
        grid_point=GridPoint(latitude=54, longitude=10, distance_km=1),
        horizontal_resolution_km=28,
        horizon_hours=6,
        u_ms=u_ms,
        v_ms=v_ms,
        speed_ms=10,
        direction_deg=270,
        gust_ms=12,
        source_key="noaa-gfs",
    )
    shared = baseline_from_normalized_values([value])

    assert shared.expected_model_ids == ("gfs-0p25",)
    assert shared.points[0].source_product == "raw_model"
    assert shared.points[0].model_run_quality == "exact"
    assert shared.points[0].model_run_id.startswith("noaa-gfs:gfs-0p25:")


def test_analysis_identity_is_stable_when_raw_points_arrive_in_another_order():
    target = station()
    measured = observation(target)
    left = point("icon_eu", OBSERVED_AT - timedelta(minutes=30), speed=8)
    right = point("icon_eu", OBSERVED_AT + timedelta(minutes=30), speed=12)

    first = calculate_station_model_error(
        target,
        measured,
        baseline(left, right),
        analyzed_at=ANALYZED_AT,
    )
    second = calculate_station_model_error(
        target,
        measured,
        baseline(right, left),
        analyzed_at=ANALYZED_AT,
    )

    assert first.analysis_id == second.analysis_id
    assert first.residual_vector == second.residual_vector


def test_analysis_identity_covers_measurement_and_effective_physics_configuration():
    target = station()
    measured = observation(target)
    shared = baseline(point("icon_eu", OBSERVED_AT))
    profile = reviewed_physics()

    initial = calculate_station_model_error(
        target,
        measured,
        shared,
        station_physics=profile,
        analyzed_at=ANALYZED_AT,
        blend_overrides={"regional": 0.25},
    )
    changed_measurement = calculate_station_model_error(
        target,
        observation(target, id=measured.id, speed=13),
        shared,
        station_physics=profile,
        analyzed_at=ANALYZED_AT,
        blend_overrides={"regional": 0.25},
    )
    changed_blend = calculate_station_model_error(
        target,
        measured,
        shared,
        station_physics=profile,
        analyzed_at=ANALYZED_AT,
        blend_overrides={"regional": 0.75},
    )

    assert initial.analysis_id != changed_measurement.analysis_id
    assert initial.analysis_id != changed_blend.analysis_id
    assert initial.configuration["observation"]["wind_u_ms"] == pytest.approx(12)
    assert initial.configuration["physics_blend"]["regional"] == 0.25


def test_interpolates_model_and_gust_at_real_observation_time_in_uv_space():
    target = station()
    measured = observation(target, speed=12, direction=270, gust=15)
    result = calculate_station_model_error(
        target,
        measured,
        baseline(
            point("icon_eu", OBSERVED_AT - timedelta(minutes=30), speed=8, gust=10),
            point("icon_eu", OBSERVED_AT + timedelta(minutes=30), speed=12, gust=14),
        ),
        analyzed_at=ANALYZED_AT,
    )

    assert result.expected_station_vector["speed_ms"] == pytest.approx(10)
    assert result.residual_vector["speed_ms"] == pytest.approx(2)
    assert result.model_members[0]["interpolation"]["fraction"] == 0.5
    assert result.model_members[0]["interpolation"]["lower"]["vector"][
        "speed_ms"
    ] == pytest.approx(8)
    assert result.model_members[0]["interpolation"]["upper"]["vector"][
        "speed_ms"
    ] == pytest.approx(12)
    assert result.model_runs[0]["valid_at"] == OBSERVED_AT.isoformat()
    assert result.gust_evidence["raw_model_gust_ms"] == pytest.approx(12)
    assert result.gust_evidence["residual_gust_ms"] == pytest.approx(3)
    assert result.gust_evidence["physics_applied"] is False
    assert result.gust_evidence["measurement_gust_period_seconds"] == 600


def test_conflicting_duplicate_model_values_are_unavailable_not_order_dependent():
    target = station()
    measured = observation(target)
    first = point("icon_eu", OBSERVED_AT, speed=10, gust=12)
    conflicting = point("icon_eu", OBSERVED_AT, speed=10, gust=14)

    result = calculate_station_model_error(
        target,
        measured,
        baseline(first, conflicting),
        analyzed_at=ANALYZED_AT,
    )

    assert result.qc_status == "unavailable"
    assert result.qc_reasons == ("model_time_conflict:icon_eu",)


def test_uv_interpolation_crosses_north_without_averaging_359_and_1_degrees():
    target = station()
    measured = observation(target, speed=10, direction=0)
    result = calculate_station_model_error(
        target,
        measured,
        baseline(
            point(
                "icon_eu",
                OBSERVED_AT - timedelta(minutes=30),
                speed=10,
                direction=359,
            ),
            point(
                "icon_eu",
                OBSERVED_AT + timedelta(minutes=30),
                speed=10,
                direction=1,
            ),
        ),
        analyzed_at=ANALYZED_AT,
    )

    assert result.expected_station_vector["direction_from_deg"] == pytest.approx(
        0, abs=1e-9
    )
    assert result.expected_station_vector["speed_ms"] > 9.99
    assert result.residual_vector["speed_ms"] < 0.01


def test_missing_model_member_is_visible_and_degrades_but_does_not_drop_result():
    target = station()
    result = calculate_station_model_error(
        target,
        observation(target),
        baseline(
            point("icon_eu", OBSERVED_AT),
            expected=("icon_eu", "ncep_gfs_global"),
        ),
        analyzed_at=ANALYZED_AT,
    )

    assert result.qc_status == "degraded"
    assert "model_member_missing:ncep_gfs_global" in result.qc_reasons
    assert "single_model_member" in result.qc_reasons
    assert len(result.model_members) == 1


def test_reviewed_station_physics_changes_expected_vector_before_residual():
    target = station()
    measured = observation(target, speed=12, direction=270)
    raw = baseline(point("icon_eu", OBSERVED_AT, speed=10, direction=270))

    without_profile = calculate_station_model_error(
        target, measured, raw, analyzed_at=ANALYZED_AT
    )
    with_profile = calculate_station_model_error(
        target,
        measured,
        raw,
        station_physics=reviewed_physics(factor=1.2),
        analyzed_at=ANALYZED_AT,
    )

    assert without_profile.expected_station_vector["speed_ms"] == pytest.approx(10)
    assert without_profile.residual_vector["speed_ms"] == pytest.approx(2)
    assert (
        without_profile.representativeness_uncertainty
        == "elevated_no_reviewed_station_profile"
    )
    assert with_profile.expected_station_vector["speed_ms"] == pytest.approx(12)
    assert with_profile.residual_vector["speed_ms"] == pytest.approx(0, abs=1e-8)
    assert with_profile.physics_applied is True
    assert with_profile.physics_version == "station-physics-v1"


@pytest.mark.parametrize(
    ("point_patch", "reason"),
    [
        ({"source_product": "station_adjusted"}, "adjusted_model_input_forbidden"),
        (
            {"source_observation_ids": ("some-measurement",)},
            "observation_derived_model_input_forbidden",
        ),
        ({"model_run_quality": "capture-time-only"}, "model_run_identity_not_verified"),
    ],
)
def test_rejects_corrected_observation_derived_or_unverified_model_input(
    point_patch, reason
):
    target = station()
    result = calculate_station_model_error(
        target,
        observation(target),
        baseline(point("icon_eu", OBSERVED_AT, **point_patch)),
        analyzed_at=ANALYZED_AT,
    )

    assert result.qc_status == "rejected"
    assert reason in result.qc_reasons
    assert result.expected_station_vector == {}
    assert result.residual_vector == {}


def test_does_not_mix_forecast_runs_to_create_a_false_time_bracket():
    target = station()
    older_run = RUN_AT
    newer_run = RUN_AT + timedelta(hours=3)
    result = calculate_station_model_error(
        target,
        observation(target),
        baseline(
            point(
                "icon_eu",
                OBSERVED_AT - timedelta(minutes=30),
                run_at=older_run,
            ),
            point(
                "icon_eu",
                OBSERVED_AT + timedelta(minutes=30),
                run_at=newer_run,
            ),
        ),
        analyzed_at=ANALYZED_AT,
    )

    assert result.qc_status == "unavailable"
    assert "model_time_not_bracketed:icon_eu" in result.qc_reasons


def test_model_run_at_or_after_observation_cannot_supply_the_residual():
    target = station()
    result = calculate_station_model_error(
        target,
        observation(target),
        baseline(point("icon_eu", OBSERVED_AT, run_at=OBSERVED_AT)),
        analyzed_at=ANALYZED_AT,
    )

    assert result.qc_status == "unavailable"
    assert "model_run_not_prior_to_observation:icon_eu" in result.qc_reasons
    assert result.residual_vector == {}


def test_residual_evidence_persistence_is_idempotent(db):
    from geoalchemy2 import WKTElement
    from sqlalchemy import func, select

    from app.models import (
        Region,
        Spot,
        WeatherObservation,
        WeatherStation,
        WeatherStationModelResidual,
    )
    from app.weather.model_error import calculate_and_persist_station_model_error

    suffix = uuid.uuid4().hex[:8]
    region = Region(
        slug=f"model-error-region-{suffix}",
        name=f"Model Error {suffix}",
        normalized_name=f"model error {suffix}",
        country="DE",
        status="published",
    )
    db.add(region)
    db.flush()
    spot = Spot(
        slug=f"model-error-spot-{suffix}",
        name=f"Model Error Spot {suffix}",
        normalized_name=f"model error spot {suffix}",
        region_id=region.id,
        location=WKTElement("POINT(10 54)", srid=4326),
        sports=["wind"],
        water_type=["sea"],
        status="published",
    )
    db.add(spot)
    db.flush()
    station_row = WeatherStation(
        spot_id=spot.id,
        provider="dwd",
        provider_station_id=f"residual-{suffix}",
        latitude=54,
        longitude=10,
        active=True,
        approved=True,
        representativeness_status="passed",
    )
    db.add(station_row)
    db.flush()
    measured_u, measured_v = wind_to_uv(12, 270)
    observation_row = WeatherObservation(
        station_id=station_row.id,
        observed_at=OBSERVED_AT,
        wind_speed_ms=12,
        wind_direction_deg=270,
        wind_u_ms=measured_u,
        wind_v_ms=measured_v,
        provider_quality="good",
        import_status="accepted",
    )
    db.add(observation_row)
    db.commit()

    try:
        model_baseline = baseline(point("icon_eu", OBSERVED_AT))
        first = calculate_and_persist_station_model_error(
            db,
            station_row,
            observation_row,
            model_baseline,
            analyzed_at=ANALYZED_AT,
        )
        db.commit()
        second = calculate_and_persist_station_model_error(
            db,
            station_row,
            observation_row,
            model_baseline,
            analyzed_at=ANALYZED_AT,
        )
        db.commit()
        count = db.scalar(
            select(func.count())
            .select_from(WeatherStationModelResidual)
            .where(
                WeatherStationModelResidual.observation_id == observation_row.id
            )
        )
        assert first.analysis_id == second.analysis_id
        assert count == 1
    finally:
        db.delete(spot)
        db.flush()
        db.delete(region)
        db.commit()
