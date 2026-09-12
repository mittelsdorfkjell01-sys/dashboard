"""Candidate-sector activation for the forecast serving path.

Separate from the producer runner by design: the runner writes candidates
(enabled=False); activation is a deliberate, WP1-gated decision. Keeping it here
lets both the admin endpoint and the activation CLI share one implementation.
The separate, neutral wind-climatology direction rows share the legacy table but
are explicitly outside this lifecycle.
"""

from __future__ import annotations

from collections import defaultdict
import logging
from statistics import mean

from sqlalchemy import or_, select, update

from app.live.cache import Cache
from app.models import (
    ForecastSnapshot,
    ForecastVerificationScore,
    Spot,
    SpotWeatherProfile,
    SpotWeatherSector,
)
from app.weather.profiles import WIND_CLIMATOLOGY_V3_NOTE, is_forecast_sector
from app.weather.serving_context import serving_context_hash

CANDIDATE_VARIANT_PREFIX = "candidate:"
GATE_MODEL_ID = "consensus"

logger = logging.getLogger(__name__)


def _log_gate_rejection(
    *,
    spot_id,
    version: int,
    gate_run_id,
    reason_code: str,
    **details,
) -> None:
    """Emit a stable, aggregation-friendly event for WP1 gate failures."""
    logger.warning(
        "weather_sector_gate_rejected",
        extra={
            "weather_event": "weather_sector_gate_rejected",
            "weather_reason_code": reason_code,
            "weather_spot_id": str(spot_id),
            "weather_candidate_version": version,
            "weather_gate_run_id": str(gate_run_id),
            **details,
        },
    )


def _forecast_sector_clause():
    return or_(
        SpotWeatherSector.note.is_(None),
        SpotWeatherSector.note != WIND_CLIMATOLOGY_V3_NOTE,
    )


def _base36(value: int) -> str:
    digits = "0123456789abcdefghijklmnopqrstuvwxyz"
    output = ""
    while value:
        value, remainder = divmod(value, 36)
        output = digits[remainder] + output
    return output or "0"


def candidate_variant(version: int) -> str:
    """Compact, schema-safe score variant that binds a run to one version."""
    if version < 1:
        raise ValueError("candidate version must be positive")
    variant = f"{CANDIDATE_VARIANT_PREFIX}{_base36(version)}"
    if len(variant) > 16:  # ForecastVerificationScore.variant is varchar(16).
        raise ValueError("candidate version cannot be encoded in score variant")
    return variant


def parse_candidate_variant(variant: str) -> int | None:
    if not variant.startswith(CANDIDATE_VARIANT_PREFIX):
        return None
    encoded = variant[len(CANDIDATE_VARIANT_PREFIX):]
    try:
        version = int(encoded, 36)
    except ValueError:
        return None
    return version if version > 0 and candidate_variant(version) == variant else None


def latest_candidate_version(db, spot_id) -> int | None:
    profile = db.scalar(select(SpotWeatherProfile).where(SpotWeatherProfile.spot_id == spot_id))
    if profile is None:
        return None
    rows = db.scalars(
        select(SpotWeatherSector)
        .where(
            SpotWeatherSector.profile_id == profile.id,
            _forecast_sector_clause(),
        )
        .order_by(SpotWeatherSector.version.desc())
    ).all()
    if not rows:
        return None
    active_version = max((row.version for row in rows if row.enabled), default=0)
    by_version: dict[int, list[SpotWeatherSector]] = defaultdict(list)
    for row in rows:
        by_version[row.version].append(row)
    for version in sorted(by_version, reverse=True):
        if version <= active_version:
            continue
        try:
            _validate_candidate(by_version[version])
        except ValueError:
            continue
        return version
    return None


def _validate_candidate(candidate) -> None:
    """Require the complete canonical axis produced and scored by WP3–WP6."""
    if any(row.enabled for row in candidate):
        raise ValueError("sector version is already active or only partially disabled")
    expected = {
        (round(float(index * 30), 6), round(float((index + 1) * 30 % 360), 6))
        for index in range(12)
    }
    actual = {
        (round(float(row.start_deg) % 360.0, 6), round(float(row.end_deg) % 360.0, 6))
        for row in candidate
    }
    if len(candidate) != 12 or actual != expected:
        raise ValueError("sector candidate must contain all 12 canonical 30-degree sectors")


