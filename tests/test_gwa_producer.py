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


def test_reader_unmounted_reads_none(monkeypatch):
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "gwa_raster_dir", None)
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


def test_doctor_reports_unmounted(monkeypatch):
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "gwa_raster_dir", None)
    report = gwa_raster_doctor(None)
    assert report["ok"] is False and report["mounted"] is False


def test_doctor_refuses_non_ten_metre_height():
    report = gwa_raster_doctor("dir", height=100)
    assert report["ok"] is False
    assert any("10 m" in p for p in report["problems"])


def test_required_height_constant_is_ten():
    assert REQUIRED_HEIGHT_M == 10


# --- doctor: usable-set + empty-raster hardening ---------------------------


def _present(variable, path, **stats):
    base = {"path": path, "variable": variable, "exists": True, "crs": "EPSG:4326",
            "nodata": None, "valid_pixels": 300}
    return {**base, **stats}


def _patch_inspect(monkeypatch, by_variable):
    from app.forecast import gwa_producer as gp

    def fake_inspect(path, variable):
        make = by_variable.get(variable)
        return make(path) if make else {"path": path, "variable": variable, "exists": False}

    monkeypatch.setattr(gp, "_inspect_file", fake_inspect)
    return gp


def test_doctor_flags_a_lone_weibull_a_without_k(monkeypatch):
    gp = _patch_inspect(monkeypatch, {
        WEIBULL_A_VARIABLE: lambda p: _present(WEIBULL_A_VARIABLE, p, min=3.0, max=12.0, mean=7.0),
    })
    report = gp.gwa_raster_doctor("dir")
    assert report["ok"] is False
    assert any("usable GWA layer" in problem for problem in report["problems"])


def test_doctor_flags_an_empty_wind_speed_raster(monkeypatch):
    gp = _patch_inspect(monkeypatch, {
        WIND_SPEED_VARIABLE: lambda p: _present(WIND_SPEED_VARIABLE, p, valid_pixels=0,
                                                min=None, max=None, mean=None, nodata=-9999.0),
    })
    report = gp.gwa_raster_doctor("dir")
    assert report["ok"] is False
    assert any("empty raster" in problem for problem in report["problems"])


def test_doctor_accepts_a_usable_wind_speed_layer(monkeypatch):
    gp = _patch_inspect(monkeypatch, {
        WIND_SPEED_VARIABLE: lambda p: _present(WIND_SPEED_VARIABLE, p, min=2.0, max=12.0, mean=6.5),
    })
    report = gp.gwa_raster_doctor("dir")
    assert report["ok"] is True and report["problems"] == []


def test_doctor_accepts_the_weibull_fallback_when_both_present(monkeypatch):
    gp = _patch_inspect(monkeypatch, {
        WEIBULL_A_VARIABLE: lambda p: _present(WEIBULL_A_VARIABLE, p, min=3.0, max=12.0, mean=7.0),
        "combined-Weibull-k": lambda p: _present("combined-Weibull-k", p, min=1.2, max=3.0, mean=2.0),
    })
    report = gp.gwa_raster_doctor("dir")
    assert report["ok"] is True
