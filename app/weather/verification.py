"""Forecast verification and conservative, measurement-backed calibration."""

from __future__ import annotations

from bisect import bisect_left
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from statistics import mean, median
from types import SimpleNamespace
import hashlib
import json
import math
import random
import uuid

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert

from app.models import (
    ForecastVerificationScore,
    ForecastSectorGateEvidence,
    Spot,
    SpotWeatherProfile,
    SpotWeatherSector,
    WeatherForecastSample,
    WeatherModelCalibration,
    WeatherObservation,
    WeatherStation,
)
from app.weather.observations import public_measurement

# 30 samples can cover only five hours at a ten-minute cadence and is too easy
# to overfit. Sixty is still deliberately modest for local preparation; an
# activation additionally needs a chronological holdout improvement.
MIN_CALIBRATION_SAMPLES = 60
CALIBRATION_DECISION_VERSION = "holdout-v1"

# Identifies the forecast-sample time normalisation in force. Bump this whenever
# the UTC conversion of provider timestamps changes so that gate evidence built
# from differently-timed samples is not trusted for activation. "provider-utc-v1"
# = naive Open-Meteo axes resolved in the provider timezone (DST-fold aware).
TIME_NORMALIZATION_VERSION = "provider-utc-v1"


def lead_bucket(hours: float) -> str:
    if hours <= 48:
        return "0-48h"
    if hours <= 120:
        return "49-120h"
    return "121-240h"


