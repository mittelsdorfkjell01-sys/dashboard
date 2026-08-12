"""Central provider, model, licence and attribution registry."""

from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True)
class ModelDefinition:
    key: str
    provider: str
    family: str
    coverage: str
    resolution_km: float
    horizon_hours: int
    step_hours: int
    enabled: bool
    reason: str | None = None


@dataclass(frozen=True)
class SourceDefinition:
    key: str
    provider: str
    dataset: str
    licence: str
    attribution: str
    official_url: str
    checked_on: str
    public: bool
    commercial_review_required: bool
    restrictions: str


SOURCES = {
    "noaa-gfs": SourceDefinition(
        "noaa-gfs",
        "NOAA/NCEP",
        "GFS 0.25° via NOMADS GRIB Filter",
        "US Government public data",
        "Forecast data: NOAA/NCEP GFS",
        "https://www.nco.ncep.noaa.gov/pmb/products/gfs/nomads/",
        "2026-08-12",
        True,
        True,
        "Subset requests only; respect NOMADS load guidance.",
    ),
    "dwd-icon": SourceDefinition(
        "dwd-icon",
        "Deutscher Wetterdienst",
        "ICON Open Data",
        "CC BY 4.0",
        "Forecast data © Deutscher Wetterdienst",
        "https://opendata.dwd.de/weather/nwp/",
        "2026-08-12",
        True,
        False,
        "Attribution required; variable files are GRIB2/BZip2.",
    ),
    "ecmwf-open": SourceDefinition(
        "ecmwf-open",
        "ECMWF",
        "IFS/AIFS Open Data",
        "CC BY 4.0",
        "This service is based on data and products of ECMWF",
        "https://data.ecmwf.int/forecasts/",
        "2026-08-12",
        True,
        False,
        "Open subset only; attribution and modification notice required.",
    ),
    "open-meteo": SourceDefinition(
        "open-meteo",
        "Open-Meteo",
        "Forecast and Marine APIs",
        "CC BY 4.0",
        "Weather data by Open-Meteo.com",
        "https://open-meteo.com/",
        "2026-08-12",
        True,
        True,
        "Migration fallback; free non-commercial limits apply.",
    ),
    "nasa-srtm": SourceDefinition(
        "nasa-srtm",
        "NASA/USGS",
        "Shuttle Radar Topography Mission",
        "Public domain (US Government work)",
        "Terrain data: NASA SRTM",
        "https://www.earthdata.nasa.gov/data/instruments/srtm",
        "2026-08-12",
        True,
        True,
        "Local operator-provisioned HGT tiles; voids remain uncorrected.",
    ),
}

MODELS = (
    ModelDefinition("gfs-0p25", "noaa-gfs", "gfs", "global", 28, 384, 3, True),
    ModelDefinition("icon-global", "dwd-icon", "icon", "global", 13, 180, 3, True),
    ModelDefinition("icon-eu", "dwd-icon", "icon", "europe", 7, 120, 3, True),
    ModelDefinition("icon-d2", "dwd-icon", "icon", "central-europe", 2.2, 48, 1, True),
    ModelDefinition(
        "ifs-open",
        "ecmwf-open",
        "ifs",
        "global",
        25,
        240,
        3,
        False,
        "Registry-ready; operational downloader deferred until GRIB delivery limits are measured.",
    ),
    ModelDefinition(
        "aifs-open",
        "ecmwf-open",
        "aifs",
        "global",
        28,
        360,
        6,
        False,
        "Registry-ready; not needed for the first no-budget cutover.",
    ),
)


def public_attributions(keys: set[str]) -> list[dict]:
    return [
        {
            "key": s.key,
            "provider": s.provider,
            "text": s.attribution,
            "url": s.official_url,
            "licence": s.licence,
        }
        for key in sorted(keys)
        if (s := SOURCES.get(key)) and s.public
    ]
