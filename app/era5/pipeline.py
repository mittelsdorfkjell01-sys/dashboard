"""Assemble the per-week climatology and write it to a spot.

``derive_climatology`` is pure (series in, 52-week record out) so the whole
derivation is testable without a database. ``build_climatology_record`` and
``recompute_climatology`` are thin wrappers that read the raw file, call the
pure core, and persist to ``spots.climatology`` / advance the Era5Job.
"""

from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.era5 import rawfile, seriesutil
from app.era5.aggregate import aggregate_weekly_histogram, derive_display_stats
from app.era5.bins import N_WEEKS
from app.era5.grid import resolve_grid_cell
from app.era5.freshness import CLIMATOLOGY_YEARS, finalize_record
from app.era5.openmeteo import (
    ATTRIBUTION,
    LICENSE,
    SOURCE_WAVE,
    SOURCE_WIND,
)
from app.era5.smoothing import smooth_weeks
from app.era5.solar import filter_daylight
from app.models import Era5Job, Spot
from app.climatology.core import encode_hourly_samples


def _wave_window(series: dict) -> str | None:
    """Year range of the hours that actually carry wave data (waves have a
    shorter history than wind), or None when the series has no waves."""
    swh = series.get("swh")
    if swh is None:
        return None
    swh = np.asarray(swh, dtype=float)
    finite = np.isfinite(swh)
    if not finite.any():
        return None
    times = seriesutil.as_datetime64(series["time"])[finite]
    y0, y1 = str(times.min())[:4], str(times.max())[:4]
    return y0 if y0 == y1 else f"{y0}-{y1}"


# --- pure core -------------------------------------------------------------

def derive_climatology(
    series: dict, lat: float, lon: float, window: str, *, smooth_window: int = 3,
    timezone_name: str | None = None,
) -> dict:
    """Turn an hourly ``series`` into a 52-week climatology record.

    Night-time hours are dropped first; histograms and display statistics are
    then computed per week over the remaining daytime hours. The weekly curve is
    smoothed (rolling window, wrap-around) — the smoothed weeks are the score/
    display curve, the raw weeks are kept under ``weeks_raw``.
    """
    day_series, daylight_hours = filter_daylight(series, lat, lon)
    histograms = aggregate_weekly_histogram(day_series)

    times = seriesutil.as_datetime64(day_series["time"])
    weeks = seriesutil.week_index(times)

    week_records: list[dict] = []
    for w in range(N_WEEKS):
        wk = seriesutil.subset(day_series, weeks == w)
        stats = derive_display_stats(wk)
        joints = histograms[w + 1]
        week_records.append(
            {
                "week": w + 1,
                "daylight_hours": daylight_hours[w],
                "wind": {**stats["wind"], "joint": joints["wind_joint"]},
                "swell": {**stats["swell"], "joint": joints["swell_joint"]},
                "air_p50_c": stats["air_p50_c"],
                "sst_p50_c": stats["sst_p50_c"],
            }
        )

    smoothed = smooth_weeks(week_records, smooth_window)

    record = {
        "source": SOURCE_WIND,
        "license": LICENSE,
        "attribution": ATTRIBUTION,
        "window": window,
        "smoothing": {"method": "rolling_mean", "window_weeks": smooth_window, "wrap": True},
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "weeks": smoothed,
        "weeks_raw": week_records,
        # Compact daylight-hour archive for calendar-month thresholds, sessions
        # and per-year travel windows.  The public endpoint recomputes from this
        # payload; it never approximates those metrics from 52 pooled weeks.
        "hourly_calendar": encode_hourly_samples(series, lat, lon, timezone_name),
    }

    wave_window = _wave_window(series)
    if wave_window:
        record["wave_source"] = SOURCE_WAVE
        record["wave_window"] = wave_window
        record["wave_note"] = (
            "Wellen-Historie ist kürzer als die Wind-Historie "
            f"(nur {wave_window}); Wind = {window}."
        )

    return record


def climatology_weeks_equal(a: dict | None, b: dict | None) -> bool:
    """Compare two climatology records ignoring volatile metadata."""
    if not a or not b:
        return a == b
    return a.get("weeks") == b.get("weeks") and a.get("window") == b.get("window")


# --- DB helpers ------------------------------------------------------------

def _spot_lat_lon(spot: Spot) -> tuple[float, float]:
    from geoalchemy2.shape import to_shape

    point = to_shape(spot.location)
    return point.y, point.x  # (lat, lon)


def _latest_job_with_raw(db: Session, spot_id) -> Era5Job | None:
    return db.scalar(
        select(Era5Job)
        .where(Era5Job.spot_id == spot_id)
        .where(Era5Job.raw_path.is_not(None))
        .order_by(Era5Job.created_at.desc())
    )


def _window_from_job(job: Era5Job) -> str:
    if job.params and job.params.get("window"):
        return job.params["window"]
    return "unknown"


# --- public DB entry points ------------------------------------------------

