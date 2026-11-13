from app.config import Settings


def test_wave_forecast_is_public_by_default_and_backtest_stays_parallel(
    monkeypatch,
) -> None:
    monkeypatch.delenv("WAVE_FIELD_PUBLIC_ENABLED", raising=False)
    monkeypatch.delenv("WAVE_FIELD_AUTO_ACTIVATE", raising=False)
    monkeypatch.delenv("WAVE_BACKTEST_ARCHIVE_ENABLED", raising=False)

    settings = Settings(_env_file=None)

    assert settings.wave_field_public_enabled is True
    assert settings.wave_field_auto_activate is True
    assert settings.wave_backtest_archive_enabled is True
