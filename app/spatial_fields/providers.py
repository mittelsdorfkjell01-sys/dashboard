"""Free official provider adapters for weather-field run discovery and ingestion."""

from __future__ import annotations

import bz2
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import gc
from pathlib import Path
import tempfile
import time
from typing import Protocol
from urllib.parse import urlencode

import httpx
import numpy as np

from app.forecast.providers import DwdIconProvider, InvalidModelData, ProviderUnavailable
from app.spatial_fields.phase0 import RegularGrid, assert_same_grid, decode_regular_latlon


EUROPE_COVERAGE = (-23.5, 29.5, 45.0, 70.5)  # west, south, east, north
ICON_D2_COVERAGE = (-3.5, 43.0, 20.5, 58.0)
GLOBAL_COVERAGE = (-180.0, -85.0, 180.0, 85.0)
EWAM_COVERAGE = (-10.5, 30.0, 42.0, 66.0)
GWAM_COVERAGE = (-180.0, -85.0, 180.0, 85.0)
GFS_WAVE_COVERAGE = (-180.0, -85.0, 180.0, 85.0)

SCALAR_SOURCE_VARIABLES = {
    "temperature_2m": "t_2m",
    "precipitation": "tot_prec",
    "pressure_msl": "pmsl",
    "cloud_cover": "clct",
}


@dataclass(frozen=True)
class FieldSourceSlice:
    forecast_hour: int
    valid_time: datetime
    u: RegularGrid
    v: RegularGrid
    gust: RegularGrid | None
    source_urls: tuple[str, ...]
    downloaded_bytes: int
    scalar_fields: dict[str, RegularGrid] = field(default_factory=dict)
    product: str = "wind"
    vector_u_name: str = "wind_u"
    vector_v_name: str = "wind_v"
    magnitude_name: str = "wind_gust"


def _grid_with_values(grid: RegularGrid, values: np.ndarray) -> RegularGrid:
    return RegularGrid(grid.longitudes, grid.latitudes, values, grid.definition)


def _normalize_scalar(name: str, grid: RegularGrid) -> RegularGrid:
    values = np.asarray(grid.values, dtype=np.float64)
    if name == "temperature_2m":
        values = values - 273.15
    elif name == "pressure_msl":
        values = values / 100.0
    elif name in {"precipitation", "cloud_cover"}:
        values = np.maximum(values, 0.0)
    return _grid_with_values(grid, values)


def _normalize_wave_field(name: str, grid: RegularGrid) -> RegularGrid:
    values = np.asarray(grid.values, dtype=np.float64)
    if name.endswith("_direction"):
        values = np.mod(values, 360.0)
    elif name.endswith("_height") or name.endswith("_period"):
        values = np.maximum(values, 0.0)
    return _grid_with_values(grid, values)


_D2_REMAP_CACHE: dict[str, tuple[np.ndarray, np.ndarray, np.ndarray, dict]] = {}


