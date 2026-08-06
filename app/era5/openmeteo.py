"""Open-Meteo Historical adapter for the climatology pipeline.

Drop-in replacement for the CDS client behind the same ``submit/poll/fetch_series``
seam — only the *data source* changes, not the pipeline. Wind/temperature come
from the **Historical Weather API** (ERA5, archive-api), waves from the **Marine
API** (shorter history, ~2022+; see ``Konzept und Prompts/wellen_datenquelle_pruefung.md``).
Both are plain HTTP GET JSON, no auth, licence CC BY 4.0 — no ``cdsapi`` /
``~/.cdsapirc`` needed.

The seam is **stateless**: the ``request_id`` encodes lat/lon/window, so a fresh
client instance in a later request can complete a job an earlier one submitted
(mirrors ``_real_cds.py``, which uses the file path as the id). Fetched series are
cached as Parquet under ``ERA5_RAW_DIR`` keyed by cell+window, so re-running never
re-hits the network.
"""

from __future__ import annotations

import os

import numpy as np

from app.config import get_settings
from app.era5 import rawfile
from app.era5.cds import last_full_years

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
MARINE_URL = "https://marine-api.open-meteo.com/v1/marine"

# Open-Meteo's wave model has real values only from this year on (verified).
DEFAULT_WAVE_START_YEAR = 2022

SOURCE_WIND = "Open-Meteo ERA5 (Historical Weather API)"
SOURCE_WAVE = "Open-Meteo Marine (wave model)"
LICENSE = "CC BY 4.0"
ATTRIBUTION = "Open-Meteo.com"


def _default_http(url: str, params: dict) -> dict:
    """Real HTTP GET returning parsed JSON (httpx is already a dependency)."""
    import httpx

    resp = httpx.get(url, params=params, timeout=60.0)
    resp.raise_for_status()
    return resp.json()


def _arr(values) -> np.ndarray:
    """None -> NaN float array."""
    return np.array([np.nan if v is None else v for v in values], dtype="float64")


class OpenMeteoHistoryClient:
    """CdsClient-compatible client backed by Open-Meteo Historical APIs."""

    def __init__(
        self,
        *,
        years: int = 20,
        wave_start_year: int = DEFAULT_WAVE_START_YEAR,
        http=None,
        raw_dir: str | None = None,
        today=None,
    ) -> None:
        self._years = years
        self._wave_start_year = wave_start_year
        self._http = http or _default_http
        self._raw_dir = raw_dir or get_settings().era5_raw_dir
        self._today = today

    # --- seam ---------------------------------------------------------------

    def submit(self, dataset: str, request: dict) -> str:
        """Encode cell + window into a stateless request id.

        Reads the wind cell centre (``request['area'] = [lat, lon, lat, lon]``)
        and the year range that ``request_era5_extract`` already resolved.
        """
        area = request["area"]
        lat, lon = float(area[0]), float(area[1])
        years = [int(y) for y in request.get("year") or last_full_years(self._years, today=self._today)]
        return f"omh|{lat}|{lon}|{min(years)}|{max(years)}"

    def poll(self, request_id: str) -> str:
        # Synchronous source: a submitted request is immediately fetchable.
        return "completed" if request_id.startswith("omh|") else "failed"

    def fetch_series(self, request_id: str) -> dict:
        _, lat_s, lon_s, y0_s, y1_s = request_id.split("|")
        lat, lon, y0, y1 = float(lat_s), float(lon_s), int(y0_s), int(y1_s)

        cache = os.path.join(
            self._raw_dir, "omcache", f"omh_{lat}_{lon}_{y0}-{y1}.parquet"
        )
        # The Parquet cache is an optimisation only. On the serverless request
        # path pyarrow is not bundled and the filesystem is read-only, so a
        # read/write may raise (ImportError / OSError) — fall back to a fresh
        # in-memory fetch and skip caching rather than failing the whole compute.
        try:
            if os.path.exists(cache):
                return rawfile.read_raw(cache)
        except Exception:
            pass

        series = self._build_series(lat, lon, y0, y1)
        try:
            rawfile.write_raw(cache, series)
        except Exception:
            pass
        return series

    # --- fetching -----------------------------------------------------------

    def _build_series(self, lat: float, lon: float, y0: int, y1: int) -> dict:
        time, u10, v10, t2m = self._fetch_wind(lat, lon, y0, y1)

        series = {"time": time, "u10": u10, "v10": v10, "t2m": t2m}

        wy0 = max(y0, self._wave_start_year)
        if wy0 <= y1:
            wt, swh, mwp, mwd = self._fetch_wave(lat, lon, wy0, y1)
            # Align the (shorter) wave record onto the wind time axis by
            # timestamp; hours without wave data stay NaN and are dropped by the
            # existing isfinite filter in _swell_joint / derive_display_stats.
            n = len(time)
            full = {k: np.full(n, np.nan) for k in ("swh", "mwp", "mwd")}
            idx = np.searchsorted(time, wt)
            valid = (idx < n) & (time[np.clip(idx, 0, n - 1)] == wt)
            full["swh"][idx[valid]] = swh[valid]
            full["mwp"][idx[valid]] = mwp[valid]
            full["mwd"][idx[valid]] = mwd[valid]
            series.update(full)

        return series

    def _fetch_wind(self, lat, lon, y0, y1):
        h = self._get_range(
            ARCHIVE_URL,
            lat,
            lon,
            y0,
            y1,
            hourly="wind_speed_10m,wind_direction_10m,temperature_2m",
            wind_speed_unit="ms",
        )
        time = np.array(h["time"], dtype="datetime64[s]")
        speed = _arr(h["wind_speed_10m"])
        direction = np.radians(_arr(h["wind_direction_10m"]))
        # Meteorological "from" direction -> ERA5 u/v components (m/s).
        # compute_wind_components() inverts this exactly (atan2(-u,-v)).
        u10 = -speed * np.sin(direction)
        v10 = -speed * np.cos(direction)
        t2m = _arr(h["temperature_2m"]) + 273.15  # °C -> Kelvin
        return time, u10, v10, t2m

    def _fetch_wave(self, lat, lon, y0, y1):
        h = self._get_range(
            MARINE_URL,
            lat,
            lon,
            y0,
            y1,
            hourly="wave_height,wave_period,wave_direction",
        )
        return (
            np.array(h["time"], dtype="datetime64[s]"),
            _arr(h["wave_height"]),
            _arr(h["wave_period"]),
            _arr(h["wave_direction"]),
        )

    def _get_range(self, url, lat, lon, start_year, end_year, **extra) -> dict:
        params = {
            "latitude": lat,
            "longitude": lon,
            "start_date": f"{start_year}-01-01",
            "end_date": f"{end_year}-12-31",
            "timezone": "GMT",
            **extra,
        }
        payload = self._http(url, params)
        hourly = payload.get("hourly")
        if not hourly or "time" not in hourly:
            raise RuntimeError(
                f"Open-Meteo returned no hourly data for {url} "
                f"{start_year}-{end_year}: "
                f"{payload.get('reason') or payload}"
            )
        return hourly