# Twelve canonical 30-degree sectors aligned to the Global Wind Atlas bins so the
# verification breakdown shares the axis a future GWA sector-factor producer uses.
def direction_sector(direction_deg: float) -> int:
    """Return the 30-degree sector index (0 = [0,30) ... 11 = [330,360))."""
    return int((float(direction_deg) % 360.0) // 30.0)


@dataclass(frozen=True)
class CalibrationStats:
    sample_count: int
    bias_ms: float
    mae_ms: float
    weight_multiplier: float


@dataclass(frozen=True)
class VerificationMetrics:
    sample_count: int
    wind_mae_ms: float
    wind_bias_ms: float
    wind_rmse_ms: float
    direction_mae_deg: float | None
    gust_mae_ms: float | None


@dataclass(frozen=True)
class CalibrationDecision:
    approved: bool
    version: str
    reason: str
    training_count: int
    holdout_count: int
    baseline_mae_ms: float | None
    calibrated_mae_ms: float | None


@dataclass(frozen=True)
class BenchmarkMetrics:
    spot_id: str
    model_family: str
    lead_bucket: str
    candidate: VerificationMetrics
    single_model: VerificationMetrics | None
    uncalibrated_consensus: VerificationMetrics | None
    persistence: VerificationMetrics | None


def circular_error_deg(predicted: float, observed: float) -> float:
    return abs((float(predicted) - float(observed) + 180.0) % 360.0 - 180.0)


def observation_index(observations) -> tuple[list[float], list]:
    """Sort observations once for O(log n) nearest-time matching."""
    ordered = sorted(observations, key=lambda row: row.observed_at)
    return [row.observed_at.timestamp() for row in ordered], ordered


def nearest_observation(index, target, *, tolerance_s: int):
    """Return the closest observation inside ``tolerance_s`` from a time index."""
    times, observations = index
    if not times:
        return None
    target_s = target.timestamp()
    position = bisect_left(times, target_s)
    candidates = []
    if position < len(observations):
        candidates.append(observations[position])
    if position:
        candidates.append(observations[position - 1])
    nearest = min(
        candidates,
        key=lambda row: abs(row.observed_at.timestamp() - target_s),
        default=None,
    )
    if (
        nearest is None
        or abs(nearest.observed_at.timestamp() - target_s) > tolerance_s
    ):
        return None
    return nearest


def verification_metrics(rows: list[dict]) -> VerificationMetrics | None:
    clean = [row for row in rows if all(math.isfinite(float(row[key])) for key in ("wind_pred", "wind_obs"))]
    if not clean:
        return None
    errors = [float(row["wind_pred"]) - float(row["wind_obs"]) for row in clean]
    direction = [circular_error_deg(row["direction_pred"], row["direction_obs"])
                 for row in clean if row.get("direction_pred") is not None and row.get("direction_obs") is not None]
    gust = [abs(float(row["gust_pred"]) - float(row["gust_obs"]))
            for row in clean if row.get("gust_pred") is not None and row.get("gust_obs") is not None]
    rmse = math.sqrt(mean(value * value for value in errors))
    return VerificationMetrics(len(clean), round(mean(abs(v) for v in errors), 3), round(mean(errors), 3),
                               round(rmse, 3),
                               round(mean(direction), 3) if direction else None,
                               round(mean(gust), 3) if gust else None)


def evaluate_calibration_holdout(rows: list[dict], *, holdout_fraction: float = 0.25) -> CalibrationDecision:
    """Chronological split; approve only a speed improvement without direction regression."""
    ordered = sorted(rows, key=lambda row: row["valid_at"])
    split = max(1, int(len(ordered) * (1 - holdout_fraction)))
    training, holdout = ordered[:split], ordered[split:]
    if len(training) < MIN_CALIBRATION_SAMPLES or len(holdout) < 20:
        return CalibrationDecision(False, CALIBRATION_DECISION_VERSION, "insufficient_samples",
                                   len(training), len(holdout), None, None)
    baseline = verification_metrics(holdout)
    calibrated_rows = [{
        **row,
        "wind_pred": row["wind_calibrated"],
        "direction_pred": row.get("direction_calibrated", row.get("direction_pred")),
    } for row in holdout]
    calibrated = verification_metrics(calibrated_rows)
    if baseline is None or calibrated is None:
        return CalibrationDecision(False, CALIBRATION_DECISION_VERSION, "invalid_holdout", len(training), len(holdout), None, None)
    direction_regressed = (calibrated.direction_mae_deg is not None and baseline.direction_mae_deg is not None
                           and calibrated.direction_mae_deg > baseline.direction_mae_deg + 1.0)
    approved = calibrated.wind_mae_ms < baseline.wind_mae_ms and not direction_regressed
    reason = "holdout_improved" if approved else ("direction_regressed" if direction_regressed else "holdout_not_improved")
    return CalibrationDecision(approved, CALIBRATION_DECISION_VERSION, reason, len(training), len(holdout),
                               baseline.wind_mae_ms, calibrated.wind_mae_ms)


def grouped_benchmarks(rows: list[dict]) -> list[BenchmarkMetrics]:
    """Compare candidate, single-model, raw consensus and persistence by cohort."""
    grouped: dict[tuple[str, str, str], list[dict]] = defaultdict(list)
    for row in rows:
        key = (str(row["spot_id"]), str(row["model_family"]), lead_bucket(float(row["lead_hours"])))
        grouped[key].append(row)
    output = []
    for (spot_id, family, bucket), values in sorted(grouped.items()):
        def metrics_for(column: str) -> VerificationMetrics | None:
            subset = [{**row, "wind_pred": row[column]} for row in values if row.get(column) is not None]
            return verification_metrics(subset)
        candidate = metrics_for("wind_pred")
        if candidate is not None:
            output.append(BenchmarkMetrics(
                spot_id, family, bucket, candidate, metrics_for("single_model_pred"),
                metrics_for("uncalibrated_consensus_pred"), metrics_for("persistence_pred")))
    return output


def calibration_stats(errors: list[float], peer_mae: float | None = None) -> CalibrationStats | None:
    """Robust stats for errors defined as forecast minus observation."""
    clean = [float(value) for value in errors if isinstance(value, (int, float))]
    if len(clean) < MIN_CALIBRATION_SAMPLES:
        return None
    bias = median(clean)
    mae = median(abs(value) for value in clean)
    # Never let historical fitting dominate the meteorological family weights.
    multiplier = 1.0 if not peer_mae or mae <= 0 else max(0.5, min(2.0, peer_mae / mae))
    return CalibrationStats(len(clean), round(bias, 3), round(mae, 3), round(multiplier, 3))


def load_calibrations(db, spot_id) -> dict[tuple[str, str], WeatherModelCalibration]:
    if not hasattr(db, "scalars"):
        return {}
    rows = db.scalars(select(WeatherModelCalibration).where(WeatherModelCalibration.spot_id == spot_id)).all()
    return {(row.model_id, row.lead_bucket): row for row in rows
            if row.sample_count >= MIN_CALIBRATION_SAMPLES
            and getattr(row, "decision_status", "legacy_active") in {"active", "legacy_active"}}


def store_forecast_samples(db, spot_id, raw: dict, models: list[str], issued_at: datetime) -> int:
    """Persist raw per-model hourly forecasts only for spots linked to a station."""
    if not hasattr(db, "scalar") or not hasattr(db, "execute"):
        return 0
    if db.scalar(select(WeatherStation.id).where(WeatherStation.spot_id == spot_id, WeatherStation.active.is_(True)).limit(1)) is None:
        return 0
    from app.live.weather_contract import provider_axis_utc, provider_timezone

    hourly = raw.get("hourly") or {}
    times = hourly.get("time") or []
    multi = len(models) > 1
    # Use the SAME normalisation as serving: Open-Meteo is queried with
    # ``timezone=auto`` so the hourly axis is local-naive; it must be resolved in
    # the provider timezone (DST-fold aware) to UTC. Stamping it directly as UTC
    # shifted every sample by the spot's offset, so valid_at no longer referenced
    # the same real instant as the observations and lead buckets were wrong.
    axis = provider_axis_utc(times, provider_timezone(raw))
    rows = []
    for index, _value in enumerate(times):
        valid_at = axis[index] if index < len(axis) else None
        if valid_at is None:
            continue
        lead = max(0, round((valid_at - issued_at).total_seconds() / 3600))
        for model in models:
            suffix = f"_{model}" if multi else ""
            speed_col = hourly.get(f"wind_speed_10m{suffix}") or []
            dir_col = hourly.get(f"wind_direction_10m{suffix}") or []
            gust_col = hourly.get(f"wind_gusts_10m{suffix}") or []
            speed = speed_col[index] if index < len(speed_col) else None
            direction = dir_col[index] if index < len(dir_col) else None
            if not isinstance(speed, (int, float)) or not isinstance(direction, (int, float)):
                continue
            rows.append({"spot_id": spot_id, "model_id": model, "issued_at": issued_at,
                         "valid_at": valid_at, "lead_hours": lead, "wind_speed_ms": float(speed),
                         "wind_gust_ms": float(gust_col[index]) if index < len(gust_col) and isinstance(gust_col[index], (int, float)) else None,
                         "wind_direction_deg": float(direction) % 360})
    if rows:
        stmt = insert(WeatherForecastSample).values(rows).on_conflict_do_nothing(
            constraint="uq_weather_forecast_sample"
        )
        db.execute(stmt)
        db.commit()
    return len(rows)


def recompute_calibrations(db, *, lookback_days: int = 90) -> int:
    """Match forecasts to observations within 20 minutes and refresh robust stats."""
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=max(7, min(lookback_days, 365)))
    stations = db.scalars(select(WeatherStation).where(WeatherStation.active.is_(True))).all()
    updated = 0
    for station in stations:
        observations = db.scalars(select(WeatherObservation).where(
            WeatherObservation.station_id == station.id,
            WeatherObservation.observed_at >= cutoff,
            WeatherObservation.observed_at <= now,
        )).all()
        samples = db.scalars(select(WeatherForecastSample).where(
            WeatherForecastSample.spot_id == station.spot_id,
            WeatherForecastSample.valid_at >= cutoff,
            WeatherForecastSample.valid_at <= now,
        )).all()
        observations_by_time = observation_index(observations)
        grouped: dict[tuple[str, str], list[float]] = defaultdict(list)
        for sample in samples:
            nearest = nearest_observation(
                observations_by_time, sample.valid_at, tolerance_s=1200
            )
            if nearest is None:
                continue
            grouped[(sample.model_id, lead_bucket(sample.lead_hours))].append(sample.wind_speed_ms - nearest.wind_speed_ms)
        provisional = {key: calibration_stats(errors) for key, errors in grouped.items()}
        peer_mae = median(s.mae_ms for s in provisional.values() if s is not None) if any(provisional.values()) else None
        for (model_id, bucket), errors in grouped.items():
            stats = calibration_stats(errors, peer_mae)
            if stats is None:
                continue
            stmt = insert(WeatherModelCalibration).values(
                spot_id=station.spot_id, model_id=model_id, lead_bucket=bucket,
                sample_count=stats.sample_count, bias_ms=stats.bias_ms, mae_ms=stats.mae_ms,
                weight_multiplier=stats.weight_multiplier,
                decision_status="pending_review", decision_version=CALIBRATION_DECISION_VERSION,
                decision_reason="holdout_evaluation_required",
                decision_metrics={"training_samples": stats.sample_count},
            ).on_conflict_do_update(
                constraint="uq_weather_calibration",
                set_={"sample_count": stats.sample_count, "bias_ms": stats.bias_ms,
                      "mae_ms": stats.mae_ms, "weight_multiplier": stats.weight_multiplier,
                      "decision_status": "pending_review", "decision_version": CALIBRATION_DECISION_VERSION,
                      "decision_reason": "holdout_evaluation_required",
                      "decision_metrics": {"training_samples": stats.sample_count},
                      "updated_at": datetime.now(timezone.utc)},
            )
            db.execute(stmt)
            updated += 1
    db.commit()
    return updated


