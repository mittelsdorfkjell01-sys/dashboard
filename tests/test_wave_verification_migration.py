from sqlalchemy import inspect


TABLE_COLUMNS = {
    "wave_observation_platforms": {
        "provider_key",
        "external_id",
        "region_code",
        "location_class",
    },
    "wave_observations": {
        "platform_id",
        "observed_at",
        "significant_height_m",
        "period_semantic",
        "direction_semantic",
        "qc_status",
    },
    "wave_forecast_samples": {
        "platform_id",
        "field_run_id",
        "model_run_at",
        "valid_at",
        "lead_hours",
        "evidence_sha256",
    },
    "wave_verification_runs": {
        "dataset_start",
        "dataset_end",
        "policy_version",
        "artifact_sha256",
    },
    "wave_verification_scores": {
        "verification_run_id",
        "model_key",
        "parameter",
        "lead_bucket",
        "sample_count",
    },
}


def test_wave_verification_models_match_migrated_tables(db) -> None:
    inspector = inspect(db.get_bind())

    for table, expected_columns in TABLE_COLUMNS.items():
        assert inspector.has_table(table)
        actual_columns = {
            column["name"] for column in inspector.get_columns(table)
        }
        assert expected_columns <= actual_columns
