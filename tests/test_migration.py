from sqlalchemy import inspect, text

EXPECTED_TABLES = {
    "regions",
    "spots",
    "era5_jobs",
    "watches",
    "notifications",
    "scoring_params",
    "spot_audit",
    "required_fields",
}


def test_all_tables_created(db):
    inspector = inspect(db.get_bind())
    tables = set(inspector.get_table_names())
    assert EXPECTED_TABLES.issubset(tables)


def test_postgis_enabled(db):
    version = db.execute(text("SELECT PostGIS_Version()")).scalar()
    assert version  # non-empty version string


def test_geography_columns_present(db):
    rows = db.execute(
        text(
            "SELECT f_table_name, f_geography_column "
            "FROM geography_columns "
            "WHERE f_table_name IN ('spots', 'regions')"
        )
    ).all()
    cols = {(t, c) for t, c in rows}
    assert ("spots", "location") in cols
    assert ("regions", "center") in cols
    assert ("regions", "bounds") in cols


def test_spatial_indexes_exist(db):
    rows = db.execute(
        text("SELECT indexname FROM pg_indexes WHERE schemaname = 'public'")
    ).scalars().all()
    names = set(rows)
    for expected in {
        "ix_spots_location",
        "ix_spots_sports",
        "ix_spots_style",
        "ix_spots_region_status",
        # water_type/level became arrays (0019) — the old composite btree was
        # replaced by per-column GIN indexes.
        "ix_spots_water_type",
        "ix_spots_level",
        "ix_regions_center",
    }:
        assert expected in names


def test_category_columns_present(db):
    cols = db.execute(
        text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'spots' "
            "AND column_name IN ('water_character', 'style', 'facilities')"
        )
    ).scalars().all()
    assert {"water_character", "style", "facilities"} == set(cols)


def test_migration_0003_down_and_up(db):
    """The category migration reverses cleanly and re-applies (up→down→up)."""
    from pathlib import Path

    from alembic import command
    from alembic.config import Config

    root = Path(__file__).resolve().parents[1]
    cfg = Config(str(root / "alembic.ini"))
    cfg.set_main_option("script_location", str(root / "alembic"))
    url = db.get_bind().engine.url.render_as_string(hide_password=False)
    cfg.set_main_option("sqlalchemy.url", url)

    def cols() -> set[str]:
        return set(
            db.execute(
                text(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_name='spots' AND column_name IN "
                    "('water_character','style','facilities')"
                )
            ).scalars().all()
        )

    command.downgrade(cfg, "0002_era5_raw_path")
    db.commit()
    assert cols() == set()  # columns gone
    command.upgrade(cfg, "head")
    db.commit()
    assert len(cols()) == 3  # and back