# ---------------------------------------------------------------------------
# WP1 validation harness: score the raw forecast against station measurements.
#
# The station wind never enters the forecast; it only produces bias/MAE/RMSE
# broken down by lead-time bucket and 30-degree direction sector. Only
# measurements passing ``observations.public_measurement`` are scored, and the
# staleness gate is neutralised for historical scoring by evaluating each
# observation at its own timestamp (``now == observed_at``).
# ---------------------------------------------------------------------------

CONSENSUS_MODEL_ID = "consensus"


def _circular_mean_deg(values: list[float]) -> float:
    xs = sum(math.cos(math.radians(float(v))) for v in values)
    ys = sum(math.sin(math.radians(float(v))) for v in values)
    return math.degrees(math.atan2(ys, xs)) % 360.0


def _sample_predictions(samples) -> list[dict]:
    return [{
        "model_id": s.model_id, "issued_at": s.issued_at,
        "valid_at": s.valid_at, "lead_hours": s.lead_hours,
        "wind_speed_ms": s.wind_speed_ms, "wind_direction_deg": s.wind_direction_deg,
        "wind_gust_ms": s.wind_gust_ms,
    } for s in samples]


def _consensus_predictions(samples) -> list[dict]:
    """One vector-consistent consensus prediction per issued forecast run and hour."""
    by_run: dict[tuple, list] = defaultdict(list)
    for sample in samples:
        by_run[(sample.issued_at, sample.valid_at)].append(sample)
    output = []
    for (_issued_at, valid_at), members in by_run.items():
        gusts = [m.wind_gust_ms for m in members if m.wind_gust_ms is not None]
        output.append({
            "model_id": CONSENSUS_MODEL_ID, "issued_at": _issued_at,
            "valid_at": valid_at,
            "lead_hours": members[0].lead_hours,
            "wind_speed_ms": mean(m.wind_speed_ms for m in members),
            "wind_direction_deg": _circular_mean_deg([m.wind_direction_deg for m in members]),
            "wind_gust_ms": mean(gusts) if len(gusts) == len(members) else None,
        })
    return output


def _score_predictions(predictions: list[dict], observations: list, *, tolerance_s: int) -> list[dict]:
    """Match each prediction to the nearest gated observation and group by cohort."""
    groups: dict[tuple[str, str, int], list[dict]] = defaultdict(list)
    observations_by_time = observation_index(observations)
    for pred in predictions:
        nearest = nearest_observation(
            observations_by_time, pred["valid_at"], tolerance_s=tolerance_s
        )
        if nearest is None:
            continue
        key = (pred["model_id"], lead_bucket(pred["lead_hours"]), direction_sector(pred["wind_direction_deg"]))
        groups[key].append({
            "wind_pred": pred["wind_speed_ms"], "wind_obs": nearest.wind_speed_ms,
            "direction_pred": pred["wind_direction_deg"], "direction_obs": nearest.wind_direction_deg,
            "gust_pred": pred["wind_gust_ms"], "gust_obs": nearest.wind_gust_ms,
        })
    records = []
    for (model_id, bucket, sector), rows in sorted(groups.items()):
        metrics = verification_metrics(rows)
        if metrics is None:
            continue
        records.append({
            "model_id": model_id, "lead_bucket": bucket, "direction_sector": sector,
            "sample_count": metrics.sample_count, "bias_ms": metrics.wind_bias_ms,
            "mae_ms": metrics.wind_mae_ms, "rmse_ms": metrics.wind_rmse_ms,
            "direction_mae_deg": metrics.direction_mae_deg, "gust_mae_ms": metrics.gust_mae_ms,
        })
    return records