def activate_spot_sectors(
    db,
    spot_id,
    version: int,
    *,
    actor: str,
    gate_run_id,
    min_bias_drop: float = 0.0,
    reason: str | None = None,
    cache: Cache | None = None,
) -> dict:
    """Enable one complete, currently scored version after its WP1 gate passes."""
    from app.admin.audit import record_audit

    # Every serving-state mutation and final snapshot publication takes the spot
    # lock first, then the weather-profile lock.  This shared order prevents an
    # in-flight publisher from promoting data computed before this activation.
    spot = db.scalar(select(Spot).where(Spot.id == spot_id).with_for_update())
    if spot is None:
        raise LookupError("spot not found")
    profile = db.scalar(
        select(SpotWeatherProfile)
        .where(SpotWeatherProfile.spot_id == spot_id)
        .with_for_update()
    )
    if profile is None:
        raise LookupError("spot has no weather profile")
    if not profile.active:
        raise ValueError("weather profile is inactive")
    candidate = db.scalars(select(SpotWeatherSector).where(
        SpotWeatherSector.profile_id == profile.id,
        SpotWeatherSector.version == version,
        _forecast_sector_clause(),
    )).all()
    if not candidate:
        raise LookupError(f"no sector version {version} for spot")
    _validate_candidate(candidate)
    current_candidate = latest_candidate_version(db, spot_id)
    if current_candidate != version:
        raise ValueError("scored sector candidate is no longer the latest candidate")
    gate = candidate_gate_results(
        db, gate_run_id, spot_id=spot_id
    ).get(str(spot_id))
    if gate is None or int(gate["version"]) != version:
        _log_gate_rejection(
            spot_id=spot_id,
            version=version,
            gate_run_id=gate_run_id,
            reason_code="run_does_not_authorize_candidate",
        )
        raise ValueError("verification run does not authorize this candidate version")
    drop = float(gate["mae_drop"])
    if drop <= 0 or drop < min_bias_drop:
        _log_gate_rejection(
            spot_id=spot_id,
            version=version,
            gate_run_id=gate_run_id,
            reason_code="insufficient_mae_drop",
            weather_mae_drop=drop,
            weather_min_mae_drop=min_bias_drop,
        )
        raise ValueError(
            f"candidate MAE drop {drop:.4f} must be positive and at least "
            f"{min_bias_drop:.4f} m/s"
        )
    current_context = serving_context_hash(
        db, spot_id, candidate_version=version
    )
    if gate["context_hash"] != current_context:
        _log_gate_rejection(
            spot_id=spot_id,
            version=version,
            gate_run_id=gate_run_id,
            reason_code="stale_serving_context",
            weather_expected_context_hash=gate["context_hash"],
            weather_current_context_hash=current_context,
        )
        raise ValueError(
            "verification context is stale; re-score after profile, calibration, "
            "blend, physics, baseline, or candidate changes"
        )
    active_rows = db.scalars(select(SpotWeatherSector).where(
        SpotWeatherSector.profile_id == profile.id,
        SpotWeatherSector.enabled.is_(True),
    )).all()
    active_corrections = [row for row in active_rows if is_forecast_sector(row)]
    previously_active = sorted({row.version for row in active_corrections})
    if active_corrections:
        db.execute(update(SpotWeatherSector)
                   .where(SpotWeatherSector.id.in_([row.id for row in active_corrections]))
                   .values(enabled=False))
    db.execute(update(SpotWeatherSector)
               .where(
                   SpotWeatherSector.profile_id == profile.id,
                   SpotWeatherSector.version == version,
                   _forecast_sector_clause(),
               )
               .values(enabled=True))
    invalidated = db.execute(
        update(ForecastSnapshot)
        .where(ForecastSnapshot.spot_id == spot_id, ForecastSnapshot.active.is_(True))
        .values(active=False)
    )
    record_audit(db, spot_id, "weather_sector_activation", {
        "version": version,
        "deactivated_versions": previously_active,
        "gate_run_id": str(gate_run_id),
        "gate_context_hash": current_context,
        "mae_drop": drop,
        "min_bias_drop": min_bias_drop,
        "reason": reason,
    }, actor)
    db.commit()
    if cache is not None:
        from app.live.public_cache import invalidate_public_weather

        invalidate_public_weather(cache, spot_id)
    logger.info(
        "weather_sector_activation_succeeded",
        extra={
            "weather_event": "weather_sector_activation_succeeded",
            "weather_spot_id": str(spot_id),
            "weather_candidate_version": version,
            "weather_gate_run_id": str(gate_run_id),
            "weather_gate_context_hash": current_context,
            "weather_mae_drop": drop,
            "weather_snapshots_invalidated": max(0, invalidated.rowcount or 0),
        },
    )
    return {"spot_id": str(spot_id), "activated_version": version,
            "deactivated_versions": previously_active, "sectors": len(candidate),
            "snapshots_invalidated": max(0, invalidated.rowcount or 0),
            "gate_run_id": str(gate_run_id), "mae_drop": drop,
            "gate_context_hash": current_context}


def _run_mean_mae(db, run_id, variant: str = "raw") -> dict[str, float]:
    rows = db.execute(
        select(ForecastVerificationScore.spot_id, ForecastVerificationScore.mae_ms)
        .where(ForecastVerificationScore.run_id == run_id, ForecastVerificationScore.variant == variant)
    ).all()
    by_spot: dict[str, list[float]] = defaultdict(list)
    for spot_id, mae in rows:
        by_spot[str(spot_id)].append(float(mae))
    return {spot_id: mean(values) for spot_id, values in by_spot.items() if values}