def build_climatology_record(spot_id, *, db: Session) -> dict:
    """Derive the climatology from the job's raw file and persist it.

    Reads ``era5_jobs.raw_path``, writes ``spots.climatology`` (52 weeks), and
    advances the job to 'derived'. ``spots.overrides`` is never touched.
    """
    spot = db.get(Spot, spot_id)
    if spot is None:
        raise LookupError(f"unknown spot {spot_id}")
    job = _latest_job_with_raw(db, spot_id)
    if job is None:
        raise LookupError(f"no ERA5 raw extract for spot {spot_id}")

    try:
        lat, lon = _spot_lat_lon(spot)
        if not spot.era5_cell:
            spot.era5_cell = resolve_grid_cell(lat, lon)
        series = rawfile.read_raw(job.raw_path)
        record = derive_climatology(
            series, lat, lon, _window_from_job(job),
            smooth_window=get_settings().climatology_smooth_weeks,
            timezone_name=getattr(getattr(spot, "weather_profile", None), "timezone", None),
        )
        finalize_record(record, spot.era5_cell)

        spot.climatology = record
        job.status = "derived"
        job.completed_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(spot)
        return record
    except Exception as exc:
        db.rollback()
        job = db.get(Era5Job, job.id)
        if job is not None:
            job.status = "failed"
            job.error = f"derive failed: {exc}"
            db.commit()
        raise


def derive_and_store(
    spot: Spot,
    *,
    db: Session,
    client,
    years: int = CLIMATOLOGY_YEARS,
    job_id=None,
) -> dict:
    """Request-path climatology: fetch the hourly series *in memory* via the
    client seam and persist the derived 52-week record — with **no on-disk
    Parquet**.

    :func:`build_climatology_record` hands the series from fetch to derive through
    a Parquet raw file (pyarrow), which the serverless function deliberately does
    NOT bundle (see ``api/requirements.txt``). This variant keeps everything in
    memory so it can run on the request path — e.g. synchronously on go-live —
    where background workers don't run reliably and pyarrow is absent.
    """
    from app.era5.bins import VARS
    from app.era5.cds import (
        CDS_DATASET,
        build_cds_request,
        last_available_years,
        window_label,
    )

    lat, lon = _spot_lat_lon(spot)
    cell = spot.era5_cell or resolve_grid_cell(lat, lon)
    if not spot.era5_cell:
        spot.era5_cell = cell

    year_list = last_available_years(years)
    request = build_cds_request(cell, year_list, list(VARS))
    request_id = client.submit(CDS_DATASET, request)
    state = client.poll(request_id)
    if state != "completed":
        raise RuntimeError(f"extract not ready (state={state})")
    series = client.fetch_series(request_id)

    record = derive_climatology(
        series,
        lat,
        lon,
        window_label(year_list),
        smooth_window=get_settings().climatology_smooth_weeks,
        timezone_name=getattr(getattr(spot, "weather_profile", None), "timezone", None),
    )
    finalize_record(record, cell)
    spot.climatology = record

    # Advance (or create) the spot's job to 'derived' so the overview/status
    # strip reflects completion.
    now = datetime.now(timezone.utc)
    job = db.get(Era5Job, job_id) if job_id is not None else db.scalar(
        select(Era5Job)
        .where(Era5Job.spot_id == spot.id)
        .order_by(Era5Job.created_at.desc())
    )
    if job is None:
        job = Era5Job(
            spot_id=spot.id,
            cell=cell,
            params={"window": window_label(year_list)},
            status="derived",
            started_at=now,
        )
        db.add(job)
    else:
        job.status = "derived"
    job.error = None
    job.completed_at = now
    db.commit()
    db.refresh(spot)
    return record


def recompute_climatology(spot_id, *, db: Session) -> dict:
    """Re-derive the climatology from the stored raw file, without any CDS call.

    Produces the same record as :func:`build_climatology_record` (deterministic).
    ``spots.overrides`` is left untouched; if the freshly derived weeks differ
    from what is currently stored, a ``recompute.changed`` hint flag is set.
    """
    spot = db.get(Spot, spot_id)
    if spot is None:
        raise LookupError(f"unknown spot {spot_id}")
    job = _latest_job_with_raw(db, spot_id)
    if job is None:
        raise LookupError(f"no ERA5 raw extract for spot {spot_id}")

    lat, lon = _spot_lat_lon(spot)
    series = rawfile.read_raw(job.raw_path)
    record = derive_climatology(
        series, lat, lon, _window_from_job(job),
        timezone_name=getattr(getattr(spot, "weather_profile", None), "timezone", None),
    )
    cell = spot.era5_cell or resolve_grid_cell(lat, lon)
    if not spot.era5_cell:
        spot.era5_cell = cell
    finalize_record(record, cell)

    changed = not climatology_weeks_equal(spot.climatology, record)
    record["recompute"] = {
        "changed": changed,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }

    spot.climatology = record  # overrides column deliberately untouched
    db.commit()
    db.refresh(spot)
    return record
