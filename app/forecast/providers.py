"""Direct official model source adapters with bounded point/subset downloads."""

from __future__ import annotations
import bz2
import gc
import hashlib
import math
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
import httpx
import numpy as np

from app.forecast.contracts import GridPoint, NormalizedModelValue, ProviderRequest
from app.weather.vectors import uv_to_wind


class ProviderUnavailable(RuntimeError):
    pass


class InvalidModelData(RuntimeError):
    pass


class NoaaGfsProvider:
    """NOAA GFS coordinate subsets through the official NOMADS GRIB Filter."""

    source_key = "noaa-gfs"

    def __init__(self, client: httpx.Client | None = None, timeout: float = 15):
        self.client, self.timeout = client or httpx.Client(), timeout

    @staticmethod
    def point_indices(lat: float, lon: float) -> tuple[int, int]:
        return round((90 - lat) / 0.25), round((lon % 360) / 0.25)

    def fetch(self, request: ProviderRequest) -> list[NormalizedModelValue]:
        if request.model != "gfs-0p25":
            raise ProviderUnavailable("unsupported NOAA model")
        out = []
        for hour in request.forecast_hours:
            params = {
                "file": f"gfs.t{request.run_at:%H}z.pgrb2.0p25.f{hour:03d}",
                "dir": f"/gfs.{request.run_at:%Y%m%d}/{request.run_at:%H}/atmos",
                "subregion": "",
                "leftlon": request.longitude - 0.3,
                "rightlon": request.longitude + 0.3,
                "toplat": request.latitude + 0.3,
                "bottomlat": request.latitude - 0.3,
                "var_UGRD": "on",
                "var_VGRD": "on",
                "var_GUST": "on",
                "var_TMP": "on",
                "var_APCP": "on",
                "lev_10_m_above_ground": "on",
                "lev_2_m_above_ground": "on",
                "lev_surface": "on",
            }
            try:
                response = self.client.get(
                    "https://nomads.ncep.noaa.gov/cgi-bin/filter_gfs_0p25.pl",
                    params=params,
                    timeout=self.timeout,
                    headers={"User-Agent": "surfwinddata/1.0"},
                )
                response.raise_for_status()
            except httpx.HTTPError as exc:
                raise ProviderUnavailable(
                    "NOAA NOMADS GRIB Filter unavailable"
                ) from exc
            out.append(self.parse_grib(response.content, request, hour))
        return out

    @staticmethod
    def parse_grib(
        data: bytes, request: ProviderRequest, hour: int
    ) -> NormalizedModelValue:
        import tempfile

        try:
            from eccodes import (
                codes_get,
                codes_get_array,
                codes_grib_new_from_file,
                codes_release,
            )
        except ImportError as exc:
            raise ProviderUnavailable("ecCodes runtime is not installed") from exc
        values = {}
        grid = None
        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".grib2", delete=False) as temp:
                temp.write(data)
                temp_path = Path(temp.name)
            with temp_path.open("rb") as stream:
                while (gid := codes_grib_new_from_file(stream)) is not None:
                    try:
                        name = str(codes_get(gid, "shortName"))
                        lats = np.asarray(codes_get_array(gid, "latitudes"))
                        lons = np.asarray(codes_get_array(gid, "longitudes"))
                        field = np.asarray(codes_get_array(gid, "values"))
                        delta = np.minimum(
                            abs(lons - request.longitude),
                            360 - abs(lons - request.longitude),
                        )
                        index = int(
                            np.argmin(
                                (lats - request.latitude) ** 2
                                + (delta * np.cos(np.radians(request.latitude))) ** 2
                            )
                        )
                        values[name] = float(field[index])
                        grid = (float(lats[index]), float(lons[index]))
                    finally:
                        codes_release(gid)
        finally:
            if temp_path is not None:
                for attempt in range(3):
                    try:
                        temp_path.unlink(missing_ok=True)
                        break
                    except PermissionError:
                        # ecCodes can release its Windows handle one GC turn late.
                        gc.collect()
                        if attempt < 2:
                            time.sleep(0.01)
        u = values.get("10u", values.get("u10"))
        v = values.get("10v", values.get("v10"))
        if u is None or v is None or grid is None:
            raise InvalidModelData("NOAA GRIB misses 10 m wind components")
        speed, direction = uv_to_wind(u, v)
        gust = values.get("gust")
        temp = values.get("2t", values.get("t2m"))
        precip = values.get("tp", values.get("apcp"))
        lon_delta = ((grid[1] - request.longitude + 180) % 360) - 180
        distance = math.hypot(
            (grid[0] - request.latitude) * 111,
            lon_delta * 111 * math.cos(math.radians(request.latitude)),
        )
        return NormalizedModelValue(
            provider="NOAA/NCEP",
            model=request.model,
            dataset_version="GFS 0.25",
            model_run=request.run_at,
            valid_at=request.run_at + timedelta(hours=hour),
            fetched_at=datetime.now(timezone.utc),
            grid_point=GridPoint(
                latitude=grid[0], longitude=grid[1], distance_km=distance
            ),
            horizontal_resolution_km=28,
            horizon_hours=hour,
            u_ms=u,
            v_ms=v,
            speed_ms=speed,
            direction_deg=direction,
            gust_ms=gust,
            temperature_c=temp - 273.15 if temp is not None else None,
            precipitation_mm=max(0, precip) if precip is not None else None,
            source_key="noaa-gfs",
        )

    @staticmethod
    def parse_ascii(text: str, request: ProviderRequest) -> list[NormalizedModelValue]:
        lat_i, lon_i = NoaaGfsProvider.point_indices(
            request.latitude, request.longitude
        )
        blocks = {
            name: [
                float(v)
                for v in re.findall(r"[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?", body)
            ]
            for name, body in re.findall(
                r"(?ms)^(ugrd10m|vgrd10m|gustsfc|tmp2m|apcpsfc),[^\n]*\n(.*?)(?=^[a-z]|\Z)",
                text,
            )
        }
        if not {"ugrd10m", "vgrd10m"}.issubset(blocks):
            raise InvalidModelData("NOAA response misses 10 m wind components")
        out = []
        fetched = datetime.now(timezone.utc)
        for index, hour in enumerate(request.forecast_hours):
            try:
                u, v = blocks["ugrd10m"][index], blocks["vgrd10m"][index]
            except IndexError as exc:
                raise InvalidModelData(
                    "NOAA response has an incomplete time axis"
                ) from exc
            speed, direction = uv_to_wind(u, v)

            def optional(name):
                values = blocks.get(name, [])
                return values[index] if index < len(values) else None

            out.append(
                NormalizedModelValue(
                    provider="NOAA/NCEP",
                    model=request.model,
                    dataset_version="GFS 0.25",
                    model_run=request.run_at,
                    valid_at=request.run_at + timedelta(hours=hour),
                    fetched_at=fetched,
                    grid_point=GridPoint(
                        latitude=90 - lat_i * 0.25,
                        longitude=lon_i * 0.25,
                        distance_km=0,
                    ),
                    horizontal_resolution_km=28,
                    horizon_hours=hour,
                    u_ms=u,
                    v_ms=v,
                    speed_ms=speed,
                    direction_deg=direction,
                    gust_ms=optional("gustsfc"),
                    temperature_c=(
                        optional("tmp2m") - 273.15
                        if optional("tmp2m") is not None
                        else None
                    ),
                    precipitation_mm=optional("apcpsfc"),
                    source_key="noaa-gfs",
                )
            )
        return out


