"""Open-Meteo Historical adapter tests — against recorded/synthetic responses,
never the live network. Verifies the seam, the m/s + direction -> u/v conversion,
the wave alignment, provenance, and the on-disk cache (no re-fetch)."""

from __future__ import annotations

import numpy as np
import pytest

from app.era5.components import compute_wind_components
from app.era5.openmeteo import ARCHIVE_URL, MARINE_URL, OpenMeteoHistoryClient
from app.era5.pipeline import derive_climatology


def _iso_hours(year: int) -> list[str]:
    t = np.arange(f"{year}-01-01", f"{year + 1}-01-01", dtype="datetime64[h]")
    return t.astype("datetime64[m]").astype(str).tolist()


def _archive(year: int) -> dict:
    times = _iso_hours(year)
    n = len(times)
    i = np.arange(n)
    speed = (6.0 + 3.0 * np.sin(2 * np.pi * (i % 24 - 15) / 24.0)).clip(0.2)  # m/s
    direction = (200.0 + 40.0 * np.sin(2 * np.pi * i / (365 * 24))) % 360.0
    temp_c = 15.0 + 8.0 * np.sin(2 * np.pi * (i / (365 * 24) - 0.2))
    return {"hourly": {
        "time": times,
        "wind_speed_10m": speed.round(2).tolist(),
        "wind_direction_10m": direction.round(0).tolist(),
        "temperature_2m": temp_c.round(1).tolist(),
    }}


def _marine(year: int) -> dict:
    times = _iso_hours(year)
    n = len(times)
    i = np.arange(n)
    return {"hourly": {
        "time": times,
        "wave_height": (1.2 + 0.6 * np.sin(2 * np.pi * i / (365 * 24))).round(2).tolist(),
        "wave_period": (8.0 + 2.0 * np.sin(2 * np.pi * i / (365 * 24))).round(1).tolist(),
        "wave_direction": ((290.0 + 20 * np.sin(2 * np.pi * i / (365 * 24))) % 360).round(0).tolist(),
    }}


class _FakeHttp:
    """Serves recorded archive/marine responses; counts calls (for cache tests)."""

    def __init__(self, waves: bool = True):
        self.calls: list[tuple[str, int, int]] = []
        self.waves = waves

    def __call__(self, url: str, params: dict) -> dict:
        y0 = int(params["start_date"][:4])
        y1 = int(params["end_date"][:4])
        self.calls.append((url, y0, y1))
        if url == ARCHIVE_URL:
            rows = [_archive(year)["hourly"] for year in range(y0, y1 + 1)]
        if url == MARINE_URL:
            if not self.waves:
                return {"hourly": {"time": [], "wave_height": []}}
            rows = [_marine(year)["hourly"] for year in range(y0, y1 + 1)]
        if url not in (ARCHIVE_URL, MARINE_URL):
            raise AssertionError(url)
        return {
            "hourly": {
                key: [value for row in rows for value in row[key]]
                for key in rows[0]
            }
        }


def _request(y0: int, y1: int) -> dict:
    return {"area": [36.0, -5.75, 36.0, -5.75], "year": [str(y) for y in range(y0, y1 + 1)]}


def _client(tmp_path, http, **kw) -> OpenMeteoHistoryClient:
    return OpenMeteoHistoryClient(http=http, raw_dir=str(tmp_path), **kw)


def test_seam_and_wind_conversion_roundtrips(tmp_path):
    http = _FakeHttp()
    c = _client(tmp_path, http, wave_start_year=2022)
    rid = c.submit("x", _request(2022, 2022))
    assert rid.startswith("omh|") and c.poll(rid) == "completed"

    series = c.fetch_series(rid)
    assert set(("time", "u10", "v10", "t2m")).issubset(series)
    assert len(series["time"]) == 8760

    # u/v recovered by the pipeline must match the direction we fed in.
    src = _archive(2022)["hourly"]
    comp = compute_wind_components(series["u10"], series["v10"])
    assert np.allclose(comp["speed_kt"] / 1.9438444924406046, src["wind_speed_10m"], atol=1e-2)
    dir_in = np.array(src["wind_direction_10m"]) % 360
    diff = np.abs((comp["dir_deg"] - dir_in + 180) % 360 - 180)
    assert diff.max() < 0.5  # direction preserved
    # temperatures converted to Kelvin
    assert np.isfinite(series["t2m"]).all() and series["t2m"].mean() > 250


def test_full_derivation_wind_and_wave_provenance(tmp_path):
    c = _client(tmp_path, _FakeHttp(), wave_start_year=2022)
    series = c.fetch_series(c.submit("x", _request(2022, 2023)))
    record = derive_climatology(series, 36.0, -5.75, "2022-2023")

    assert record["source"].startswith("Open-Meteo")
    assert record["license"] == "CC BY 4.0"
    assert len(record["weeks"]) == 52
    # waves present -> shallow-history provenance is recorded
    assert record["wave_source"].startswith("Open-Meteo")
    assert record["wave_window"]


def test_wave_history_shorter_than_wind(tmp_path):
    # wind 2020-2023, waves only from 2022 -> swell finite only in the tail.
    c = _client(tmp_path, _FakeHttp(), wave_start_year=2022)
    series = c.fetch_series(c.submit("x", _request(2020, 2023)))
    finite = np.isfinite(series["swh"])
    years = series["time"][finite].astype("datetime64[Y]").astype(int) + 1970
    assert years.min() == 2022 and years.max() == 2023
    assert not finite[:8760].any()  # 2020 has no wave data


def test_multi_year_windows_use_one_request_per_source(tmp_path):
    http = _FakeHttp()
    c = _client(tmp_path, http, wave_start_year=2022)
    c.fetch_series(c.submit("x", _request(2020, 2023)))
    assert http.calls == [
        (ARCHIVE_URL, 2020, 2023),
        (MARINE_URL, 2022, 2023),
    ]


def test_incomplete_wind_window_is_rejected(tmp_path):
    class _IncompleteHttp(_FakeHttp):
        def __call__(self, url: str, params: dict) -> dict:
            payload = super().__call__(url, params)
            if url == ARCHIVE_URL:
                for values in payload["hourly"].values():
                    values.pop()
            return payload

    c = _client(tmp_path, _IncompleteHttp(), wave_start_year=2022)
    with pytest.raises(RuntimeError, match="not complete"):
        c.fetch_series(c.submit("x", _request(2022, 2022)))


def test_cache_prevents_refetch(tmp_path):
    http = _FakeHttp()
    c = _client(tmp_path, http, wave_start_year=2022)
    rid = c.submit("x", _request(2022, 2022))
    c.fetch_series(rid)
    n_after_first = len(http.calls)
    assert n_after_first > 0
    # second client instance, same cache dir -> served from Parquet, no HTTP
    c2 = _client(tmp_path, http, wave_start_year=2022)
    c2.fetch_series(rid)
    assert len(http.calls) == n_after_first