def gated_observations(db, spot_id, *, cutoff, until=None) -> list:
    """Observations for a spot that pass the public station/quality gate."""
    accepted = []
    stations = db.scalars(select(WeatherStation).where(
        WeatherStation.spot_id == spot_id, WeatherStation.active.is_(True))).all()
    for station in stations:
        statement = select(WeatherObservation).where(
            WeatherObservation.station_id == station.id,
            WeatherObservation.observed_at >= cutoff,
        )
        if until is not None:
            statement = statement.where(WeatherObservation.observed_at <= until)
        observations = db.scalars(statement).all()
        for observation in observations:
            ok, _reasons = public_measurement(station, observation, now=observation.observed_at.astimezone(timezone.utc))
            if ok:
                accepted.append(observation)
    return accepted


def score_spot_forecasts(db, spot_id, *, now=None, lookback_days: int = 45, tolerance_s: int = 1200) -> list[dict]:
    """Per-model and consensus bias/MAE/RMSE of the raw forecast versus gated observations."""
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(days=max(1, min(lookback_days, 365)))
    observations = gated_observations(db, spot_id, cutoff=cutoff, until=now)
    if not observations:
        return []
    samples = db.scalars(select(WeatherForecastSample).where(
        WeatherForecastSample.spot_id == spot_id,
        WeatherForecastSample.valid_at >= cutoff,
        WeatherForecastSample.valid_at <= now,
    )).all()
    if not samples:
        return []
    records = _score_predictions(_sample_predictions(samples), observations, tolerance_s=tolerance_s)
    records += _score_predictions(_consensus_predictions(samples), observations, tolerance_s=tolerance_s)
    return records


# ---------------------------------------------------------------------------
# Counterfactual ("shadow") scoring of a concrete candidate sector version.
#
# The raw forecast samples are stored BEFORE any correction, so comparing raw
# scores across two runs can never show a candidate's effect — it only reflects
# a different time window. Instead we replay the live member preparation
# (active bias calibration + ``apply_local_physics`` + per-family blend) and the
# family-weighted vector consensus over the SAME stored samples, then score the
# result against the SAME gated observations, tagged with the exact candidate
# version. The activation gate compares baseline-vs-candidate WITHIN ONE run
# (``sector_activation.candidate_bias_improvement``), removing the weather-window
# confound. This is a measurement only: no served value is touched, and station
# wind never enters a forecast value here either.
# ---------------------------------------------------------------------------


def _scoring_sector_profile(db, spot_id, version: int):
    """Resolve sector ``version`` through the same profile path as serving.

    Lets the live engine correction be replayed over stored samples for a
    candidate that is (by design) still disabled. Returns None when the spot has
    no such version. Candidate rows are exposed as enabled only inside this
    in-memory shim; ``resolve_weather_profile`` then applies exactly the same
    quality tier, metadata and clamp semantics the serving path will use.
    """
    from app.weather.profiles import is_forecast_sector, resolve_weather_profile
    from app.weather.sector_activation import _validate_candidate

    profile = db.scalar(select(SpotWeatherProfile).where(SpotWeatherProfile.spot_id == spot_id))
    if profile is None:
        return None
    rows = [
        row
        for row in db.scalars(select(SpotWeatherSector).where(
            SpotWeatherSector.profile_id == profile.id,
            SpotWeatherSector.version == version)).all()
        if is_forecast_sector(row)
    ]
    if not rows:
        return None
    try:
        _validate_candidate(rows)
    except ValueError:
        return None
    sectors = [SimpleNamespace(
        enabled=True, version=row.version, start_deg=row.start_deg, end_deg=row.end_deg,
        speed_factor=row.speed_factor, direction_offset_deg=row.direction_offset_deg,
        note=row.note,
    ) for row in rows]
    shim = SimpleNamespace(
        active=getattr(profile, "active", False),
        quality_tier=getattr(profile, "quality_tier", "coordinates"),
        timezone=getattr(profile, "timezone", None),
        elevation_m=getattr(profile, "elevation_m", None),
        coastal_normal_deg=getattr(profile, "coastal_normal_deg", None),
        reviewed_at=getattr(profile, "reviewed_at", None),
        sectors=sectors,
    )
    return resolve_weather_profile(shim)


def _corrected_samples(samples, sector_profile, blend_overrides, calibrations=None):
    """Replay serving's member preparation over stored raw samples.

    This mirrors the active bias adjustment, per-family sector blend and gust
    scaling. Passing ``sector_profile=None`` produces the current serving
    baseline without local sector physics. Station wind is never involved.
    """
    from app.weather.catalog import family_for
    from app.weather.physics import apply_local_physics
    from app.weather.physics.blend import family_blend

    corrected = []
    for s in samples:
        speed = float(s.wind_speed_ms)
        calibration = (calibrations or {}).get((s.model_id, lead_bucket(s.lead_hours)))
        if calibration is not None:
            speed = max(0.0, speed - float(calibration.bias_ms))
        blend = family_blend(family_for(s.model_id), blend_overrides)
        applied = apply_local_physics(speed, s.wind_direction_deg, sector_profile, blend=blend)
        gust_factor = applied.speed_ms / speed if speed > 0 else 1.0
        corrected.append(SimpleNamespace(
            model_id=s.model_id, issued_at=s.issued_at, valid_at=s.valid_at,
            lead_hours=s.lead_hours, wind_speed_ms=applied.speed_ms,
            wind_direction_deg=applied.direction_deg,
            wind_gust_ms=(s.wind_gust_ms * gust_factor) if s.wind_gust_ms is not None else None,
        ))
    return corrected


