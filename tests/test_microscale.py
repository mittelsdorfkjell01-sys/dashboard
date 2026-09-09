"""WP5 microscale: IBL roughness transfer, WBM/DSM handling, and persistence override."""

from __future__ import annotations

import uuid

import pytest
from geoalchemy2 import WKTElement

from app.forecast.microscale import (
    CHARNOCK_SEA_Z0,
    RasterSurfaceProvider,
    SectorSurface,
    compute_microscale_sectors,
    destination_point,
    dtm_from_dsm,
    internal_boundary_layer_height,
    persist_microscale_sectors,
    resolve_surface_change,
    roughness_for_class,
    roughness_transfer_factor,
    surface_is_water,
)
from app.models import Region, Spot, SpotWeatherProfile, SpotWeatherSector
from app.weather.physics.manual import select_sector


# --- pure physics ----------------------------------------------------------


def test_roughness_for_class_maps_water_land_and_unknown():
    assert roughness_for_class(80) == CHARNOCK_SEA_Z0      # permanent_water
    assert roughness_for_class(50) == 1.0                   # built_up
    assert roughness_for_class(30) == 0.03                  # grassland
    assert roughness_for_class(999) == 0.03                 # unknown -> default


def test_wbm_nodata_counts_as_water():
    assert surface_is_water(0) is False                     # explicit land
    assert surface_is_water(1) is True                      # ocean
    assert surface_is_water(None) is True                   # missing sample
    assert surface_is_water(255, nodata=255) is True        # NoData ocean cell


def test_dtm_subtracts_canopy_only_on_vegetated_classes():
    assert dtm_from_dsm(40.0, 10) == pytest.approx(25.0)    # tree_cover -15 m
    assert dtm_from_dsm(40.0, 30) == pytest.approx(40.0)    # grassland unchanged
    assert dtm_from_dsm(2.0, 80) == pytest.approx(2.0)      # water unchanged


def test_ibl_height_grows_with_fetch_and_is_floored():
    assert internal_boundary_layer_height(0.0, 0.03) == 10.0
    near = internal_boundary_layer_height(500.0, 0.1)
    far = internal_boundary_layer_height(5000.0, 0.1)
    assert far > near >= 10.0


def test_roughness_transfer_limits_and_direction():
    assert roughness_transfer_factor(0.1, 0.1, 3000) == 1.0      # no change
    assert roughness_transfer_factor(0.0002, 0.1, 2000) == 1.0 or \
        roughness_transfer_factor(0.0002, 0.1, 0.0) == 1.0        # zero fetch neutral
    offshore = roughness_transfer_factor(0.10, 0.0002, 3000)      # land -> sea (smoother)
    onshore = roughness_transfer_factor(0.0002, 0.10, 3000)       # sea -> land (rougher)
    assert offshore > 1.0 and onshore < 1.0


def test_roughness_transfer_deviation_grows_with_fetch():
    short = roughness_transfer_factor(0.10, 0.0002, 300)
    long = roughness_transfer_factor(0.10, 0.0002, 8000)
    assert long > short > 1.0


# --- geodesic walk + surface change ----------------------------------------


def test_destination_point_moves_north_and_east():
    north_lat, north_lon = destination_point(45.0, 0.0, 0.0, 111195.0)  # ~1 deg north
    assert north_lat == pytest.approx(46.0, abs=0.01)
    assert north_lon == pytest.approx(0.0, abs=1e-6)
    east_lat, east_lon = destination_point(0.0, 0.0, 90.0, 111195.0)  # ~1 deg east at equator
    assert east_lon == pytest.approx(1.0, abs=0.01)
    assert east_lat == pytest.approx(0.0, abs=1e-6)


def test_resolve_surface_change_finds_first_transition():
    # Land spot; water appears at the 3rd upwind step (index 2) -> fetch 300 m.
    upwind = [(False, 0.1), (False, 0.1), (True, CHARNOCK_SEA_Z0), (True, CHARNOCK_SEA_Z0)]
    surface = resolve_surface_change(False, 0.1, upwind, step_m=100.0, max_fetch_m=2000.0)
    assert surface.upwind_is_water is True
    assert surface.upwind_z0 == CHARNOCK_SEA_Z0 and surface.downwind_z0 == 0.1
    assert surface.fetch_m == pytest.approx(300.0)


def test_resolve_surface_change_uniform_surface_is_neutral():
    upwind = [(False, 0.1)] * 5
    surface = resolve_surface_change(False, 0.1, upwind, step_m=100.0, max_fetch_m=500.0)
    assert surface.upwind_z0 == surface.downwind_z0 == 0.1  # -> IBL factor 1.0
    assert surface.fetch_m == pytest.approx(500.0)
    assert roughness_transfer_factor(surface.upwind_z0, surface.downwind_z0, surface.fetch_m) == 1.0


class _CounterRaster(RasterSurfaceProvider):
    """Fake IO: land until the Nth _is_water call, then water; land z0 = 0.1."""

    def __init__(self, water_from_call):
        super().__init__("wc", "wbm", step_m=100.0, max_fetch_m=2000.0)
        self._n = 0
        self._water_from = water_from_call

    def _is_water(self, lat, lon):
        self._n += 1
        return self._n >= self._water_from

    def _z0(self, lat, lon, is_water):
        return CHARNOCK_SEA_Z0 if is_water else 0.1


