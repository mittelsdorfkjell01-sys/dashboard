"""Disposable local PostgreSQL databases for empty and legacy 0058 upgrades."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import uuid

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.config import Settings
from app.live.live_wind import load_station_residual_inputs


def _isolated_database(db):
    url = make_url(Settings().test_database_url)
    assert url.host in {"localhost", "127.0.0.1", "::1"}
    assert url.database == "surfwind_test"
    name = "surfwind_exact_" + uuid.uuid4().hex[:16]
    admin = db.get_bind().connect().execution_options(isolation_level="AUTOCOMMIT")
    admin.execute(text(f'CREATE DATABASE "{name}"'))
    return admin, name, url.set(database=name)


def _upgrade(url, revision):
    root = Path(__file__).resolve().parents[1]
    cfg = Config(str(root / "alembic.ini"))
    cfg.set_main_option("script_location", str(root / "alembic"))
    cfg.set_main_option("sqlalchemy.url", url.render_as_string(hide_password=False))
    command.upgrade(cfg, revision)


def test_exact_dataset_identity_empty_and_legacy_upgrade(db):
    for legacy in (False, True):
        admin, name, url = _isolated_database(db)
        target_engine = create_engine(url)
        try:
            _upgrade(url, "0057_exact_run_baseline" if legacy else "head")
            with target_engine.begin() as connection:
                if legacy:
                    connection.execute(text("""
                        INSERT INTO regions (id, slug, name, normalized_name, status)
                        VALUES (gen_random_uuid(), 'legacy-exact', 'Legacy Exact',
                                'legacy exact', 'published')
                    """))
                    connection.execute(text("""
                        INSERT INTO spots (id, slug, name, normalized_name, region_id,
                                           location, status)
                        SELECT gen_random_uuid(), 'legacy-exact', 'Legacy Exact',
                               'legacy exact', id, ST_GeogFromText('POINT(10 54)'),
                               'published' FROM regions WHERE slug='legacy-exact'
                    """))
                    connection.execute(text("""
                        INSERT INTO weather_stations
                            (id, spot_id, provider, provider_station_id,
                             latitude, longitude, active, approved,
                             representativeness_status)
                        SELECT gen_random_uuid(), id, 'dwd', 'legacy-fixture',
                               54, 10, true, true, 'passed'
                        FROM spots WHERE slug='legacy-exact'
                    """))
                    connection.execute(text("""
                        INSERT INTO weather_observations
                            (id, station_id, observed_at, wind_speed_ms, import_status)
                        SELECT gen_random_uuid(), id, now() - interval '10 minutes',
                               10, 'accepted' FROM weather_stations
                        WHERE provider_station_id='legacy-fixture'
                    """))
                    connection.execute(text("""
                        INSERT INTO weather_station_model_residuals
                            (station_id, observation_id, analysis_id,
                             calculation_version, baseline_version,
                             baseline_bundle_hash, activation_eligible,
                             analyzed_at, observed_at, physics_version,
                             representativeness_uncertainty, qc_status)
                        SELECT station_id, id, repeat('a',64),
                               'station-model-error-uv-v1',
                               'exact-run-bundle-v1', repeat('b',64), true,
                               now(), observed_at, 'none',
                               'elevated_no_reviewed_station_profile', 'accepted'
                        FROM weather_observations
                    """))
                    connection.execute(text("""
                        INSERT INTO weather_live_wind_verification_evidence
                            (run_id, candidate_version, context_hash, input_hash,
                             training_window_end, window_start, window_end,
                             matched_samples, distinct_stations, distinct_days,
                             status, reason)
                        VALUES (gen_random_uuid(), 'legacy-candidate', repeat('c',64),
                                repeat('d',64), now() - interval '3 days',
                                now() - interval '1 day', now(), 0, 0, 0,
                                'collecting', 'legacy_capture_time_baseline')
                    """))
            if legacy:
                _upgrade(url, "head")
            with target_engine.connect() as connection:
                assert connection.execute(text(
                    "SELECT version_num FROM alembic_version")).scalar_one() == "0059_live_wind_holdout_cases"
                assert inspect(connection).has_table("weather_live_wind_holdout_cases")
                columns = {item["name"] for item in inspect(connection).get_columns(
                    "weather_station_model_residuals")}
                assert {"dataset_bundle_hash", "dataset_manifest", "sample_hash",
                        "sample_manifest"}.issubset(columns)
                indices = {item["name"] for item in inspect(connection).get_indexes(
                    "weather_station_model_residuals")}
                assert "ix_weather_station_residual_dataset_bundle" in indices
                uniques = {item["name"] for item in inspect(connection).get_unique_constraints(
                    "weather_station_model_residuals")}
                assert "uq_weather_station_model_residual_evidence" in uniques
                foreign_keys = {item["name"] for item in inspect(connection).get_foreign_keys(
                    "weather_station_model_residuals")}
                assert any("observation" in name for name in foreign_keys if name)
                if legacy:
                    legacy_row = connection.execute(text("""
                        SELECT baseline_version, baseline_bundle_hash, dataset_bundle_hash,
                               dataset_manifest, sample_hash, sample_manifest
                        FROM weather_station_model_residuals
                    """)).one()
                    assert legacy_row[0:2] == ("exact-run-bundle-v1", "b" * 64)
                    assert legacy_row[2:] == (None, None, None, None)
                    assert connection.execute(text(
                        "SELECT count(*) FROM weather_live_wind_verification_evidence "
                        "WHERE candidate_version='legacy-candidate'"
                    )).scalar_one() == 1
            if legacy:
                with Session(target_engine) as session:
                    observation_id = session.execute(text(
                        "SELECT id FROM weather_observations LIMIT 1")).scalar_one()
                    selection = SimpleNamespace(candidates=(SimpleNamespace(
                        eligible=True, observation_id=str(observation_id)),))
                    diagnostics = {}
                    assert not load_station_residual_inputs(
                        session, selection,
                        target_model_ids=("gfs-0p25", "icon-eu"),
                        target_dataset_bundle_hash="b" * 64,
                        target_dataset_manifest={},
                        diagnostics_out=diagnostics,
                    )
                    assert diagnostics["residual_rejection_reasons"] == {
                        "legacy_or_nonexact_baseline": 1,
                    }
        finally:
            target_engine.dispose()
            admin.execute(text(f'DROP DATABASE "{name}" WITH (FORCE)'))
            admin.close()


def test_disposable_0056_to_0059_keeps_legacy_residual_ineligible(db):
    admin, name, url = _isolated_database(db)
    target_engine = create_engine(url)
    try:
        _upgrade(url, "0056_live_wind_verification")
        with target_engine.begin() as connection:
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "0056_live_wind_verification"
            connection.execute(text("""
                INSERT INTO regions (id, slug, name, normalized_name, status)
                VALUES (gen_random_uuid(), 'pre-exact', 'Pre Exact', 'pre exact', 'published')
            """))
            connection.execute(text("""
                INSERT INTO spots (id, slug, name, normalized_name, region_id, location, status)
                SELECT gen_random_uuid(), 'pre-exact', 'Pre Exact', 'pre exact', id,
                       ST_GeogFromText('POINT(10 54)'), 'published'
                FROM regions WHERE slug='pre-exact'
            """))
            connection.execute(text("""
                INSERT INTO weather_stations
                    (id, spot_id, provider, provider_station_id, latitude, longitude,
                     active, approved, representativeness_status)
                SELECT gen_random_uuid(), id, 'dwd', 'pre-exact-fixture', 54, 10,
                       true, true, 'passed' FROM spots WHERE slug='pre-exact'
            """))
            connection.execute(text("""
                INSERT INTO weather_observations
                    (id, station_id, observed_at, wind_speed_ms, import_status)
                SELECT gen_random_uuid(), id, now() - interval '10 minutes', 10, 'accepted'
                FROM weather_stations WHERE provider_station_id='pre-exact-fixture'
            """))
            connection.execute(text("""
                INSERT INTO weather_station_model_residuals
                    (station_id, observation_id, analysis_id, calculation_version,
                     baseline_version, analyzed_at, observed_at, physics_version,
                     representativeness_uncertainty, qc_status)
                SELECT station_id, id, repeat('a',64), 'station-model-error-uv-v1',
                       'legacy-capture-time', now(), observed_at, 'none',
                       'elevated_no_reviewed_station_profile', 'accepted'
                FROM weather_observations
            """))
            before = connection.scalar(text("SELECT count(*) FROM weather_station_model_residuals"))
        assert before == 1
        _upgrade(url, "0057_exact_run_baseline")
        _upgrade(url, "0058_exact_dataset_identity")
        _upgrade(url, "0059_live_wind_holdout_cases")
        with target_engine.connect() as connection:
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "0059_live_wind_holdout_cases"
            row = connection.execute(text("""
                SELECT baseline_version, activation_eligible, dataset_bundle_hash,
                       dataset_manifest, sample_hash, sample_manifest
                FROM weather_station_model_residuals
            """)).one()
            assert row == ("legacy-capture-time", False, None, None, None, None)
            assert connection.scalar(text("SELECT count(*) FROM weather_observations")) == 1
            assert connection.scalar(text("SELECT count(*) FROM weather_live_wind_holdout_cases")) == 0
            assert "ix_live_wind_holdout_candidate_time" in {
                item["name"] for item in inspect(connection).get_indexes("weather_live_wind_holdout_cases")}
    finally:
        target_engine.dispose()
        admin.execute(text(f'DROP DATABASE "{name}" WITH (FORCE)'))
        admin.close()
