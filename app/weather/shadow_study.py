"""Immutable persistence helpers for the internal phase-4 study."""

from __future__ import annotations
import hashlib
import json
from datetime import datetime, timezone
from sqlalchemy import select
from app.models import WeatherShadowForecast, WeatherShadowStudy

STUDY_VERSION = "swd-phase4-shadow-v1"
NORMALIZER_VERSION = "swd-wind-normalizer-v1"
CONSENSUS_VERSION = "swd-consensus-v1"
GEO_CANDIDATE_VERSION = "swd-shadow-geo-candidate-v1"


def payload_hash(values: dict) -> str:
    return hashlib.sha256(
        json.dumps(values, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def get_or_create_study(db, *, status="ready_but_scheduler_pending"):
    row = db.scalar(
        select(WeatherShadowStudy).where(WeatherShadowStudy.version == STUDY_VERSION)
    )
    if row:
        return row
    row = WeatherShadowStudy(
        version=STUDY_VERSION,
        status=status,
        started_at=datetime.now(timezone.utc),
        config={
            "spots": [
                "Baleal",
                "Brouwersdam",
                "Mundaka",
                "Lo Stagnone",
                "Pozo Izquierdo",
            ],
            "frequency_hours": 6,
            "event_threshold_kn": 14,
            "lead_bands": ["0-24h", "25-48h", "49-72h", "73-120h", "121-240h"],
        },
        algorithms={
            "normalizer": NORMALIZER_VERSION,
            "consensus": CONSENSUS_VERSION,
            "geo_candidate": GEO_CANDIDATE_VERSION,
            "public_effect": False,
        },
    )
    db.add(row)
    db.flush()
    return row


def store_forecast(db, **values) -> tuple[WeatherShadowForecast, bool]:
    identity = {
        k: values[k]
        for k in (
            "run_id",
            "spot_id",
            "variant",
            "provider_model",
            "model_run_at",
            "valid_at",
            "lead_hours",
        )
    }
    existing = db.scalar(select(WeatherShadowForecast).filter_by(**identity))
    hashed = payload_hash({k: v for k, v in values.items() if k != "payload_hash"})
    if existing:
        if existing.payload_hash != hashed:
            raise RuntimeError("as-issued forecast conflict")
        return existing, False
    row = WeatherShadowForecast(**values, payload_hash=hashed)
    db.add(row)
    db.flush()
    return row, True
