import os

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from app.api import (
    account,
    admin,
    admin_tides,
    admin_moderation,
    admin_users,
    auth,
    community,
    regions,
    search,
    spots,
)
from app.config import get_settings
from app.csrf import CSRFMiddleware
from app.security_headers import SecurityHeadersMiddleware

settings = get_settings()
EXPECTED_DB_REVISION = "0026_remove_admin_totp"

app = FastAPI(title=settings.api_title, debug=settings.api_debug)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(CSRFMiddleware)


@app.on_event("startup")
def _bootstrap_admin_user() -> None:
    """Create the first admin from ADMIN_BOOTSTRAP_* if no AdminUser exists.

    Best-effort and idempotent: a missing DB or unset settings is a no-op, so the
    app still starts (e.g. in a broken-DB state a health check can report it).
    """
    if not settings.enable_admin_api:
        return  # public deployment: no back office, no bootstrap
    try:
        from app.auth.service import bootstrap_admin
        from app.db.session import SessionLocal

        db = SessionLocal()
        try:
            user = bootstrap_admin(db)
            if user is not None:
                print(f"[bootstrap] created initial admin: {user.email}")
        finally:
            db.close()
    except Exception as exc:  # never let bootstrap crash startup
        print(f"[bootstrap] skipped ({type(exc).__name__}: {exc})")


@app.on_event("startup")
def _start_featured_warmup() -> None:
    """Keep the featured "Top Spots" cache warm from inside the app process, so no
    visitor pays the cold forecast-fetch cost on the request path.

    A daemon thread (no extra container — lean on a small VPS), gated by
    FEATURED_WARMUP_ENABLED so dev/tests make no background network calls."""
    try:
        cfg = get_settings()
        if cfg.featured_warmup_enabled:
            from app.discovery.warmup import run_in_background

            run_in_background(interval=cfg.featured_warmup_interval)
            print("[warmup] featured Top-Spots warm-up thread started")
    except Exception as exc:  # never let the warm-up crash startup
        print(f"[warmup] skipped ({type(exc).__name__}: {exc})")


@app.on_event("startup")
def _drain_era5_queue() -> None:
    """When ERA5 auto-processing is on, drain any pending climatology jobs in a
    background thread — so leftover queued spots get computed with no manual
    button (fully in the background)."""
    try:
        if get_settings().era5_autoprocess:
            from app.admin.era5_worker import run_queue_in_background

            run_queue_in_background()
            print("[era5] background queue drain started")
    except Exception as exc:
        print(f"[era5] queue drain skipped ({type(exc).__name__}: {exc})")


# Let the browser SPA (Vite dev server, and any configured origins) call the API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve uploaded media (hero images) from disk at the configured URL prefix —
# ONLY in local mode. With media_backend="blob" images live in Vercel Blob and
# are referenced by absolute URLs, and the serverless filesystem is read-only, so
# creating a dir / mounting StaticFiles here would crash the app at import.
if settings.media_backend == "local":
    os.makedirs(settings.media_dir, exist_ok=True)
    app.mount(
        settings.media_url_prefix,
        StaticFiles(directory=settings.media_dir),
        name="media",
    )

# Public + community endpoints — served by every deployment.
app.include_router(spots.router)
app.include_router(regions.router)
app.include_router(search.router)
app.include_router(community.router)
# Public visitor accounts also live on the public site, so this is ungated
# (unlike the admin /auth router below).
app.include_router(account.router)

# Back office — auth + /admin* routers. Excluded on the public deployment
# (ENABLE_ADMIN_API=false) so surfwinddata.com's origin exposes no admin surface.
if settings.enable_admin_api:
    app.include_router(auth.router)
    app.include_router(admin.router)
    app.include_router(admin_tides.router)
    app.include_router(admin_users.router)
    app.include_router(admin_moderation.router)


def _check_db() -> tuple[bool, bool]:
    """Check connectivity and that the deployed code matches the DB schema."""
    try:
        from app.db.session import engine

        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            try:
                revision = conn.execute(
                    text("SELECT version_num FROM alembic_version")
                ).scalar()
            except Exception:
                return True, False
            return True, revision == EXPECTED_DB_REVISION
    except Exception:
        return False, False


def _check_redis() -> bool:
    try:
        import redis

        client = redis.Redis.from_url(
            settings.redis_url, socket_connect_timeout=1, socket_timeout=1
        )
        return bool(client.ping())
    except Exception:
        return False


@app.get("/health", tags=["meta"])
def health(response: Response) -> dict[str, str]:
    """Liveness + dependency readiness with a separate status per dependency.

    Redis is a non-critical cache: if it is down the API still serves (status
    ``degraded``, HTTP 200) so an uptime check / the proxy does not confuse a
    broken cache with a broken server. A dead DB or mismatched schema is fatal
    and returns HTTP 503.
    """
    db_ok, schema_ok = _check_db()
    redis_ok = _check_redis()
    if db_ok and schema_ok and redis_ok:
        status = "ok"
    elif db_ok and schema_ok:
        status = "degraded"
    else:
        status = "error"
        response.status_code = 503
    return {
        "status": status,
        "db": "ok" if db_ok else "down",
        "schema": "ok" if schema_ok else "outdated",
        "redis": "ok" if redis_ok else "down",
    }
