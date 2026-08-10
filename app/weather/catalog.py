"""V1 model catalogue for Germany, the Netherlands and Denmark."""

from __future__ import annotations

from dataclasses import dataclass

from app.weather.contracts import ModelFamily


@dataclass(frozen=True)
class ModelSpec:
    id: str
    family: ModelFamily
    regional: bool = False


ICON_D2 = ModelSpec("icon_d2", ModelFamily.REGIONAL, True)
KNMI_NL = ModelSpec("knmi_harmonie_arome_netherlands", ModelFamily.REGIONAL, True)
KNMI_EU = ModelSpec("knmi_harmonie_arome_europe", ModelFamily.REGIONAL, True)
DMI_EU = ModelSpec("dmi_harmonie_arome_europe", ModelFamily.REGIONAL, True)
IFS = ModelSpec("ecmwf_ifs", ModelFamily.IFS)
GFS = ModelSpec("ncep_gfs_global", ModelFamily.GFS)
AIFS = ModelSpec("ecmwf_aifs025_single", ModelFamily.AIFS)
ICON_GLOBAL = ModelSpec("icon_global", ModelFamily.ICON_GLOBAL)

BY_ID = {spec.id: spec for spec in (ICON_D2, KNMI_NL, KNMI_EU, DMI_EU, IFS, GFS, AIFS, ICON_GLOBAL)}


def regional_models(latitude: float, longitude: float) -> tuple[ModelSpec, ...]:
    """Return independent regional configurations covering a V1 coordinate."""
    found: list[ModelSpec] = []
    if 47.0 <= latitude <= 56.0 and 5.0 <= longitude <= 16.0:
        found.append(ICON_D2)
    if 50.5 <= latitude <= 54.0 and 3.0 <= longitude <= 7.5:
        found.extend((KNMI_NL, KNMI_EU))
    elif 48.0 <= latitude <= 58.0 and 0.0 <= longitude <= 16.0:
        found.append(KNMI_EU)
    if 53.0 <= latitude <= 58.5 and 7.0 <= longitude <= 16.0:
        found.append(DMI_EU)
    return tuple(dict.fromkeys(found))


def forecast_models(latitude: float, longitude: float) -> tuple[ModelSpec, ...]:
    """Stable, de-duplicated model set; seamless blends are excluded."""
    regional = regional_models(latitude, longitude)
    return tuple(dict.fromkeys((*regional, IFS, GFS, AIFS, ICON_GLOBAL)))


def family_for(model_id: str) -> ModelFamily:
    return BY_ID.get(model_id, ModelSpec(model_id, ModelFamily.OTHER)).family
