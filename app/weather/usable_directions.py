"""Fail-closed derivation of usable meteorological wind directions.

Usable directions describe onshore and sideshore access at a documented launch.
They are deliberately independent of forecast correction sectors and are not a
general safety assessment.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

from shapely.geometry import LineString, MultiLineString, MultiPolygon, Point, Polygon, shape
from shapely.geometry.base import BaseGeometry

from app.wind_climatology.v3_direction import canonical_windows


AUTOMATIC_RULE_VERSION = "onshore-sideshore-16-v1"
LEGACY_RULE_VERSION = "legacy-v3-sector-migration-v1"
SECTOR_COUNT = 16
SECTOR_WIDTH_DEG = 360.0 / SECTOR_COUNT
MAX_ONSHORE_SIDE_DEVIATION_DEG = 90.0


@dataclass(frozen=True)
class DirectionDerivation:
    status: str
    sectors: list[int]
    windows: list[dict[str, float]]
    missing: list[str]
    evidence: dict[str, Any]


def _angular_difference(left: float, right: float) -> float:
    return abs((left - right + 180.0) % 360.0 - 180.0)


def _valid_source(source: Any) -> bool:
    if not isinstance(source, dict) or not str(source.get("label") or "").strip():
        return False
    parsed = urlparse(str(source.get("url") or ""))
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _geometry(value: Any, allowed: tuple[type[BaseGeometry], ...]) -> BaseGeometry | None:
    if not isinstance(value, dict):
        return None
    try:
        result = shape(value)
    except (TypeError, ValueError):
        return None
    if result.is_empty or not result.is_valid or not isinstance(result, allowed):
        return None
    return result


def _waterward_probe_is_inside(
    shoreline: BaseGeometry, usable_water: BaseGeometry, bearing_deg: float
) -> bool:
    point = shoreline.interpolate(0.5, normalized=True)
    radians = math.radians(bearing_deg)
    cosine = max(0.2, math.cos(math.radians(point.y)))
    for step in (0.00001, 0.00005, 0.0001):
        probe = Point(
            point.x + math.sin(radians) * step / cosine,
            point.y + math.cos(radians) * step,
        )
        if usable_water.covers(probe):
            return True
    return False


def sectors_for_waterward_normals(
    normals: list[float], *, excluded: set[int] | None = None
) -> list[int]:
    """Return canonical 16-bin sectors within onshore through sideshore.

    Sector indices use the repository's established centre convention:
    ``0 == 0°``, ``1 == 22.5°`` and so on. Boundary values at exactly 90° are
    sideshore and therefore included.
    """
    excluded = excluded or set()
    selected = {
        index
        for normal in normals
        for index in range(SECTOR_COUNT)
        if _angular_difference(index * SECTOR_WIDTH_DEG, normal)
        <= MAX_ONSHORE_SIDE_DEVIATION_DEG + 1e-9
    }
    return sorted(selected - excluded)


def windows_for_sectors(sectors: list[int]) -> list[dict[str, float]]:
    return [
        {
            "start_deg": index * SECTOR_WIDTH_DEG,
            "end_deg": ((index + 1) * SECTOR_WIDTH_DEG) % 360.0,
        }
        for index in sorted(set(sectors))
        if 0 <= index < SECTOR_COUNT
    ]


def classify_legacy_v3_sectors(rows: list[Any]) -> dict[str, Any]:
    """Classify old V3 marker rows without mutating them.

    A row is safe to migrate only when it is an enabled, neutral version-one
    16-bin sector. Disabled rows carried no effective direction selection and
    can be discarded. Any enabled deviation is retained as audit evidence but
    fails closed as ``ambiguous``.
    """
    enabled = [row for row in rows if bool(row.get("enabled") if isinstance(row, Mapping) else getattr(row, "enabled", False))]
    sectors: list[int] = []
    problems: list[str] = []
    evidence_rows: list[dict[str, Any]] = []
    for position, row in enumerate(enabled):
        def value(name: str, default: Any = None) -> Any:
            return row.get(name, default) if isinstance(row, Mapping) else getattr(row, name, default)

        raw = {
            "id": str(value("id")) if value("id") is not None else None,
            "start_deg": value("start_deg"),
            "end_deg": value("end_deg"),
            "speed_factor": value("speed_factor", 1),
            "direction_offset_deg": value("direction_offset_deg", 0),
            "version": value("version", 1),
        }
        evidence_rows.append(raw)
        try:
            start = float(raw["start_deg"]) % 360.0
            end = float(raw["end_deg"]) % 360.0
            index = round(start / SECTOR_WIDTH_DEG) % SECTOR_COUNT
            canonical_start = index * SECTOR_WIDTH_DEG
            canonical_end = ((index + 1) * SECTOR_WIDTH_DEG) % 360.0
            neutral = (
                _angular_difference(start, canonical_start) <= 1e-7
                and _angular_difference(end, canonical_end) <= 1e-7
                and abs(float(raw["speed_factor"]) - 1.0) <= 1e-9
                and abs(float(raw["direction_offset_deg"])) <= 1e-9
                and int(raw["version"]) == 1
            )
        except (TypeError, ValueError, OverflowError):
            neutral = False
            index = -1
        if not neutral:
            problems.append(f"row[{position}]_not_canonical_neutral_v1")
        elif index in sectors:
            problems.append(f"row[{position}]_duplicate_sector")
        else:
            sectors.append(index)
    if problems:
        status = "ambiguous"
        sectors = []
    elif sectors:
        status = "active"
        sectors.sort()
    else:
        status = "missing"
    return {
        "status": status,
        "sectors": sectors,
        "windows": windows_for_sectors(sectors),
        "problems": problems,
        "rows": evidence_rows,
    }


def derive_usable_directions(geometry: Any) -> DirectionDerivation:
    """Validate geometry evidence and derive onshore/sideshore direction bins."""
    missing: list[str] = []
    if not isinstance(geometry, dict):
        geometry = {}
    version = str(geometry.get("geometry_version") or "").strip()
    if not version:
        missing.append("geometry_version")
    conflicts = [str(value).strip() for value in geometry.get("conflicts") or [] if str(value).strip()]
    if conflicts:
        missing.append("unresolved_local_conflicts")

    areas = geometry.get("start_areas")
    if not isinstance(areas, list) or not areas:
        missing.append("start_areas")
        areas = []

    normals: list[float] = []
    area_evidence: list[dict[str, Any]] = []
    for index, area in enumerate(areas):
        prefix = f"start_areas[{index}]"
        if not isinstance(area, dict):
            missing.append(f"{prefix}.invalid")
            continue
        name = str(area.get("name") or "").strip()
        if not name:
            missing.append(f"{prefix}.name")
        source = area.get("source")
        if not _valid_source(source):
            missing.append(f"{prefix}.source")
        start_area = _geometry(area.get("start_area"), (Polygon, MultiPolygon))
        water = _geometry(area.get("usable_water"), (Polygon, MultiPolygon))
        shoreline = _geometry(area.get("shoreline"), (LineString, MultiLineString))
        if start_area is None or start_area.area <= 0:
            missing.append(f"{prefix}.start_area")
        if water is None or water.area <= 0:
            missing.append(f"{prefix}.usable_water")
        if shoreline is None or shoreline.length <= 0:
            missing.append(f"{prefix}.shoreline")
        raw_normal = area.get("waterward_normal_deg")
        if not isinstance(raw_normal, (int, float)) or not math.isfinite(float(raw_normal)):
            missing.append(f"{prefix}.waterward_normal_deg")
            normal = None
        else:
            normal = float(raw_normal) % 360.0
        if start_area is not None and shoreline is not None and start_area.distance(shoreline) > 0.00001:
            missing.append(f"{prefix}.shoreline_not_at_start")
        if water is not None and shoreline is not None and water.distance(shoreline) > 0.00001:
            missing.append(f"{prefix}.shoreline_not_at_water")
        if water is not None and shoreline is not None and normal is not None:
            if not _waterward_probe_is_inside(shoreline, water, normal):
                missing.append(f"{prefix}.normal_not_waterward")
        if not any(value.startswith(prefix) for value in missing) and normal is not None:
            normals.append(normal)
            area_evidence.append(
                {
                    "name": name,
                    "waterward_normal_deg": normal,
                    "source": source,
                }
            )

    exclusions = geometry.get("exclusions") or []
    excluded: set[int] = set()
    exclusion_evidence: list[dict[str, Any]] = []
    if not isinstance(exclusions, list):
        missing.append("exclusions")
        exclusions = []
    for index, item in enumerate(exclusions):
        prefix = f"exclusions[{index}]"
        if not isinstance(item, dict):
            missing.append(f"{prefix}.invalid")
            continue
        sector = item.get("sector_index")
        if not isinstance(sector, int) or not 0 <= sector < SECTOR_COUNT:
            missing.append(f"{prefix}.sector_index")
        if not str(item.get("reason") or "").strip():
            missing.append(f"{prefix}.reason")
        if not _valid_source(item.get("source")):
            missing.append(f"{prefix}.source")
        if not any(value.startswith(prefix) for value in missing):
            excluded.add(sector)
            exclusion_evidence.append(item)

    sectors = sectors_for_waterward_normals(normals, excluded=excluded) if not missing else []
    if not missing and not sectors:
        missing.append("all_directions_excluded")
    normalized = json.loads(json.dumps(geometry, sort_keys=True, separators=(",", ":")))
    digest = hashlib.sha256(
        json.dumps(normalized, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    evidence = {
        "origin": "automatic_geometry",
        "geometry_version": version or None,
        "rule_version": AUTOMATIC_RULE_VERSION,
        "rule": "meteorological-from sector centre within 90 degrees of a waterward normal",
        "input_hash": digest,
        "start_areas": area_evidence,
        "exclusions": exclusion_evidence,
        "conflicts": conflicts,
        "missing": sorted(set(missing)),
        "safety_scope": "geometric_onshore_sideshore_suitability_only",
    }
    return DirectionDerivation(
        status="active" if not missing else "blocked",
        sectors=sectors,
        windows=windows_for_sectors(sectors),
        missing=sorted(set(missing)),
        evidence=evidence,
    )


def apply_geometry_to_profile(
    profile: Any, geometry: dict[str, Any], *, at: datetime | None = None
) -> DirectionDerivation:
    result = derive_usable_directions(geometry)
    timestamp = at or datetime.now(timezone.utc)
    profile.usable_direction_geometry = geometry
    profile.usable_direction_geometry_version = str(
        geometry.get("geometry_version") or ""
    ).strip() or None
    profile.usable_direction_rule_version = AUTOMATIC_RULE_VERSION
    profile.usable_direction_status = result.status
    profile.usable_direction_sectors = result.sectors
    profile.usable_direction_windows = result.windows
    profile.usable_direction_evidence = result.evidence
    profile.usable_direction_calculated_at = timestamp
    return result


def usable_direction_state(profile: Any) -> dict[str, Any]:
    if profile is None:
        return {
            "status": "missing",
            "effective": False,
            "missing": ["weather_profile"],
            "sectors": [],
            "windows": [],
            "geometry": None,
            "geometry_version": None,
            "rule_version": None,
            "evidence": {},
            "calculated_at": None,
        }
    status = getattr(profile, "usable_direction_status", "missing") or "missing"
    evidence = getattr(profile, "usable_direction_evidence", None) or {}
    rule_version = getattr(profile, "usable_direction_rule_version", None)
    origin = evidence.get("origin")
    stale_rule = origin == "automatic_geometry" and rule_version != AUTOMATIC_RULE_VERSION
    missing = list(evidence.get("missing") or [])
    if stale_rule:
        missing.append("direction_rule_changed")
    windows = canonical_windows(getattr(profile, "usable_direction_windows", None))
    effective = bool(
        getattr(profile, "active", False)
        and status == "active"
        and not stale_rule
        and windows
    )
    return {
        "status": "stale_rule" if stale_rule else status,
        "effective": effective,
        "missing": sorted(set(missing)),
        "sectors": list(getattr(profile, "usable_direction_sectors", None) or []),
        "windows": windows if effective else [],
        "geometry": getattr(profile, "usable_direction_geometry", None),
        "geometry_version": getattr(profile, "usable_direction_geometry_version", None),
        "rule_version": rule_version,
        "evidence": evidence,
        "calculated_at": getattr(profile, "usable_direction_calculated_at", None),
    }


def usable_direction_windows(profile: Any) -> list[dict[str, float]]:
    return usable_direction_state(profile)["windows"]
