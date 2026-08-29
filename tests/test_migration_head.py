from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

from app.db.schema import EXPECTED_DB_REVISION


def test_expected_database_revision_is_the_single_alembic_head():
    root = Path(__file__).resolve().parents[1]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "alembic"))
    heads = ScriptDirectory.from_config(config).get_heads()
    assert heads == [EXPECTED_DB_REVISION], (
        f"application expects {EXPECTED_DB_REVISION!r}, Alembic heads are {heads!r}"
    )
