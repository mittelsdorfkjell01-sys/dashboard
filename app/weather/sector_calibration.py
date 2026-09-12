"""WP6 measurement calibration: shrink each sector factor from prior to posterior.

The WP3/WP5 sector factor is a climatological/physical PRIOR. As station
measurements accumulate (WP1 infrastructure), each sector's factor is blended
towards the measured multiplier obs/model with a shrinkage weight n/(n+k): few
samples stay near the prior, many approach the measurement. Every update writes
a NEW disabled candidate version (the prior is never deleted). The candidate
must pass the same shadow-scoring and activation gate as every other sector
version. Station wind only calibrates the FACTOR; it is never emitted as a
forecast value.
"""

from __future__ import annotations

import json
import hashlib
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from statistics import mean
import math

from sqlalchemy import select

from app.models import SpotWeatherProfile, SpotWeatherSector, WeatherForecastSample
from app.weather.physics.limits import clamp
from app.weather.profiles import is_forecast_sector
from app.weather.verification import (
    _circular_mean_deg,
    _consensus_predictions,
    direction_sector,
    gated_observations,
    nearest_observation,
    observation_index,
)

MIN_SECTOR_SAMPLES = 10
# Samples at which the posterior sits halfway between prior and measurement.
SHRINKAGE_K = 40.0
FACTOR_LOW, FACTOR_HIGH = 0.50, 1.60
POSTERIOR_SCHEMA = "sector-holdout-v2"


def shrink_factor(prior: float, measured: float, sample_count: int, *, k: float = SHRINKAGE_K) -> float:
    """Blend prior->measured by n/(n+k). n=0 keeps the prior; n>>k approaches measured."""
    if sample_count <= 0:
        return float(prior)
    weight = sample_count / (sample_count + k)
    return float(prior) + (float(measured) - float(prior)) * weight


def sector_measured_factor(pairs: list[tuple[float, float]]) -> tuple[float, int] | None:
    """Empirical obs/model multiplier for one sector as a ratio of means.

    ``pairs`` are (observed_speed, model_speed). Returns None below the minimum
    sample count or when no model speed is positive.
    """
    clean = [(float(o), float(m)) for o, m in pairs
             if m and m > 0 and math.isfinite(o) and math.isfinite(m)]
    if len(clean) < MIN_SECTOR_SAMPLES:
        return None
    model_mean = mean(m for _, m in clean)
    if model_mean <= 0:
        return None
    return mean(o for o, _ in clean) / model_mean, len(clean)


def _pairs_by_sector(observations, samples, *, tolerance_s: int) -> dict[int, list[tuple[float, float]]]:
    """Match the raw consensus forecast to the nearest gated observation per sector."""
    pairs: dict[int, list[tuple[float, float]]] = defaultdict(list)
    if not observations or not samples:
        return pairs
    observations_by_time = observation_index(observations)
    predictions_by_valid: dict[datetime, list[dict]] = defaultdict(list)
    for pred in _consensus_predictions(samples):
        predictions_by_valid[pred["valid_at"]].append(pred)
    for valid_at, predictions in predictions_by_valid.items():
        nearest = nearest_observation(
            observations_by_time, valid_at, tolerance_s=tolerance_s
        )
        if nearest is None:
            continue
        speed = mean(float(pred["wind_speed_ms"]) for pred in predictions)
        direction = _circular_mean_deg(
            [float(pred["wind_direction_deg"]) for pred in predictions]
        )
        pairs[direction_sector(direction)].append((nearest.wind_speed_ms, speed))
    return pairs


def _posterior_signature(rows: list[tuple[float, float, bool]]) -> str:
    payload = {
        "schema": POSTERIOR_SCHEMA,
        "sectors": [
            [round(start, 3), round(factor, 4), calibrated]
            for start, factor, calibrated in rows
        ],
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:16]