def decode_dwd_field(
    data: bytes,
    *,
    coverage: tuple[float, float, float, float],
    resolution_degrees: float = 0.05,
    source_coordinates: tuple[np.ndarray, np.ndarray] | None = None,
) -> RegularGrid:
    """Decode regular DWD grids or deterministically remap ICON-D2 nodes."""
    try:
        from eccodes import (
            codes_get,
            codes_get_array,
            codes_new_from_message,
            codes_release,
        )
    except ImportError as exc:  # pragma: no cover - deployment dependency
        raise ProviderUnavailable("ecCodes runtime is not installed") from exc

    handle = codes_new_from_message(data)
    try:
        grid_type = str(codes_get(handle, "gridType"))
        if grid_type == "regular_ll":
            return decode_regular_latlon(data)
        if grid_type != "unstructured_grid":
            raise InvalidModelData(f"unsupported DWD grid type: {grid_type}")
        if source_coordinates is None:
            try:
                source_latitudes = np.asarray(codes_get_array(handle, "latitudes"), dtype=np.float64)
                source_longitudes = np.asarray(codes_get_array(handle, "longitudes"), dtype=np.float64)
            except Exception as exc:
                raise InvalidModelData(
                    "unstructured DWD field requires CLAT/CLON coordinates"
                ) from exc
        else:
            source_latitudes, source_longitudes = source_coordinates
        source_values = np.asarray(codes_get_array(handle, "values"), dtype=np.float64)
        try:
            missing_value = float(codes_get(handle, "missingValue"))
            source_values[np.isclose(source_values, missing_value)] = np.nan
        except Exception:
            pass
    finally:
        codes_release(handle)

    coordinate_digest = __import__("hashlib").sha256(
        source_latitudes.tobytes() + source_longitudes.tobytes()
    ).hexdigest()
    cached = _D2_REMAP_CACHE.get(coordinate_digest)
    if cached is None:
        try:
            from scipy.spatial import cKDTree
        except ImportError as exc:  # pragma: no cover - deployment dependency
            raise ProviderUnavailable("ICON-D2 remapping requires scipy") from exc
        west, south, east, north = coverage
        longitudes = np.arange(west, east + resolution_degrees / 2, resolution_degrees)
        latitudes = np.arange(south, north + resolution_degrees / 2, resolution_degrees)
        source_lat_radians = np.radians(source_latitudes)
        source_lon_radians = np.radians(source_longitudes)
        source_points = np.column_stack(
            (
                np.cos(source_lat_radians) * np.cos(source_lon_radians),
                np.cos(source_lat_radians) * np.sin(source_lon_radians),
                np.sin(source_lat_radians),
            )
        )
        target_lon, target_lat = np.meshgrid(longitudes, latitudes)
        target_lat_radians = np.radians(target_lat.ravel())
        target_lon_radians = np.radians(target_lon.ravel())
        target_points = np.column_stack(
            (
                np.cos(target_lat_radians) * np.cos(target_lon_radians),
                np.cos(target_lat_radians) * np.sin(target_lon_radians),
                np.sin(target_lat_radians),
            )
        )
        _distance, nearest = cKDTree(source_points).query(target_points, workers=-1)
        definition = {
            "gridType": "regular_ll",
            "Ni": int(longitudes.size),
            "Nj": int(latitudes.size),
            "latitudeOfFirstGridPointInDegrees": float(latitudes[0]),
            "longitudeOfFirstGridPointInDegrees": float(longitudes[0]),
            "latitudeOfLastGridPointInDegrees": float(latitudes[-1]),
            "longitudeOfLastGridPointInDegrees": float(longitudes[-1]),
            "iDirectionIncrementInDegrees": resolution_degrees,
            "jDirectionIncrementInDegrees": resolution_degrees,
            "iScansNegatively": 0,
            "jScansPositively": 1,
            "jPointsAreConsecutive": 0,
            "sourceGridType": "unstructured_grid",
            "remapping": "nearest_spherical_ckdtree",
        }
        cached = (longitudes, latitudes, nearest.astype(np.int64), definition)
        _D2_REMAP_CACHE[coordinate_digest] = cached
    longitudes, latitudes, nearest, definition = cached
    return RegularGrid(
        longitudes,
        latitudes,
        source_values[nearest].reshape(latitudes.size, longitudes.size),
        definition,
    )


class WeatherFieldProvider(Protocol):
    provider_key: str
    model_key: str
    coverage: tuple[float, float, float, float]

    def discover_latest(
        self, now: datetime, *, forecast_hours: list[int] | None = None
    ) -> datetime | None: ...

    def fetch(self, run_at: datetime, forecast_hour: int) -> FieldSourceSlice: ...