def _serving_consensus_predictions(samples, calibrations) -> list[dict]:
    """Aggregate prepared members exactly like the public serving path."""
    from app.weather.consensus import WindMember, calculate_wind_consensus

    by_run: dict[tuple, list] = defaultdict(list)
    for sample in samples:
        by_run[(sample.issued_at, sample.valid_at)].append(sample)

    output = []
    for (_issued_at, valid_at), members in by_run.items():
        lead_hours = members[0].lead_hours
        bucket = lead_bucket(lead_hours)
        multipliers = {
            member.model_id: calibration.weight_multiplier
            for member in members
            if (calibration := (calibrations or {}).get((member.model_id, bucket)))
            is not None
        }
        consensus = calculate_wind_consensus(
            [
                WindMember(
                    member.model_id,
                    member.wind_speed_ms,
                    member.wind_direction_deg,
                    member.wind_gust_ms,
                )
                for member in members
            ],
            lead_hours,
            multipliers=multipliers,
        )
        if consensus is None or consensus.direction_deg is None:
            continue
        output.append({
            "model_id": CONSENSUS_MODEL_ID,
            "issued_at": _issued_at,
            "valid_at": valid_at,
            "lead_hours": lead_hours,
            "wind_speed_ms": consensus.speed_ms,
            "wind_direction_deg": consensus.direction_deg,
            "wind_gust_ms": consensus.gust_ms,
        })
    return output


def _score_spot_serving_variant(
    db,
    spot_id,
    *,
    sector_profile,
    now,
    lookback_days: int,
    tolerance_s: int,
    blend_overrides,
    cutoff=None,
) -> list[dict]:
    cutoff = cutoff or now - timedelta(days=max(1, min(lookback_days, 365)))
    observations = gated_observations(db, spot_id, cutoff=cutoff, until=now)
    if not observations:
        return []
    samples = db.scalars(select(WeatherForecastSample).where(
        WeatherForecastSample.spot_id == spot_id,
        WeatherForecastSample.valid_at >= cutoff,
        WeatherForecastSample.valid_at <= now,
    )).all()
    if not samples:
        return []
    calibrations = load_calibrations(db, spot_id)
    prepared = _corrected_samples(
        samples,
        sector_profile,
        blend_overrides,
        calibrations=calibrations,
    )
    records = _score_predictions(
        _sample_predictions(prepared), observations, tolerance_s=tolerance_s
    )
    records += _score_predictions(
        _serving_consensus_predictions(prepared, calibrations),
        observations,
        tolerance_s=tolerance_s,
    )
    return records


