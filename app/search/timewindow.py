"""Open-axis time logic: resolve a time window and rank candidates over it.

Ranking over a window is **coverage-first**: the share of the window's weeks in
which a candidate is good (``pct_usable_hours ≥ week_good_threshold``), with mean
``pct_usable`` as the **intensity** tie-breaker. This is deliberately *not* a plain
average — a spot that is reliably good across many weeks should beat one that is
spectacular in a single week.
"""

from __future__ import annotations

from datetime import date, timedelta
from statistics import mean
from typing import Any

from app.scoring.context import primary_sport, spot_editorial
from app.scoring.climatology import climatology_curve
from app.scoring.params import WEEK_GOOD_THRESHOLD, get_params

N_WEEKS = 52
MAX_CURRENT_DAYS = 7  # the live/forecast horizon (Sprint 3)

_SEASON_LENSES = {"season", "saison"}
_CURRENT_LENSES = {"current", "aktuell", "live"}


# --- week / month helpers --------------------------------------------------

def _week_midpoint_month(week: int) -> int:
    """Calendar month (1..12) of a week's midpoint, on a non-leap reference year."""
    doy = (week - 1) * 7 + 4  # ~Thursday of the week
    d = date(2001, 1, 1) + timedelta(days=min(doy, 365) - 1)
    return d.month


def months_to_weeks(months: list[int]) -> list[int]:
    wanted = set(months)
    return [w for w in range(1, N_WEEKS + 1) if _week_midpoint_month(w) in wanted]


def week_range_to_weeks(start: int, end: int) -> list[int]:
    """Inclusive week range, wrapping across the year boundary if ``start > end``."""
    if start <= end:
        return list(range(start, end + 1))
    return list(range(start, N_WEEKS + 1)) + list(range(1, end + 1))


def resolve_time_window(lens: str, range_input: dict | None) -> dict:
    """Normalise a time selection into a window.

    ``lens`` is ``season`` (weeks/months) or ``current`` (days ≤ 7). ``range_input``
    may be ``None`` / ``{"open": True}`` (the open axis → the whole season or full
    horizon), ``{"month": m}`` / ``{"months": [...]}``, ``{"weeks": [start, end]}``,
    or for the current lens ``{"days": n}`` / ``{"day_range": [a, b]}``.
    """
    lens_n = (lens or "season").lower()
    ri = range_input or {}
    is_open = not range_input or bool(ri.get("open"))

    if lens_n in _CURRENT_LENSES:
        if is_open:
            days = MAX_CURRENT_DAYS
        elif "days" in ri:
            days = max(1, min(int(ri["days"]), MAX_CURRENT_DAYS))
        elif "day_range" in ri:
            a, b = ri["day_range"]
            days = max(1, min(int(b) - int(a) + 1, MAX_CURRENT_DAYS))
        else:
            days = MAX_CURRENT_DAYS
        return {"lens": "current", "open": is_open, "days": days}

    # season lens
    if is_open:
        weeks = list(range(1, N_WEEKS + 1))
    elif "weeks" in ri:
        weeks = week_range_to_weeks(int(ri["weeks"][0]), int(ri["weeks"][1]))
    elif "months" in ri or "month" in ri:
        months = ri.get("months") or [ri["month"]]
        weeks = months_to_weeks([int(m) for m in months])
    else:
        weeks = list(range(1, N_WEEKS + 1))
        is_open = True
    return {"lens": "season", "open": is_open, "weeks": weeks}


def window_weeks(window: Any) -> list[int]:
    """Extract the list of week numbers from a window dict / list / None."""
    if window is None:
        return list(range(1, N_WEEKS + 1))
    if isinstance(window, dict):
        return window.get("weeks") or list(range(1, N_WEEKS + 1))
    return list(window)


# --- per-candidate weekly scores -------------------------------------------

