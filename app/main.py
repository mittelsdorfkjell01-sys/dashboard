import os

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api import (
    account,
    admin,
    admin_media,
    admin_tides,
    admin_moderation,
    admin_users,
    admin_weather,
    auth,
    community,
    cron,
    regions,
    search,
    spots,
    weather_fields,
)
from app.config import get_settings
from app.csrf import CSRFMiddleware
from app.safety import RemoteWriteGuardMiddleware
from app.security_headers import SecurityHeadersMiddleware
from app.health import check_database, check_redis

settings = get_settings()

app = FastAPI(title=settings.api_title, debug=settings.api_debug)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(CSRFMiddleware)
app.add_middleware(RemoteWriteGuardMiddleware)


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
        print(f"[bootstrap] skipped ({type(exc).__name__})")


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
        print(f"[warmup] skipped ({type(exc).__name__})")


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
app.include_router(weather_fields.router)
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
    app.include_router(admin_media.router)
    app.include_router(admin_tides.router)
    app.include_router(admin_users.router)
    app.include_router(admin_moderation.router)
    app.include_router(admin_weather.router)
    app.include_router(cron.router)


def _readiness(response: Response) -> dict[str, object]:
    """Dependency readiness with a separate status per dependency.

    Redis is a non-critical cache: if it is down the API still serves (status
    ``degraded``, HTTP 200) so an uptime check / the proxy does not confuse a
    broken cache with a broken server. A dead DB or mismatched schema is fatal
    and returns HTTP 503.
    """
    from app.db.session import engine

    database = check_database(engine)
    redis_ok, redis_error = check_redis(settings.redis_url)
    ready = database.db == "ok" and database.schema == "ok"
    if ready and redis_ok:
        status = "ok"
    elif ready:
        status = "degraded"
    else:
        status = "error"
        response.status_code = 503
    payload: dict[str, object] = {
        "status": status,
        "db": database.db,
        "schema": database.schema,
        "redis": "ok" if redis_ok else "down",
    }
    diagnostics = {
        key: value
        for key, value in {
            "db_error": database.db_error,
            "schema_error": database.schema_error,
            "redis_error": redis_error,
        }.items()
        if value is not None
    }
    if diagnostics:
        payload["diagnostics"] = diagnostics
    return payload


@app.get("/health/live", tags=["meta"])
def liveness() -> dict[str, str]:
    """Confirm only that the API process can serve requests."""
    return {"status": "ok"}


@app.get("/health/ready", tags=["meta"])
def readiness(response: Response) -> dict[str, object]:
    return _readiness(response)


@app.get("/health", tags=["meta"])
def health(response: Response) -> dict[str, object]:
    """Backward-compatible readiness response for existing external checks."""
    return _readiness(response)
