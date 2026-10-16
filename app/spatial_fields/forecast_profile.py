"""Bounded operational forecast-hour profiles for each field model."""

from __future__ import annotations


def forecast_hours_for_model(model_key: str, hours: list[int]) -> list[int]:
    if model_key == "dwd-ewam":
        return [hour for hour in hours if hour <= 78]
    if model_key == "dwd-gwam":
        return [hour for hour in hours if hour <= 174 and hour % 3 == 0]
    if model_key == "noaa-gfs-wave":
        return [hour for hour in hours if hour <= 384 and hour % 3 == 0]
    if model_key == "icon-d2":
        return [hour for hour in hours if hour <= 48 and (hour <= 24 or hour % 3 == 0)]
    if model_key == "icon-eu":
        # DWD publishes ICON-EU through T+120.  Asking discovery to probe the
        # shared 10-day horizon makes every otherwise complete run look
        # incomplete; GFS supplies the extended day-six-to-ten window.
        return [hour for hour in hours if hour <= 120]
    if model_key == "gfs-0p25":
        # Keep the expensive global source sparse near-term while retaining a
        # continuous six-hour planning horizon through day ten.
        near_term = {0, 3, 6, 9, 12, 18, 24, 36, 48, 72, 96, 120}
        return [
            hour
            for hour in hours
            if hour in near_term or (126 <= hour <= 240 and hour % 6 == 0)
        ]
    return hours


def wave_model_keys(settings) -> tuple[str, ...]:
    """Return the ordered regional, global and extended-range wave chain."""
    return tuple(
        dict.fromkeys(
            (
                settings.wave_field_primary_model,
                getattr(settings, "wave_field_fallback_model", "dwd-gwam"),
                getattr(settings, "wave_field_extended_model", "noaa-gfs-wave"),
            )
        )
    )


def configured_wave_hours(settings, model_key: str) -> list[int]:
    if model_key == settings.wave_field_primary_model:
        configured = settings.wave_field_forecast_hours
    elif model_key == getattr(settings, "wave_field_extended_model", "noaa-gfs-wave"):
        configured = getattr(
            settings,
            "wave_field_extended_forecast_hours",
            range(168, 241, 3),
        )
    else:
        configured = settings.wave_field_global_forecast_hours
    return forecast_hours_for_model(model_key, list(configured))