def test_provider_walk_finds_the_coastline_fetch():
    provider = _CounterRaster(water_from_call=6)  # local + 4 land steps, then water
    surface = provider.sector_surface(43.66, -1.44, 0)
    assert surface.upwind_is_water is True
    assert surface.downwind_z0 == 0.1 and surface.upwind_z0 == CHARNOCK_SEA_Z0
    assert surface.fetch_m == pytest.approx(500.0)  # 5th step


def test_unmounted_raster_provider_returns_none():
    assert RasterSurfaceProvider(None, None).mounted is False
    assert RasterSurfaceProvider(None, None).sector_surface(43.0, -1.4, 0) is None


# --- producer status paths -------------------------------------------------


class FakeSurface:
    def __init__(self, surfaces, *, mounted=True):
        self.mounted = mounted
        self._surfaces = surfaces

    def sector_surface(self, lat, lon, index):
        return self._surfaces.get(index)


def _all_offshore():
    surface = SectorSurface(upwind_z0=0.10, downwind_z0=CHARNOCK_SEA_Z0, fetch_m=3000, upwind_is_water=False)
    return FakeSurface({i: surface for i in range(12)})


def test_unmounted_provider_is_unavailable():
    result = compute_microscale_sectors(43.0, -1.4, surface_provider=FakeSurface({}, mounted=False))
    assert result.status == "microscale_unavailable" and result.sectors == []


def test_available_sectors_only_are_produced():
    surface = SectorSurface(0.10, CHARNOCK_SEA_Z0, 3000, False)
    provider = FakeSurface({2: surface, 5: surface})  # others None
    result = compute_microscale_sectors(43.0, -1.4, surface_provider=provider)
    assert result.status == "ok"
    assert {s.index for s in result.sectors} == {2, 5}
    assert all(s.speed_factor > 1.0 for s in result.sectors)  # offshore over water


# --- persistence overrides the GWA prior -----------------------------------


@pytest.fixture
def micro_spot(db):
    suffix = uuid.uuid4().hex[:8]
    region = Region(slug=f"ms-region-{suffix}", name=f"MS Region {suffix}",
                    normalized_name=f"ms region {suffix}", country="FR", status="published")
    db.add(region)
    db.flush()
    spot = Spot(slug=f"ms-spot-{suffix}", name=f"MS Spot {suffix}",
                normalized_name=f"ms spot {suffix}", region_id=region.id,
                location=WKTElement("POINT(-1.44 43.66)", srid=4326),
                sports=["wind"], water_type=["sea"], status="published")
    db.add(spot)
    db.commit()
    yield spot
    db.query(SpotWeatherSector).delete()
    profile = db.query(SpotWeatherProfile).filter_by(spot_id=spot.id).one_or_none()
    if profile:
        db.delete(profile)
    db.delete(spot)
    db.flush()
    db.delete(region)
    db.commit()


def test_microscale_overrides_gwa_with_higher_version(db, micro_spot):
    profile = SpotWeatherProfile(spot_id=micro_spot.id)
    db.add(profile)
    db.flush()
    # Existing GWA prior at version 1 for the sector around 270 deg.
    db.add(SpotWeatherSector(profile_id=profile.id, start_deg=240, end_deg=270, speed_factor=1.2,
                             version=1, enabled=True, note='{"method":"gwa_over_reference"}'))
    db.commit()

    result = compute_microscale_sectors(43.66, -1.44, surface_provider=_all_offshore(), grid_cell=[43.75, -1.5])
    outcome = persist_microscale_sectors(db, micro_spot.id, result)
    assert outcome["version"] == 2 and outcome["written"] == 12

    db.expire_all()
    rows = db.query(SpotWeatherSector).filter_by(profile_id=profile.id).all()
    chosen = select_sector(255.0, rows)  # in the 240-270 sector
    assert chosen.version == 2  # microscale wins over the GWA prior
    refreshed = db.get(SpotWeatherProfile, profile.id)
    assert refreshed.land_reference is not None and refreshed.water_reference is not None

    # Idempotent re-run.
    again = persist_microscale_sectors(db, micro_spot.id, compute_microscale_sectors(
        43.66, -1.44, surface_provider=_all_offshore(), grid_cell=[43.75, -1.5]))
    assert again["reason"] == "idempotent" and again["version"] == 2


def test_unavailable_microscale_never_touches_existing_sectors(db, micro_spot):
    profile = SpotWeatherProfile(spot_id=micro_spot.id)
    db.add(profile)
    db.flush()
    db.add(SpotWeatherSector(profile_id=profile.id, start_deg=0, end_deg=30, speed_factor=1.2,
                             version=1, enabled=True, note='{"method":"gwa_over_reference"}'))
    db.commit()
    result = compute_microscale_sectors(43.66, -1.44, surface_provider=FakeSurface({}, mounted=False))
    outcome = persist_microscale_sectors(db, micro_spot.id, result)
    assert outcome["written"] == 0 and outcome["reason"] == "no_write"
    assert db.query(SpotWeatherSector).filter_by(profile_id=profile.id).count() == 1