def _candidate_training_end(profile) -> datetime | None:
    """Return the immutable WP6 fit boundary encoded in a candidate.

    Physical candidates do not learn from recent station observations and need
    no temporal holdout.  Every row in a shrinkage candidate must agree on one
    timezone-aware boundary; legacy candidates without it deliberately cannot
    produce activation evidence and must be rebuilt.
    """
    sectors = list(getattr(profile, "sectors", ()) or ())
    posterior = []
    for sector in sectors:
        try:
            note = json.loads(sector.note or "{}")
        except (TypeError, ValueError):
            note = {}
        if note.get("method") == "shrinkage_posterior":
            posterior.append(note)
    if not posterior:
        return None
    if len(posterior) != len(sectors):
        raise ValueError("candidate mixes WP6 posterior and physical sectors")
    if any(
        note.get("posterior_schema") != "sector-holdout-v2" for note in posterior
    ):
        raise ValueError("candidate uses an unsupported WP6 posterior schema")
    boundaries = [note.get("training_window_end") for note in posterior]
    if any(value is None for value in boundaries) or len(set(boundaries)) != 1:
        raise ValueError("candidate has no unambiguous WP6 training boundary")
    parsed = datetime.fromisoformat(str(boundaries[0]).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("candidate WP6 training boundary must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def _paired_gate_statistics(
    baseline_predictions: list[dict],
    candidate_predictions: list[dict],
    observations: list,
    *,
    tolerance_s: int,
    min_unique_valid_times: int,
    min_distinct_days: int,
    min_mae_drop_ms: float,
    bootstrap_iterations: int,
) -> dict:
    """Build a paired, day-blocked confidence interval for candidate benefit."""
    candidate_by_key = {
        (row["issued_at"], row["valid_at"]): row for row in candidate_predictions
    }
    observations_by_time = observation_index(observations)
    per_valid: dict[datetime, list[tuple[float, float]]] = defaultdict(list)
    matched_forecasts = 0
    for baseline in baseline_predictions:
        candidate = candidate_by_key.get(
            (baseline["issued_at"], baseline["valid_at"])
        )
        if candidate is None:
            continue
        observation = nearest_observation(
            observations_by_time,
            baseline["valid_at"],
            tolerance_s=tolerance_s,
        )
        if observation is None:
            continue
        per_valid[baseline["valid_at"]].append(
            (
                abs(float(baseline["wind_speed_ms"]) - observation.wind_speed_ms),
                abs(float(candidate["wind_speed_ms"]) - observation.wind_speed_ms),
            )
        )
        matched_forecasts += 1

    valid_rows = [
        (
            valid_at,
            mean(pair[0] for pair in pairs),
            mean(pair[1] for pair in pairs),
        )
        for valid_at, pairs in sorted(per_valid.items())
    ]
    baseline_mae = mean(row[1] for row in valid_rows) if valid_rows else None
    candidate_mae = mean(row[2] for row in valid_rows) if valid_rows else None
    mae_drop = (
        baseline_mae - candidate_mae
        if baseline_mae is not None and candidate_mae is not None
        else None
    )
    by_day: dict[str, list[float]] = defaultdict(list)
    for valid_at, baseline_error, candidate_error in valid_rows:
        by_day[valid_at.astimezone(timezone.utc).date().isoformat()].append(
            baseline_error - candidate_error
        )
    day_improvements = [mean(values) for _, values in sorted(by_day.items())]

    ci_lower = ci_upper = None
    if len(day_improvements) >= 2:
        seed_payload = json.dumps(
            [round(value, 9) for value in day_improvements], separators=(",", ":")
        )
        seed = int(hashlib.sha256(seed_payload.encode()).hexdigest()[:16], 16)
        rng = random.Random(seed)
        bootstrap_means = sorted(
            mean(rng.choice(day_improvements) for _ in day_improvements)
            for _ in range(bootstrap_iterations)
        )
        ci_lower = bootstrap_means[int(0.025 * (bootstrap_iterations - 1))]
        ci_upper = bootstrap_means[int(0.975 * (bootstrap_iterations - 1))]

    if len(valid_rows) < min_unique_valid_times:
        status, reason = "collecting", "insufficient_unique_valid_times"
    elif len(day_improvements) < min_distinct_days:
        status, reason = "collecting", "insufficient_distinct_days"
    elif mae_drop is None or mae_drop < min_mae_drop_ms:
        status, reason = "rejected", "mae_drop_below_policy"
    elif ci_lower is None or ci_lower <= 0:
        status, reason = "rejected", "improvement_not_significant"
    else:
        status, reason = "passed", "holdout_improved"

    return {
        "matched_forecasts": matched_forecasts,
        "unique_valid_times": len(valid_rows),
        "distinct_days": len(day_improvements),
        "baseline_mae_ms": round(baseline_mae, 4) if baseline_mae is not None else None,
        "candidate_mae_ms": round(candidate_mae, 4) if candidate_mae is not None else None,
        "mae_drop_ms": round(mae_drop, 4) if mae_drop is not None else None,
        "ci_lower_ms": round(ci_lower, 4) if ci_lower is not None else None,
        "ci_upper_ms": round(ci_upper, 4) if ci_upper is not None else None,
        "status": status,
        "reason": reason,
    }


def persist_sector_gate_evidence(
    db,
    *,
    run_id,
    spot_id,
    candidate_version: int,
    context_hash: str,
    window_start,
    window_end,
    training_window_end,
    evidence: dict,
    policy: dict,
) -> None:
    """Upsert the one authoritative activation-evidence row for a spot/run."""
    from app.weather.sector_activation import require_gate_evidence_table

    # Writing evidence against a non-migrated database must fail clearly, not with
    # an opaque DB error mid-run.
    require_gate_evidence_table(db)
    values = {
        "run_id": run_id,
        "spot_id": spot_id,
        "candidate_version": candidate_version,
        "gate_context_hash": context_hash,
        "window_start": window_start,
        "window_end": window_end,
        "training_window_end": training_window_end,
        **evidence,
        "policy": policy,
        "computed_at": window_end,
    }
    excluded = insert(ForecastSectorGateEvidence).excluded
    db.execute(
        insert(ForecastSectorGateEvidence)
        .values(values)
        .on_conflict_do_update(
            constraint="uq_forecast_sector_gate_evidence_run_spot",
            set_={
                key: getattr(excluded, key)
                for key in values
                if key not in {"run_id", "spot_id"}
            },
        )
    )
    db.commit()


def prune_forecast_samples(
    db,
    *,
    retention_days: int = 400,
    batch_size: int = 5000,
    now=None,
) -> dict:
    """Delete one bounded batch of expired verification samples."""
    now = now or datetime.now(timezone.utc)
    retention_days = max(120, min(int(retention_days), 730))
    batch_size = max(100, min(int(batch_size), 50_000))
    cutoff = now - timedelta(days=retention_days)
    expired_ids = select(WeatherForecastSample.id).where(
        WeatherForecastSample.valid_at < cutoff
    ).order_by(WeatherForecastSample.valid_at).limit(batch_size)
    result = db.execute(
        delete(WeatherForecastSample).where(
            WeatherForecastSample.id.in_(expired_ids)
        )
    )
    db.commit()
    return {
        "cutoff": cutoff.isoformat(),
        "deleted": max(0, result.rowcount or 0),
        "batch_size": batch_size,
    }


def score_spot_forecasts_serving_baseline(
    db,
    spot_id,
    *,
    now=None,
    lookback_days: int = 45,
    tolerance_s: int = 1200,
    blend_overrides=None,
) -> list[dict]:
    """Score the currently served profile before replacing it with a candidate."""
    from app.weather.profiles import resolve_weather_profile

    now = now or datetime.now(timezone.utc)
    profile = db.scalar(
        select(SpotWeatherProfile).where(SpotWeatherProfile.spot_id == spot_id)
    )
    return _score_spot_serving_variant(
        db,
        spot_id,
        sector_profile=resolve_weather_profile(profile),
        now=now,
        lookback_days=lookback_days,
        tolerance_s=tolerance_s,
        blend_overrides=blend_overrides,
    )


def score_spot_forecasts_corrected(db, spot_id, *, version: int, now=None, lookback_days: int = 45,
                                   tolerance_s: int = 1200, blend_overrides=None) -> list[dict]:
    """Shadow score: apply candidate sector ``version`` to the stored raw samples and
    score per-model + consensus against the SAME gated observations as the raw pass.

    Returns [] when the version, samples or observations are missing. No served value
    changes; this only produces candidate-variant measurement rows.
    """
    now = now or datetime.now(timezone.utc)
    sector_profile = _scoring_sector_profile(db, spot_id, version)
    if sector_profile is None:
        return []
    return _score_spot_serving_variant(
        db,
        spot_id,
        sector_profile=sector_profile,
        now=now,
        lookback_days=lookback_days,
        tolerance_s=tolerance_s,
        blend_overrides=blend_overrides,
    )


def eligible_spot_ids(db) -> list:
    """Published spots with an approved, representative station worth scoring."""
    rows = db.execute(
        select(WeatherStation.spot_id)
        .join(Spot, Spot.id == WeatherStation.spot_id)
        .where(
            WeatherStation.active.is_(True),
            WeatherStation.approved.is_(True),
            WeatherStation.representativeness_status == "passed",
            Spot.status == "published",
        )
        .distinct()
    ).all()
    return [row[0] for row in rows]


def persist_verification_scores(
    db,
    run_id,
    spot_id,
    records,
    *,
    variant: str = "raw",
    window_start=None,
    window_end=None,
    computed_at=None,
    gate_context_hash: str | None = None,
) -> int:
    if not records or not hasattr(db, "execute"):
        return 0
    computed_at = computed_at or datetime.now(timezone.utc)
    values = [{
        "run_id": run_id, "spot_id": spot_id, "model_id": r["model_id"], "variant": variant,
        "lead_bucket": r["lead_bucket"], "direction_sector": r["direction_sector"],
        "sample_count": r["sample_count"], "bias_ms": r["bias_ms"], "mae_ms": r["mae_ms"],
        "rmse_ms": r["rmse_ms"], "direction_mae_deg": r["direction_mae_deg"],
        "gust_mae_ms": r["gust_mae_ms"],
        "window_start": window_start, "window_end": window_end,
        "gate_context_hash": gate_context_hash, "computed_at": computed_at,
    } for r in records]
    excluded = insert(ForecastVerificationScore).excluded
    stmt = insert(ForecastVerificationScore).values(values).on_conflict_do_update(
        constraint="uq_forecast_verification_score",
        set_={"sample_count": excluded.sample_count, "bias_ms": excluded.bias_ms,
              "mae_ms": excluded.mae_ms, "rmse_ms": excluded.rmse_ms,
              "direction_mae_deg": excluded.direction_mae_deg, "gust_mae_ms": excluded.gust_mae_ms,
              "window_start": excluded.window_start, "window_end": excluded.window_end,
              "gate_context_hash": excluded.gate_context_hash,
              "computed_at": excluded.computed_at},
    )
    db.execute(stmt)
    db.commit()
    return len(values)


def run_verification_scoring(db, *, spot_ids=None, now=None, lookback_days: int = 45,
                             tolerance_s: int = 1200, variant: str = "raw",
                             run_id=None, persist: bool = True) -> dict:
    """Score every eligible spot in one reproducible run; returns a compact summary."""
    now = now or datetime.now(timezone.utc)
    run_id = run_id or uuid.uuid4()
    window_start = now - timedelta(days=max(1, min(lookback_days, 365)))
    targets = list(spot_ids) if spot_ids is not None else eligible_spot_ids(db)
    spots_scored = 0
    total_rows = 0
    for spot_id in targets:
        records = score_spot_forecasts(db, spot_id, now=now, lookback_days=lookback_days, tolerance_s=tolerance_s)
        if not records:
            continue
        spots_scored += 1
        total_rows += len(records)
        if persist:
            persist_verification_scores(db, run_id, spot_id, records, variant=variant,
                                        window_start=window_start, window_end=now, computed_at=now)
    return {
        "run_id": str(run_id), "spots_scored": spots_scored, "rows": total_rows,
        "variant": variant, "lookback_days": lookback_days,
        "window_start": window_start.isoformat(), "window_end": now.isoformat(),
    }


def run_gated_verification_scoring(db, *, spot_ids=None, now=None, lookback_days: int = 45,
                                   tolerance_s: int = 1200, run_id=None, persist: bool = True,
                                   blend_overrides=None) -> dict:
    """Score and persist statistically defensible candidate activation evidence.

    Baseline and candidate use identical observations and raw forecast members.
    WP6 candidates are evaluated only after their immutable training boundary.
    The activation statistic collapses repeated runs by valid time and uses a
    deterministic day-block bootstrap, while the existing cohort score rows are
    retained for diagnostics.
    """
    from app.config import get_settings
    from app.weather.profiles import resolve_weather_profile
    from app.weather.sector_activation import candidate_variant, latest_candidate_version
    from app.weather.serving_context import serving_context_hash

    now = now or datetime.now(timezone.utc)
    run_id = run_id or uuid.uuid4()
    settings = get_settings()
    if blend_overrides is None:
        blend_overrides = settings.wind_sector_blend
    policy = {
        "version": "sector-gate-v2",
        # Records which forecast-sample time normalisation produced this evidence.
        # Evidence written before the provider-zone UTC fix lacks this marker and
        # is refused at the activation gate, so time-corrupted samples can never
        # authorise a new activation until a correctly-normalised run rebuilds it.
        "time_normalization": TIME_NORMALIZATION_VERSION,
        "min_mae_drop_ms": settings.wind_sector_min_mae_drop_ms,
        "min_unique_valid_times": settings.wind_sector_gate_min_unique_valid_times,
        "min_distinct_days": settings.wind_sector_gate_min_distinct_days,
        "bootstrap_iterations": settings.wind_sector_gate_bootstrap_iterations,
        "confidence": 0.95,
        "block": "utc_day",
    }
    window_start = now - timedelta(days=max(1, min(lookback_days, 365)))
    targets = list(spot_ids) if spot_ids is not None else eligible_spot_ids(db)
    raw_spots = corrected_spots = raw_rows = corrected_rows = 0
    contexts_changed = 0
    candidate_versions: dict[str, int] = {}
    gate_statuses: dict[str, int] = defaultdict(int)
    for spot_id in targets:
        version = latest_candidate_version(db, spot_id)
        context_before = (
            serving_context_hash(
                db,
                spot_id,
                candidate_version=version,
                blend_overrides=blend_overrides,
            )
            if version is not None
            else None
        )
        candidate_profile = (
            _scoring_sector_profile(db, spot_id, version)
            if version is not None
            else None
        )
        training_end = None
        training_error = False
        if candidate_profile is not None:
            try:
                training_end = _candidate_training_end(candidate_profile)
            except (TypeError, ValueError):
                training_error = True

        spot_window_start = window_start
        if training_end is not None:
            spot_window_start = max(
                spot_window_start, training_end + timedelta(microseconds=1)
            )
        observations = gated_observations(
            db, spot_id, cutoff=spot_window_start, until=now
        )
        samples = db.scalars(
            select(WeatherForecastSample).where(
                WeatherForecastSample.spot_id == spot_id,
                WeatherForecastSample.valid_at >= spot_window_start,
                WeatherForecastSample.valid_at <= now,
            )
        ).all()
        calibrations = load_calibrations(db, spot_id)
        stored_profile = db.scalar(
            select(SpotWeatherProfile).where(SpotWeatherProfile.spot_id == spot_id)
        )
        baseline_prepared = _corrected_samples(
            samples,
            resolve_weather_profile(stored_profile),
            blend_overrides,
            calibrations=calibrations,
        )
        baseline_consensus = _serving_consensus_predictions(
            baseline_prepared, calibrations
        )
        raw = _score_predictions(
            _sample_predictions(baseline_prepared),
            observations,
            tolerance_s=tolerance_s,
        )
        raw += _score_predictions(
            baseline_consensus, observations, tolerance_s=tolerance_s
        )

        corrected = []
        candidate_consensus = []
        if candidate_profile is not None and not training_error:
            candidate_prepared = _corrected_samples(
                samples,
                candidate_profile,
                blend_overrides,
                calibrations=calibrations,
            )
            candidate_consensus = _serving_consensus_predictions(
                candidate_prepared, calibrations
            )
            corrected = _score_predictions(
                _sample_predictions(candidate_prepared),
                observations,
                tolerance_s=tolerance_s,
            )
            corrected += _score_predictions(
                candidate_consensus,
                observations,
                tolerance_s=tolerance_s,
            )

        evidence = None
        if version is not None and candidate_profile is not None:
            if training_error:
                evidence = {
                    "matched_forecasts": 0,
                    "unique_valid_times": 0,
                    "distinct_days": 0,
                    "baseline_mae_ms": None,
                    "candidate_mae_ms": None,
                    "mae_drop_ms": None,
                    "ci_lower_ms": None,
                    "ci_upper_ms": None,
                    "status": "collecting",
                    "reason": "invalid_training_boundary",
                }
            else:
                evidence = _paired_gate_statistics(
                    baseline_consensus,
                    candidate_consensus,
                    observations,
                    tolerance_s=tolerance_s,
                    min_unique_valid_times=policy["min_unique_valid_times"],
                    min_distinct_days=policy["min_distinct_days"],
                    min_mae_drop_ms=policy["min_mae_drop_ms"],
                    bootstrap_iterations=policy["bootstrap_iterations"],
                )
        if version is not None:
            context_after = serving_context_hash(
                db,
                spot_id,
                candidate_version=version,
                blend_overrides=blend_overrides,
            )
            if context_after != context_before:
                contexts_changed += 1
                continue
        if evidence is not None:
            gate_statuses[evidence["status"]] += 1
        if raw:
            raw_spots += 1
            raw_rows += len(raw)
            if persist:
                persist_verification_scores(
                    db, run_id, spot_id, raw, variant="raw",
                    window_start=spot_window_start, window_end=now, computed_at=now,
                    gate_context_hash=context_before,
                )
        if version is not None and candidate_profile is not None:
            candidate_versions[str(spot_id)] = version
        if corrected:
            corrected_spots += 1
            corrected_rows += len(corrected)
            if persist:
                persist_verification_scores(
                    db, run_id, spot_id, corrected,
                    variant=candidate_variant(version),
                    window_start=spot_window_start, window_end=now, computed_at=now,
                    gate_context_hash=context_before,
                )
        if persist and evidence is not None:
            persist_sector_gate_evidence(
                db,
                run_id=run_id,
                spot_id=spot_id,
                candidate_version=version,
                context_hash=context_before,
                window_start=spot_window_start,
                window_end=now,
                training_window_end=training_end,
                evidence=evidence,
                policy=policy,
            )
    return {
        "run_id": str(run_id), "raw_spots_scored": raw_spots, "raw_rows": raw_rows,
        "corrected_spots_scored": corrected_spots, "corrected_rows": corrected_rows,
        "candidate_versions": candidate_versions,
        "contexts_changed": contexts_changed,
        "gate_statuses": dict(gate_statuses),
        "lookback_days": lookback_days,
        "window_start": window_start.isoformat(), "window_end": now.isoformat(),
    }