def recalibrate_spot_sectors(db, spot_id, *, now=None, lookback_days: int = 120,
                             tolerance_s: int = 1200, k: float = SHRINKAGE_K,
                             min_recalibration_days: int = 30) -> dict:
    """Shrink sector priors towards measurement; write a disabled candidate."""
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(days=max(14, min(lookback_days, 720)))
    training_window = {
        "training_window_start": cutoff.isoformat(),
        "training_window_end": now.isoformat(),
        "posterior_schema": POSTERIOR_SCHEMA,
    }

    profile = db.scalar(select(SpotWeatherProfile).where(SpotWeatherProfile.spot_id == spot_id))
    if profile is None:
        return {"status": "no_profile", "written": 0, "version": None, "calibrated": 0}
    sectors = [
        row
        for row in db.scalars(
            select(SpotWeatherSector).where(SpotWeatherSector.profile_id == profile.id)
        ).all()
        if is_forecast_sector(row)
    ]
    if not sectors:
        return {"status": "no_prior", "written": 0, "version": None, "calibrated": 0}
    by_version: dict[int, list[SpotWeatherSector]] = defaultdict(list)
    for row in sectors:
        by_version[row.version].append(row)
    latest_version = max(by_version)
    latest_rows = by_version[latest_version]
    latest_note = _note_payload(next((row.note for row in latest_rows if row.note), None))
    current_posterior = (
        latest_note.get("method") == "shrinkage_posterior"
        and latest_note.get("posterior_schema") == POSTERIOR_SCHEMA
    )
    invalid_current_boundary = False
    if current_posterior:
        training_end = _note_training_end(latest_note)
        if training_end is None:
            # A malformed/legacy note cannot ever produce valid holdout
            # evidence.  Rebuild it with a fresh immutable boundary instead of
            # freezing the spot forever on an unactivatable candidate.
            invalid_current_boundary = True
        # A disabled posterior needs a genuinely future holdout. Re-fitting it
        # on every cron tick would move the boundary forever and make that
        # evidence impossible to collect.
        elif not any(row.enabled for row in latest_rows):
            return {
                "status": "candidate_pending",
                "written": 0,
                "version": latest_version,
                "calibrated": sum(
                    bool(_note_payload(row.note).get("calibrated"))
                    for row in latest_rows
                ),
            }
        elif now - training_end < timedelta(
            days=max(1, min_recalibration_days)
        ):
            return {
                "status": "recalibration_cooldown",
                "written": 0,
                "version": latest_version,
                "calibrated": 0,
            }
    # Always shrink from the stable climatological/physical prior (GWA/microscale),
    # never from a previous posterior, so repeated runs converge by sample count
    # rather than drifting to the measurement.
    base_versions = [v for v, rows in by_version.items()
                     if not any(_note_method(r.note) == "shrinkage_posterior" for r in rows)]
    base_version = max(base_versions) if base_versions else min(by_version)
    priors = sorted(by_version[base_version], key=lambda row: row.start_deg)

    observations = gated_observations(db, spot_id, cutoff=cutoff, until=now)
    samples = db.scalars(select(WeatherForecastSample).where(
        WeatherForecastSample.spot_id == spot_id,
        WeatherForecastSample.valid_at >= cutoff,
        WeatherForecastSample.valid_at <= now,
    )).all()
    pairs = _pairs_by_sector(observations, samples, tolerance_s=tolerance_s)

    planned: list[tuple[SpotWeatherSector, float, dict]] = []
    calibrated = 0
    for prior in priors:
        index = int(prior.start_deg // 30) % 12
        measured = sector_measured_factor(pairs.get(index, []))
        if measured is None:
            planned.append((prior, float(prior.speed_factor), {
                "method": "shrinkage_posterior",
                "calibrated": False,
                "prior": round(prior.speed_factor, 4),
                **training_window,
            }))
            continue
        measured_factor, sample_count = measured
        posterior = clamp(shrink_factor(prior.speed_factor, measured_factor, sample_count, k=k),
                          FACTOR_LOW, FACTOR_HIGH)
        calibrated += 1
        planned.append((prior, posterior, {
            "method": "shrinkage_posterior", "calibrated": True,
            "prior": round(prior.speed_factor, 4), "measured": round(measured_factor, 4),
            "samples": sample_count, "k": k,
            **training_window,
        }))

    if calibrated == 0:
        return {"status": "insufficient_measurements", "written": 0, "version": latest_version, "calibrated": 0}

    signature = _posterior_signature([(p.start_deg, f, n["calibrated"]) for p, f, n in planned])
    latest_sig = next((_note_sig(r.note) for r in by_version[latest_version] if r.note), None)
    if latest_sig == signature and not invalid_current_boundary:
        return {"status": "idempotent", "written": 0, "version": latest_version, "calibrated": calibrated}

    version = latest_version + 1
    for prior, factor, note in planned:
        note["sig"] = signature
        db.add(SpotWeatherSector(
            profile_id=profile.id, start_deg=prior.start_deg, end_deg=prior.end_deg,
            speed_factor=round(factor, 4), direction_offset_deg=prior.direction_offset_deg,
            version=version, enabled=False, note=_encode_note(note),
        ))
    db.commit()
    return {"status": "ok", "written": len(planned), "version": version, "calibrated": calibrated}


def _note_sig(note: str | None) -> str | None:
    if not note:
        return None
    try:
        return json.loads(note).get("sig")
    except (ValueError, TypeError):
        return None


def _note_payload(note: str | None) -> dict:
    if not note:
        return {}
    try:
        value = json.loads(note)
        return value if isinstance(value, dict) else {}
    except (ValueError, TypeError):
        return {}


def _note_training_end(note: dict) -> datetime | None:
    value = note.get("training_window_end")
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def _encode_note(note: dict) -> str:
    """Keep WP6 audit metadata valid JSON within the model's 500-char field."""
    encoded = json.dumps(note, separators=(",", ":"))
    if len(encoded) <= 500:
        return encoded
    compact = {
        key: note[key]
        for key in (
            "method",
            "calibrated",
            "prior",
            "measured",
            "samples",
            "k",
            "training_window_end",
            "posterior_schema",
            "sig",
        )
        if key in note
    }
    return json.dumps(compact, separators=(",", ":"))


def _note_method(note: str | None) -> str | None:
    if not note:
        return None
    try:
        return json.loads(note).get("method")
    except (ValueError, TypeError):
        return None


def recalibrate_eligible_spots(db, **kwargs) -> dict:
    """Recalibrate every spot that has a weather profile with sector rows."""
    spot_ids = [row[0] for row in db.execute(
        select(SpotWeatherProfile.spot_id)
        .join(SpotWeatherSector, SpotWeatherSector.profile_id == SpotWeatherProfile.id)
        .distinct()
    ).all()]
    updated = 0
    calibrated_spots = 0
    for spot_id in spot_ids:
        outcome = recalibrate_spot_sectors(db, spot_id, **kwargs)
        if outcome["status"] == "ok":
            updated += 1
            calibrated_spots += 1 if outcome["calibrated"] else 0
    return {"spots": len(spot_ids), "updated": updated}
