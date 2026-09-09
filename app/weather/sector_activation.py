"""Sector activation — the ONLY path that sets spot_weather_sectors.enabled=True.

Separate from the producer runner by design: the runner writes candidates
(enabled=False); activation is a deliberate, WP1-gated decision. Keeping it here
lets both the admin endpoint and the activation CLI share one implementation.
"""

from __future__ import annotations

from collections import defaultdict
from statistics import mean

from sqlalchemy import select, update

from app.models import ForecastVerificationScore, SpotWeatherProfile, SpotWeatherSector


def latest_candidate_version(db, spot_id) -> int | None:
    profile = db.scalar(select(SpotWeatherProfile).where(SpotWeatherProfile.spot_id == spot_id))
    if profile is None:
        return None
    return db.scalar(
        select(SpotWeatherSector.version)
        .where(SpotWeatherSector.profile_id == profile.id, SpotWeatherSector.enabled.is_(False))
        .order_by(SpotWeatherSector.version.desc())
        .limit(1)
    )


def activate_spot_sectors(db, spot_id, version: int, *, actor: str, reason: str | None = None) -> dict:
    """Enable exactly ``version`` and disable any previously active version."""
    from app.admin.audit import record_audit

    profile = db.scalar(select(SpotWeatherProfile).where(SpotWeatherProfile.spot_id == spot_id))
    if profile is None:
        raise LookupError("spot has no weather profile")
    candidate = db.scalars(select(SpotWeatherSector).where(
        SpotWeatherSector.profile_id == profile.id, SpotWeatherSector.version == version)).all()
    if not candidate:
        raise LookupError(f"no sector version {version} for spot")
    previously_active = sorted({s.version for s in db.scalars(select(SpotWeatherSector).where(
        SpotWeatherSector.profile_id == profile.id, SpotWeatherSector.enabled.is_(True))).all()})
    db.execute(update(SpotWeatherSector)
               .where(SpotWeatherSector.profile_id == profile.id, SpotWeatherSector.enabled.is_(True))
               .values(enabled=False))
    db.execute(update(SpotWeatherSector)
               .where(SpotWeatherSector.profile_id == profile.id, SpotWeatherSector.version == version)
               .values(enabled=True))
    record_audit(db, spot_id, "weather_sector_activation",
                 {"version": version, "deactivated_versions": previously_active, "reason": reason}, actor)
    db.commit()
    return {"spot_id": str(spot_id), "activated_version": version,
            "deactivated_versions": previously_active, "sectors": len(candidate)}


def _run_mean_mae(db, run_id, variant: str = "raw") -> dict[str, float]:
    rows = db.execute(
        select(ForecastVerificationScore.spot_id, ForecastVerificationScore.mae_ms)
        .where(ForecastVerificationScore.run_id == run_id, ForecastVerificationScore.variant == variant)
    ).all()
    by_spot: dict[str, list[float]] = defaultdict(list)
    for spot_id, mae in rows:
        by_spot[str(spot_id)].append(float(mae))
    return {spot_id: mean(values) for spot_id, values in by_spot.items() if values}


def spot_bias_improvement(db, after_run, baseline_run, *, variant: str = "raw") -> dict[str, float]:
    """Mean-MAE drop per spot (baseline - after); positive means improvement."""
    after = _run_mean_mae(db, after_run, variant)
    baseline = _run_mean_mae(db, baseline_run, variant)
    return {spot_id: round(baseline[spot_id] - after[spot_id], 4)
            for spot_id in after if spot_id in baseline}