def spot_week_scores(
    spot: Any,
    sport: str | None,
    profile: dict | None,
    params: dict | None = None,
    db: Any | None = None,
) -> list[float]:
    """A spot's ``pct_usable`` for every week (1..52), 0 where no climatology.

    ``sport=None`` uses the spot's primary (first-listed) sport. A ``db`` lets the
    sport params resolve from a deployed ``scoring_params`` row (else in-code).
    """
    sp = sport or primary_sport(spot)
    clim = getattr(spot, "climatology", None)
    if sp is None or not (isinstance(clim, dict) and clim.get("weeks")):
        return [0.0] * N_WEEKS
    params = params or get_params(sp, db)
    scores = [0.0] * N_WEEKS
    for w in climatology_curve(clim, spot_editorial(spot), profile, sp, params):
        wk = w.get("week")
        if wk and 1 <= wk <= N_WEEKS:
            scores[wk - 1] = w["pct_usable"]
    return scores


def coverage_intensity(
    scores: list[float], weeks: list[int], threshold: float
) -> tuple[float, float]:
    """``(coverage, intensity)`` of a weekly score series over ``weeks``."""
    vals = [scores[w - 1] for w in weeks if 1 <= w <= len(scores)]
    if not vals:
        return 0.0, 0.0
    coverage = sum(1 for v in vals if v >= threshold) / len(vals)
    return coverage, mean(vals)


def rank_by_timewindow(
    candidates: list[Any],
    window: Any,
    sport: str | None,
    profile: dict | None,
    *,
    params: dict | None = None,
    db: Any | None = None,
) -> list[dict]:
    """Rank spot candidates over a window by coverage, then intensity.

    Returns ``[{spot, coverage, intensity}]`` best-first.
    """
    weeks = window_weeks(window)
    ranked: list[dict] = []
    params_by_sport: dict[str, dict] = {}
    for spot in candidates:
        sp = sport or primary_sport(spot)
        if params is not None:
            p = params
        elif sp is not None:
            if sp not in params_by_sport:
                params_by_sport[sp] = get_params(sp, db)
            p = params_by_sport[sp]
        else:
            p = None
        thr = p["week_good_threshold"] if p else WEEK_GOOD_THRESHOLD
        scores = spot_week_scores(spot, sp, profile, p, db)
        cov, inten = coverage_intensity(scores, weeks, thr)
        ranked.append(
            {"spot": spot, "coverage": round(cov, 4), "intensity": round(inten, 4)}
        )
    ranked.sort(
        key=lambda r: (-r["coverage"], -r["intensity"], getattr(r["spot"], "name", ""))
    )
    return ranked


def best_weeks_for_area(
    spots: list[Any],
    sport: str | None,
    profile: dict | None,
    *,
    params: dict | None = None,
    db: Any | None = None,
    top: int | None = None,
) -> list[dict]:
    """Open *time*: rank the 52 weeks for a set of spots (the area).

    Each week's area score is the best spot's ``pct_usable`` (so a single spot
    reduces to its own season curve), with ``spots_working`` = how many spots are
    good that week. Returns weeks best-first.
    """
    curves = []
    thresholds = []
    params_by_sport: dict[str, dict] = {}
    for s in spots:
        sp = sport or primary_sport(s)
        if params is not None:
            p = params
        elif sp is not None:
            if sp not in params_by_sport:
                params_by_sport[sp] = get_params(sp, db)
            p = params_by_sport[sp]
        else:
            p = None
        curves.append(spot_week_scores(s, sp, profile, p, db))
        thresholds.append(p["week_good_threshold"] if p else WEEK_GOOD_THRESHOLD)

    weeks_out = []
    for w in range(1, N_WEEKS + 1):
        col = [c[w - 1] for c in curves]
        score = max(col) if col else 0.0
        working = sum(1 for c, thr in zip(curves, thresholds) if c[w - 1] >= thr)
        weeks_out.append(
            {"week": w, "score": round(score, 4), "spots_working": working}
        )
    weeks_out.sort(key=lambda x: (-x["score"], -x["spots_working"], x["week"]))
    return weeks_out[:top] if top else weeks_out
