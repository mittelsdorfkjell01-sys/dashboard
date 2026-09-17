"""Offline-only candidate contract for direction-dependent LiveWind physics.

This module never opens a URL or raster.  Callers must supply already prepared
GLO-30, WorldCover, GWA and geometry evidence.  The resulting profile remains a
non-serving candidate until a separate reviewed sector activation copies an
approved response into the existing enabled-sector gate.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import math

from sqlalchemy import func, select

from app.models import SpotGeoProfileVersion

LIVE_WIND_PHYSICS_PROFILE_VERSION = "live-wind-physics-profile-v1"
REQUIRED_SOURCE_KEYS = ("glo30_dem", "glo30_wbm", "worldcover")
OPTIONAL_SOURCE_KEYS = ("gwa_10m",)
SECTOR_COUNT = 16

# These alternatives estimate the same long-term speed-level error and must
# replace, not multiply, one another.  Station residuals are deliberately not
# in this set: they correct the current regional model error before spot physics.
LONG_TERM_LEVEL_COMPONENTS = {
    "model_calibration",
    "gwa_era5_factor",
    "wp6_posterior",
}


@dataclass(frozen=True)
class CorrectionLedgerResult:
    ok: bool
    reasons: tuple[str, ...]
    ordered_components: tuple[str, ...]


def validate_correction_ledger(components) -> CorrectionLedgerResult:
    """Reject repeated layers and mutually exclusive long-term corrections."""
    if isinstance(components, dict):
        names = [str(name) for name, value in components.items() if value is not None]
    else:
        names = [str(name) for name in (components or ())]
    reasons = []
    if len(names) != len(set(names)):
        reasons.append("duplicate_correction_component")
    long_term = sorted(set(names) & LONG_TERM_LEVEL_COMPONENTS)
    if len(long_term) > 1:
        reasons.append("overlapping_long_term_speed_correction")
    if "combined_sector" in names and any(
        name in names
        for name in ("gwa_era5_factor", "roughness", "orography", "wp6_posterior")
    ):
        reasons.append("combined_sector_reapplied_as_individual_layers")
    return CorrectionLedgerResult(
        ok=not reasons,
        reasons=tuple(reasons),
        ordered_components=tuple(names),
    )


def _source(raw: dict, key: str) -> dict:
    value = (raw.get("sources") or {}).get(key)
    if not isinstance(value, dict):
        return {
            "status": "unavailable",
            "reason": "source_metadata_missing",
            "dataset_version": None,
            "resolution_m": None,
            "data_at": None,
        }
    status = value.get("status")
    if status not in {"available", "unavailable"}:
        status = "unavailable"
    return {
        "status": status,
        "reason": value.get("reason") if status == "unavailable" else None,
        "dataset_version": value.get("dataset_version"),
        "resolution_m": value.get("resolution_m"),
        "data_at": value.get("data_at"),
        "license": value.get("license"),
        "attribution": value.get("attribution"),
    }


def _field(value, *, sources: tuple[str, ...], reason="input_missing") -> dict:
    return {
        "status": "available" if value is not None else "unavailable",
        "value": value,
        "sources": list(sources),
        "reason": None if value is not None else reason,
    }


def _finite(value) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _normalize_component(name: str, value) -> dict:
    if not isinstance(value, dict) or value.get("status") != "available":
        reason = value.get("reason") if isinstance(value, dict) else "component_missing"
        return {
            "status": "unavailable",
            "factor": None,
            "direction_offset_deg": None,
            "reason": reason or "component_unavailable",
        }
    factor = _finite(value.get("factor"))
    offset = _finite(value.get("direction_offset_deg"))
    if factor is None or factor <= 0 or offset is None:
        return {
            "status": "unavailable",
            "factor": None,
            "direction_offset_deg": None,
            "reason": "component_response_invalid",
        }
    return {
        "status": "available",
        "factor": factor,
        "direction_offset_deg": offset,
        "reason": None,
        "evidence": value.get("evidence") or {},
        "source": value.get("source"),
    }


def _normalize_sector(index: int, raw_sector: dict | None) -> dict:
    width = 360.0 / SECTOR_COUNT
    start = index * width
    end = (index + 1) * width
    raw_sector = raw_sector if isinstance(raw_sector, dict) else {}
    components = {
        name: _normalize_component(name, value)
        for name, value in sorted((raw_sector.get("components") or {}).items())
    }
    available = {
        name: value for name, value in components.items() if value["status"] == "available"
    }
    ledger = validate_correction_ledger(available)
    if not ledger.ok:
        status, reason = "unavailable", ",".join(ledger.reasons)
        factor, offset = None, None
    elif not available:
        status, reason = "unavailable", "no_validated_sector_response"
        factor, offset = None, None
    else:
        raw_factor = math.prod(component["factor"] for component in available.values())
        raw_offset = sum(
            component["direction_offset_deg"] for component in available.values()
        )
        factor = max(0.65, min(1.45, raw_factor))
        offset = max(-25.0, min(25.0, raw_offset))
        status, reason = "candidate", None
    return {
        "index": index,
        "start_deg": start,
        "end_deg": end,
        "status": status,
        "reason": reason,
        "candidate_factor": factor,
        "candidate_direction_offset_deg": offset,
        "components": components,
        "correction_ledger": {
            "ok": ledger.ok,
            "ordered_components": list(ledger.ordered_components),
            "reasons": list(ledger.reasons),
            "application_order": [
                "model_baseline",
                "regional_station_residual",
                "local_spot_physics",
            ],
        },
        "serving_enabled": False,
    }


def build_offline_live_wind_physics_profile(
    raw: dict,
    *,
    generated_at: datetime,
) -> dict:
    """Normalize precomputed raster/geometry evidence into a hard-gated profile."""
    if generated_at.tzinfo is None or generated_at.utcoffset() is None:
        raise ValueError("generated_at must be timezone-aware")
    generated_at = generated_at.astimezone(timezone.utc)
    sources = {
        key: _source(raw, key) for key in (*REQUIRED_SOURCE_KEYS, *OPTIONAL_SOURCE_KEYS)
    }
    terrain = raw.get("terrain") if isinstance(raw.get("terrain"), dict) else {}
    surface = raw.get("surface") if isinstance(raw.get("surface"), dict) else {}
    raw_sectors = raw.get("sector_responses")
    raw_sectors = raw_sectors if isinstance(raw_sectors, list) else []
    sectors = [
        _normalize_sector(index, raw_sectors[index] if index < len(raw_sectors) else None)
        for index in range(SECTOR_COUNT)
    ]
    required_available = all(sources[key]["status"] == "available" for key in REQUIRED_SOURCE_KEYS)
    candidate_sector_count = sum(sector["status"] == "candidate" for sector in sectors)
    profile = {
        "schema_version": LIVE_WIND_PHYSICS_PROFILE_VERSION,
        "generated_at": generated_at.isoformat(),
        "status": "candidate" if required_available and candidate_sector_count else "unavailable",
        "serving_eligible": False,
        "activation": {
            "status": "not_reviewed",
            "reason": "offline_candidate_requires_manual_activation",
        },
        "sources": sources,
        "terrain": {
            "spot_elevation_m": _field(terrain.get("spot_elevation_m"), sources=("glo30_dem",)),
            "surrounding_elevation_m": _field(terrain.get("surrounding_elevation_m"), sources=("glo30_dem",)),
            "slope_deg": _field(terrain.get("slope_deg"), sources=("glo30_dem",)),
            "aspect_deg": _field(terrain.get("aspect_deg"), sources=("glo30_dem",)),
            "upwind_profiles": _field(terrain.get("upwind_profiles"), sources=("glo30_dem",)),
            "ridge_lee": _field(terrain.get("ridge_lee"), sources=("glo30_dem",)),
            "valley_axis": _field(terrain.get("valley_axis"), sources=("glo30_dem",)),
            "pass_nozzle": _field(terrain.get("pass_nozzle"), sources=("glo30_dem",)),
        },
        "surface": {
            "coast_orientation_deg": _field(surface.get("coast_orientation_deg"), sources=("glo30_wbm",)),
            "land_water_transition": _field(surface.get("land_water_transition"), sources=("glo30_wbm",)),
            "fetch_by_sector_m": _field(surface.get("fetch_by_sector_m"), sources=("glo30_wbm",)),
            "estuary_opening": _field(surface.get("estuary_opening"), sources=("glo30_wbm", "glo30_dem")),
            "roughness_by_sector_m": _field(surface.get("roughness_by_sector_m"), sources=("worldcover",)),
            "forest_fraction": _field(surface.get("forest_fraction"), sources=("worldcover",)),
            "built_fraction": _field(surface.get("built_fraction"), sources=("worldcover",)),
        },
        "sectors": sectors,
        "quality": {
            "required_sources_available": required_available,
            "candidate_sector_count": candidate_sector_count,
            "unavailable_sector_count": SECTOR_COUNT - candidate_sector_count,
        },
        "dynamic_inputs": {
            "stability": "unavailable",
            "daytime_thermal": "unavailable",
            "reason": "no_validated_dynamic_method_configured",
        },
    }
    profile["content_hash"] = hashlib.sha256(
        json.dumps(profile, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return profile


def ablate_physics_profile(profile: dict, omitted_components: set[str]) -> dict:
    """Recompute sector candidates without selected layers for verification."""
    clone = json.loads(json.dumps(profile))
    for sector in clone.get("sectors", []):
        raw_components = {
            name: value
            for name, value in (sector.get("components") or {}).items()
            if name not in omitted_components
        }
        normalized = _normalize_sector(sector["index"], {"components": raw_components})
        sector.update(normalized)
    clone["ablation"] = {"omitted_components": sorted(omitted_components)}
    clone["serving_eligible"] = False
    clone["content_hash"] = hashlib.sha256(
        json.dumps(clone, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return clone


def live_wind_physics_profile_doctor(profile: dict) -> dict:
    problems = []
    if profile.get("schema_version") != LIVE_WIND_PHYSICS_PROFILE_VERSION:
        problems.append("schema_version_invalid")
    if profile.get("serving_eligible") is not False:
        problems.append("candidate_must_not_be_serving_eligible")
    sectors = profile.get("sectors") if isinstance(profile.get("sectors"), list) else []
    if len(sectors) != SECTOR_COUNT:
        problems.append("sector_count_invalid")
    for index, sector in enumerate(sectors):
        if sector.get("index") != index:
            problems.append(f"sector_order_invalid:{index}")
        if sector.get("status") == "unavailable" and not sector.get("reason"):
            problems.append(f"unavailable_sector_without_reason:{index}")
        ledger = validate_correction_ledger(
            {
                name: value
                for name, value in (sector.get("components") or {}).items()
                if value.get("status") == "available"
            }
        )
        if not ledger.ok:
            problems.extend(f"sector_{index}:{reason}" for reason in ledger.reasons)
    for key in REQUIRED_SOURCE_KEYS:
        source = (profile.get("sources") or {}).get(key)
        if not isinstance(source, dict) or source.get("status") not in {"available", "unavailable"}:
            problems.append(f"source_status_missing:{key}")
    return {
        "ok": not problems,
        "problems": list(dict.fromkeys(problems)),
        "candidate_sector_count": sum(
            sector.get("status") == "candidate" for sector in sectors
        ),
    }


def persist_offline_live_wind_physics_candidate(
    db,
    *,
    spot_id,
    coordinate_hash: str,
    profile: dict,
) -> SpotGeoProfileVersion:
    """Persist a versioned inactive candidate; never flips an active profile."""
    doctor = live_wind_physics_profile_doctor(profile)
    if not doctor["ok"]:
        raise ValueError("invalid LiveWind physics candidate: " + ",".join(doctor["problems"]))
    existing = db.scalar(
        select(SpotGeoProfileVersion).where(
            SpotGeoProfileVersion.spot_id == spot_id,
            SpotGeoProfileVersion.coordinate_hash == coordinate_hash,
            SpotGeoProfileVersion.algorithm_version == LIVE_WIND_PHYSICS_PROFILE_VERSION,
        )
    )
    if existing is not None:
        return existing
    version = int(
        db.scalar(
            select(func.max(SpotGeoProfileVersion.version)).where(
                SpotGeoProfileVersion.spot_id == spot_id
            )
        )
        or 0
    ) + 1
    row = SpotGeoProfileVersion(
        spot_id=spot_id,
        version=version,
        algorithm_version=LIVE_WIND_PHYSICS_PROFILE_VERSION,
        coordinate_hash=coordinate_hash,
        status="ready" if profile.get("status") == "candidate" else "failed",
        quality="advanced" if profile.get("status") == "candidate" else "unavailable",
        sources=list((profile.get("sources") or {}).values()),
        profile=profile,
        warnings=doctor["problems"],
        active=False,
    )
    db.add(row)
    db.flush()
    return row
