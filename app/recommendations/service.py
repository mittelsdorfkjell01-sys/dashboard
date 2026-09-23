"""DB, forecast, cache, and audit orchestration for recommendation surfaces."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from enum import Enum
import hashlib
import json
import logging
import math
import uuid
from typing import Any, Iterable, Sequence

from geoalchemy2.shape import to_shape
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session, selectinload

from app.live.cache import Cache
from app.live.client import OpenMeteoClient
from app.models import RecommendationLog, Spot, SpotWeatherProfile
from app.recommendations.engine import Components, character_fit, forecast_components, reachability
from app.scoring.params import SCORING_PARAMS_VERSION, get_params
from app.scoring.rider.resolve import RiderContext
from app.search.timewindow import rank_by_timewindow, resolve_time_window

logger = logging.getLogger(__name__)

CACHE_VERSION = 1
LOCATION_BUCKET_DEGREES = 0.25


class RecommendationSurface(str, Enum):
    NOW = "now"
    NEXT_WEEK = "next_week"
    SEASON = "season"
    REGION = "region"


@dataclass(frozen=True, slots=True)
class LocationBucket:
    lat_index: int
    lon_index: int

    @property
    def center(self) -> tuple[float, float]:
        return (
            -90.0 + (self.lat_index + 0.5) * LOCATION_BUCKET_DEGREES,
            -180.0 + (self.lon_index + 0.5) * LOCATION_BUCKET_DEGREES,
        )

    @property
    def cache_token(self) -> str:
        return f"{self.lat_index}.{self.lon_index}"


def bucket_location(lat: float | None, lon: float | None) -> LocationBucket | None:
    """Discard raw coordinates immediately and retain only a coarse cell."""
    if lat is None and lon is None:
        return None
    if lat is None or lon is None:
        raise ValueError("lat and lon must be supplied together")
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise ValueError("coordinates outside valid range")
    lat_index = min(int((lat + 90.0) // LOCATION_BUCKET_DEGREES), 719)
    lon_index = min(int((lon + 180.0) // LOCATION_BUCKET_DEGREES), 1439)
    return LocationBucket(lat_index, lon_index)


def _rider_location_bucket(rider: RiderContext) -> LocationBucket | None:
    value = rider.profile.get("home_location")
    if not isinstance(value, dict):
        return None
    return bucket_location(value.get("lat"), value.get("lon"))


def _profile_for_scoring(rider: RiderContext) -> dict[str, Any]:
    return {
        **rider.profile,
        "sport": rider.sport,
        "personal_band": {
            "min_kt": rider.band.min_kt,
            "ideal_lo_kt": rider.band.ideal_lo_kt,
            "ideal_hi_kt": rider.band.ideal_hi_kt,
            "max_kt": rider.band.max_kt,
            "gust_tolerance_kt": rider.band.gust_tolerance_kt,
        },
    }


def _audience_fingerprint(rider: RiderContext) -> str:
    payload = {
        "band": rider.band.fingerprint,
        "excluded_bottoms": sorted(rider.profile.get("excluded_bottoms") or []),
        "preferred_water_character": sorted(
            rider.profile.get("preferred_water_character") or []
        ),
        "availability": sorted(rider.profile.get("availability") or []),
        "max_travel_km": rider.profile.get("max_travel_km"),
        "min_water_temp_c": rider.profile.get("min_water_temp_c"),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _window_start(
    surface: RecommendationSurface,
    *,
    now: datetime,
    month: int | None,
    weeks: tuple[int, int] | None,
) -> datetime:
    if surface in {RecommendationSurface.NOW, RecommendationSurface.REGION}:
        minute = (now.minute // 15) * 15
        return now.replace(minute=minute, second=0, microsecond=0)
    if surface == RecommendationSurface.NEXT_WEEK:
        return now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=2)
    if month is not None:
        return datetime(now.year, month, 1, tzinfo=timezone.utc)
    week = weeks[0] if weeks else 1
    return datetime.fromisocalendar(now.year, week, 1).replace(tzinfo=timezone.utc)


def _cache_key(
    *,
    sport: str,
    surface: RecommendationSurface,
    region_id: uuid.UUID | None,
    month: int | None,
    weeks: tuple[int, int] | None,
    location: LocationBucket | None,
    fingerprint: str,
    window_start: datetime,
    limit: int,
    params_version: int,
) -> str:
    return ":".join(
        (
            "recommendations",
            f"v{CACHE_VERSION}",
            sport,
            surface.value,
            str(region_id or "global"),
            str(month or "open"),
            f"{weeks[0]}-{weeks[1]}" if weeks else "open",
            location.cache_token if location else "no-location",
            fingerprint,
            window_start.isoformat(),
            str(limit),
            f"params-{params_version}",
        )
    )


def _cache_ttl(surface: RecommendationSurface) -> int:
    if surface in {RecommendationSurface.NOW, RecommendationSurface.REGION}:
        return 15 * 60
    if surface == RecommendationSurface.NEXT_WEEK:
        return 30 * 60
    return 6 * 60 * 60


def _spot_coords(spot: Spot) -> tuple[float, float] | None:
    if spot.location is None:
        return None
    point = to_shape(spot.location)
    return float(point.y), float(point.x)


def _distance_km(a: tuple[float, float] | None, b: tuple[float, float] | None) -> float | None:
    if a is None or b is None:
        return None
    lat1, lon1, lat2, lon2 = map(math.radians, (*a, *b))
    dlat, dlon = lat2 - lat1, lon2 - lon1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 6371.0088 * 2 * math.asin(min(1.0, math.sqrt(h)))


def _direction_windows(spot: Spot) -> list[dict[str, float]]:
    profile = getattr(spot, "weather_profile", None)
    if not profile or not profile.active or profile.reviewed_at is None:
        return []
    return [
        {"min": float(sector.start_deg), "max": float(sector.end_deg)}
        for sector in profile.sectors
        if sector.enabled
    ]


def _recommendable(spot: Spot, sport: str) -> bool:
    return (
        sport in (spot.sports or [])
        and spot.facing is not None
        and bool(_direction_windows(spot))
    )


def _load_candidates(
    db: Session, *, sport: str, region_id: uuid.UUID | None = None
) -> list[Spot]:
    stmt = (
        select(Spot)
        .where(Spot.status == "published", Spot.sports.any(sport))
        .options(
            selectinload(Spot.region),
            selectinload(Spot.weather_profile).selectinload(SpotWeatherProfile.sectors),
        )
    )
    if region_id is not None:
        stmt = stmt.where(Spot.region_id == region_id)
    return list(db.scalars(stmt))


def _with_daylight(days: Sequence[dict], coords: tuple[float, float] | None) -> list[dict]:
    """Use provider daylight when present, otherwise derive it once per day."""
    if coords is None:
        return [dict(day) for day in days]
    from app.era5.solar import solar_elevation_deg

    output: list[dict] = []
    for day in days:
        hours = [dict(hour) for hour in day.get("hours") or []]
        missing = [index for index, hour in enumerate(hours) if hour.get("is_day") is None]
        if missing:
            times = [datetime.fromisoformat(str(hours[index]["time"])) for index in missing]
            elevations = solar_elevation_deg(times, *coords)
            for index, elevation in zip(missing, elevations):
                hours[index]["is_day"] = bool(elevation > 0)
        output.append({**day, "hours": hours})
    return output


def _season_components(
    spot: Spot,
    rider: RiderContext,
    *,
    db: Session,
    window: dict,
    location: LocationBucket | None,
) -> Components:
    profile = _profile_for_scoring(rider)
    ranked = rank_by_timewindow([spot], window, rider.sport, profile, db=db)[0]
    climatology_fit = 0.65 * float(ranked["coverage"]) + 0.35 * float(ranked["intensity"])
    return Components(
        feasibility=1.0 if climatology_fit > 0 else 0.0,
        condition_fit=climatology_fit,
        character_fit=character_fit(profile, spot),
        confidence=1.0,
        reachability=reachability(
            _distance_km(location.center if location else None, _spot_coords(spot)), profile
        ),
    )


def _forecast_components(
    spot: Spot,
    rider: RiderContext,
    surface: RecommendationSurface,
    *,
    db: Session,
    client: OpenMeteoClient,
    cache: Cache,
    location: LocationBucket | None,
) -> Components:
    from app.live.service import get_forecast_series

    series = get_forecast_series(spot.id, 10, db=db, client=client, cache=cache)
    days = list(series.get("days") or [])
    selected = days[2:10] if surface == RecommendationSurface.NEXT_WEEK else days[:2]
    coords = _spot_coords(spot)
    return forecast_components(
        _profile_for_scoring(rider),
        rider.band,
        spot,
        _with_daylight(selected, coords),
        direction_windows=_direction_windows(spot),
        distance_km=_distance_km(location.center if location else None, coords),
    )


def _evaluate(
    candidates: Sequence[Spot],
    rider: RiderContext,
    surface: RecommendationSurface,
    *,
    db: Session,
    client: OpenMeteoClient,
    cache: Cache,
    location: LocationBucket | None,
    month: int | None,
    weeks: tuple[int, int] | None,
) -> list[tuple[Spot, Components, bool]]:
    if surface == RecommendationSurface.SEASON:
        range_input: dict[str, Any] | None = None
        if month is not None:
            range_input = {"month": month}
        elif weeks is not None:
            range_input = {"weeks": list(weeks)}
        window = resolve_time_window("season", range_input)
    params = get_params(rider.sport, db=db)
    social_config = params.get("social") or {}
    social_min_group = int(social_config.get("min_group_size") or 20)
    social_weight = (
        float(social_config.get("weight") or 0.0)
        if social_config.get("validated") is True
        else 0.0
    )
    from app.scoring.personal.social import SocialResult, social_scores_for_spots

    eligible_ids = [spot.id for spot in candidates if _recommendable(spot, rider.sport)]
    try:
        social_by_spot = social_scores_for_spots(
            db,
            spot_ids=eligible_ids,
            sport=rider.sport,
            level=str(rider.profile.get("level") or "advanced"),
            min_group_size=social_min_group,
            band_fingerprint=rider.band.fingerprint,
            similar_band=social_config.get("similar_band") is True,
        )
    except Exception as exc:
        logger.warning("recommendation social aggregate failed: %s", type(exc).__name__)
        try:
            db.rollback()
        except Exception:
            pass
        social_by_spot = {}
    rows: list[tuple[Spot, Components, bool]] = []
    for spot in candidates:
        eligible = _recommendable(spot, rider.sport)
        if not eligible:
            rows.append((spot, Components(0, 0, 0, 0, 0), False))
            continue
        try:
            components = (
                _season_components(spot, rider, db=db, window=window, location=location)
                if surface == RecommendationSurface.SEASON
                else _forecast_components(
                    spot, rider, surface, db=db, client=client, cache=cache, location=location
                )
            )
            social = social_by_spot.get(
                spot.id, SocialResult(0.5, 0, 0, False)
            )
            components = replace(
                components,
                social=social.score,
                social_weight=social_weight if social.available else 0.0,
            )
        except Exception as exc:
            # One provider or data failure must not erase other valid candidates.
            logger.warning("recommendation candidate %s failed: %s", spot.id, type(exc).__name__)
            try:
                db.rollback()
            except Exception:
                pass
            components = Components(0, 0, 0, 0, 0)
        rows.append((spot, components, True))
    rows.sort(key=lambda item: (not item[2], -item[1].utility, item[0].name.casefold()))
    return rows


def _ordered_spots(db: Session, ids: Iterable[str]) -> list[Spot]:
    parsed = [uuid.UUID(value) for value in ids]
    if not parsed:
        return []
    by_id = {
        spot.id: spot
        for spot in db.scalars(
            select(Spot).where(Spot.id.in_(parsed)).options(selectinload(Spot.region))
        )
    }
    return [by_id[spot_id] for spot_id in parsed if spot_id in by_id]


def _write_log(
    db: Session,
    rows: Sequence[tuple[Spot, Components | dict[str, Any], bool]],
    *,
    app_user_id: uuid.UUID | None,
    user_ref: str,
    surface: RecommendationSurface | str,
    window_start: datetime,
    fingerprint: str,
    audience_segment: str,
    params_version: int,
) -> None:
    surface_value = surface.value if isinstance(surface, RecommendationSurface) else surface
    values = [
        {
            "app_user_id": app_user_id,
            "user_ref": user_ref,
            "audience_segment": audience_segment,
            "spot_id": spot.id,
            "surface": surface_value,
            "window_start": window_start,
            "components": components.payload() if isinstance(components, Components) else components,
            "params_version": params_version,
            "profile_fingerprint": fingerprint,
        }
        for spot, components, _eligible in rows
    ]
    if not values:
        return
    stmt = pg_insert(RecommendationLog).values(values)
    stmt = stmt.on_conflict_do_update(
        constraint="uq_recommendation_log_window",
        set_={
            "components": stmt.excluded.components,
            "params_version": stmt.excluded.params_version,
            "profile_fingerprint": stmt.excluded.profile_fingerprint,
            "audience_segment": stmt.excluded.audience_segment,
            "created_at": datetime.now(timezone.utc),
        },
    )
    db.execute(stmt)
    db.commit()


def _active_params_version(db: Session, sport: str) -> int:
    from app.models import ScoringParams

    return int(db.scalar(
        select(ScoringParams.version)
        .where(ScoringParams.sport == sport, ScoringParams.active.is_(True))
        .order_by(ScoringParams.version.desc())
    ) or SCORING_PARAMS_VERSION)


def recommendations(
    db: Session,
    rider: RiderContext,
    *,
    surface: RecommendationSurface,
    sport: str,
    client: OpenMeteoClient,
    cache: Cache,
    app_user_id: uuid.UUID | None = None,
    region_id: uuid.UUID | None = None,
    month: int | None = None,
    weeks: tuple[int, int] | None = None,
    location: LocationBucket | None = None,
    limit: int = 12,
    now: datetime | None = None,
) -> list[Spot]:
    """Return feasible, recommendable spots in personalized order."""
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    location = location or _rider_location_bucket(rider)
    audience_fingerprint = _audience_fingerprint(rider)
    start = _window_start(surface, now=now, month=month, weeks=weeks)
    active_version = _active_params_version(db, sport)
    key = _cache_key(
        sport=sport, surface=surface, region_id=region_id, month=month, weeks=weeks,
        location=location, fingerprint=audience_fingerprint, window_start=start, limit=limit,
        params_version=active_version,
    )
    hit = cache.get(key)
    # Signed-in responses need an actor-specific recommendation_log row so a
    # later check-in can be attributed exactly. Anonymous responses may reuse
    # the shared average/fingerprint cache.
    if isinstance(hit, list) and app_user_id is None:
        return _ordered_spots(db, hit)

    rows = _evaluate(
        _load_candidates(db, sport=sport, region_id=region_id), rider, surface,
        db=db, client=client, cache=cache, location=location, month=month, weeks=weeks,
    )
    user_ref = f"user:{app_user_id}" if app_user_id else f"anon:{audience_fingerprint}"
    audience_segment = (
        "anonymous" if app_user_id is None
        else "logged_profile" if rider.source == "user"
        else "logged_without_profile"
    )
    _write_log(
        db, rows, app_user_id=app_user_id, user_ref=user_ref, surface=surface,
        window_start=start, fingerprint=rider.band.fingerprint,
        audience_segment=audience_segment, params_version=active_version,
    )
    ids = [str(spot.id) for spot, components, eligible in rows if eligible and components.utility > 0][:limit]
    cache.set(key, ids, _cache_ttl(surface))
    return _ordered_spots(db, ids)


def rank_existing_spots(
    db: Session,
    candidates: Sequence[Spot],
    rider: RiderContext,
    *,
    client: OpenMeteoClient,
    cache: Cache,
    location: LocationBucket | None = None,
    app_user_id: uuid.UUID | None = None,
    now: datetime | None = None,
) -> list[Spot]:
    """Personalize a filtered region set while retaining every candidate."""
    rows = _evaluate(
        candidates, rider, RecommendationSurface.REGION,
        db=db, client=client, cache=cache,
        location=location or _rider_location_bucket(rider), month=None, weeks=None,
    )
    instant = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    audience_fingerprint = _audience_fingerprint(rider)
    _write_log(
        db,
        rows,
        app_user_id=app_user_id,
        user_ref=f"user:{app_user_id}" if app_user_id else f"anon:{audience_fingerprint}",
        surface=RecommendationSurface.REGION,
        window_start=_window_start(
            RecommendationSurface.REGION, now=instant, month=None, weeks=None
        ),
        fingerprint=rider.band.fingerprint,
        audience_segment=(
            "anonymous" if app_user_id is None
            else "logged_profile" if rider.source == "user"
            else "logged_without_profile"
        ),
        params_version=_active_params_version(db, rider.sport),
    )
    return [spot for spot, _components, _eligible in rows]


class RiderUtilityScorer:
    """Search-compatible scorer that adds private rider character preferences."""

    def __init__(self, base: Any, rider: RiderContext) -> None:
        self.base = base
        self.rider = rider
        self.scored: dict[uuid.UUID, tuple[Spot, dict[str, Any]]] = {}

    def score(self, spot: Any, time_context: dict | None, profile: dict | None) -> float:
        merged = {**_profile_for_scoring(self.rider), **(profile or {})}
        base = max(0.0, min(1.0, float(self.base.score(spot, time_context, merged))))
        character = character_fit(merged, spot)
        utility = base * character
        self.scored[spot.id] = (spot, {
            "feasibility": 1.0 if utility > 0 else 0.0,
            "condition_fit": base,
            "character_fit": character,
            "confidence": 1.0,
            "reachability": 1.0,
            "anomaly": 0.0,
            "social": 0.5,
            "social_weight": 0.0,
            "utility": utility,
            "source": "search",
        })
        return utility

    def record_ranked(self, spot: Spot, score: float, rank_score: float) -> None:
        """Capture the distance-adjusted utility produced by search ranking."""
        existing = self.scored.get(spot.id)
        if existing is None:
            return
        components = dict(existing[1])
        components["reachability"] = (
            max(0.0, min(1.0, rank_score / score)) if score > 0 else 0.0
        )
        components["utility"] = max(0.0, min(1.0, rank_score))
        self.scored[spot.id] = (spot, components)

    def write_log(
        self,
        db: Session,
        *,
        app_user_id: uuid.UUID | None,
        now: datetime | None = None,
    ) -> None:
        if not self.scored:
            return
        instant = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        audience_fingerprint = _audience_fingerprint(self.rider)
        _write_log(
            db,
            [(spot, components, True) for spot, components in self.scored.values()],
            app_user_id=app_user_id,
            user_ref=(
                f"user:{app_user_id}" if app_user_id
                else f"anon:{audience_fingerprint}"
            ),
            surface="search",
            window_start=_window_start(
                RecommendationSurface.REGION, now=instant, month=None, weeks=None
            ),
            fingerprint=self.rider.band.fingerprint,
            audience_segment=(
                "anonymous" if app_user_id is None
                else "logged_profile" if self.rider.source == "user"
                else "logged_without_profile"
            ),
            params_version=_active_params_version(db, self.rider.sport),
        )


def recommendable_spot_ids(db: Session, spots: Sequence[Spot], sport: str) -> set[uuid.UUID]:
    """Batch-load evidence so search can put incomplete records last."""
    ids = [spot.id for spot in spots if sport in (spot.sports or []) and spot.facing is not None]
    if not ids:
        return set()
    profiles = db.scalars(
        select(SpotWeatherProfile)
        .where(
            SpotWeatherProfile.spot_id.in_(ids),
            SpotWeatherProfile.active.is_(True),
            SpotWeatherProfile.reviewed_at.is_not(None),
        )
        .options(selectinload(SpotWeatherProfile.sectors))
    ).all()
    return {
        profile.spot_id
        for profile in profiles
        if any(sector.enabled for sector in profile.sectors)
    }
