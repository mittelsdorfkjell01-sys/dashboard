from functools import lru_cache
from datetime import datetime, timezone
from typing import Annotated, Literal

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


def _normalize_pg_driver(url: str) -> str:
    """Pin Postgres URLs to the psycopg (v3) driver that this app installs.

    Managed providers (e.g. Vercel's Neon integration) hand out plain
    ``postgres://`` / ``postgresql://`` URLs. SQLAlchemy maps those to the
    psycopg2 dialect by default, but only ``psycopg[binary]`` (v3) is installed
    here — so import fails with ``No module named 'psycopg2'``. Rewrite the bare
    scheme to ``postgresql+psycopg://`` while leaving an explicitly chosen
    driver (``postgresql+asyncpg://`` etc.) untouched.
    """
    for scheme in ("postgresql://", "postgres://"):
        if url.startswith(scheme):
            return "postgresql+psycopg://" + url[len(scheme):]
    return url


class Settings(BaseSettings):
    """Application configuration, sourced from environment variables / .env."""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    database_url: str = "postgresql+psycopg://surf:surf@localhost:5432/surfwind"
    test_database_url: str = (
        "postgresql+psycopg://surf:surf@localhost:5432/surfwind_test"
    )
    redis_url: str = "redis://localhost:6379/0"

    # Production must declare both values explicitly. Admin exposure defaults to
    # off, so a missing environment variable cannot publish the back office.
    app_env: Literal["development", "test", "production"] = "development"
    deployment_mode: Literal["development", "public", "admin"] = "development"

    api_title: str = "Surfwinddate API"
    api_debug: bool = True

    # Whether this deployment exposes the back office (auth + /admin* routers) and
    # runs the admin bootstrap. True on the admin deployment (kjellmittelsdorf.de);
    # set ENABLE_ADMIN_API=false on the public deployment (surfwinddata.com) so its
    # origin serves only the public + community endpoints — no /auth, no /admin.
    enable_admin_api: bool = False

    # Browser origins allowed to call the API (CORS). The Vite dev server runs on
    # 5173 by default. NoDecode keeps pydantic-settings from JSON-parsing the env
    # var so the validator below can accept a comma-separated list too.
    cors_origins: Annotated[list[str], NoDecode] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]
    trusted_proxy_hops: int = 0

    # Where uploaded hero images are stored on disk, and the URL prefix they are
    # served from (StaticFiles mount in app.main). The stored image URL is
    # root-relative (e.g. "/media/spots/<id>/hero.jpg"); the frontend resolves it
    # against the API base.
    media_dir: str = "data/media"
    media_url_prefix: str = "/media"

    # Where uploaded images live: "local" writes to media_dir on disk (dev / VPS
    # with a persistent volume); "blob" uploads to Vercel Blob and stores the
    # returned public https URL (serverless hosts whose filesystem is ephemeral).
    media_backend: str = "local"  # local | blob
    # Vercel Blob read/write token (required when media_backend="blob").
    blob_read_write_token: str | None = None

    # Serverless DB pooling: on a short-lived serverless invocation, holding a
    # SQLAlchemy pool is wrong (connections outlive the function / exhaust the
    # server). True => NullPool (open+close per checkout); pair it with a
    # server-side pooler (e.g. Neon's pooled endpoint). False => normal pool.
    db_serverless: bool = False

    @field_validator("database_url", "test_database_url", mode="after")
    @classmethod
    def _pin_pg_driver(cls, v: str) -> str:
        return _normalize_pg_driver(v)

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, v):
        if isinstance(v, str):
            s = v.strip()
            if not s:
                return []
            if s.startswith("["):  # JSON array
                import json

                return json.loads(s)
            return [o.strip() for o in s.split(",") if o.strip()]
        return v

    @field_validator("break_glass_allowed_ips", mode="before")
    @classmethod
    def _split_ips(cls, v):
        if isinstance(v, str):
            return [item.strip() for item in v.split(",") if item.strip()]
        return v

    @model_validator(mode="after")
    def _validate_deployment_security(self):
        if self.deployment_mode == "public" and self.enable_admin_api:
            raise ValueError("Public deployments must set ENABLE_ADMIN_API=false")
        if self.deployment_mode == "admin" and not self.enable_admin_api:
            raise ValueError("Admin deployments must set ENABLE_ADMIN_API=true")

        if self.app_env == "production":
            errors: list[str] = []
            if self.deployment_mode == "development":
                errors.append("DEPLOYMENT_MODE must be public or admin")
            if self.api_debug:
                errors.append("API_DEBUG must be false")
            if not self.cookie_secure:
                errors.append("COOKIE_SECURE must be true")
            if (
                self.jwt_secret == "dev-insecure-change-me"
                or len(self.jwt_secret.encode("utf-8")) < 32
            ):
                errors.append("JWT_SECRET must be a unique secret of at least 32 bytes")
            if any(origin.startswith("http://") for origin in self.cors_origins):
                errors.append("CORS_ORIGINS must use HTTPS in production")
            if not self.password_breach_check_enabled:
                errors.append("PASSWORD_BREACH_CHECK_ENABLED must be true")
            if self.admin_key:
                try:
                    expiry = datetime.fromisoformat(
                        (self.break_glass_expires_at or "").replace("Z", "+00:00")
                    )
                    if expiry.tzinfo is None:
                        raise ValueError
                    if expiry <= datetime.now(timezone.utc):
                        errors.append("BREAK_GLASS_EXPIRES_AT must be in the future")
                except ValueError:
                    errors.append("BREAK_GLASS_EXPIRES_AT must be a timezone-aware ISO timestamp")
                if not self.break_glass_allowed_ips:
                    errors.append("BREAK_GLASS_ALLOWED_IPS must restrict ADMIN_KEY use")
            if errors:
                raise ValueError("Unsafe production configuration: " + "; ".join(errors))
        return self

    # Directory where ERA5 raw extracts (Parquet) are stored by the pipeline.
    era5_raw_dir: str = "data/era5_raw"

    # Rolling window (weeks) used to smooth the 52-week climatology curve
    # (wrap-around). 1 disables smoothing. 3 = ±1 week.
    climatology_smooth_weeks: int = 3

    # TTL (seconds) for cached Open-Meteo live/forecast responses (30-60 min band).
    live_cache_ttl: int = 1800

    # Keep the featured "aktuelle Top Spots" cache warm from inside the app process
    # (a daemon thread), so the first visitor after the daily entry expires never
    # pays the cold forecast-fetch cost. Off by default so dev/tests make no
    # background network calls; enable in a running deployment
    # (FEATURED_WARMUP_ENABLED=true). Interval bounds the worst-case cold window.
    featured_warmup_enabled: bool = False
    featured_warmup_interval: int = 1800
    # Wall-clock budget (seconds) for computing the Top-Spots ranking on a cache
    # miss. Once exceeded, remaining spots skip the live forecast fetch and use
    # cheap climatology instead — so the request stays bounded and never times out
    # behind a gateway / serverless limit. 0 disables the budget (fetch all).
    featured_compute_budget_seconds: float = 6.0

    # When true, a queued ERA5 job is processed automatically in the background
    # (on spot create and on the "ERA5 anstoßen" trigger) instead of waiting for
    # the batch runner. Off by default so tests stay deterministic; enable it in
    # a running deployment (ERA5_AUTOPROCESS=true).
    era5_autoprocess: bool = False

    # FES data is licensed, multi-gigabyte input for the external tide worker.
    # It must never point into the public media store or the Vercel function.
    tide_model_dir: str | None = None
    tide_pyfes_config: str | None = None
    tide_mask_file: str | None = None
    tide_land_geojson: str | None = None
    tide_horizon_days: int = 60
    tide_refresh_before_days: int = 14
    tide_sample_minutes: int = 5
    tide_batch_size: int = 25
    tide_max_anchor_distance_km: float = 25.0
    tide_offset_soft_limit_minutes: int = 90
    tide_offset_hard_limit_minutes: int = 360
    tide_reason_required_minutes: int = 30

    # Optional comma-separated override of the independent global models whose
    # disagreement forms the Sprint 18 consensus band (default: the DWD/NOAA/ECMWF
    # trio in app.live.models.CONSENSUS_GLOBAL_MODELS). None => use the default.
    live_consensus_models: str | None = None

    # Optional shared key guarding the /admin endpoints (X-Admin-Key header).
    # Since Sprint A this is only a **break-glass** fallback: when set, a correct
    # X-Admin-Key is accepted as an emergency admin (actor="break-glass"). The
    # regular path is the cookie session below. Default None => break-glass off.
    admin_key: str | None = None
    break_glass_expires_at: str | None = None
    break_glass_allowed_ips: Annotated[list[str], NoDecode] = []

    # --- Admin auth (Sprint A) ---------------------------------------------
    # Secret used to sign the session JWT. MUST be overridden in production; the
    # dev default only keeps local runs and tests working out of the box.
    jwt_secret: str = "dev-insecure-change-me"
    # Session lifetime (hours) — short-lived; re-login required after expiry.
    jwt_ttl_hours: int = 12
    # httpOnly cookie carrying the session JWT.
    auth_cookie_name: str = "swd_session"
    csrf_cookie_name: str = "swd_csrf"
    # Set True behind HTTPS in production so the cookie is only sent over TLS.
    cookie_secure: bool = False
    # SameSite policy for the session cookie ("lax" is right for a same-site SPA).
    cookie_samesite: str = "lax"

    # First-run bootstrap: if no AdminUser exists at startup and both are set, an
    # admin is created from these. Never hard-code a password default.
    admin_bootstrap_email: str | None = None
    admin_bootstrap_password: str | None = None
    password_breach_check_enabled: bool = False

    # --- Public accounts (visitor sign-up) ---------------------------------
    # Separate session cookie from the admin one, so a visitor account and an
    # admin session can coexist in one browser and neither can be mistaken for
    # the other. Signed with the same jwt_secret but carries a "typ":"app" claim
    # so an admin token is never accepted on the account API (and vice versa).
    app_auth_cookie_name: str = "swd_acct"
    # Visitor sessions are long-lived (people expect to stay signed in); admins
    # get the shorter jwt_ttl_hours above.
    app_jwt_ttl_hours: int = 720  # 30 days
    # Minimum password length enforced on registration / change (mirrors the FE).
    app_password_min_length: int = 12
    ugc_personal_data_retention_days: int = 90

    # Contact address surfaced by the take-down / image-report flow (Sprint C).
    takedown_contact_email: str | None = None

    # Comma-separated extra terms that flag a tip/rating for review (on top of the
    # built-in spam/URL indicators). Content still publishes; it just shows up
    # flagged in the review panel. Case-insensitive substring match.
    banned_words: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
