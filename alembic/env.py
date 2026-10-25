from logging.config import fileConfig

from alembic import context
from sqlalchemy import Column, MetaData, String, Table, engine_from_config, inspect, pool, text

from app.config import get_settings
from app.db.base import Base
import app.models  # noqa: F401  (registers all tables on Base.metadata)

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Inject the database URL from application settings. Honour an override placed
# in the alembic config (used by the test-suite) before falling back to .env.
if not config.get_main_option("sqlalchemy.url"):
    settings = get_settings()
    config.set_main_option(
        "sqlalchemy.url", settings.database_direct_url or settings.database_url
    )

target_metadata = Base.metadata


def _ensure_version_table_capacity(connection) -> None:
    """Allow descriptive revision IDs longer than Alembic's 32-char default."""
    if inspect(connection).has_table("alembic_version"):
        if connection.dialect.name == "postgresql":
            connection.execute(text(
                "ALTER TABLE alembic_version ALTER COLUMN version_num TYPE VARCHAR(128)"
            ))
        return
    version_metadata = MetaData()
    Table(
        "alembic_version",
        version_metadata,
        Column("version_num", String(128), primary_key=True, nullable=False),
    ).create(connection)


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        with connection.begin():
            _ensure_version_table_capacity(connection)
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
