from pathlib import Path

import pytest

from scripts.wave_backtest import enforce_evidence_thresholds


ROOT = Path(__file__).resolve().parents[1]


def test_evidence_thresholds_reject_empty_or_partial_backtest():
    with pytest.raises(ValueError, match="matched_values=0"):
        enforce_evidence_thresholds(
            {
                "forecast_samples": 12,
                "matched_values": 0,
                "coverage": {"matched_platforms": 0},
            },
            minimum_forecast_samples=1,
            minimum_matched_values=1,
            minimum_matched_platforms=1,
        )


def test_evidence_thresholds_accept_complete_evidence():
    enforce_evidence_thresholds(
        {
            "forecast_samples": 12,
            "matched_values": 4,
            "coverage": {"matched_platforms": 2},
        },
        minimum_forecast_samples=1,
        minimum_matched_values=1,
        minimum_matched_platforms=1,
    )


def test_wave_workflows_are_free_bounded_and_fail_closed():
    publication = (
        ROOT / ".github/workflows/wave-field-publish.yml"
    ).read_text(encoding="utf-8")
    verification = (ROOT / ".github/workflows/wave-backtest.yml").read_text(
        encoding="utf-8"
    )

    assert 'cron: "35 7,19 * * *"' in publication
    assert "runs-on: ubuntu-latest" in verification
    assert "WAVE_BACKTEST_ENABLED == 'true'" in verification
    assert "COPERNICUS_MARINE_USERNAME" in verification
    assert "COPERNICUS_MARINE_PASSWORD" in verification
    assert "requirements-wave-backtest.txt" in verification
    assert "--minimum-forecast-samples 1" in verification
    assert "--minimum-matched-values 1" in verification
    assert "--minimum-matched-platforms 1" in verification
    assert "actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02" in verification
    assert "self-hosted" not in verification
