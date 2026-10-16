from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect

from app.config import Settings
from app.db.session import engine


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TABLES = {
    "weather_field_models",
    "weather_field_runs",
    "weather_field_assets",
    "weather_field_quality_events",
    "weather_field_publications",
    "weather_field_jobs",
}


def _config() -> Config:
    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(PROJECT_ROOT / "alembic"))
    config.set_main_option("sqlalchemy.url", Settings().test_database_url)
    return config


def test_weather_field_foundation_migration_reverses_and_reapplies(db) -> None:
    db.rollback()
    config = _config()
    assert TABLES.issubset(set(inspect(engine).get_table_names()))

    command.downgrade(config, "0071_retention_indexes")
    assert TABLES.isdisjoint(set(inspect(engine).get_table_names()))

    command.upgrade(config, "head")
    assert TABLES.issubset(set(inspect(engine).get_table_names()))
