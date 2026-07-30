"""Region-level season aggregation.

``regions.season`` is a pre-computed 52-week aggregate. Crucially ``spots_working``
is a **count of running spots**, not an average — so a week where a single strong
spot fires still ranks, instead of being washed out by the region's quiet spots.
The environmental fields are medians across the region's spots.
"""

from __future__ import annotations

from statistics import median
from typing import Any

from app.scoring.context import primary_sport, spot_editorial
from app.scoring.climatology import _week_entry, climatology_curve
from app.scoring.params import WEEK_GOOD_THRESHOLD, get_params

N_WEEKS = 52


def _spot_curve_and_threshold(spot, sport, profile, db=None):
    sp = sport or primary_sport(spot)
    if sp is None:
        return [0.0] * N_WEEKS, 1.0
    params = get_params(sp, db)
    scores = [0.0] * N_WEEKS
    clim = getattr(spot, "climatology", None)
    if isinstance(clim, dict) and clim.get("weeks"):
        for w in climatology_curve(clim, spot_editorial(spot), profile, sp, params):
            wk = w.get("week")
            if wk and 1 <= wk <= N_WEEKS:
                scores[wk - 1] = w["pct_usable"]
    return scores, params["week_good_threshold"]


def _median_or_none(values: list[float]) -> float | None:
    vals = [v for v in values if isinstance(v, (int, float))]
    return round(median(vals), 2) if vals else None


def region_season_weeks(
    spots: list[Any], sport: str | None = None, profile: dict | None = None,
    db: Any | None = None,
) -> list[dict]:
    """Pure core: the 52-week aggregate for a region's spots."""
    curves_thresholds = [_spot_curve_and_threshold(s, sport, profile, db) for s in spots]

    weeks: list[dict] = []
    for w in range(1, N_WEEKS + 1):
        winds, ssts, airs = [], [], []
        for s in spots:
            entry = _week_entry(getattr(s, "climatology", None), w)
            if entry:
                winds.append(entry.get("wind", {}).get("p50_kt"))
                ssts.append(entry.get("sst_p50_c"))
                airs.append(entry.get("air_p50_c"))
        working = sum(
            1 for scores, thr in curves_thresholds if scores[w - 1] >= thr
        )
        weeks.append(
            {
                "week": w,
                "spots_working": working,
                "wind_p50": _median_or_none(winds),
                "sst_p50": _median_or_none(ssts),
                "air_p50": _median_or_none(airs),
            }
        )
    return weeks


def region_score_series(
    spots: list[Any], sport: str | None = None, profile: dict | None = None,
    db: Any | None = None,
) -> list[float]:
    """Per-week region score = the best spot's ``pct_usable`` (for ranking/curve)."""
    curves = [_spot_curve_and_threshold(s, sport, profile, db)[0] for s in spots]
    return [max((c[w - 1] for c in curves), default=0.0) for w in range(1, N_WEEKS + 1)]


def compute_best_months(
    spots: list[Any], *, db: Any | None = None
) -> list[int]:
    """Derive the region's best (wind-)months from its spots' climatology: a
    month counts when at least half of its weeks have ≥1 working spot (using the
    same per-sport ``week_good_threshold`` as the season aggregate). Returns
    sorted month numbers (1–12). Empty when no spot has climatology yet."""
    weeks = region_season_weeks(spots, db=db)
    good = [0] * 13
    total = [0] * 13
    for wk in weeks:
        month = min(12, (wk["week"] - 1) * 12 // N_WEEKS + 1)
        total[month] += 1
        if wk["spots_working"] > 0:
            good[month] += 1
    return [m for m in range(1, 13) if total[m] and good[m] / total[m] >= 0.5]


def smooth_circular(series: list[float], window: int = 5) -> list[float]:
    """Circular moving average (the season wraps Dec→Jan)."""
    n = len(series)
    if n == 0:
        return []
    half = window // 2
    out = []
    for i in range(n):
        vals = [series[(i + k) % n] for k in range(-half, half + 1)]
        out.append(round(sum(vals) / len(vals), 4))
    return out


# --- DB wrappers -----------------------------------------------------------

def _load_region_and_spots(db, region_id):
    from app.models import Region

    region = db.get(Region, region_id)
    if region is None:
        raise LookupError(f"unknown region {region_id}")
    return region, list(region.spots)


def aggregate_region_season(
    region_id, *, db, sport: str | None = None, profile: dict | None = None
) -> dict:
    """Compute and persist ``regions.season`` (52-week aggregate). Idempotent."""
    region, spots = _load_region_and_spots(db, region_id)
    weeks = region_season_weeks(spots, sport, profile, db)
    season = dict(region.season or {})  # preserve static keys (e.g. best_months)
    season["weeks"] = weeks
    season["aggregated_sport"] = sport
    region.season = season
    db.commit()
    db.refresh(region)
    return season


def region_when_to_go(
    region_id, *, db, sport: str | None = None, profile: dict | None = None,
    window: int = 5,
) -> dict:
    """Smoothed 52-week region curve (best-spot ``pct_usable``, circular-smoothed)."""
    region, spots = _load_region_and_spots(db, region_id)
    raw = region_score_series(spots, sport, profile, db)
    return {
        "region_id": str(region.id),
        "sport": sport,
        "curve": smooth_circular(raw, window),
        "raw": [round(v, 4) for v in raw],
    }


def aggregate_all_regions(db) -> int:
    """(Re)aggregate every region's season. Returns the count processed."""
    from sqlalchemy import select

    from app.models import Region

    regions = db.scalars(select(Region)).all()
    for region in regions:
        aggregate_region_season(region.id, db=db)
    return len(regions)


def _main() -> None:  # pragma: no cover - thin CLI
    """`python -m app.scoring.region` — aggregate every region's season."""
    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        n = aggregate_all_regions(db)
        print(f"Aggregated regions.season for {n} region(s).")
    finally:
        db.close()


if __name__ == "__main__":  # pragma: no cover
    _main()