def _run_weighted_consensus_mae(
    db, run_id, variant: str, *, spot_id=None
) -> dict[str, tuple[float, int, str]]:
    statement = select(
        ForecastVerificationScore.spot_id,
        ForecastVerificationScore.mae_ms,
        ForecastVerificationScore.sample_count,
        ForecastVerificationScore.gate_context_hash,
    ).where(
        ForecastVerificationScore.run_id == run_id,
        ForecastVerificationScore.variant == variant,
        ForecastVerificationScore.model_id == GATE_MODEL_ID,
    )
    if spot_id is not None:
        statement = statement.where(
            ForecastVerificationScore.spot_id == spot_id
        )
    rows = db.execute(statement).all()
    totals: dict[str, list] = defaultdict(lambda: [0.0, 0.0, set()])
    for spot_id, mae, sample_count, context_hash in rows:
        count = max(0, int(sample_count))
        totals[str(spot_id)][0] += float(mae) * count
        totals[str(spot_id)][1] += count
        totals[str(spot_id)][2].add(context_hash)
    return {
        spot_id: (weighted_sum / count, int(count), next(iter(contexts)))
        for spot_id, (weighted_sum, count, contexts) in totals.items()
        if count > 0 and len(contexts) == 1 and None not in contexts
    }


def candidate_bias_improvement(db, run_id) -> dict[str, float]:
    """Per-spot serving-consensus MAE drop, measured within one run.

    Compares the candidate against the current serving baseline over identical
    samples and observations (``run_gated_verification_scoring`` writes both under
    one run id). Positive means the candidate lowers the public, sample-weighted
    consensus error. This is the authoritative WP1 activation gate: it measures
    the concrete candidate, not two different time windows.
    """
    results = {
        spot_id: result["mae_drop"]
        for spot_id, result in candidate_gate_results(db, run_id).items()
    }
    # Preserve read compatibility for WP1 runs created before candidate versions
    # were embedded in the variant. Batch activation intentionally does not use
    # these legacy rows because they cannot prove which version was scored.
    raw = _run_mean_mae(db, run_id, "raw")
    legacy = _run_mean_mae(db, run_id, "corrected")
    for spot_id in legacy:
        if spot_id in raw and spot_id not in results:
            results[spot_id] = round(raw[spot_id] - legacy[spot_id], 4)
    return results


def candidate_gate_results(
    db, run_id, *, spot_id=None
) -> dict[str, dict[str, int | float | str]]:
    """Return only unambiguous, version-bound within-run candidate results."""
    raw = _run_weighted_consensus_mae(
        db, run_id, "raw", spot_id=spot_id
    )
    statement = select(
        ForecastVerificationScore.spot_id,
        ForecastVerificationScore.model_id,
        ForecastVerificationScore.variant,
        ForecastVerificationScore.mae_ms,
        ForecastVerificationScore.sample_count,
        ForecastVerificationScore.gate_context_hash,
    ).where(ForecastVerificationScore.run_id == run_id)
    if spot_id is not None:
        statement = statement.where(
            ForecastVerificationScore.spot_id == spot_id
        )
    rows = db.execute(statement).all()
    grouped: dict[str, dict[int, list[tuple[float, int, str | None]]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for spot_id, model_id, variant, mae, sample_count, context_hash in rows:
        version = parse_candidate_variant(variant)
        if version is not None and model_id == GATE_MODEL_ID:
            # Only the public consensus authorizes serving activation. Per-model
            # rows remain available for diagnosing family-specific overcorrection.
            grouped[str(spot_id)][version].append(
                (float(mae), int(sample_count), context_hash)
            )

    results: dict[str, dict[str, int | float | str]] = {}
    for spot_id, by_version in grouped.items():
        # More than one candidate version under one run id is ambiguous and must
        # never authorize either version.
        if spot_id not in raw or len(by_version) != 1:
            continue
        version, values = next(iter(by_version.items()))
        sample_count = sum(max(0, count) for _, count, _ in values)
        contexts = {context for _, _, context in values}
        baseline_mae, baseline_count, baseline_context = raw[spot_id]
        if (
            sample_count <= 0
            or sample_count != baseline_count
            or contexts != {baseline_context}
        ):
            continue
        candidate_mae = sum(
            mae * max(0, count) for mae, count, _ in values
        ) / sample_count
        results[spot_id] = {
            "version": version,
            "mae_drop": round(baseline_mae - candidate_mae, 4),
            "context_hash": baseline_context,
        }
    return results


def spot_bias_improvement(db, after_run, baseline_run, *, variant: str = "raw") -> dict[str, float]:
    """Mean-MAE drop per spot across two runs (baseline - after); positive = improvement.

    DEPRECATED for activation gating: comparing the same variant across two runs
    conflates the correction with a different weather window and cannot isolate a
    candidate's effect. Use :func:`candidate_bias_improvement` (within-run
    baseline-vs-candidate) for the gate. Kept only for run-to-run drift reporting.
    """
    after = _run_mean_mae(db, after_run, variant)
    baseline = _run_mean_mae(db, baseline_run, variant)
    return {spot_id: round(baseline[spot_id] - after[spot_id], 4)
            for spot_id in after if spot_id in baseline}
