"""WP1 validation harness: gate logic, bucketing, scoring and import idempotency."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from geoalchemy2 import WKTElement

from app.models import (
    ForecastVerificationScore,
    Region,
    Spot,
    SpotWeatherProfile,
    SpotWeatherSector,
    WeatherForecastSample,
    WeatherObservation,
    WeatherStation,
)
from app.weather.observation_worker import persist_batch
from app.weather.observations import public_measurement
from app.weather.providers.common import normalize_observation
from app.weather.sector_activation import (
    candidate_bias_improvement,
    candidate_gate_results,
    candidate_variant,
    parse_candidate_variant,
)
from app.weather.verification import (
    _consensus_predictions,
    _corrected_samples,
    _score_predictions,
    _serving_consensus_predictions,
    direction_sector,
    lead_bucket,
    run_gated_verification_scoring,
    run_verification_scoring,
    score_spot_forecasts,
)


# --- pure bucketing --------------------------------------------------------


def test_direction_sector_bins_into_twelve_thirty_degree_slices():
    assert direction_sector(0) == 0
    assert direction_sector(29.9) == 0
    assert direction_sector(30) == 1
    assert direction_sector(120) == 4
    assert direction_sector(359.9) == 11
    assert direction_sector(360) == 0  # wraps


def test_lead_buckets_follow_the_authoritative_boundaries():
    assert [lead_bucket(h) for h in (0, 48, 49, 120, 121, 240)] == [
        "0-48h", "0-48h", "49-120h", "49-120h", "121-240h", "121-240h"
    ]


@pytest.mark.parametrize("version", [1, 35, 36, 2_147_483_647])
def test_candidate_score_variant_round_trips_the_exact_version(version):
    variant = candidate_variant(version)
    assert len(variant) <= 16
    assert parse_candidate_variant(variant) == version


# --- gate logic ------------------------------------------------------------


def _station(**overrides):
    base = dict(active=True, approved=True, blocked=False, representativeness_status="passed")
    base.update(overrides)
    return SimpleNamespace(**base)


def _observation(observed_at, **overrides):
    base = dict(observed_at=observed_at, wind_speed_ms=9.0, wind_gust_ms=11.0,
                wind_direction_deg=120.0, provider_quality="1", import_status="accepted")
    base.update(overrides)
    return SimpleNamespace(**base)


def test_gate_accepts_a_historical_observation_scored_at_its_own_timestamp():
    old = datetime.now(timezone.utc) - timedelta(days=10)
    station, observation = _station(), _observation(old)
    # Live now would reject as stale; scoring evaluates each row at its own time.
    stale_now, _ = public_measurement(station, observation, now=datetime.now(timezone.utc))
    ok, reasons = public_measurement(station, observation, now=old)
    assert stale_now is False
    assert ok is True and reasons == []


def test_gate_rejects_unapproved_unrepresentative_and_out_of_range():
    now = datetime.now(timezone.utc)
    unapproved, reasons = public_measurement(_station(approved=False), _observation(now), now=now)
    assert unapproved is False and "station_unapproved" in reasons
    unrep, reasons = public_measurement(_station(representativeness_status="unreviewed"), _observation(now), now=now)
    assert unrep is False and "representativeness_unpassed" in reasons
    bad, reasons = public_measurement(_station(), _observation(now, wind_speed_ms=200.0), now=now)
    assert bad is False and "wind_speed_invalid" in reasons


# --- scoring math ----------------------------------------------------------


def _pred(model_id, valid_at, speed, direction, *, lead=5, gust=None):
    return {"model_id": model_id, "valid_at": valid_at, "lead_hours": lead,
            "wind_speed_ms": speed, "wind_direction_deg": direction, "wind_gust_ms": gust}


def test_score_predictions_groups_by_model_bucket_sector_with_symmetric_bias():
    t0 = datetime(2026, 1, 1, 12, tzinfo=timezone.utc)
    observations = [SimpleNamespace(observed_at=t0, wind_speed_ms=10.0, wind_direction_deg=100.0, wind_gust_ms=12.0)]
    predictions = [
        _pred("a", t0, 12.0, 100.0),   # +2, sector 3 (100//30)
        _pred("a", t0, 8.0, 100.0),    # -2, same cohort -> bias 0
        _pred("a", t0, 15.0, 200.0),   # different sector (6)
    ]
    records = {(r["model_id"], r["lead_bucket"], r["direction_sector"]): r
               for r in _score_predictions(predictions, observations, tolerance_s=1200)}
    sector3 = records[("a", "0-48h", 3)]
    assert sector3["sample_count"] == 2
    assert sector3["bias_ms"] == 0.0
    assert sector3["mae_ms"] == 2.0
    assert sector3["rmse_ms"] == 2.0
    assert sector3["direction_mae_deg"] == 0.0
    assert ("a", "0-48h", 6) in records  # a second sector is grouped apart


def test_score_predictions_drops_matches_outside_tolerance():
    t0 = datetime(2026, 1, 1, 12, tzinfo=timezone.utc)
    far = [SimpleNamespace(observed_at=t0 + timedelta(hours=2), wind_speed_ms=10.0,
                           wind_direction_deg=100.0, wind_gust_ms=None)]
    assert _score_predictions([_pred("a", t0, 12.0, 100.0)], far, tolerance_s=1200) == []


def test_consensus_prediction_averages_speed_and_uses_circular_direction():
    issued = datetime(2026, 1, 1, 6, tzinfo=timezone.utc)
    valid = datetime(2026, 1, 1, 12, tzinfo=timezone.utc)
    members = [
        SimpleNamespace(issued_at=issued, valid_at=valid, lead_hours=6, wind_speed_ms=10.0, wind_direction_deg=350.0, wind_gust_ms=12.0),
        SimpleNamespace(issued_at=issued, valid_at=valid, lead_hours=6, wind_speed_ms=14.0, wind_direction_deg=10.0, wind_gust_ms=16.0),
    ]
    (consensus,) = _consensus_predictions(members)
    assert consensus["model_id"] == "consensus"
    assert consensus["wind_speed_ms"] == 12.0
    # Circular mean of 350 and 10 is due north; compare modulo 360.
    circular = abs((consensus["wind_direction_deg"] + 180.0) % 360.0 - 180.0)
    assert circular == pytest.approx(0.0, abs=1e-6)
    assert consensus["wind_gust_ms"] == 14.0


# --- counterfactual (shadow) correction replay -----------------------------


def _omni_candidate(factor: float, version: int = 2):
    """A disabled 12x30-degree omnidirectional candidate shim, as the scoring view builds."""
    sectors = [SimpleNamespace(enabled=True, version=version, start_deg=float(s),
                               end_deg=float((s + 30) % 360), speed_factor=factor,
                               direction_offset_deg=0.0, note='{"method":"gwa_over_reference"}')
               for s in range(0, 360, 30)]
    return SimpleNamespace(active=True, quality_tier="advanced", coastal_normal_deg=None, sectors=sectors)


def test_corrected_samples_replay_the_engine_factor_and_scale_gust():
    valid = datetime(2026, 1, 1, 12, tzinfo=timezone.utc)
    issued = valid - timedelta(hours=5)
    samples = [SimpleNamespace(model_id="icon", issued_at=issued, valid_at=valid, lead_hours=5,
                               wind_speed_ms=10.0, wind_direction_deg=270.0, wind_gust_ms=12.0)]
    (out,) = _corrected_samples(samples, _omni_candidate(1.25), None)
    assert out.wind_speed_ms == pytest.approx(12.5)   # 10 * 1.25 (full blend, unknown family)
    assert out.wind_gust_ms == pytest.approx(15.0)    # gust scaled by the same ratio
    assert out.wind_direction_deg == pytest.approx(270.0)  # phase-1 offset is 0


def test_corrected_samples_blend_zero_leaves_samples_unchanged():
    valid = datetime(2026, 1, 1, 12, tzinfo=timezone.utc)
    samples = [SimpleNamespace(model_id="icon", issued_at=valid, valid_at=valid, lead_hours=5,
                               wind_speed_ms=10.0, wind_direction_deg=270.0, wind_gust_ms=12.0)]
    (out,) = _corrected_samples(samples, _omni_candidate(1.5), {"other": 0.0})
    assert out.wind_speed_ms == pytest.approx(10.0) and out.wind_gust_ms == pytest.approx(12.0)


def test_shadow_member_preparation_replays_active_serving_bias():
    valid = datetime(2026, 1, 1, 12, tzinfo=timezone.utc)
    samples = [SimpleNamespace(model_id="icon", issued_at=valid, valid_at=valid,
                               lead_hours=5, wind_speed_ms=10.0,
                               wind_direction_deg=270.0, wind_gust_ms=12.0)]
    calibrations = {("icon", "0-48h"): SimpleNamespace(bias_ms=2.0)}

    (out,) = _corrected_samples(samples, None, None, calibrations=calibrations)

    assert out.wind_speed_ms == pytest.approx(8.0)
    assert out.wind_gust_ms == pytest.approx(12.0)  # serving calibrates speed, not gust


def test_shadow_consensus_uses_the_serving_vector_aggregation():
    issued = datetime(2026, 1, 1, 6, tzinfo=timezone.utc)
    valid = datetime(2026, 1, 1, 12, tzinfo=timezone.utc)
    members = [
        SimpleNamespace(model_id="a", issued_at=issued, valid_at=valid, lead_hours=6,
                        wind_speed_ms=10.0, wind_direction_deg=350.0, wind_gust_ms=12.0),
        SimpleNamespace(model_id="b", issued_at=issued, valid_at=valid, lead_hours=6,
                        wind_speed_ms=14.0, wind_direction_deg=10.0, wind_gust_ms=16.0),
    ]

    (consensus,) = _serving_consensus_predictions(members, {})

    # A vector mean is shorter than the old arithmetic 12 m/s mean when member
    # directions differ; this is the value the public serving path emits.
    assert consensus["wind_speed_ms"] == pytest.approx(11.823, abs=1e-3)
    assert consensus["wind_direction_deg"] == pytest.approx(1.683, abs=1e-3)


# --- DB-backed: end-to-end scoring, persistence and import idempotency ------


@pytest.fixture
def scored_spot(db):
    suffix = uuid.uuid4().hex[:8]
    region = Region(slug=f"vh-region-{suffix}", name=f"VH Region {suffix}",
                    normalized_name=f"vh region {suffix}", country="DE", status="published")
    db.add(region)
    db.flush()
    spot = Spot(slug=f"vh-spot-{suffix}", name=f"VH Spot {suffix}",
                normalized_name=f"vh spot {suffix}", region_id=region.id,
                location=WKTElement("POINT(8.5 54.5)", srid=4326),
                sports=["wind"], water_type=["sea"], status="published")
    db.add(spot)
    db.flush()
    station = WeatherStation(spot_id=spot.id, provider="dwd", provider_station_id="00042",
                             name="Ref", latitude=54.5, longitude=8.5, active=True,
                             approved=True, representativeness_status="passed")
    db.add(station)
    db.commit()
    yield spot, station
    db.delete(spot)
    db.flush()
    db.delete(region)
    db.commit()


def test_scoring_end_to_end_persists_bucketed_scores_and_is_idempotent(db, scored_spot):
    spot, station = scored_spot
    valid = datetime.now(timezone.utc) - timedelta(days=5)
    issued = valid - timedelta(hours=5)
    db.add(WeatherObservation(station_id=station.id, observed_at=valid, wind_speed_ms=9.0,
                              wind_gust_ms=11.0, wind_direction_deg=120.0, provider_quality="1",
                              import_status="accepted"))
    db.add(WeatherForecastSample(spot_id=spot.id, model_id="icon", issued_at=issued, valid_at=valid,
                                 lead_hours=5, wind_speed_ms=11.0, wind_gust_ms=13.0, wind_direction_deg=120.0))
    db.commit()

    run_id = uuid.uuid4()
    summary = run_verification_scoring(db, spot_ids=[spot.id], run_id=run_id, lookback_days=30)
    assert summary["spots_scored"] == 1

    rows = db.query(ForecastVerificationScore).filter_by(run_id=run_id, spot_id=spot.id).all()
    by_model = {r.model_id: r for r in rows}
    assert set(by_model) == {"icon", "consensus"}
    icon = by_model["icon"]
    assert icon.lead_bucket == "0-48h"
    assert icon.direction_sector == 4  # 120 // 30
    assert icon.bias_ms == 2.0
    assert icon.mae_ms == 2.0
    assert icon.gust_mae_ms == 2.0  # |13 - 11|

    # Re-running the same run id upserts in place rather than duplicating.
    run_verification_scoring(db, spot_ids=[spot.id], run_id=run_id, lookback_days=30)
    assert db.query(ForecastVerificationScore).filter_by(run_id=run_id, spot_id=spot.id).count() == len(rows)


def test_gated_scoring_measures_the_candidate_and_gate_sees_the_drop(db, scored_spot):
    spot, station = scored_spot
    valid = datetime.now(timezone.utc) - timedelta(days=5)
    issued = valid - timedelta(hours=5)
    # Observation 13 m/s from 270 deg; the model under-forecasts at 10 m/s.
    db.add(WeatherObservation(station_id=station.id, observed_at=valid, wind_speed_ms=13.0,
                              wind_gust_ms=15.0, wind_direction_deg=270.0, provider_quality="1",
                              import_status="accepted"))
    db.add(WeatherForecastSample(spot_id=spot.id, model_id="icon", issued_at=issued, valid_at=valid,
                                 lead_hours=5, wind_speed_ms=10.0, wind_gust_ms=12.0, wind_direction_deg=270.0))
    profile = SpotWeatherProfile(spot_id=spot.id)
    db.add(profile)
    db.flush()
    # Active v1 lifts 10 -> 11 m/s. Disabled candidate v2 is clamped at the
    # coordinates tier and lifts 10 -> 12.5 m/s (baseline MAE 2 -> candidate 0.5).
    for start in range(0, 360, 30):
        db.add(SpotWeatherSector(profile_id=profile.id, start_deg=float(start),
                                 end_deg=float((start + 30) % 360), speed_factor=1.1,
                                 direction_offset_deg=0.0, version=1, enabled=True,
                                 note='{"method":"gwa_over_reference"}'))
        db.add(SpotWeatherSector(profile_id=profile.id, start_deg=float(start),
                                 end_deg=float((start + 30) % 360), speed_factor=1.3,
                                 direction_offset_deg=0.0, version=2, enabled=False,
                                 note='{"method":"gwa_over_reference"}'))
    db.commit()

    run_id = uuid.uuid4()
    summary = run_gated_verification_scoring(db, spot_ids=[spot.id], run_id=run_id, lookback_days=30)
    assert summary["raw_spots_scored"] == 1 and summary["corrected_spots_scored"] == 1

    variants = {r.variant for r in db.query(ForecastVerificationScore).filter_by(run_id=run_id).all()}
    assert variants == {"raw", "candidate:2"}

    # The gate compares the active v1 baseline vs candidate WITHIN one run and
    # binds that score to v2.
    gate = candidate_gate_results(db, run_id)
    assert gate[str(spot.id)]["version"] == 2
    assert gate[str(spot.id)]["mae_drop"] == pytest.approx(1.5, abs=1e-6)
    assert len(gate[str(spot.id)]["context_hash"]) == 64
    drops = candidate_bias_improvement(db, run_id)
    assert drops[str(spot.id)] == pytest.approx(1.5, abs=1e-6)


def test_gate_to_http_activation_reaches_live_and_forecast_serving(
    db, scored_spot, client
):
    """Prove the whole WP path, including snapshot/cache invalidation."""
    from sqlalchemy import select

    from app.db.session import SessionLocal
    from app.forecast.gwa_producer import compute_gwa_sectors
    from app.forecast.publisher import enqueue, run_job
    from app.forecast.sector_runner import _persist_candidate
    from app.live.cache import InMemoryCache
    from app.live.deps import get_cache, get_om_client
    from app.live.public_cache import (
        get_public_forecast,
        get_public_live,
        public_weather_generation,
    )
    from app.main import app
    from app.models import ForecastSnapshot
    from tests.live_helpers import FakeOpenMeteoClient

    spot, station = scored_spot
    valid = datetime.now(timezone.utc) - timedelta(days=5)
    issued = valid - timedelta(hours=5)
    db.add(
        WeatherObservation(
            station_id=station.id,
            observed_at=valid,
            wind_speed_ms=12.5,
            wind_gust_ms=15.0,
            wind_direction_deg=270.0,
            provider_quality="1",
            import_status="accepted",
        )
    )
    db.add(
        WeatherForecastSample(
            spot_id=spot.id,
            model_id="icon",
            issued_at=issued,
            valid_at=valid,
            lead_hours=5,
            wind_speed_ms=10.0,
            wind_gust_ms=12.0,
            wind_direction_deg=270.0,
        )
    )
    profile = SpotWeatherProfile(
        spot_id=spot.id,
        active=True,
        quality_tier="coordinates",
    )
    db.add(profile)
    db.flush()
    for start in range(0, 360, 30):
        db.add(
            SpotWeatherSector(
                profile_id=profile.id,
                start_deg=float(start),
                end_deg=float((start + 30) % 360),
                speed_factor=1.0,
                direction_offset_deg=0.0,
                version=1,
                enabled=True,
                note='{"method":"existing_baseline"}',
            )
        )
    db.flush()

    class GwaReader:
        mounted = True

        def read(self, lat, lon):
            return 8.0

    class Reference:
        def mean_speed(self, lat, lon, window):
            return 6.4

    candidate_result = compute_gwa_sectors(
        54.5,
        8.5,
        gwa_reader=GwaReader(),
        reference=Reference(),
        grid_cell=[54.5, 8.5],
    )
    candidate_status, candidate_version = _persist_candidate(
        db, spot.id, "gwa", candidate_result
    )
    db.commit()
    assert (candidate_status, candidate_version) == ("candidate_written", 2)
    assert all(
        not row.enabled
        for row in db.scalars(
            select(SpotWeatherSector).where(
                SpotWeatherSector.profile_id == profile.id,
                SpotWeatherSector.version == 2,
            )
        ).all()
    )

    run_id = uuid.uuid4()
    scoring = run_gated_verification_scoring(
        db,
        spot_ids=[spot.id],
        run_id=run_id,
        lookback_days=30,
    )
    assert scoring["candidate_versions"] == {str(spot.id): 2}
    assert candidate_gate_results(db, run_id)[str(spot.id)][
        "mae_drop"
    ] == pytest.approx(2.5, abs=1e-6)

    weather_client = FakeOpenMeteoClient(data_days=11)
    cache = InMemoryCache()
    app.dependency_overrides[get_om_client] = lambda: weather_client
    app.dependency_overrides[get_cache] = lambda: cache
    try:
        # Publish a real baseline snapshot first. Activation must retire it and
        # fence both assembled public caches before corrected serving begins.
        job = enqueue(
            db,
            spot.id,
            reason=f"gate-e2e-baseline-{uuid.uuid4()}",
        )
        published = run_job(
            db,
            job.id,
            client=weather_client,
            cache=cache,
        )
        assert published.status == "succeeded"
        snapshot_id = published.diagnostics["snapshot_id"]

        baseline_live_response = client.get(f"/spots/{spot.id}/live")
        baseline_forecast_response = client.get(f"/spots/{spot.id}/forecast")
        assert baseline_live_response.status_code == 200
        assert baseline_forecast_response.status_code == 200
        baseline_live = baseline_live_response.json()
        baseline_forecast = baseline_forecast_response.json()
        assert baseline_forecast["correction"]["applied"] is False
        baseline_generation = public_weather_generation(cache, spot.id)
        assert get_public_live(cache, spot.id) is not None
        assert get_public_forecast(cache, spot.id) is not None

        activated = client.post(
            f"/admin/weather/spots/{spot.id}/sectors/activate",
            params={
                "version": 2,
                "run_id": str(run_id),
                "min_bias_drop": 0.5,
                "reason": "full integration gate",
            },
        )
        assert activated.status_code == 200, activated.text
        assert activated.json()["activated_version"] == 2
        assert activated.json()["snapshots_invalidated"] == 1
        assert public_weather_generation(cache, spot.id) != baseline_generation
        assert get_public_live(cache, spot.id) is None
        assert get_public_forecast(cache, spot.id) is None

        corrected_live_response = client.get(f"/spots/{spot.id}/live")
        corrected_forecast_response = client.get(f"/spots/{spot.id}/forecast")
        assert corrected_live_response.status_code == 200
        assert corrected_forecast_response.status_code == 200
        corrected_live = corrected_live_response.json()
        corrected_forecast = corrected_forecast_response.json()
        assert corrected_forecast["correction"]["applied"] is True
        assert corrected_live["current"]["wind_ms"] > baseline_live["current"][
            "wind_ms"
        ]
        assert corrected_forecast["days"][0]["hours"][0][
            "wind_ms"
        ] > baseline_forecast["days"][0]["hours"][0]["wind_ms"]
        assert get_public_live(cache, spot.id) is not None
        assert get_public_forecast(cache, spot.id) is not None

        with SessionLocal() as verification_db:
            snapshot = verification_db.get(ForecastSnapshot, snapshot_id)
            assert snapshot is not None and snapshot.active is False
            active_versions = {
                row.version
                for row in verification_db.scalars(
                    select(SpotWeatherSector).where(
                        SpotWeatherSector.profile_id == profile.id,
                        SpotWeatherSector.enabled.is_(True),
                    )
                ).all()
            }
            assert active_versions == {2}
    finally:
        app.dependency_overrides.pop(get_om_client, None)
        app.dependency_overrides.pop(get_cache, None)


def test_scoring_skips_a_spot_whose_station_is_not_approved(db, scored_spot):
    spot, station = scored_spot
    station.approved = False
    db.add(station)
    valid = datetime.now(timezone.utc) - timedelta(days=5)
    db.add(WeatherObservation(station_id=station.id, observed_at=valid, wind_speed_ms=9.0,
                              wind_direction_deg=120.0, provider_quality="1", import_status="accepted"))
    db.add(WeatherForecastSample(spot_id=spot.id, model_id="icon", issued_at=valid - timedelta(hours=5),
                                 valid_at=valid, lead_hours=5, wind_speed_ms=11.0, wind_direction_deg=120.0))
    db.commit()
    assert score_spot_forecasts(db, spot.id, lookback_days=30) == []


def test_cron_endpoints_are_guarded_and_leak_no_secret(anon_client, monkeypatch):
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "cron_secret", "wp1-test-secret")
    # Wrong verb, missing auth and wrong secret are all rejected on both endpoints.
    assert anon_client.post("/cron/observations").status_code == 405
    assert anon_client.get("/cron/observations").status_code == 401
    assert anon_client.get("/cron/verification").status_code == 401
    assert anon_client.get("/cron/observations", headers={"Authorization": "Bearer nope"}).status_code == 401
    ok_headers = {"Authorization": "Bearer wp1-test-secret"}
    observations = anon_client.get("/cron/observations", headers=ok_headers)
    verification = anon_client.get("/cron/verification", headers=ok_headers)
    assert observations.status_code == 200 and verification.status_code == 200
    assert observations.json()["dry_run"] is False  # cron always imports for real
    assert "secret" not in (observations.text + verification.text).lower()


def test_observation_import_is_idempotent(db, scored_spot):
    _spot, station = scored_spot
    observed = datetime.now(timezone.utc) - timedelta(hours=1)
    rows = [normalize_observation(provider="dwd", station_id="00042", observed_at=observed,
                                  wind_speed_ms=7.5, wind_direction_deg=245.0, provider_quality="1")]
    first = persist_batch(db, station, rows, dry_run=False)
    second = persist_batch(db, station, rows, dry_run=False)
    assert first["persisted"] == 1
    assert second["persisted"] == 0  # uq_weather_observation_time makes replay a no-op
