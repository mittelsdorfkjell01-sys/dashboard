"""ORM models. Importing this package registers all tables on Base.metadata."""

from app.db.base import Base
from app.models.region import Region
from app.models.spot import Spot
from app.models.spot_content_source import SpotContentSource
from app.models.era5_job import Era5Job
from app.models.watch import Watch
from app.models.notification import Notification
from app.models.scoring_params import ScoringParams
from app.models.spot_audit import SpotAudit
from app.models.required_fields import RequiredField
from app.models.admin_user import AdminUser
from app.models.app_user import AppUser
from app.models.favorite import Favorite
from app.models.trip import Trip, TripStop
from app.models.spot_visit import SpotVisit
from app.models.decision_support_gate import DecisionSupportGate
from app.models.rider import GearItem, RiderProfile, RiderSportProfile, UserEvent
from app.models.gear import (
    GearBrand,
    GearClaim,
    GearColorVariant,
    GearCompatibility,
    GearProduct,
    GearProductVersion,
    GearResearchCoverage,
    GearSizeVariant,
    GearSource,
    GearUseProfile,
)
from app.models.recommendation import RecommendationLog, ScoringCalibrationProposal
from app.models.ugc import (
    SpotRating,
    LocalTip,
    CommunityUpvote,
    SpotSubmission,
    SpotImage,
    ImageReport,
)
from app.models.media import MediaProviderBudget, MediaSearchCache, MediaUsage
from app.models.media_archive import SpotImageArchive
from app.models.media_gc import MediaGarbageCandidate, MediaGcState
from app.models.moderation_audit import ModerationAudit
from app.models.team_note import TeamNote
from app.models.board_task import BoardTask
from app.models.admin_notification import AdminNotification
from app.models.tide import (
    TideCalculationRun,
    TideEvent,
    TideEventOverride,
    TideHarmonicSolution,
    TideObservation,
    TideProfile,
    TideProfileRevision,
    TideSensor,
    TideStation,
    TideStationAlias,
)
from app.models.weather_profile import SpotWeatherProfile, SpotWeatherSector
from app.models.weather_verification import (
    ForecastSectorBuild,
    ForecastSectorGateEvidence,
    ForecastVerificationScore,
    WeatherForecastSample,
    WeatherModelCalibration,
    WeatherObservation,
    WeatherObservationImportState,
    WeatherObservationQuarantine,
    WeatherObservationRevision,
    WeatherStation,
    WeatherStationApprovalAudit,
    WeatherStationDossier,
    WeatherStationEpoch,
    WeatherStationGroupDecision,
    WeatherStationMetadataRevision,
    WeatherStationProviderCursor,
    WeatherProviderHttpResource,
    WeatherStationCatalogState,
    WeatherStationCaptureCycle,
    WeatherStationModelResidual,
    WeatherExactModelBundle,
    WeatherExactModelPoint,
    WeatherStationPhysicsProfile,
)
from app.models.forecast_system import (
    ForecastModelRun,
    ForecastProcessingJob,
    ForecastProvider,
    ForecastSnapshot,
    GeodataAsset,
    GeodataDataset,
    SpotGeoProfileInput,
    SpotGeoProfileVersion,
    SpotGeoShadowProfile,
    SpotGeoShadowSector,
)
from app.models.weather_shadow import (
    WeatherShadowForecast, WeatherShadowMatch, WeatherShadowMetric,
    WeatherShadowObservation, WeatherShadowRun, WeatherShadowStationBinding,
    WeatherShadowStudy,
)
from app.models.live_wind_ops import WeatherLiveWindJob
from app.models.live_wind_verification import WeatherLiveWindHoldoutCase, WeatherLiveWindVerificationEvidence
from app.models.wind_climatology import WindClimatologyCell, WindClimatologyRun, WindClimatologyV3Run, WindClimatologyV3Variant
from app.models.weather_field import (
    WeatherFieldAsset,
    WeatherFieldModel,
    WeatherFieldJob,
    WeatherFieldPublication,
    WeatherFieldQualityEvent,
    WeatherFieldRun,
)
from app.models.weather_field_shadow import (
    WeatherFieldShadowMetric,
    WeatherFieldShadowRun,
    WeatherFieldShadowSample,
)

