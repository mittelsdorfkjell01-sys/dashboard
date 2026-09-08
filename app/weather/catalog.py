"""Europe-wide model catalogue.

Forecast values are fetched through Open-Meteo (``app/weather/openmeteo.py``),
so a model is added here by its Open-Meteo ``models=`` identifier, not by a new
provider module. Open-Meteo silently drops any model that has no data at the
requested point and the global members always anchor the grid, so the coverage
boxes below may be generous; they exist to bound request size and to document
each model's real domain. All identifiers and domains were verified against the
live Open-Meteo API (2026-09).
"""

from __future__ import annotations

from dataclasses import dataclass

from app.weather.contracts import ModelFamily


@dataclass(frozen=True)
class ModelSpec:
    id: str
    family: ModelFamily
    regional: bool = False


# High-resolution national/regional models (all REGIONAL family).
ICON_D2 = ModelSpec("icon_d2", ModelFamily.REGIONAL, True)  # DWD ~2 km, central Europe
AROME_FR = ModelSpec("meteofrance_arome_france_hd", ModelFamily.REGIONAL, True)  # ~1.5 km, France + seas
ICON_CH1 = ModelSpec("meteoswiss_icon_ch1", ModelFamily.REGIONAL, True)  # MeteoSwiss ~1 km, Alps
ICON_CH2 = ModelSpec("meteoswiss_icon_ch2", ModelFamily.REGIONAL, True)  # MeteoSwiss ~2 km, Alpine region
AROME_AT = ModelSpec("geosphere_arome_austria", ModelFamily.REGIONAL, True)  # GeoSphere ~2.5 km, Austria/central EU
ICON_2I = ModelSpec("italia_meteo_arpae_icon_2i", ModelFamily.REGIONAL, True)  # ARPAE ICON-2I ~2 km, Italy/Med
UKMO_2KM = ModelSpec("ukmo_uk_deterministic_2km", ModelFamily.REGIONAL, True)  # UKMO ~2 km, UK + NW approaches
KNMI_NL = ModelSpec("knmi_harmonie_arome_netherlands", ModelFamily.REGIONAL, True)
KNMI_EU = ModelSpec("knmi_harmonie_arome_europe", ModelFamily.REGIONAL, True)
DMI_EU = ModelSpec("dmi_harmonie_arome_europe", ModelFamily.REGIONAL, True)
# Continental fallbacks (still REGIONAL family): coarser than the sub-3 km models
# but far finer than the ~25 km globals, and they give every European coordinate
# at least one regional member so the regional family weight applies pan-Europe.
ICON_EU = ModelSpec("icon_eu", ModelFamily.REGIONAL, True)  # DWD ~7 km, all Europe
ARPEGE_EU = ModelSpec("meteofrance_arpege_europe", ModelFamily.REGIONAL, True)  # Météo-France ~11 km, Europe + Atlantic/Med

# Global / AI members.
IFS = ModelSpec("ecmwf_ifs", ModelFamily.IFS)
GFS = ModelSpec("ncep_gfs_global", ModelFamily.GFS)
AIFS = ModelSpec("ecmwf_aifs025_single", ModelFamily.AIFS)
ICON_GLOBAL = ModelSpec("icon_global", ModelFamily.ICON_GLOBAL)

_ALL_SPECS = (
    ICON_D2, AROME_FR, ICON_CH1, ICON_CH2, AROME_AT, ICON_2I, UKMO_2KM,
    KNMI_NL, KNMI_EU, DMI_EU, ICON_EU, ARPEGE_EU,
    IFS, GFS, AIFS, ICON_GLOBAL,
)
BY_ID = {spec.id: spec for spec in _ALL_SPECS}


# (spec, (lat_min, lat_max, lon_min, lon_max)) — most specific first, continental last.
_COVERAGE: tuple[tuple[ModelSpec, tuple[float, float, float, float]], ...] = (
    (AROME_FR, (38.0, 53.5, -7.5, 11.5)),
    (ICON_D2, (43.2, 58.1, -3.9, 20.3)),
    (KNMI_NL, (50.5, 54.0, 3.0, 7.5)),
    (KNMI_EU, (48.0, 58.0, 0.0, 16.0)),
    (DMI_EU, (53.0, 58.5, 7.0, 16.0)),
    (ICON_CH1, (45.0, 48.5, 5.0, 11.5)),
    (ICON_CH2, (43.5, 49.5, 2.5, 13.5)),
    (AROME_AT, (43.0, 52.0, 5.5, 22.5)),
    (ICON_2I, (34.0, 48.5, 4.0, 20.5)),
    (UKMO_2KM, (44.0, 61.5, -14.0, 5.0)),
    (ICON_EU, (29.5, 70.5, -23.5, 45.0)),
    (ARPEGE_EU, (30.0, 72.0, -30.0, 42.0)),
)


def regional_models(latitude: float, longitude: float) -> tuple[ModelSpec, ...]:
    """Return the independent regional models whose domain covers a coordinate."""
    found = [
        spec
        for spec, (lat_min, lat_max, lon_min, lon_max) in _COVERAGE
        if lat_min <= latitude <= lat_max and lon_min <= longitude <= lon_max
    ]
    return tuple(dict.fromkeys(found))


def forecast_models(latitude: float, longitude: float) -> tuple[ModelSpec, ...]:
    """Stable, de-duplicated model set; seamless blends are excluded."""
    regional = regional_models(latitude, longitude)
    return tuple(dict.fromkeys((*regional, IFS, GFS, AIFS, ICON_GLOBAL)))


def family_for(model_id: str) -> ModelFamily:
    return BY_ID.get(model_id, ModelSpec(model_id, ModelFamily.OTHER)).family
