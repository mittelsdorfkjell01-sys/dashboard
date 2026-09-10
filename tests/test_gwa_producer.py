"""WP3-A: omnidirectional GWA bias factor against the real combined layer."""

from __future__ import annotations

import math

import pytest

from app.forecast.gwa_producer import (
    FACTOR_HIGH,
    REQUIRED_HEIGHT_M,
    SECTOR_COUNT,
    WEIBULL_A_VARIABLE,
    WIND_SPEED_VARIABLE,
    MountedGwaRasterReader,
    compute_gwa_sectors,
    gwa_raster_doctor,
    weibull_mean,
)


class FakeReader:
    def __init__(self, mean_gwa, *, mounted=True):
        self.mounted = mounted
        self._mean_gwa = mean_gwa

    def read(self, lat, lon):
        return self._mean_gwa


class FakeReference:
    def __init__(self, mean_ref):
        self._mean_ref = mean_ref

    def mean_speed(self, lat, lon, window):
        return self._mean_ref


# --- pure factor -----------------------------------------------------------


def test_weibull_mean_matches_closed_form():
    assert weibull_mean(8.0, 1.0) == pytest.approx(8.0)
    assert weibull_mean(10.0, 2.0) == pytest.approx(10.0 * math.gamma(1.5))
    assert math.isnan(weibull_mean(0.0, 2.0))


def test_factor_is_gwa_over_reference_on_all_twelve_sectors():
    result = compute_gwa_sectors(0.0, 0.0, gwa_reader=FakeReader(8.0), reference=FakeReference(6.4))
    assert result.status == "ok" and result.enabled is True
    assert len(result.sectors) == SECTOR_COUNT
    assert all(s.speed_factor == pytest.approx(1.25) for s in result.sectors)   # one omni value
    assert all(s.direction_offset_deg == 0 and s.confidence == "ok" for s in result.sectors)
    assert result.provenance["variable"] == WIND_SPEED_VARIABLE and result.provenance["height"] == 10


def test_factor_saturates_at_hull_and_flags():
    result = compute_gwa_sectors(0.0, 0.0, gwa_reader=FakeReader(12.0), reference=FakeReference(6.0))
    assert all(s.speed_factor == pytest.approx(FACTOR_HIGH) and s.saturated for s in result.sectors)


def test_invalid_ratio_is_neutral_low_confidence():
    result = compute_gwa_sectors(0.0, 0.0, gwa_reader=FakeReader(8.0), reference=FakeReference(0.0))
    assert result.status == "ok"
    assert all(s.speed_factor == 1.0 and s.confidence == "low" for s in result.sectors)


def test_status_paths_are_neutral():
    not_mounted = compute_gwa_sectors(0.0, 0.0, gwa_reader=FakeReader(8.0, mounted=False), reference=FakeReference(6.4))
    assert not_mounted.status == "gwa_not_mounted" and not_mounted.enabled is False
    nodata = compute_gwa_sectors(0.0, 0.0, gwa_reader=FakeReader(None), reference=FakeReference(6.4))
    assert nodata.status == "gwa_nodata"
    no_ref = compute_gwa_sectors(0.0, 0.0, gwa_reader=FakeReader(8.0), reference=FakeReference(None))
    assert no_ref.status == "reference_unavailable"
    for result in (not_mounted, nodata, no_ref):
        assert all(s.speed_factor == 1.0 for s in result.sectors)


# --- reader: height enforcement + primary/fallback -------------------------


def test_reader_requires_ten_metre_height():
    MountedGwaRasterReader("dir", height=10)  # ok
    with pytest.raises(ValueError, match="10 m"):
        MountedGwaRasterReader("dir", height=100)


def test_reader_unmounted_reads_none():
    assert MountedGwaRasterReader(None).mounted is False


class _StubSampleReader(MountedGwaRasterReader):
    """Exercise read()'s primary/fallback logic without rasterio."""

    def __init__(self, *, wind_speed=None, a=None, k=None):
        super().__init__("dir", height=10)
        self._values = {WIND_SPEED_VARIABLE: wind_speed, WEIBULL_A_VARIABLE: a, "combined-Weibull-k": k}

    def _sample(self, path, lon, lat):
        for variable, value in self._values.items():
            if variable in path:
                return value
        return None


def test_reader_prefers_wind_speed_then_falls_back_to_weibull():
    assert _StubSampleReader(wind_speed=7.5).read(43.0, -1.4) == pytest.approx(7.5)
    fallback = _StubSampleReader(wind_speed=None, a=8.0, k=2.0).read(43.0, -1.4)
    assert fallback == pytest.approx(weibull_mean(8.0, 2.0))
    assert _StubSampleReader().read(43.0, -1.4) is None  # nothing available -> NoData


# --- doctor ----------------------------------------------------------------


def test_doctor_reports_unmounted():
    report = gwa_raster_doctor(None)
    assert report["ok"] is False and report["mounted"] is False


def test_doctor_refuses_non_ten_metre_height():
    report = gwa_raster_doctor("dir", height=100)
    assert report["ok"] is False
    assert any("10 m" in p for p in report["problems"])


def test_required_height_constant_is_ten():
    assert REQUIRED_HEIGHT_M == 10
