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
    "tide_profiles",
    "tide_profile_revisions",
    "tide_events",
    "tide_event_overrides",
    "tide_calculation_runs",
    "media_usage",
    "media_search_cache",
    "media_provider_budget",
    "media_garbage_candidates",
    "media_gc_state",
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
            "WHERE f_table_name IN ('spots', 'regions', 'tide_profiles')"
        )
    ).all()
    cols = {(t, c) for t, c in rows}
    assert ("spots", "location") in cols
    assert ("regions", "center") in cols
    assert ("regions", "bounds") in cols
    assert ("tide_profiles", "automatic_anchor") in cols
    assert ("tide_profiles", "manual_anchor") in cols


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
        "ix_spots_bottom_type",
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


def test_admin_totp_columns_removed(db):
    cols = db.execute(
        text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'admin_users' "
            "AND column_name IN "
            "('totp_secret_encrypted', 'totp_enabled_at', 'totp_last_step')"
        )
    ).scalars().all()
    assert cols == []


def test_gallery_accepts_a_region_but_not_both_entities(db):
    """0027 generalised ``spot_images`` to spot-or-region; the check constraint
    is what keeps a row from belonging to both or to neither."""
    import uuid

    from sqlalchemy.exc import IntegrityError

    region_id = db.execute(text("SELECT id FROM regions LIMIT 1")).scalar()
    if region_id is None:
        region_id = uuid.uuid4()
        db.execute(
            text(
                "INSERT INTO regions (id, slug, name, normalized_name) "
                "VALUES (:id, :slug, 'Media Test', 'media test')"
            ),
            {"id": region_id, "slug": f"media-test-{uuid.uuid4().hex[:8]}"},
        )
        db.commit()

    insert = text(
        "INSERT INTO spot_images (spot_id, region_id, url, kind, status) "
        "VALUES (:spot_id, :region_id, 'https://img/x.jpg', 'gallery', 'approved')"
    )
    db.execute(insert, {"spot_id": None, "region_id": region_id})
    db.commit()

    spot_id = db.execute(text("SELECT id FROM spots LIMIT 1")).scalar()
    if spot_id is not None:
        try:
            db.execute(insert, {"spot_id": spot_id, "region_id": region_id})
            db.commit()
            raise AssertionError("a gallery row must not carry both entities")
        except IntegrityError:
            db.rollback()

    try:
        db.execute(insert, {"spot_id": None, "region_id": None})
        db.commit()
        raise AssertionError("a gallery row must carry one entity")
    except IntegrityError:
        db.rollback()

    db.execute(
        text("DELETE FROM spot_images WHERE region_id = :rid"), {"rid": region_id}
    )
    db.commit()


def test_migration_0027_down_and_up(db):
    """The media-provenance migration reverses cleanly and re-applies."""
    from pathlib import Path

    from alembic import command
    from alembic.config import Config

    root = Path(__file__).resolve().parents[1]
    cfg = Config(str(root / "alembic.ini"))
    cfg.set_main_option("script_location", str(root / "alembic"))
    url = db.get_bind().engine.url.render_as_string(hide_password=False)
    cfg.set_main_option("sqlalchemy.url", url)

    def media_tables() -> set[str]:
        return set(
            db.execute(
                text(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_name IN "
                    "('media_usage','media_search_cache','media_provider_budget')"
                )
            ).scalars().all()
        )

    command.downgrade(cfg, "0026_remove_admin_totp")
    db.commit()
    assert media_tables() == set()
    command.upgrade(cfg, "head")
    db.commit()
    assert len(media_tables()) == 3


def test_migration_0027_upgrades_legacy_image_objects(db):
    """Legacy values survive normalization and later sparse compaction."""
    import json
    import uuid
    from pathlib import Path

    from alembic import command
    from alembic.config import Config

    from app.media.image_object import CANONICAL_KEYS, upgrade_legacy

    slug = f"legacy-image-{uuid.uuid4().hex[:8]}"
    region_id = db.execute(text("SELECT id FROM regions LIMIT 1")).scalar()
    db.execute(
        text(
            "INSERT INTO spots (slug, name, normalized_name, region_id, location, "
            "sports, image) VALUES (:slug, 'Legacy Image', :slug, :region_id, "
            "ST_GeogFromText('POINT(10 54)'), '{}', CAST(:image AS jsonb))"
        ),
        {
            "slug": slug,
            "region_id": region_id,
            "image": json.dumps(
                {
                    "url": "https://img/legacy.jpg",
                    "source": "upload",
                    "license": "own",
                    "credit": "Jo",
                    "focal": {"x": 20, "y": 80},
                }
            ),
        },
    )
    db.commit()

    root = Path(__file__).resolve().parents[1]
    cfg = Config(str(root / "alembic.ini"))
    cfg.set_main_option("script_location", str(root / "alembic"))
    cfg.set_main_option(
        "sqlalchemy.url", db.get_bind().engine.url.render_as_string(hide_password=False)
    )
    command.downgrade(cfg, "0026_remove_admin_totp")
    db.commit()
    command.upgrade(cfg, "head")
    db.commit()

    image = db.execute(
        text("SELECT image FROM spots WHERE slug = :slug"), {"slug": slug}
    ).scalar()
    logical = upgrade_legacy(image)
    assert set(logical) == set(CANONICAL_KEYS)
    assert logical["provider"] == "unknown"
    assert logical["delivery"] == "hosted"
    assert image["credit"] == "Jo"          # existing values win
    assert image["focal"] == {"x": 20, "y": 80}
    assert "license_url" not in image       # unknown is reconstructable

    db.execute(text("DELETE FROM spots WHERE slug = :slug"), {"slug": slug})
    db.commit()


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

    # 0014 (later) made spots.region_id nullable. Downgrading past it re-adds
    # NOT NULL, which fails whenever earlier tests in the shared DB have left
    # region-less spots behind. Wipe them first so the round-trip is really
    # testing the migration, not incidental fixture state.
    db.execute(text("DELETE FROM spots WHERE region_id IS NULL"))
    db.commit()

    command.downgrade(cfg, "0002_era5_raw_path")
    db.commit()
    assert cols() == set()  # columns gone
    command.upgrade(cfg, "head")
    db.commit()
    assert len(cols()) == 3  # and back
