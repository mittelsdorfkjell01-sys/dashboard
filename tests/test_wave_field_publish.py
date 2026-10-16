from types import SimpleNamespace

from scripts.wave_field_publish import _configured_hours


def test_publish_command_uses_complete_model_specific_wave_horizons() -> None:
    settings = SimpleNamespace(
        wave_field_forecast_hours=list(range(0, 79)),
        wave_field_global_forecast_hours=list(range(0, 175, 3)),
        wave_field_extended_forecast_hours=list(range(168, 241, 3)),
        wave_field_primary_model="dwd-ewam",
        wave_field_extended_model="noaa-gfs-wave",
    )
    assert _configured_hours(settings, "dwd-ewam") == list(range(0, 79))
    assert _configured_hours(settings, "dwd-gwam") == list(range(0, 175, 3))
    assert _configured_hours(settings, "noaa-gfs-wave") == list(range(168, 241, 3))
