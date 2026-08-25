from fastapi import APIRouter

from app.spatial_fields.contracts import FieldAvailability

router = APIRouter(prefix="/weather-fields", tags=["weather-fields"])


@router.get("/wind", response_model=FieldAvailability)
def wind_field_manifest() -> FieldAvailability:
    return FieldAvailability(
        reason="No licensed gridded provider and publication snapshot are configured. Point forecasts are not expanded into tiles."
    )


@router.get("/waves", response_model=FieldAvailability)
def wave_field_manifest() -> FieldAvailability:
    return FieldAvailability(
        status="blocked_credentials",
        reason="Copernicus Marine access, licence approval and an operational ingestion decision are required."
    )


@router.get("/nearshore", response_model=FieldAvailability)
def nearshore_field_manifest() -> FieldAvailability:
    return FieldAvailability(
        reason="Nearshore publication is disabled until bathymetry, model and holdout validation gates pass."
    )