class DwdIconProvider:
    """Bounded DWD ICON variable-file downloader and ecCodes point sampler."""

    source_key = "dwd-icon"

    def __init__(
        self,
        client: httpx.Client | None = None,
        timeout: float = 20,
        max_bytes: int = 8_000_000,
    ):
        self.client, self.timeout, self.max_bytes = (
            client or httpx.Client(),
            timeout,
            max_bytes,
        )

    @staticmethod
    def file_url(model: str, run_at: datetime, variable: str, hour: int) -> str:
        folder = {
            "icon-global": "icon",
            "icon-eu": "icon-eu",
            "icon-d2": "icon-d2",
        }.get(model)
        if not folder:
            raise ProviderUnavailable("unsupported DWD model")
        prefix = {
            "icon-global": "icon_global_icosahedral",
            "icon-eu": "icon-eu_europe_regular-lat-lon",
            "icon-d2": "icon-d2_germany_regular-lat-lon",
        }[model]
        return f"https://opendata.dwd.de/weather/nwp/{folder}/grib/{run_at:%H}/{variable}/{prefix}_single-level_{run_at:%Y%m%d%H}_{hour:03d}_{variable.upper()}.grib2.bz2"

    def download(self, url: str) -> bytes:
        try:
            with self.client.stream(
                "GET",
                url,
                timeout=self.timeout,
                headers={"User-Agent": "surfwinddata/1.0"},
            ) as response:
                response.raise_for_status()
                data = bytearray()
                for chunk in response.iter_bytes():
                    data.extend(chunk)
                    if len(data) > self.max_bytes:
                        raise InvalidModelData(
                            "DWD variable file exceeds configured byte budget"
                        )
            return bz2.decompress(bytes(data))
        except (httpx.HTTPError, OSError) as exc:
            raise ProviderUnavailable("DWD Open Data unavailable") from exc

    @staticmethod
    def checksum(data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()

    @staticmethod
    def _nearest(data: bytes, lat: float, lon: float) -> tuple[float, float, float]:
        try:
            from eccodes import (
                codes_get_array,
                codes_grib_new_from_message,
                codes_release,
            )
        except ImportError as exc:
            raise ProviderUnavailable("ecCodes runtime is not installed") from exc
        gid = codes_grib_new_from_message(data)
        try:
            lats = np.asarray(codes_get_array(gid, "latitudes"))
            lons = np.asarray(codes_get_array(gid, "longitudes"))
            values = np.asarray(codes_get_array(gid, "values"))
            delta_lon = np.minimum(abs(lons - lon), 360 - abs(lons - lon))
            index = int(
                np.argmin(
                    (lats - lat) ** 2 + (delta_lon * np.cos(np.radians(lat))) ** 2
                )
            )
            return float(values[index]), float(lats[index]), float(lons[index])
        finally:
            codes_release(gid)

    def fetch(self, request: ProviderRequest) -> list[NormalizedModelValue]:
        if request.model not in {"icon-global", "icon-eu", "icon-d2"}:
            raise ProviderUnavailable("unsupported DWD model")
        resolution = {"icon-global": 13, "icon-eu": 7, "icon-d2": 2.2}[request.model]
        out = []
        fetched = datetime.now(timezone.utc)
        for hour in request.forecast_hours:
            sampled = {}
            grid = None
            for key in ("u_10m", "v_10m", "vmax_10m", "t_2m", "tot_prec"):
                value, glat, glon = self._nearest(
                    self.download(
                        self.file_url(request.model, request.run_at, key, hour)
                    ),
                    request.latitude,
                    request.longitude,
                )
                sampled[key] = value
                grid = (glat, glon)
            speed, direction = uv_to_wind(sampled["u_10m"], sampled["v_10m"])
            lon_delta = ((grid[1] - request.longitude + 180) % 360) - 180
            distance = math.hypot(
                (grid[0] - request.latitude) * 111,
                lon_delta * 111 * math.cos(math.radians(request.latitude)),
            )
            out.append(
                NormalizedModelValue(
                    provider="Deutscher Wetterdienst",
                    model=request.model,
                    dataset_version="DWD Open Data",
                    model_run=request.run_at,
                    valid_at=request.run_at + timedelta(hours=hour),
                    fetched_at=fetched,
                    grid_point=GridPoint(
                        latitude=grid[0], longitude=grid[1], distance_km=distance
                    ),
                    horizontal_resolution_km=resolution,
                    horizon_hours=hour,
                    u_ms=sampled["u_10m"],
                    v_ms=sampled["v_10m"],
                    speed_ms=speed,
                    direction_deg=direction,
                    gust_ms=sampled["vmax_10m"],
                    temperature_c=sampled["t_2m"] - 273.15,
                    precipitation_mm=max(0, sampled["tot_prec"]),
                    source_key=self.source_key,
                )
            )
        return out