class IconEuFieldProvider:
    provider_key = "dwd"
    model_key = "icon-eu"
    coverage = EUROPE_COVERAGE
    cadence_hours = 6

    def __init__(
        self,
        *,
        client: httpx.Client | None = None,
        timeout: float = 45,
        max_source_bytes: int = 16_777_216,
    ):
        self.client = client or httpx.Client()
        self.timeout = timeout
        self.max_source_bytes = max_source_bytes
        self._source_coordinates: tuple[np.ndarray, np.ndarray] | None = None

    @staticmethod
    def _unstructured_values(data: bytes) -> np.ndarray:
        try:
            from eccodes import codes_get_array, codes_new_from_message, codes_release
        except ImportError as exc:  # pragma: no cover - deployment dependency
            raise ProviderUnavailable("ecCodes runtime is not installed") from exc
        handle = codes_new_from_message(data)
        try:
            return np.asarray(codes_get_array(handle, "values"), dtype=np.float64)
        finally:
            codes_release(handle)

    def _coordinates(self, run_at: datetime) -> tuple[tuple[np.ndarray, np.ndarray] | None, list[str], int]:
        if self.model_key != "icon-d2":
            return None, [], 0
        if self._source_coordinates is not None:
            return self._source_coordinates, [], 0
        base = f"https://opendata.dwd.de/weather/nwp/icon-d2/grib/{run_at:%H}"
        urls = [
            f"{base}/{name}/icon-d2_germany_icosahedral_time-invariant_"
            f"{run_at:%Y%m%d%H}_000_0_{name}.grib2.bz2"
            for name in ("clat", "clon")
        ]
        payloads = [self._download(url) for url in urls]
        latitudes, longitudes = (self._unstructured_values(payload) for payload, _size in payloads)
        if np.nanmax(np.abs(latitudes)) <= np.pi + 0.01:
            latitudes = np.degrees(latitudes)
        if np.nanmax(np.abs(longitudes)) <= 2 * np.pi + 0.01:
            longitudes = np.degrees(longitudes)
        longitudes = ((longitudes + 180.0) % 360.0) - 180.0
        self._source_coordinates = (latitudes, longitudes)
        return self._source_coordinates, urls, sum(size for _payload, size in payloads)

    def _available(self, run_at: datetime, forecast_hours: list[int]) -> bool:
        probes = sorted({0, max(forecast_hours, default=0)})
        for forecast_hour in probes:
            for variable in (
                "u_10m",
                "v_10m",
                "vmax_10m",
                *SCALAR_SOURCE_VARIABLES.values(),
            ):
                try:
                    response = self.client.head(
                        DwdIconProvider.file_url(
                            self.model_key, run_at, variable, forecast_hour
                        ),
                        timeout=self.timeout,
                        follow_redirects=True,
                    )
                except httpx.HTTPError:
                    return False
                if response.status_code != 200:
                    return False
        return True

    def discover_latest(
        self, now: datetime, *, forecast_hours: list[int] | None = None
    ) -> datetime | None:
        candidate = now.astimezone(timezone.utc).replace(
            minute=0, second=0, microsecond=0
        )
        candidate = candidate.replace(
            hour=(candidate.hour // self.cadence_hours) * self.cadence_hours
        )
        for offset in range(0, 31, self.cadence_hours):
            run_at = candidate - timedelta(hours=offset)
            if self._available(run_at, forecast_hours or [0]):
                return run_at
        return None

    def _download(self, url: str) -> tuple[bytes, int]:
        try:
            with self.client.stream(
                "GET",
                url,
                timeout=self.timeout,
                follow_redirects=True,
                headers={"User-Agent": "surfwinddata/1.0"},
            ) as response:
                response.raise_for_status()
                compressed = bytearray()
                for chunk in response.iter_bytes():
                    compressed.extend(chunk)
                    if len(compressed) > self.max_source_bytes:
                        raise InvalidModelData(
                            f"{self.model_key.upper()} source exceeds byte budget"
                        )
            return bz2.decompress(bytes(compressed)), len(compressed)
        except (httpx.HTTPError, OSError) as exc:
            raise ProviderUnavailable(
                f"DWD {self.model_key.upper()} field unavailable"
            ) from exc

    def fetch(self, run_at: datetime, forecast_hour: int) -> FieldSourceSlice:
        grids: dict[str, RegularGrid] = {}
        urls: list[str] = []
        downloaded = 0
        source_coordinates, coordinate_urls, coordinate_bytes = self._coordinates(run_at)
        urls.extend(coordinate_urls)
        downloaded += coordinate_bytes
        for name, variable in (
            ("u", "u_10m"),
            ("v", "v_10m"),
            ("gust", "vmax_10m"),
            *SCALAR_SOURCE_VARIABLES.items(),
        ):
            url = DwdIconProvider.file_url(
                self.model_key, run_at, variable, forecast_hour
            )
            raw, size = self._download(url)
            grids[name] = decode_dwd_field(
                raw,
                coverage=self.coverage,
                source_coordinates=source_coordinates,
            )
            urls.append(url)
            downloaded += size
        assert_same_grid(grids["u"], grids["v"])
        assert_same_grid(grids["u"], grids["gust"])
        for name in SCALAR_SOURCE_VARIABLES:
            assert_same_grid(grids["u"], grids[name])
        return FieldSourceSlice(
            forecast_hour=forecast_hour,
            valid_time=run_at + timedelta(hours=forecast_hour),
            u=grids["u"],
            v=grids["v"],
            gust=grids["gust"],
            source_urls=tuple(urls),
            downloaded_bytes=downloaded,
            scalar_fields={
                name: _normalize_scalar(name, grids[name])
                for name in SCALAR_SOURCE_VARIABLES
            },
        )


class IconD2FieldProvider(IconEuFieldProvider):
    model_key = "icon-d2"
    coverage = ICON_D2_COVERAGE
    cadence_hours = 3


class DwdWaveFieldProvider:
    """DWD open-data EWAM/GWAM adapter with no credential dependency."""

    provider_key = "dwd"
    cadence_hours = 12
    source_variables = {
        "total_wave_height": "swh",
        "total_wave_direction": "mwd",
        "total_wave_period": "tm10",
        "wind_sea_height": "shww",
        "wind_sea_direction": "mdww",
        "wind_sea_period": "mpww",
        "primary_swell_height": "shts",
        "primary_swell_direction": "mdts",
        "primary_swell_period": "mpts",
    }

    def __init__(
        self,
        model_key: str,
        *,
        client: httpx.Client | None = None,
        timeout: float = 45,
        max_source_bytes: int = 67_108_864,
    ):
        if model_key not in {"dwd-ewam", "dwd-gwam"}:
            raise ValueError(f"unsupported DWD wave model: {model_key}")
        self.model_key = model_key
        self.dwd_model = model_key.removeprefix("dwd-")
        self.coverage = EWAM_COVERAGE if model_key == "dwd-ewam" else GWAM_COVERAGE
        self.client = client or httpx.Client()
        self.timeout = timeout
        self.max_source_bytes = max_source_bytes

    def file_url(self, run_at: datetime, variable: str, forecast_hour: int) -> str:
        model = self.dwd_model
        return (
            "https://opendata.dwd.de/weather/maritime/wave_models/"
            f"{model}/grib/{run_at:%H}/{variable}/"
            f"{model.upper()}_{variable.upper()}_{run_at:%Y%m%d%H}_{forecast_hour:03d}.grib2.bz2"
        )

    def _available(self, run_at: datetime, forecast_hours: list[int]) -> bool:
        for forecast_hour in sorted({0, max(forecast_hours, default=0)}):
            try:
                response = self.client.head(
                    self.file_url(run_at, "swh", forecast_hour),
                    timeout=self.timeout,
                    follow_redirects=True,
                )
            except httpx.HTTPError:
                return False
            if response.status_code != 200:
                return False
        return True

    def discover_latest(
        self, now: datetime, *, forecast_hours: list[int] | None = None
    ) -> datetime | None:
        candidate = now.astimezone(timezone.utc).replace(
            minute=0, second=0, microsecond=0
        )
        candidate = candidate.replace(hour=(candidate.hour // 12) * 12)
        for offset in range(0, 49, 12):
            run_at = candidate - timedelta(hours=offset)
            if self._available(run_at, forecast_hours or [0]):
                return run_at
        return None

    def _download(self, url: str) -> tuple[bytes, int]:
        try:
            with self.client.stream(
                "GET",
                url,
                timeout=self.timeout,
                follow_redirects=True,
                headers={"User-Agent": "surfwinddata/1.0"},
            ) as response:
                response.raise_for_status()
                compressed = bytearray()
                for chunk in response.iter_bytes():
                    compressed.extend(chunk)
                    if len(compressed) > self.max_source_bytes:
                        raise InvalidModelData(
                            f"{self.model_key.upper()} source exceeds byte budget"
                        )
            return bz2.decompress(bytes(compressed)), len(compressed)
        except (httpx.HTTPError, OSError) as exc:
            raise ProviderUnavailable(
                f"DWD {self.model_key.upper()} field unavailable"
            ) from exc

    def fetch(self, run_at: datetime, forecast_hour: int) -> FieldSourceSlice:
        grids: dict[str, RegularGrid] = {}
        urls: list[str] = []
        downloaded = 0
        for name, variable in self.source_variables.items():
            url = self.file_url(run_at, variable, forecast_hour)
            raw, size = self._download(url)
            grids[name] = _normalize_wave_field(
                name, decode_dwd_field(raw, coverage=self.coverage)
            )
            urls.append(url)
            downloaded += size
        reference = grids["total_wave_height"]
        for grid in grids.values():
            assert_same_grid(reference, grid)

        # DWD directions use the meteorological "from" convention. Encoding the
        # height as a vector preserves circular direction interpolation in tiles.
        direction = np.radians(grids["total_wave_direction"].values)
        height = grids["total_wave_height"].values
        wave_u = _grid_with_values(reference, -height * np.sin(direction))
        wave_v = _grid_with_values(reference, -height * np.cos(direction))
        return FieldSourceSlice(
            forecast_hour=forecast_hour,
            valid_time=run_at + timedelta(hours=forecast_hour),
            u=wave_u,
            v=wave_v,
            gust=None,
            source_urls=tuple(urls),
            downloaded_bytes=downloaded,
            scalar_fields=grids,
            product="wave",
            vector_u_name="wave_u",
            vector_v_name="wave_v",
            magnitude_name="total_wave_height",
        )


def decode_gfs_wave_fields(data: bytes) -> dict[str, RegularGrid]:
    """Decode the bounded NOAA GFS-Wave subset used by the ten-day tail."""
    try:
        from eccodes import (
            codes_get,
            codes_get_message,
            codes_grib_new_from_file,
            codes_release,
        )
    except ImportError as exc:  # pragma: no cover - deployment dependency
        raise ProviderUnavailable("ecCodes runtime is not installed") from exc

    roles = {
        "swh": "total_wave_height",
        "perpw": "total_wave_period",
        "dirpw": "total_wave_direction",
        "shww": "wind_sea_height",
        "mpww": "wind_sea_period",
        "wvdir": "wind_sea_direction",
        "shts": "primary_swell_height",
        "mpts": "primary_swell_period",
        "swdir": "primary_swell_direction",
    }
    fields: dict[str, RegularGrid] = {}
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".grib2", delete=False) as temporary:
            temporary.write(data)
            temporary_path = Path(temporary.name)
        with temporary_path.open("rb") as stream:
            while (handle := codes_grib_new_from_file(stream)) is not None:
                try:
                    short_name = str(codes_get(handle, "shortName")).casefold()
                    role = roles.get(short_name)
                    if role is None or role in fields:
                        continue
                    # SWELL/SWPER/SWDIR contain three ordered partitions. The
                    # first message is the primary swell and later partitions
                    # deliberately remain outside the v2 public contract.
                    if short_name in {"shts", "mpts", "swdir"}:
                        try:
                            if int(codes_get(handle, "level")) != 1:
                                continue
                        except Exception:
                            pass
                    fields[role] = _normalize_wave_field(
                        role,
                        decode_regular_latlon(codes_get_message(handle)),
                    )
                finally:
                    codes_release(handle)
    finally:
        if temporary_path is not None:
            for attempt in range(3):
                try:
                    temporary_path.unlink(missing_ok=True)
                    break
                except PermissionError:  # ecCodes can release late on Windows
                    gc.collect()
                    if attempt < 2:
                        time.sleep(0.02)

    required = set(roles.values())
    missing = sorted(required - fields.keys())
    if missing:
        raise InvalidModelData(
            f"NOAA GFS-Wave subset misses fields: {', '.join(missing)}"
        )
    reference = fields["total_wave_height"]
    for grid in fields.values():
        assert_same_grid(reference, grid)
    return fields


class NoaaGfsWaveProvider:
    """Credential-free NOAA GFS-Wave adapter for the T+168..T+240 tail."""

    provider_key = "noaa"
    model_key = "noaa-gfs-wave"
    coverage = GFS_WAVE_COVERAGE
    cadence_hours = 6
    filter_url = "https://nomads.ncep.noaa.gov/cgi-bin/filter_gfswave.pl"

    def __init__(
        self,
        *,
        client: httpx.Client | None = None,
        timeout: float = 45,
        max_source_bytes: int = 67_108_864,
        coverage: tuple[float, float, float, float] = GFS_WAVE_COVERAGE,
    ):
        self.client = client or httpx.Client()
        self.timeout = timeout
        self.max_source_bytes = max_source_bytes
        self.coverage = coverage

    @staticmethod
    def _index_url(run_at: datetime, forecast_hour: int) -> str:
        return (
            "https://nomads.ncep.noaa.gov/pub/data/nccf/com/gfs/prod/"
            f"gfs.{run_at:%Y%m%d}/{run_at:%H}/wave/gridded/"
            f"gfswave.t{run_at:%H}z.global.0p25.f{forecast_hour:03d}.grib2.idx"
        )

    def discover_latest(
        self, now: datetime, *, forecast_hours: list[int] | None = None
    ) -> datetime | None:
        candidate = now.astimezone(timezone.utc).replace(
            minute=0, second=0, microsecond=0
        )
        candidate = candidate.replace(hour=(candidate.hour // 6) * 6)
        probes = sorted({min(forecast_hours or [0]), max(forecast_hours or [0])})
        for offset in range(0, 37, 6):
            run_at = candidate - timedelta(hours=offset)
            available = True
            for forecast_hour in probes:
                try:
                    response = self.client.head(
                        self._index_url(run_at, forecast_hour),
                        timeout=self.timeout,
                        follow_redirects=True,
                    )
                except httpx.HTTPError:
                    available = False
                    break
                if response.status_code != 200:
                    available = False
                    break
            if available:
                return run_at
        return None

    def _request(self, run_at: datetime, forecast_hour: int) -> tuple[str, bytes]:
        west, south, east, north = self.coverage
        request_west, request_east = (
            (0.0, 360.0) if west <= -180 and east >= 180 else (west, east)
        )
        params = {
            "file": f"gfswave.t{run_at:%H}z.global.0p25.f{forecast_hour:03d}.grib2",
            "dir": f"/gfs.{run_at:%Y%m%d}/{run_at:%H}/wave/gridded",
            "subregion": "",
            "leftlon": request_west,
            "rightlon": request_east,
            "toplat": north,
            "bottomlat": south,
            "var_HTSGW": "on",
            "var_PERPW": "on",
            "var_DIRPW": "on",
            "var_WVHGT": "on",
            "var_WVPER": "on",
            "var_WVDIR": "on",
            "var_SWELL": "on",
            "var_SWPER": "on",
            "var_SWDIR": "on",
        }
        source_url = f"{self.filter_url}?{urlencode(sorted(params.items()))}"
        try:
            with self.client.stream(
                "GET",
                self.filter_url,
                params=params,
                timeout=self.timeout,
                headers={"User-Agent": "surfwinddata/1.0"},
            ) as response:
                response.raise_for_status()
                data = bytearray()
                for chunk in response.iter_bytes():
                    data.extend(chunk)
                    if len(data) > self.max_source_bytes:
                        raise InvalidModelData(
                            "NOAA GFS-Wave subset exceeds byte budget"
                        )
        except httpx.HTTPError as exc:
            raise ProviderUnavailable("NOAA GFS-Wave field unavailable") from exc
        return source_url, bytes(data)

    def fetch(self, run_at: datetime, forecast_hour: int) -> FieldSourceSlice:
        source_url, data = self._request(run_at, forecast_hour)
        grids = decode_gfs_wave_fields(data)
        reference = grids["total_wave_height"]
        direction = np.radians(grids["total_wave_direction"].values)
        height = reference.values
        return FieldSourceSlice(
            forecast_hour=forecast_hour,
            valid_time=run_at + timedelta(hours=forecast_hour),
            u=_grid_with_values(reference, -height * np.sin(direction)),
            v=_grid_with_values(reference, -height * np.cos(direction)),
            gust=None,
            source_urls=(source_url,),
            downloaded_bytes=len(data),
            scalar_fields=grids,
            product="wave",
            vector_u_name="wave_u",
            vector_v_name="wave_v",
            magnitude_name="total_wave_height",
        )


def decode_gfs_fields(
    data: bytes, *, forecast_hour: int | None = None
) -> dict[str, RegularGrid]:
    """Decode selected wind and scalar messages from one bounded NOMADS subset."""
    try:
        from eccodes import (
            codes_get,
            codes_get_message,
            codes_grib_new_from_file,
            codes_release,
        )
    except ImportError as exc:  # pragma: no cover - deployment dependency
        raise ProviderUnavailable("ecCodes runtime is not installed") from exc

    fields: dict[str, RegularGrid] = {}
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".grib2", delete=False) as temporary:
            temporary.write(data)
            temporary_path = Path(temporary.name)
        with temporary_path.open("rb") as stream:
            while (handle := codes_grib_new_from_file(stream)) is not None:
                try:
                    short_name = str(codes_get(handle, "shortName"))
                    role = {
                        "10u": "u",
                        "u10": "u",
                        "10v": "v",
                        "v10": "v",
                        "gust": "gust",
                        "2t": "temperature_2m",
                        "t2m": "temperature_2m",
                        "prmsl": "pressure_msl",
                        "msl": "pressure_msl",
                        "tp": "precipitation",
                        "apcp": "precipitation",
                        "tcc": "cloud_cover",
                    }.get(short_name)
                    if role and role not in fields:
                        fields[role] = decode_regular_latlon(codes_get_message(handle))
                finally:
                    codes_release(handle)
    finally:
        if temporary_path is not None:
            for attempt in range(3):
                try:
                    temporary_path.unlink(missing_ok=True)
                    break
                except PermissionError:  # ecCodes can release late on Windows
                    gc.collect()
                    if attempt < 2:
                        time.sleep(0.02)
    if "u" not in fields or "v" not in fields:
        raise InvalidModelData("NOAA GFS subset misses 10 m u/v components")
    assert_same_grid(fields["u"], fields["v"])
    if "gust" in fields:
        assert_same_grid(fields["u"], fields["gust"])
    # NOMADS does not expose APCP for the analysis (f000): there is no
    # accumulation interval yet.  Model that physical zero explicitly, while
    # continuing to reject a missing precipitation message for forecast steps.
    if "precipitation" not in fields and forecast_hour == 0:
        fields["precipitation"] = RegularGrid(
            longitudes=fields["u"].longitudes.copy(),
            latitudes=fields["u"].latitudes.copy(),
            values=np.zeros_like(fields["u"].values),
            definition={
                **fields["u"].definition,
                "derivedFrom": "gfs-analysis-zero-accumulation",
            },
        )
    for name in SCALAR_SOURCE_VARIABLES:
        if name not in fields:
            raise InvalidModelData(f"NOAA GFS subset misses {name}")
        assert_same_grid(fields["u"], fields[name])
        fields[name] = _normalize_scalar(name, fields[name])
    return fields


def decode_gfs_wind_fields(data: bytes) -> tuple[RegularGrid, RegularGrid, RegularGrid | None]:
    fields = decode_gfs_fields(data, forecast_hour=0)
    return fields["u"], fields["v"], fields.get("gust")


class GfsFieldProvider:
    provider_key = "noaa"
    model_key = "gfs-0p25"
    coverage = GLOBAL_COVERAGE
    filter_url = "https://nomads.ncep.noaa.gov/cgi-bin/filter_gfs_0p25.pl"

    def __init__(
        self,
        *,
        client: httpx.Client | None = None,
        timeout: float = 45,
        max_source_bytes: int = 16_777_216,
        coverage: tuple[float, float, float, float] = GLOBAL_COVERAGE,
    ):
        self.client = client or httpx.Client()
        self.timeout = timeout
        self.max_source_bytes = max_source_bytes
        self.coverage = coverage

    @staticmethod
    def _index_url(run_at: datetime, forecast_hour: int = 0) -> str:
        return (
            "https://nomads.ncep.noaa.gov/pub/data/nccf/com/gfs/prod/"
            f"gfs.{run_at:%Y%m%d}/{run_at:%H}/atmos/"
            f"gfs.t{run_at:%H}z.pgrb2.0p25.f{forecast_hour:03d}.idx"
        )

    def discover_latest(
        self, now: datetime, *, forecast_hours: list[int] | None = None
    ) -> datetime | None:
        candidate = now.astimezone(timezone.utc).replace(
            minute=0, second=0, microsecond=0
        )
        candidate = candidate.replace(hour=(candidate.hour // 6) * 6)
        probes = sorted({0, max(forecast_hours or [0])})
        for offset in range(0, 37, 6):
            run_at = candidate - timedelta(hours=offset)
            available = True
            for forecast_hour in probes:
                try:
                    response = self.client.head(
                        self._index_url(run_at, forecast_hour),
                        timeout=self.timeout,
                        follow_redirects=True,
                    )
                except httpx.HTTPError:
                    available = False
                    break
                if response.status_code != 200:
                    available = False
                    break
            if available:
                return run_at
        return None

    def _request(self, run_at: datetime, forecast_hour: int) -> tuple[str, bytes]:
        west, south, east, north = self.coverage
        request_west, request_east = (0.0, 360.0) if west <= -180 and east >= 180 else (west, east)
        params = {
            "file": f"gfs.t{run_at:%H}z.pgrb2.0p25.f{forecast_hour:03d}",
            "dir": f"/gfs.{run_at:%Y%m%d}/{run_at:%H}/atmos",
            "subregion": "",
            "leftlon": request_west,
            "rightlon": request_east,
            "toplat": north,
            "bottomlat": south,
            "var_UGRD": "on",
            "var_VGRD": "on",
            "var_GUST": "on",
            "var_TMP": "on",
            "var_APCP": "on",
            "var_PRMSL": "on",
            "var_TCDC": "on",
            "lev_10_m_above_ground": "on",
            "lev_2_m_above_ground": "on",
            "lev_surface": "on",
            "lev_mean_sea_level": "on",
            "lev_entire_atmosphere": "on",
        }
        source_url = f"{self.filter_url}?{urlencode(sorted(params.items()))}"
        try:
            with self.client.stream(
                "GET",
                self.filter_url,
                params=params,
                timeout=self.timeout,
                headers={"User-Agent": "surfwinddata/1.0"},
            ) as response:
                response.raise_for_status()
                data = bytearray()
                for chunk in response.iter_bytes():
                    data.extend(chunk)
                    if len(data) > self.max_source_bytes:
                        raise InvalidModelData("NOAA GFS subset exceeds byte budget")
        except httpx.HTTPError as exc:
            raise ProviderUnavailable("NOAA GFS field unavailable") from exc
        return source_url, bytes(data)

    def fetch(self, run_at: datetime, forecast_hour: int) -> FieldSourceSlice:
        source_url, data = self._request(run_at, forecast_hour)
        fields = decode_gfs_fields(data, forecast_hour=forecast_hour)
        return FieldSourceSlice(
            forecast_hour=forecast_hour,
            valid_time=run_at + timedelta(hours=forecast_hour),
            u=fields["u"],
            v=fields["v"],
            gust=fields.get("gust"),
            source_urls=(source_url,),
            downloaded_bytes=len(data),
            scalar_fields={name: fields[name] for name in SCALAR_SOURCE_VARIABLES},
        )