__all__ = [
    "Base",
    "Region",
    "Spot",
    "SpotContentSource",
    "Era5Job",
    "Watch",
    "Notification",
    "ScoringParams",
    "SpotAudit",
    "RequiredField",
    "AdminUser",
    "AppUser",
    "Favorite",
    "RiderProfile",
    "RiderSportProfile",
    "GearItem",
    "GearBrand",
    "GearProduct",
    "GearProductVersion",
    "GearSizeVariant",
    "GearColorVariant",
    "GearSource",
    "GearClaim",
    "GearCompatibility",
    "GearUseProfile",
    "GearResearchCoverage",
    "UserEvent",
    "Trip",
    "TripStop",
    "SpotVisit",
    "DecisionSupportGate",
    "RecommendationLog",
    "ScoringCalibrationProposal",
    "SpotRating",
    "LocalTip",
    "CommunityUpvote",
    "SpotSubmission",
    "SpotImage",
    "ImageReport",
    "MediaUsage",
    "MediaSearchCache",
    "MediaProviderBudget",
    "SpotImageArchive",
    "MediaGarbageCandidate",
    "MediaGcState",
    "ModerationAudit",
    "TeamNote",
    "BoardTask",
    "AdminNotification",
    "TideProfile",
    "TideProfileRevision",
    "TideEvent",
    "TideEventOverride",
    "TideCalculationRun",
    "TideStation",
    "TideStationAlias",
    "TideSensor",
    "TideObservation",
    "TideHarmonicSolution",
    "SpotWeatherProfile",
    "SpotWeatherSector",
    "WeatherStation",
    "WeatherObservation",
    "WeatherObservationImportState",
    "WeatherObservationRevision",
    "WeatherStationApprovalAudit",
    "WeatherStationDossier",
    "WeatherStationEpoch",
    "WeatherStationGroupDecision",
    "WeatherStationMetadataRevision",
    "WeatherStationProviderCursor",
    "WeatherProviderHttpResource",
    "WeatherStationCatalogState",
    "WeatherStationCaptureCycle",
    "WeatherObservationQuarantine",
    "WeatherStationPhysicsProfile",
    "WeatherStationModelResidual",
    "WeatherExactModelBundle",
    "WeatherExactModelPoint",
    "WeatherLiveWindJob",
    "WeatherLiveWindVerificationEvidence",
    "WeatherLiveWindHoldoutCase",
    "ForecastSectorBuild",
    "ForecastSectorGateEvidence",
    "ForecastVerificationScore",
    "WeatherForecastSample",
    "WeatherModelCalibration",
    "ForecastProvider",
    "ForecastModelRun",
    "SpotGeoProfileVersion",
    "ForecastSnapshot",
    "ForecastProcessingJob",
    "GeodataDataset",
    "GeodataAsset",
    "SpotGeoProfileInput",
    "SpotGeoShadowProfile",
    "SpotGeoShadowSector",
    "WeatherShadowStudy", "WeatherShadowRun", "WeatherShadowForecast",
    "WeatherShadowStationBinding", "WeatherShadowObservation",
    "WeatherShadowMatch", "WeatherShadowMetric",
    "WindClimatologyCell", "WindClimatologyRun", "WindClimatologyV3Run", "WindClimatologyV3Variant",
    "WeatherFieldModel", "WeatherFieldJob", "WeatherFieldRun", "WeatherFieldAsset", "WeatherFieldQualityEvent",
    "WeatherFieldPublication",
    "WeatherFieldShadowRun", "WeatherFieldShadowSample", "WeatherFieldShadowMetric",
]
