"""CDS request construction, the client seam, and job submission/polling.

The pipeline talks to Copernicus through a small :class:`CdsClient` protocol so
the network can be mocked in tests. Three operations are enough:

* ``submit(dataset, request)``  -> opaque request id
* ``poll(request_id)``          -> "queued" | "running" | "completed" | "failed"
* ``fetch_series(request_id)``  -> normalised hourly series (dict of arrays)

The real adapter (:func:`real_cds_client`) wraps ``cdsapi`` and is imported
lazily, so tests that inject a fake client never need ``cdsapi`` installed.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.era5 import rawfile
from app.era5.bins import CDS_VARIABLE_NAMES, VARS
from app.models import Era5Job

CDS_DATASET = "reanalysis-era5-single-levels"


class CdsClient(Protocol):
    def submit(self, dataset: str, request: dict) -> str: ...

    def poll(self, request_id: str) -> str: ...

    def fetch_series(self, request_id: str) -> dict: ...


# --- request building ------------------------------------------------------

def last_full_years(n: int = 20, today: date | None = None) -> list[int]:
    """The ``n`` most recent *complete* calendar years, ascending."""
    today = today or datetime.now(timezone.utc).date()
    last_complete = today.year - 1
    return list(range(last_complete - n + 1, last_complete + 1))


def last_available_years(n: int = 20, today: date | None = None) -> list[int]:
    """Rolling window with a January grace period for provider ingestion.

    The previous calendar year is complete on January 1, but archive providers
    still need time to ingest and validate its final days.  We therefore roll
    the climatology window on February 1 instead of generating predictable
    failures at the turn of the year.
    """
    today = today or datetime.now(timezone.utc).date()
    last_available = today.year - (2 if today.month == 1 else 1)
    return list(range(last_available - n + 1, last_available + 1))


def window_label(years: list[int]) -> str:
    """``"2006-2025"`` for a contiguous list of years."""
    return f"{years[0]}-{years[-1]}"


def build_cds_request(cell: dict, years: list[int], variables: list[str]) -> dict:
    """Assemble the CDS ERA5 single-levels request payload.

    ``area`` is the (single) wind-cell centre as a degenerate box; CDS returns
    the nearest grid value for both the 0.25 deg atmospheric and 0.50 deg wave
    variables.
    """
    lat, lon = cell["wind"]
    return {
        "product_type": "reanalysis",
        "variable": [CDS_VARIABLE_NAMES[v] for v in variables],
        "year": [str(y) for y in years],
        "month": [f"{m:02d}" for m in range(1, 13)],
        "day": [f"{d:02d}" for d in range(1, 32)],
        "time": [f"{h:02d}:00" for h in range(24)],
        "area": [lat, lon, lat, lon],  # N, W, S, E
        "data_format": "netcdf",
        "download_format": "unarchived",
    }


# --- submission & polling --------------------------------------------------

def request_era5_extract(
    spot_id,
    cell: dict,
    *,
    db: Session,
    client: CdsClient,
    years: int = 20,
    variables: list[str] | None = None,
    today: date | None = None,
    force: bool = False,
    job_metadata: dict | None = None,
) -> Era5Job:
    """Submit a CDS extract for ``spot_id`` and record a 'queued' Era5Job.

    Idempotent per spot: if a non-failed job already exists it is returned
    unchanged rather than resubmitting (CDS extracts are expensive).
    """
    variables = list(variables) if variables is not None else list(VARS)

    if not force:
        existing = db.scalar(
            select(Era5Job)
            .where(Era5Job.spot_id == spot_id)
            .where(Era5Job.status.not_in(("failed", "superseded")))
            .order_by(Era5Job.created_at.desc())
        )
        if existing is not None:
            return existing

    year_list = last_available_years(years, today=today)
    request = build_cds_request(cell, year_list, variables)
    request_id = client.submit(CDS_DATASET, request)

    job = Era5Job(
        spot_id=spot_id,
        cell=cell,
        params={
            "cds_request_id": request_id,
            "dataset": CDS_DATASET,
            "variables": variables,
            "years": year_list,
            "window": window_label(year_list),
            "request": request,
            **(job_metadata or {}),
        },
        status="queued",
        started_at=datetime.now(timezone.utc),
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def _job_for_request(
    db: Session, cds_request_id: str, spot_id=None
) -> Era5Job | None:
    """Find the Era5Job for a request id, optionally scoped to one spot.

    ``spot_id`` matters because the Open-Meteo seam derives ``cds_request_id``
    from the *grid cell* (``omh|lat|lon|y0|y1``), so every spot sharing a 0.25°
    cell carries the SAME id. Polling one spot must resolve *its own* job — an
    unscoped lookup could return a cell-sibling's already-derived job and leave
    this spot without a raw extract (``build_climatology_record`` then raising
    ``LookupError: no ERA5 raw extract for spot``). Latest job first.
    """
    stmt = select(Era5Job).where(
        Era5Job.params["cds_request_id"].astext == cds_request_id
    )
    if spot_id is not None:
        stmt = stmt.where(Era5Job.spot_id == spot_id)
    return db.scalar(stmt.order_by(Era5Job.created_at.desc()))


def poll_cds_job(
    cds_request_id: str,
    *,
    db: Session,
    client: CdsClient,
    raw_dir: str | None = None,
    spot_id=None,
) -> Era5Job:
    """Poll CDS; on completion download the raw extract and advance the job.

    State transitions: still running -> 'queued' (unchanged); completed ->
    raw Parquet written, ``raw_path`` set, status 'extracting'; failed ->
    'failed' with an error message. Re-polling a job that already has a
    ``raw_path`` is a no-op.

    Pass ``spot_id`` to scope the job lookup to one spot — required when the
    ``cds_request_id`` is cell-based (Open-Meteo) and shared by cell-siblings.
    """
    job = _job_for_request(db, cds_request_id, spot_id=spot_id)
    if job is None:
        raise LookupError(f"no ERA5 job for cds_request_id={cds_request_id!r}")
    if job.raw_path:
        return job

    state = client.poll(cds_request_id)
    if state == "failed":
        job.status = "failed"
        job.error = f"CDS reported failure for request {cds_request_id}"
        db.commit()
        return job
    if state != "completed":
        return job  # still queued/running

    series = client.fetch_series(cds_request_id)
    raw_dir = raw_dir or get_settings().era5_raw_dir
    path = f"{raw_dir}/{job.spot_id or 'region'}_{uuid.uuid4().hex[:8]}.parquet"
    rawfile.write_raw(path, series)

    job.raw_path = path
    job.status = "extracting"
    db.commit()
    db.refresh(job)
    return job


# --- real adapter (lazy) ---------------------------------------------------

def real_cds_client():  # pragma: no cover - exercised only against live CDS
    """Build a :class:`CdsClient` backed by ``cdsapi`` + ``xarray``.

    Imported lazily; requires ``cdsapi`` (network) and ``xarray``/``netCDF4`` to
    parse the downloaded NetCDF. Tests use a fake client instead.
    """
    from app.era5._real_cds import RealCdsClient

    return RealCdsClient()
