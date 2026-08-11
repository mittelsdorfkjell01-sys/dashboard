"""ORM models. Importing this package registers all tables on Base.metadata."""

from app.db.base import Base
from app.models.region import Region
from app.models.spot import Spot
from app.models.era5_job import Era5Job
from app.models.watch import Watch
from app.models.notification import Notification
from app.models.scoring_params import ScoringParams
from app.models.spot_audit import SpotAudit
from app.models.required_fields import RequiredField
from app.models.admin_user import AdminUser
from app.models.app_user import AppUser
from app.models.favorite import Favorite
from app.models.ugc import (
    SpotRating,
    LocalTip,
    CommunityUpvote,
    SpotSubmission,
    SpotImage,
    ImageReport,
)
from app.models.media import MediaProviderBudget, MediaSearchCache, MediaUsage
from app.models.moderation_audit import ModerationAudit
from app.models.team_note import TeamNote
from app.models.board_task import BoardTask
from app.models.admin_notification import AdminNotification
from app.models.tide import (
    TideCalculationRun,
    TideEvent,
    TideEventOverride,
    TideProfile,
    TideProfileRevision,
)
from app.models.weather_profile import SpotWeatherProfile, SpotWeatherSector
from app.models.weather_verification import WeatherForecastSample, WeatherModelCalibration, WeatherObservation, WeatherStation

__all__ = [
    "Base",
    "Region",
    "Spot",
    "Era5Job",
    "Watch",
    "Notification",
    "ScoringParams",
    "SpotAudit",
    "RequiredField",
    "AdminUser",
    "AppUser",
    "Favorite",
    "SpotRating",
    "LocalTip",
    "CommunityUpvote",
    "SpotSubmission",
    "SpotImage",
    "ImageReport",
    "MediaUsage",
    "MediaSearchCache",
    "MediaProviderBudget",
    "ModerationAudit",
    "TeamNote",
    "BoardTask",
    "AdminNotification",
    "TideProfile",
    "TideProfileRevision",
    "TideEvent",
    "TideEventOverride",
    "TideCalculationRun",
    "SpotWeatherProfile",
    "SpotWeatherSector",
    "WeatherStation",
    "WeatherObservation",
    "WeatherForecastSample",
    "WeatherModelCalibration",
]
