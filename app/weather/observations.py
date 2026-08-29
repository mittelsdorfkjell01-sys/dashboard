"""Public station-selection gates. Never mixes model and station wind."""
from datetime import datetime, timedelta, timezone

MAX_MEASUREMENT_AGE = timedelta(minutes=30)
MAX_FUTURE_SKEW = timedelta(minutes=2)
ACCEPTED_QUALITY = {None, "0", "1", "2", "3", "accepted", "good"}


def public_measurement(station, observation, *, now=None):
    now = now or datetime.now(timezone.utc)
    reasons = []
    if not getattr(station, "active", False): reasons.append("station_inactive")
    if not getattr(station, "approved", False): reasons.append("station_unapproved")
    if getattr(station, "blocked", False): reasons.append("station_blocked")
    if getattr(station, "representativeness_status", "unreviewed") != "passed": reasons.append("representativeness_unpassed")
    observed = observation.observed_at.astimezone(timezone.utc)
    age = now - observed
    if age > MAX_MEASUREMENT_AGE: reasons.append("observation_stale")
    if age < -MAX_FUTURE_SKEW: reasons.append("observation_future")
    speed, gust, direction = observation.wind_speed_ms, observation.wind_gust_ms, observation.wind_direction_deg
    if not isinstance(speed, (int, float)) or not 0 <= speed <= 75: reasons.append("wind_speed_invalid")
    if direction is not None and not 0 <= direction < 360: reasons.append("wind_direction_invalid")
    if gust is not None and gust < speed: reasons.append("gust_below_wind")
    quality = getattr(observation, "provider_quality", None)
    if quality not in ACCEPTED_QUALITY and str(quality).lower() not in ACCEPTED_QUALITY: reasons.append("provider_quality_rejected")
    if getattr(observation, "import_status", "accepted") != "accepted": reasons.append("import_rejected")
    return (not reasons), reasons
