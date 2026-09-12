"""Deterministic fingerprints for weather-correction serving decisions.

The hash is deliberately based on effective values rather than database row ids
or timestamps.  It lets the WP1 gate prove that the candidate is being activated
against the same profile, calibration and blend configuration that was scored,
and lets the forecast publisher reject work computed across a profile change.
"""

from __future__ import annotations

import hashlib
import json

from sqlalchemy import or_, select

from app.config import get_settings
from app.forecast import CONSENSUS_VERSION, PHYSICS_VERSION
from app.models import (
    SpotWeatherProfile,
    SpotWeatherSector,
    WeatherModelCalibration,
)
from app.weather.profiles import WIND_CLIMATOLOGY_V3_NOTE

MIN_SERVING_CALIBRATION_SAMPLES = 60
ACTIVE_CALIBRATION_STATES = {"active", "legacy_active"}


def _forecast_sector_clause():
    return or_(
        SpotWeatherSector.note.is_(None),
        SpotWeatherSector.note != WIND_CLIMATOLOGY_V3_NOTE,
    )


def _number(value):
    return None if value is None else round(float(value), 9)


def _sector_value(row) -> dict:
    return {
        "version": int(row.version),
        "start_deg": _number(row.start_deg),
        "end_deg": _number(row.end_deg),
        "speed_factor": _number(row.speed_factor),
        "direction_offset_deg": _number(row.direction_offset_deg),
        "note": row.note,
    }


def serving_context_hash(
    db,
    spot_id,
    *,
    candidate_version: int | None = None,
    blend_overrides: dict[str, float] | None = None,
    lock_profile: bool = False,
) -> str:
    """Hash every effective input used by serving or candidate shadow scoring.

    ``lock_profile`` is used immediately before snapshot publication and sector
    activation.  Holding that row lock until commit serializes those two state
    transitions, so an in-flight publisher cannot resurrect pre-activation data.
    """

    profile_query = select(SpotWeatherProfile).where(
        SpotWeatherProfile.spot_id == spot_id
    )
    if lock_profile:
        profile_query = profile_query.with_for_update()
    profile = db.scalar(profile_query.execution_options(populate_existing=True))

    sectors = []
    if profile is not None:
        sectors = list(
            db.scalars(
                select(SpotWeatherSector)
                .where(
                    SpotWeatherSector.profile_id == profile.id,
                    _forecast_sector_clause(),
                )
                .execution_options(populate_existing=True)
            ).all()
        )

    active_sectors = sorted(
        (_sector_value(row) for row in sectors if row.enabled),
        key=lambda value: (
            value["version"], value["start_deg"], value["end_deg"]
        ),
    )
    candidate_sectors = []
    if candidate_version is not None:
        candidate_sectors = sorted(
            (
                _sector_value(row)
                for row in sectors
                if row.version == candidate_version
            ),
            key=lambda value: (value["start_deg"], value["end_deg"]),
        )

    calibration_rows = db.scalars(
        select(WeatherModelCalibration)
        .where(WeatherModelCalibration.spot_id == spot_id)
        .execution_options(populate_existing=True)
    ).all()
    calibrations = sorted(
        (
            {
                "model_id": row.model_id,
                "lead_bucket": row.lead_bucket,
                "sample_count": int(row.sample_count),
                "bias_ms": _number(row.bias_ms),
                "weight_multiplier": _number(row.weight_multiplier),
                "decision_status": getattr(
                    row, "decision_status", "legacy_active"
                ),
            }
            for row in calibration_rows
            if row.sample_count >= MIN_SERVING_CALIBRATION_SAMPLES
            and getattr(row, "decision_status", "legacy_active")
            in ACTIVE_CALIBRATION_STATES
        ),
        key=lambda value: (value["model_id"], value["lead_bucket"]),
    )

    blend = (
        get_settings().wind_sector_blend
        if blend_overrides is None
        else blend_overrides
    )
    payload = {
        "contract": 1,
        "physics_version": PHYSICS_VERSION,
        "consensus_version": CONSENSUS_VERSION,
        "blend": {
            str(key): _number(value)
            for key, value in sorted((blend or {}).items(), key=lambda item: str(item[0]))
        },
        "profile": None
        if profile is None
        else {
            "active": bool(profile.active),
            "quality_tier": profile.quality_tier,
            "timezone": profile.timezone,
            "elevation_m": _number(profile.elevation_m),
            "coastal_normal_deg": _number(profile.coastal_normal_deg),
            "exposure": profile.exposure,
            "roughness_length_m": _number(profile.roughness_length_m),
            "land_reference": profile.land_reference,
            "water_reference": profile.water_reference,
            "physics_version": profile.physics_version,
        },
        "active_sectors": active_sectors,
        "candidate_version": candidate_version,
        "candidate_sectors": candidate_sectors,
        "calibrations": calibrations,
    }
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
