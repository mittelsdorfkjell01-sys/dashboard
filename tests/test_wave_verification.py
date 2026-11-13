from datetime import datetime, timezone

import pytest

from app.models.wave_verification import WaveForecastSample, WaveObservationPlatform
from app.spatial_fields.catalog import sync_free_model_catalog
from app.spatial_fields.control_plane import get_or_create_run
from app.weather.wave_verification import (
    WavePair,
    evaluate_wave_verification,
    forecast_semantics,
    import_wave_observation_rows,
    lead_bucket,
    normalize_qc,
    score_pairs,
)


def _pair(*, parameter: str, forecast: float, observed: float, day: int = 1) -> WavePair:
    return WavePair(
        model_key="dwd-ewam",
        parameter=parameter,
        lead_bucket="0-24h",
        region_code="north-sea",
        location_class="offshore",
        valid_at=datetime(2026, 11, day, tzinfo=timezone.utc),
        forecast=forecast,
        observed=observed,
    )


def test_provider_wave_semantics_are_not_conflated() -> None:
    assert forecast_semantics("dwd-ewam") == (
        "energy_period_tm10",
        "mean_direction_from",
    )
    assert forecast_semantics("noaa-gfs-wave") == (
        "primary_wave_mean_period",
        "primary_wave_direction_from",
    )


@pytest.mark.parametrize(
    ("hours", "expected"),
    [(0, "0-24h"), (23, "0-24h"), (24, "24-48h"), (240, "168-240h"), (241, "240h+")],
)
def test_lead_bucket_boundaries(hours: int, expected: str) -> None:
    assert lead_bucket(hours) == expected


def test_negative_lead_is_rejected() -> None:
    with pytest.raises(ValueError, match="must not be negative"):
        lead_bucket(-1)


def test_height_scores_are_deterministic() -> None:
    result = score_pairs(
        [
            _pair(parameter="significant_height", forecast=2.0, observed=1.5),
            _pair(parameter="significant_height", forecast=2.0, observed=2.5, day=2),
        ]
    )

    assert result["sample_count"] == 2
    assert result["distinct_days"] == 2
    assert result["bias"] == pytest.approx(0.0)
    assert result["mae"] == pytest.approx(0.5)
    assert result["rmse"] == pytest.approx(0.5)
    assert result["within_tolerance_ratio"] == pytest.approx(1.0)


def test_direction_scores_use_shortest_circular_error() -> None:
    result = score_pairs(
        [_pair(parameter="direction", forecast=350.0, observed=10.0)]
    )

    assert result["bias"] == pytest.approx(-20.0)
    assert result["mae"] == pytest.approx(20.0)
    assert result["within_tolerance_ratio"] == pytest.approx(1.0)


def test_copernicus_numeric_qc_is_normalized_fail_closed() -> None:
    assert normalize_qc("1") == "good"
    assert normalize_qc("2") == "probably_good"
    assert normalize_qc("9") == "unknown"


def test_import_and_evaluate_report_regional_coverage(db) -> None:
    valid_at = datetime(2026, 11, 2, 12, tzinfo=timezone.utc)
    imported = import_wave_observation_rows(
        db,
        [
            {
                "platform_id": "north-sea-test-buoy",
                "platform_name": "North Sea test buoy",
                "observed_at": valid_at.isoformat(),
                "latitude": 54.0,
                "longitude": 5.0,
                "location_class": "offshore",
                "significant_height_m": 2.0,
                "period_s": 8.0,
                "period_semantic": "energy_period_tm10",
                "direction_from_deg": 350.0,
                "direction_semantic": "mean_direction_from",
                "qc_status": "1",
            }
        ],
        provider_key="copernicus-marine",
        region_code="north-sea",
        source_revision="test-revision",
    )
    assert imported["persisted"] == 1
    platform = db.query(WaveObservationPlatform).filter_by(
        external_id="north-sea-test-buoy"
    ).one()
    model = next(
        row for row in sync_free_model_catalog(db) if row.model_key == "dwd-ewam"
    )
    run = get_or_create_run(
        db,
        model=model,
        model_run_at=valid_at,
        processing_version="wave-verification-test-v1",
        contract_version="weather-field-v2",
        coverage={"west": -12.0, "south": 28.0, "east": 44.0, "north": 68.0},
        native_grid={"status": "test"},
        valid_times=[valid_at.isoformat()],
    )
    run.status = "ready"
    db.add(
        WaveForecastSample(
            platform_id=platform.id,
            field_run_id=run.id,
            provider_key="dwd",
            model_key="dwd-ewam",
            model_run_at=valid_at,
            valid_at=valid_at,
            lead_hours=0,
            processing_version="wave-verification-test-v1",
            latitude=54.0,
            longitude=5.0,
            significant_height_m=2.2,
            period_s=9.0,
            period_semantic="energy_period_tm10",
            direction_from_deg=10.0,
            direction_semantic="mean_direction_from",
            interpolation="bilinear_native_grid",
            evidence_sha256="a" * 64,
            sample_metadata={},
        )
    )
    db.commit()

    artifact = evaluate_wave_verification(
        db,
        start=valid_at,
        end=valid_at,
        model_keys=["dwd-ewam"],
    )

    assert artifact["matched_values"] == 3
    assert artifact["score_groups"] == 3
    assert artifact["coverage"]["matched_platforms"] == 1
    region = next(
        row
        for row in artifact["coverage"]["regions"]
        if row["region_code"] == "north-sea"
    )
    assert region["active_platforms"] >= 1
    assert region["sampled_platforms"] == 1
    assert region["platforms_with_accepted_observations"] == 1
    assert region["matched_platforms"] == 1
