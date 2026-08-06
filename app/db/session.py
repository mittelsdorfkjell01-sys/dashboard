import os
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

from app.config import get_settings

settings = get_settings()

# On serverless don't keep a client-side pool: each checkout
# opens and closes its own connection, and a server-side pooler (e.g. Neon's
# pooled endpoint) owns the real pooling. Otherwise use SQLAlchemy's normal pool.
#
# Neon's pooled endpoint uses transaction pooling (PgBouncer), which cannot reuse
# psycopg's server-side prepared statements across checkouts — that surfaces as
# `prepared statement "..." already exists`. Disable auto-preparation in serverless
# mode (prepare_threshold=None) so every pooled endpoint works.
_engine_kwargs: dict = {"pool_pre_ping": True, "future": True}
_running_on_vercel = os.environ.get("VERCEL") == "1"
if settings.db_serverless or _running_on_vercel:
    _engine_kwargs = {
        "poolclass": NullPool,
        "future": True,
        "connect_args": {"prepare_threshold": None},
    }

engine = create_engine(settings.database_url, **_engine_kwargs)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency yielding a scoped database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
