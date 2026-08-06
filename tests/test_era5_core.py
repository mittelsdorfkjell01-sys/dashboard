"""Pure-function tests for the ERA5 pipeline. No database, no network."""

from __future__ import annotations

import datetime as dt

import numpy as np
import pytest

from app.era5 import cds, rawfile, seriesutil
from app.era5.aggregate import aggregate_weekly_histogram, derive_display_stats
from app.era5.bins import MS_TO_KNOTS, N_MAG_BINS, N_SECTORS, N_WEEKS
from app.era5.components import compute_wind_components
from app.era5.grid import resolve_grid_cell
from app.era5.pipeline import climatology_weeks_equal, derive_climatology
from app.era5.solar import filter_daylight, solar_elevation_deg
from tests.era5_helpers import FakeCdsClient, make_synthetic_series

LAT, LON = 36.0128, -5.6035  # Tarifa


# --- grid ------------------------------------------------------------------

def test_resolve_grid_cell_snaps_to_two_grids():
    cell = resolve_grid_cell(36.0250, -5.6280)
    assert cell["wind"] == [36.0, -5.75]  # 0.25 deg grid
    assert cell["wave"] == [36.0, -5.5]   # 0.50 deg grid (coarser, differs)

    # a point that snaps differently on the two grids
    cell2 = resolve_grid_cell(36.13, -5.13)
    assert cell2["wind"] == [36.25, -5.25]
    assert cell2["wave"] == [36.0, -5.0]


def test_resolve_grid_cell_rejects_bad_lat():
    with pytest.raises(ValueError):
        resolve_grid_cell(120.0, 0.0)


# --- wind components -------------------------------------------------------

def test_wind_from_west_is_270_sector_12():
    # u>0 (blowing east), v=0  => wind comes FROM the west (270 deg).
    comp = compute_wind_components(3.0, 0.0)
    assert comp["dir_deg"] == pytest.approx(270.0)
    assert int(comp["sector"]) == 12
    assert float(comp["speed_kt"]) == pytest.approx(3.0 * MS_TO_KNOTS)


def test_wind_from_south_is_180_sector_8():
    # v>0 (blowing north) => wind comes FROM the south (180 deg).
    comp = compute_wind_components(0.0, 5.0)
    assert comp["dir_deg"] == pytest.approx(180.0)
    assert int(comp["sector"]) == 8


def test_wind_components_vectorised():
    u = np.array([0.0, 1.0, 0.0, -1.0])
    v = np.array([1.0, 0.0, -1.0, 0.0])
    comp = compute_wind_components(u, v)
    # from S, from W, from N, from E
    assert list(comp["sector"]) == [8, 12, 0, 4]


# --- daylight filter -------------------------------------------------------

def test_solar_elevation_noon_vs_midnight():
    # Summer-solstice local noon (~12 UTC at lon ~0) is high; midnight is below.
    noon = np.array(["2021-06-21T12:00:00"], dtype="datetime64[s]")
    midnight = np.array(["2021-06-21T00:00:00"], dtype="datetime64[s]")
    assert solar_elevation_deg(noon, LAT, 0.0)[0] > 50
    assert solar_elevation_deg(midnight, LAT, 0.0)[0] < 0


def test_filter_daylight_removes_night_and_counts_weeks():
    series = make_synthetic_series()
    total = seriesutil.n_hours(series)
    day_series, daylight_hours = filter_daylight(series, LAT, LON)

    kept = seriesutil.n_hours(day_series)
    assert 0 < kept < total                      # night hours were dropped
    assert len(daylight_hours) == N_WEEKS
    assert sum(daylight_hours) == kept           # per-week counts reconcile
    # every kept hour really is daytime
    assert np.all(solar_elevation_deg(day_series["time"], LAT, LON) > 0)


# --- histograms ------------------------------------------------------------

def test_weekly_histogram_shape_and_sums():
    series = make_synthetic_series()
    day_series, _ = filter_daylight(series, LAT, LON)
    hist = aggregate_weekly_histogram(day_series)

    assert len(hist) == N_WEEKS
    weeks = seriesutil.week_index(seriesutil.as_datetime64(day_series["time"]))
    for w in range(N_WEEKS):
        wind = np.array(hist[w + 1]["wind_joint"])
        swell = np.array(hist[w + 1]["swell_joint"])
        assert wind.shape == (N_SECTORS, N_MAG_BINS)
        assert swell.shape == (N_SECTORS, N_MAG_BINS)
        # wind cells sum to the daytime hours that week
        assert int(wind.sum()) == int((weeks == w).sum())
        # synthetic swell is always valid, so swell sums match too
        assert int(swell.sum()) == int((weeks == w).sum())


def test_swell_histogram_ignores_nan_samples():
    series = make_synthetic_series()
    series["swh"] = series["swh"].copy()
    series["swh"][:] = np.nan  # inland-style spot: no waves
    hist = aggregate_weekly_histogram(series)
    total = sum(int(np.array(hist[w]["swell_joint"]).sum()) for w in hist)
    assert total == 0


