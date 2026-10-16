"""Explicit free-data model catalog for weather-field rollout."""

from __future__ import annotations

from dataclasses import asdict, dataclass

from sqlalchemy import select

from app.models.weather_field import WeatherFieldModel


@dataclass(frozen=True)
class FieldModelDefinition:
    provider_key: str
    model_key: str
    display_name: str
    status: str
    coverage: dict
    native_grid: dict
    cadence_hours: int
    forecast_step_hours: int
    max_horizon_hours: int
    priority: int
    licence: dict
    attribution: list[dict]
    metadata: dict


FREE_FIELD_MODELS = (
    FieldModelDefinition(
        provider_key="dwd",
        model_key="dwd-ewam",
        display_name="DWD EWAM",
        status="active",
        coverage={"region": "europe-marine", "authoritative_from_grid": True},
        native_grid={"grid_type": "regular_ll", "authoritative_from_grib": True},
        cadence_hours=12,
        forecast_step_hours=1,
        max_horizon_hours=78,
        priority=6,
        licence={"name": "GeoNutzV", "cost": "free-open-data"},
        attribution=[
            {
                "provider": "Deutscher Wetterdienst",
                "text": "Contains DWD EWAM wave forecast data",
                "url": "https://opendata.dwd.de/weather/maritime/wave_models/ewam/",
                "licence": "GeoNutzV",
            }
        ],
        metadata={"product": "wave", "role": "europe-primary", "blend": False},
    ),
    FieldModelDefinition(
        provider_key="dwd",
        model_key="dwd-gwam",
        display_name="DWD GWAM",
        status="active",
        coverage={"region": "global-marine", "authoritative_from_grid": True},
        native_grid={"grid_type": "regular_ll", "authoritative_from_grib": True},
        cadence_hours=12,
        forecast_step_hours=3,
        max_horizon_hours=174,
        priority=16,
        licence={"name": "GeoNutzV", "cost": "free-open-data"},
        attribution=[
            {
                "provider": "Deutscher Wetterdienst",
                "text": "Contains DWD GWAM wave forecast data",
                "url": "https://opendata.dwd.de/weather/maritime/wave_models/gwam/",
                "licence": "GeoNutzV",
            }
        ],
        metadata={"product": "wave", "role": "global-fallback", "blend": False},
    ),
    FieldModelDefinition(
        provider_key="noaa",
        model_key="noaa-gfs-wave",
        display_name="NOAA GFS-Wave 0.25°",
        status="active",
        coverage={"region": "global-marine", "authoritative_from_grid": True},
        native_grid={"grid_type": "regular_ll", "authoritative_from_grib": True},
        cadence_hours=6,
        forecast_step_hours=3,
        max_horizon_hours=384,
        priority=26,
        licence={"name": "United States public domain", "cost": "free-open-data"},
        attribution=[
            {
                "provider": "NOAA/NCEP",
                "text": "Contains NOAA/NCEP GFS-Wave forecast data",
                "url": "https://nomads.ncep.noaa.gov/",
                "licence": "United States public domain",
            }
        ],
        metadata={"product": "wave", "role": "extended-range", "blend": False},
    ),
    FieldModelDefinition(
        provider_key="dwd",
        model_key="icon-d2",
        display_name="DWD ICON-D2",
        status="active",
        coverage={"region": "central-europe", "authoritative_from_grid": True},
        native_grid={"grid_type": "regular_ll", "authoritative_from_grib": True},
        cadence_hours=3,
        forecast_step_hours=1,
        max_horizon_hours=48,
        priority=5,
        licence={"name": "GeoNutzV", "cost": "free-open-data"},
        attribution=[
            {
                "provider": "Deutscher Wetterdienst",
                "text": "Contains data from Deutscher Wetterdienst Open Data",
                "url": "https://opendata.dwd.de/weather/nwp/icon-d2/",
                "licence": "GeoNutzV",
            }
        ],
        metadata={"role": "central-europe-high-resolution", "blend": False, "operational": True},
    ),
    FieldModelDefinition(
        provider_key="dwd",
        model_key="icon-eu",
        display_name="DWD ICON-EU",
        status="active",
        coverage={"region": "europe", "authoritative_from_grid": True},
        native_grid={"grid_type": "regular_ll", "authoritative_from_grib": True},
        cadence_hours=6,
        forecast_step_hours=1,
        max_horizon_hours=120,
        priority=10,
        licence={"name": "GeoNutzV", "cost": "free-open-data"},
        attribution=[
            {
                "provider": "Deutscher Wetterdienst",
                "text": "Contains data from Deutscher Wetterdienst Open Data",
                "url": "https://opendata.dwd.de/weather/nwp/icon-eu/",
                "licence": "GeoNutzV",
            }
        ],
        metadata={"role": "europe-primary", "blend": False},
    ),
    FieldModelDefinition(
        provider_key="noaa",
        model_key="gfs-0p25",
        display_name="NOAA GFS 0.25°",
        status="active",
        coverage={"region": "global", "authoritative_from_grid": True},
        native_grid={"grid_type": "regular_ll", "authoritative_from_grib": True},
        cadence_hours=6,
        forecast_step_hours=1,
        max_horizon_hours=384,
        priority=20,
        licence={"name": "United States public domain", "cost": "free-open-data"},
        attribution=[
            {
                "provider": "NOAA/NCEP",
                "text": "Contains NOAA/NCEP Global Forecast System data",
                "url": "https://nomads.ncep.noaa.gov/",
                "licence": "United States public domain",
            }
        ],
        metadata={"role": "global-fallback", "blend": False, "operational": True},
    ),
)


def sync_free_model_catalog(db) -> list[WeatherFieldModel]:
    """Idempotently create/update the operational free-data catalog."""
    rows: list[WeatherFieldModel] = []
    for definition in FREE_FIELD_MODELS:
        row = db.scalar(
            select(WeatherFieldModel).where(
                WeatherFieldModel.provider_key == definition.provider_key,
                WeatherFieldModel.model_key == definition.model_key,
            )
        )
        values = asdict(definition)
        values["model_metadata"] = values.pop("metadata")
        if row is None:
            row = WeatherFieldModel(**values)
            db.add(row)
        else:
            # Status is operational state. A later Phase-2 activation must not
            # be silently undone by a metadata sync.
            values.pop("status")
            for key, value in values.items():
                setattr(row, key, value)
        rows.append(row)
    db.flush()
    return sorted(rows, key=lambda row: (row.status != "active", row.priority))
