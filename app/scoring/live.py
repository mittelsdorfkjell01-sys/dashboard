"""Now-badge: evaluate the live conditions for a spot (via the Sprint 3 cache)."""

from __future__ import annotations

from datetime import datetime, timezone

from app.scoring.confidence import confidence_for
from app.scoring.context import primary_sport, spot_editorial
from app.scoring.evaluate import evaluate_conditions


def _is_daylight_now(lat: float, lon: float) -> bool:
    from app.era5.solar import solar_elevation_deg

    now = datetime.now(timezone.utc)
    return bool(solar_elevation_deg([now], lat, lon)[0] > 0.0)


def score_live(
    spot_id,
    profile: dict | None = None,
    sport: str | None = None,
    *,
    db,
    client=None,
    cache=None,
) -> dict:
    """Current-conditions badge for a spot.

    Pulls live values through :func:`app.live.service.get_live_conditions` (cached)
    and runs the *same* :func:`evaluate_conditions` used for climatology.
    """
    from geoalchemy2.shape import to_shape

    from app.live.service import get_live_conditions
    from app.models import Spot

    spot = db.get(Spot, spot_id)
    if spot is None:
        raise LookupError(f"unknown spot {spot_id}")
    sport = primary_sport(spot, sport)
    if sport is None:
        raise ValueError(f"spot {spot_id} has no sport to score")

    live = get_live_conditions(spot_id, db=db, client=client, cache=cache)
    cur = live.get("current", {})

    from app.tides.service import current_tide_level

    tide = current_tide_level(spot_id, db=db)

    point = to_shape(spot.location)
    daylight = _is_daylight_now(point.y, point.x)

    values = {
        "wind_kt": cur.get("wind"),
        "gust_kt": cur.get("gust"),
        "wind_dir": cur.get("dir"),
        "swell_m": cur.get("swell"),
        "period_s": cur.get("period"),
        "swell_dir": cur.get("swell_dir"),
        "air": cur.get("air"),
        "sst": cur.get("sst"),
        "tide": tide,
        "daylight": daylight,
    }
    # Resolve params with the db so a deployed scoring_params override drives the
    # now-badge too (same gates/thresholds as the seasonal path).
    from app.scoring.params import get_params

    params = get_params(sport, db)
    result = evaluate_conditions(values, spot_editorial(spot), profile, sport, params)
    return {
        "spot_id": spot.id,
        "sport": sport,
        "rating": result["rating"],
        "reasons": result["reasons"],
        "confidence": confidence_for(
            spot.climatology, spot.editorial, sport, numeric_confidence=spot.confidence
        ),
        "model": live.get("model"),
        "time": live.get("time"),
        "daylight": daylight,
        "current": cur,
    }