# --- display stats ---------------------------------------------------------

def test_display_stats_percentiles_monotonic_and_celsius():
    series = make_synthetic_series()
    stats = derive_display_stats(series)
    wind = stats["wind"]
    assert wind["p10_kt"] <= wind["p50_kt"] <= wind["p90_kt"]
    assert 0 <= wind["dir_dominant"] < N_SECTORS
    # Kelvin -> Celsius conversion lands in a sane range
    assert -5 < stats["air_p50_c"] < 40
    assert 0 < stats["sst_p50_c"] < 35
    assert 0.0 <= stats["swell"]["longperiod_frac"] <= 1.0


def test_display_stats_handles_empty_series():
    empty = {"time": np.array([], dtype="datetime64[s]")}
    for v in ("u10", "v10", "t2m", "sst", "swh", "mwp", "mwd"):
        empty[v] = np.array([], dtype=float)
    stats = derive_display_stats(empty)
    assert stats["hours"] == 0
    assert stats["wind"]["p50_kt"] is None
    assert stats["air_p50_c"] is None


# --- raw file round-trip ---------------------------------------------------

def test_rawfile_roundtrip(tmp_path):
    series = make_synthetic_series()
    path = str(tmp_path / "raw.parquet")
    rawfile.write_raw(path, series)
    loaded = rawfile.read_raw(path)

    assert np.array_equal(loaded["time"], series["time"])
    for var in ("u10", "v10", "t2m", "sst", "swh", "mwp", "mwd"):
        assert np.allclose(loaded[var], series[var], equal_nan=True)


# --- full climatology + recompute determinism ------------------------------

def test_derive_climatology_has_52_weeks_and_plausible_sums():
    series = make_synthetic_series()
    record = derive_climatology(series, LAT, LON, window="2006-2025")

    assert record["window"] == "2006-2025"
    assert len(record["weeks"]) == N_WEEKS
    # smoothed weeks keep the histogram shape (values are float averages now)
    assert np.array(record["weeks"][0]["wind"]["joint"]).shape == (N_SECTORS, N_MAG_BINS)
    assert record["smoothing"]["window_weeks"] == 3

    # The raw (unsmoothed) weeks carry the exact integer invariant:
    total_daylight = 0
    for wk in record["weeks_raw"]:
        wind = np.array(wk["wind"]["joint"])
        assert wind.shape == (N_SECTORS, N_MAG_BINS)
        # histogram total equals the week's daylight-hour count
        assert int(wind.sum()) == wk["daylight_hours"]
        total_daylight += wk["daylight_hours"]
    # daylight filter was effective: well under the 8760 hours of the year
    assert 0 < total_daylight < 8760


def test_recompute_from_rawfile_is_deterministic(tmp_path):
    series = make_synthetic_series()
    path = str(tmp_path / "raw.parquet")
    rawfile.write_raw(path, series)

    first = derive_climatology(series, LAT, LON, "2006-2025")
    # re-derive from the persisted raw file, exactly as recompute does (no CDS)
    reloaded = rawfile.read_raw(path)
    second = derive_climatology(reloaded, LAT, LON, "2006-2025")

    assert climatology_weeks_equal(first, second)
    assert first["weeks"] == second["weeks"]


# --- CDS request building (no network) -------------------------------------

def test_last_full_years_and_window_label():
    import datetime as dt

    years = cds.last_full_years(20, today=dt.date(2026, 6, 29))
    assert years[0] == 2006 and years[-1] == 2025
    assert len(years) == 20
    assert cds.window_label(years) == "2006-2025"


def test_last_available_years_uses_a_january_ingestion_grace_period():
    assert cds.last_available_years(20, today=dt.date(2026, 1, 31)) == list(
        range(2005, 2025)
    )
    assert cds.last_available_years(20, today=dt.date(2026, 2, 1)) == list(
        range(2006, 2026)
    )


def test_build_cds_request_contents():
    cell = resolve_grid_cell(LAT, LON)
    req = cds.build_cds_request(cell, [2024, 2025], ["u10", "v10", "t2m"])
    assert req["product_type"] == "reanalysis"
    assert "10m_u_component_of_wind" in req["variable"]
    assert req["year"] == ["2024", "2025"]
    assert len(req["time"]) == 24
    assert req["area"][0] == cell["wind"][0]


def test_fake_client_cycle_writes_rawfile(tmp_path):
    series = make_synthetic_series()
    client = FakeCdsClient(series)
    rid = client.submit(cds.CDS_DATASET, {"any": "request"})
    assert client.poll(rid) == "completed"
    fetched = client.fetch_series(rid)

    path = str(tmp_path / "out.parquet")
    rawfile.write_raw(path, fetched)
    assert rawfile.read_raw(path)["u10"].shape == series["u10"].shape
    assert client.submitted  # submission was recorded
