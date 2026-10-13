from functools import lru_cache
from datetime import datetime, timezone
from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator
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
            return "postgresql+psycopg://" + url[len(scheme) :]
    return url


class Settings(BaseSettings):
    """Application configuration, sourced from environment variables / .env."""

    # `.env.local` (gitignored) overrides `.env` when present, so a developer can
    # point at the local Docker Postgres without editing the shared `.env`. A
    # missing file is silently skipped, so this is a no-op in prod/CI. OS env vars
    # still win over both.
    model_config = SettingsConfigDict(
        env_file=(".env", ".env.local"), env_file_encoding="utf-8", extra="ignore"
    )

    database_url: str = "postgresql+psycopg://surf:surf@localhost:5432/surfwind"
    database_direct_url: str | None = None
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

    # Safety valve for the remote-write guard: a non-production app pointed at a
    # remote (production-like) database refuses admin-surface writes unless this
    # is explicitly set. Keeps a dev/local session from mutating production data.
    allow_remote_writes: bool = False

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

    # Immutable weather-field data plane. Local storage keeps development free;
    # the S3-compatible backend is portable across production object stores.
    weather_field_storage_backend: Literal["local", "s3"] = "local"
    weather_field_storage_dir: str = "data/weather-fields"
    weather_field_public_base_url: str = "/weather-field-assets"
    weather_field_storage_endpoint: str = ""
    weather_field_storage_region: str = ""
    weather_field_storage_bucket: str = ""
    weather_field_storage_prefix: str = ""
    weather_field_storage_access_key: str = ""
    weather_field_storage_secret_key: str = ""
    weather_field_storage_addressing_style: Literal["auto", "path", "virtual"] = "auto"
    weather_field_pipeline_enabled: bool = False
    weather_field_public_enabled: bool = False
    weather_field_auto_activate: bool = False
    weather_field_scope_key: str = "europe-wind"
    weather_field_primary_model: str = "icon-eu"
    wave_field_scope_key: str = "europe-waves"
    wave_field_primary_model: str = "dwd-ewam"
    wave_field_fallback_model: str = "dwd-gwam"
    wave_field_extended_model: str = "noaa-gfs-wave"
    wave_field_public_enabled: bool = False
    weather_field_processing_version: str = "field-v2.1.0"
    wave_field_processing_version: str = "wave-v2.0.0"
    weather_field_forecast_hours: Annotated[list[int], NoDecode] = Field(
        default_factory=lambda: [
            *range(0, 25),
            *range(27, 73, 3),
            *range(78, 121, 6),
            *range(126, 241, 6),
        ]
    )
    wave_field_forecast_hours: Annotated[list[int], NoDecode] = Field(
        default_factory=lambda: list(range(0, 79))
    )
    wave_field_global_forecast_hours: Annotated[list[int], NoDecode] = Field(
        default_factory=lambda: list(range(0, 175, 3))
    )
    wave_field_extended_forecast_hours: Annotated[list[int], NoDecode] = Field(
        default_factory=lambda: list(range(168, 241, 3))
    )
    weather_field_worker_batch_size: int = Field(default=1, ge=1, le=4)
    weather_field_worker_poll_seconds: int = Field(default=30, ge=5, le=300)
    weather_field_series_rate_limit_per_minute: int = Field(default=30, ge=1, le=600)
    weather_field_discovery_interval_seconds: int = Field(
        default=10_800, ge=900, le=21_600
    )
    weather_field_health_interval_seconds: int = Field(
        default=900, ge=60, le=21_600
    )
    weather_field_max_attempts: int = Field(default=3, ge=1, le=10)
    weather_field_request_timeout_seconds: float = Field(default=45, ge=5, le=180)
    weather_field_max_source_bytes: int = Field(
        default=67_108_864, ge=1_000_000, le=134_217_728
    )
    weather_field_max_run_download_bytes: int = Field(
        default=1_073_741_824, ge=10_000_000, le=10_737_418_240
    )
    weather_field_retention_runs: int = Field(default=3, ge=2, le=12)
    weather_field_processing_stale_minutes: int = Field(default=45, ge=15, le=360)
    weather_field_activation_min_shadow_runs: int = Field(default=3, ge=1, le=12)
    weather_field_activation_lookback_hours: int = Field(default=30, ge=6, le=168)
    weather_field_activation_max_download_bytes: int = Field(
        default=402_653_184, ge=10_000_000, le=2_147_483_648
    )
    weather_field_activation_max_asset_bytes: int = Field(
        default=367_001_600, ge=10_000_000, le=2_147_483_648
    )
    weather_field_activation_max_processing_seconds: int = Field(
        default=300, ge=30, le=3600
    )
    weather_field_shadow_enabled: bool = False
    weather_field_shadow_profile_version: str = "field-shadow-v1"
    weather_field_shadow_pilot_config: str = "config/weather-pilot-spots.json"
    weather_field_shadow_pilot_group: Literal["core", "extension", "all"] = "core"
    weather_field_shadow_max_spots: int = Field(default=20, ge=1, le=200)
    weather_field_shadow_max_samples: int = Field(default=2000, ge=1, le=20_000)
    weather_field_shadow_max_horizon_hours: int = Field(default=72, ge=6, le=240)
    # Phase 6 is fail-closed. ``pilot``/``regional`` require an explicit
    # comma-separated region allow-list; ``europe`` still has to pass the same
    # per-spot evidence and freshness gates before it can affect a snapshot.
    weather_field_spot_rollout_stage: Literal[
        "shadow", "pilot", "regional", "europe"
    ] = "shadow"
    weather_field_spot_rollout_region_slugs: str = ""
    weather_field_spot_allow_unverified: bool = False
    weather_field_spot_min_shadow_cycles: int = Field(default=3, ge=1, le=12)
    weather_field_spot_min_shadow_samples: int = Field(default=72, ge=1, le=20_000)
    weather_field_spot_min_observations: int = Field(default=24, ge=1, le=10_000)
    weather_field_spot_evidence_lookback_hours: int = Field(
        default=168, ge=24, le=2160
    )
    weather_field_spot_max_speed_mae_ms: float = Field(default=2.0, gt=0, le=20)
    weather_field_spot_max_direction_mae_deg: float = Field(
        default=35.0, gt=0, le=180
    )
    weather_field_spot_max_gust_mae_ms: float = Field(default=3.0, gt=0, le=30)
    weather_field_spot_max_observed_speed_mae_ms: float = Field(
        default=3.0, gt=0, le=20
    )
    weather_field_spot_max_observed_direction_mae_deg: float = Field(
        default=45.0, gt=0, le=180
    )
    weather_field_spot_max_observed_gust_mae_ms: float = Field(
        default=4.0, gt=0, le=30
    )
    weather_field_spot_max_speed_regression_ms: float = Field(
        default=0.25, ge=0, le=5
    )

    # Versioned geodata cache. HTTP request handlers enqueue work only; they
    # never download a raster inline.
    geodata_cache_dir: str = "data/geodata-cache"
    geodata_max_parallel_downloads: int = 2
    geodata_max_parallel_profiles: int = 2
    geodata_max_run_bytes: int = 10_000_000
    geodata_max_daily_bytes: int = 50_000_000
    geodata_max_asset_bytes: int = 8_000_000
    geodata_max_temp_bytes: int = 20_000_000
    geodata_cache_max_bytes: int = 1_000_000_000
    geodata_download_timeout_seconds: float = 20
    geodata_analysis_timeout_seconds: float = 90
    geodata_coastal_tolerance_m: float = 250
    # Official CDSE S3 generated credentials. These are not OAuth client
    # credentials and must never be logged or persisted.
    cdse_s3_access_key: str | None = None
    cdse_s3_secret_key: str | None = None
    cdse_s3_endpoint: str = "https://eodata.dataspace.copernicus.eu"
    geodata_phase2_max_asset_bytes: int = 268_435_456
    geodata_phase2_max_run_bytes: int = 1_073_741_824
    geodata_phase2_max_daily_bytes: int = 2_147_483_648
    geodata_phase2_cache_max_bytes: int = 10_737_418_240
    geodata_phase2_max_requests: int = 200

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
    # Bounded SQLAlchemy pool for the persistent VPS process. Serverless keeps
    # using NullPool and ignores these values.
    db_pool_size: int = Field(default=10, ge=1, le=50)
    db_max_overflow: int = Field(default=10, ge=0, le=50)
    db_pool_timeout_seconds: int = Field(default=10, ge=1, le=120)
    db_pool_recycle_seconds: int = Field(default=1800, ge=60, le=86_400)
    # Redis remains primary; this caps the per-process fail-open cache too.
    cache_memory_max_entries: int = Field(default=500, ge=10, le=10_000)

    # Provider and retention jobs are opt-in while the product has no users.
    # Manual cron endpoint calls therefore fail closed unless the operator
    # explicitly enables them for a bounded measurement campaign.
    run_maintenance_crons: bool = False

    @field_validator("database_url", "database_direct_url", "test_database_url", mode="after")
    @classmethod
    def _pin_pg_driver(cls, v: str | None) -> str | None:
        return _normalize_pg_driver(v) if v else v

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

    @field_validator("live_wind_enabled_region_slugs", mode="before")
    @classmethod
    def _split_live_wind_regions(cls, v):
        if isinstance(v, str):
            return sorted({item.strip().casefold() for item in v.split(",") if item.strip()})
        return sorted({str(item).strip().casefold() for item in v if str(item).strip()})

    @field_validator(
        "weather_field_forecast_hours",
        "wave_field_forecast_hours",
        "wave_field_global_forecast_hours",
        "wave_field_extended_forecast_hours",
        mode="before",
    )
    @classmethod
    def _split_weather_field_hours(cls, value):
        if isinstance(value, str):
            value = [item.strip() for item in value.split(",") if item.strip()]
        hours = sorted({int(item) for item in value})
        if not hours or hours[0] < 0 or hours[-1] > 384:
            raise ValueError("weather field forecast hours must be between 0 and 384")
        return hours

    @model_validator(mode="after")
    def _validate_deployment_security(self):
        if self.live_wind_canary_mode and (
            self.app_env == "production" or self.database_target != "local"
            or self.live_wind_rollout_stage != "shadow"
            or not self.live_wind_force_baseline
            or self.live_wind_enabled_region_slugs
        ):
            raise ValueError("Canary requires local non-production shadow with forced baseline")
        if self.weather_observation_retry_max_seconds < self.weather_observation_retry_initial_seconds:
            raise ValueError("weather observation retry max must be >= initial backoff")
        if self.live_wind_retry_max_seconds < self.live_wind_retry_initial_seconds:
            raise ValueError("LiveWind retry max must be >= initial backoff")
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
            if self.account_smtp_host:
                if not self.account_smtp_from:
                    errors.append("ACCOUNT_SMTP_FROM is required when account SMTP is enabled")
                if not self.account_public_origin.startswith("https://"):
                    errors.append("ACCOUNT_PUBLIC_ORIGIN must use HTTPS when account SMTP is enabled")
                if not self.account_smtp_starttls:
                    errors.append("ACCOUNT_SMTP_STARTTLS must be true in production")
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
                    errors.append(
                        "BREAK_GLASS_EXPIRES_AT must be a timezone-aware ISO timestamp"
                    )
                if not self.break_glass_allowed_ips:
                    errors.append("BREAK_GLASS_ALLOWED_IPS must restrict ADMIN_KEY use")
            if errors:
                raise ValueError(
                    "Unsafe production configuration: " + "; ".join(errors)
                )
        return self

    @property
    def database_target(self) -> str:
        """``"local"``, ``"remote"`` or ``"unknown"`` for the active DATABASE_URL."""
        from app.environment import classify_db

        return classify_db(self.database_url)

    @property
    def admin_writes_blocked(self) -> bool:
        """True when admin-surface writes must be refused: a non-production app
        talking to a remote (production-like) DB, without an explicit override."""
        return (
            self.database_target == "remote"
            and self.app_env != "production"
            and not self.allow_remote_writes
        )

    def environment_summary(self) -> dict:
        """Compact banner payload for the back office."""
        return {
            "app_env": self.app_env,
            "database_target": self.database_target,
            "admin_writes_blocked": self.admin_writes_blocked,
            "allow_remote_writes": self.allow_remote_writes,
        }

    # Directory where ERA5 raw extracts (Parquet) are stored by the pipeline.
    era5_raw_dir: str = "data/era5_raw"

    # Mounted Global Wind Atlas v3 raster (per-sector Weibull A/k @10 m). Empty
    # means "not mounted": the GWA sector producer then emits only neutral
    # factors with a clear status and never invents a speed-up. Never fetched on
    # a request path.
    gwa_raster_dir: str | None = None
    # GWA layer filename template ({variable}/{height}); default is the real DTU
    # combined-layer schema. The producer enforces the 10 m height.
    gwa_raster_filename_template: str = "gwa_{variable}_{height}.tif"

    # Mounted rasters for the WP5 microscale producer (offline only, never on a
    # request path): ESA WorldCover 10 m for roughness, GLO-30 Water Body Mask
    # for the coastline/fetch. Empty means microscale stays "unavailable".
    worldcover_raster_dir: str | None = None
    glo30_wbm_raster_dir: str | None = None
    # Optional offline GLO-30 DEM tile mount used only while building rich
    # LiveWind physics candidates. Serving never downloads or opens this mount.
    glo30_dem_raster_dir: str | None = None

    # Per-model-family blend for GWA sector factors, keyed by ModelFamily value
    # (e.g. {"regional": 0.5}). Missing family = 1.0 (full factor). WP1's
    # per-family verification dials an overcorrecting family down here with no
    # code change. Effective factor = 1 + blend * (speed_factor - 1).
    wind_sector_blend: dict[str, float] = Field(default_factory=dict)

    # Rolling window (weeks) used to smooth the 52-week climatology curve
    # (wrap-around). 1 disables smoothing. 3 = ±1 week.
    climatology_smooth_weeks: int = 3
    # Vercel sends this value as ``Authorization: Bearer ...`` to the daily
    # climatology maintenance endpoint. Missing means the endpoint fails closed.
    cron_secret: str | None = None
    climatology_cron_batch_size: int = 3
    # WP1 validation harness: bounded station-observation import per cron tick and
    # the historical window scored for raw-forecast verification.
    weather_observation_cron_batch_size: int = 45
    # Only providers with an approved downstream-use policy belong in the
    # automatic production cycle.  AWC/METAR is implemented but deliberately
    # opt-in until the originating aviation-data licences are cleared.
    weather_observation_providers: Annotated[list[str], NoDecode] = [
        "dwd", "dmi", "eumetnet_esoh"
    ]
    weather_observation_retry_initial_seconds: int = Field(default=60, ge=10, le=3600)
    weather_observation_retry_max_seconds: int = Field(default=3600, ge=60, le=86400)
    weather_station_catalog_bounds: tuple[float, float, float, float] = (
        29.0, 72.0, -30.0, 45.0
    )
    weather_station_catalog_providers: Annotated[list[str], NoDecode] = [
        "dwd", "dmi", "eumetnet_esoh"
    ]
    weather_europe_campaign_station_limit: int = Field(default=240, ge=25, le=1000)
    weather_station_catalog_spot_limit: int = Field(default=100, ge=1, le=1000)
    weather_station_catalog_candidate_limit: int = Field(default=30, ge=1, le=100)
    weather_station_catalog_max_km: float = Field(default=250.0, gt=0, le=1000)
    weather_station_catalog_retry_initial_seconds: int = Field(
        default=900, ge=60, le=86400
    )
    weather_station_catalog_retry_max_seconds: int = Field(
        default=21600, ge=300, le=172800
    )
    weather_station_catalog_late_hours: int = Field(default=36, ge=2, le=168)
    weather_verification_lookback_days: int = 45

    # LiveWind station corrections are publicly enabled by product decision.
    # Every individual result still has to pass the station, vector, conflict,
    # uncertainty and correction-magnitude quality gates.  ``force_baseline``
    # remains the immediate kill switch.
    live_wind_rollout_stage: Literal[
        "shadow", "internal", "pilot", "regional", "global"
    ] = "global"
    live_wind_force_baseline: bool = False
    live_wind_canary_mode: bool = False
    # Shared persistent mount captured before observations. Missing mount fails
    # the internal exact-run shadow path closed; it never falls back to Current.
    live_wind_exact_run_cache_dir: str | None = None
    live_wind_exact_run_cache_id: str | None = None
    live_wind_exact_run_min_free_bytes: int = Field(default=5_000_000_000, ge=0)
    live_wind_exact_capture_tile_limit: int = Field(default=16, ge=1, le=200)
    live_wind_exact_point_batch_size: int = Field(default=16, ge=1, le=500)
    live_wind_exact_capture_mode: Literal["scheduled", "disabled"] = "scheduled"
    live_wind_enabled_region_slugs: Annotated[list[str], NoDecode] = []
    live_wind_cycle_minutes: int = Field(default=15, ge=5, le=60)
    live_wind_enqueue_batch_size: int = Field(default=50, ge=1, le=1000)
    live_wind_worker_batch_size: int = Field(default=25, ge=1, le=200)
    live_wind_job_max_attempts: int = Field(default=5, ge=1, le=20)
    live_wind_retry_initial_seconds: int = Field(default=30, ge=5, le=3600)
    live_wind_retry_max_seconds: int = Field(default=1800, ge=30, le=86400)
    live_wind_job_lease_seconds: int = Field(default=300, ge=30, le=3600)
    live_wind_min_station_count: int = Field(default=2, ge=1, le=20)
    live_wind_min_confidence: float = Field(default=0.20, ge=0, le=1)
    live_wind_max_conflict_index: float = Field(default=0.65, ge=0, le=1)
    live_wind_max_uncertainty_ms: float = Field(default=5.0, gt=0, le=30)
    live_wind_max_correction_ms: float = Field(default=6.0, gt=0, le=30)
    live_wind_import_late_minutes: int = Field(default=30, ge=5, le=1440)
    live_wind_job_late_minutes: int = Field(default=45, ge=5, le=1440)
    live_wind_health_window_minutes: int = Field(default=360, ge=30, le=10080)
    live_wind_health_min_analyses: int = Field(default=10, ge=1, le=10000)
    live_wind_readiness_min_days: int = Field(default=14, ge=2, le=180)
    live_wind_readiness_min_analyses: int = Field(default=500, ge=10)
    live_wind_readiness_min_wind_sectors: int = Field(default=4, ge=2, le=8)
    live_wind_readiness_max_fallback_rate: float = Field(default=0.35, ge=0, le=1)
    # Provisional public operation deliberately validates through a separately
    # agreed route, so persisted holdout and shadow-health evidence are not
    # serving prerequisites. Set both flags to true to restore the original
    # evidence-gated rollout without changing the product contract.
    live_wind_require_verification_evidence: bool = False
    live_wind_require_operational_health: bool = False
    live_wind_candidate_version: str = "regional-live-wind-uv-v2"
    live_wind_verification_context_hash: str | None = None
    live_wind_verification_min_samples: int = Field(default=500, ge=10)
    live_wind_verification_min_days: int = Field(default=14, ge=2)
    live_wind_verification_min_stations: int = Field(default=10, ge=2)
    live_wind_verification_min_uv_mae_drop_ms: float = Field(default=0.15, gt=0)
    # No scientific subgroup harm threshold has been approved yet. None keeps
    # public candidate activation closed even when aggregate evidence passes.
    live_wind_verification_max_subgroup_regression_ms: float | None = Field(default=None, ge=0)
    live_wind_verification_subgroup_policy_version: str | None = None
    # Sector activation is a scientific governance boundary, not an operator
    # convention.  These defaults are enforced again by the activation service.
    wind_sector_min_mae_drop_ms: float = Field(default=0.2, gt=0)
    wind_sector_gate_min_unique_valid_times: int = Field(default=100, ge=1)
    wind_sector_gate_min_distinct_days: int = Field(default=14, ge=2)
    wind_sector_gate_bootstrap_iterations: int = Field(default=2000, ge=200, le=20_000)
    # Spots processed per /cron/build-sectors tick (candidate writes only).
    sector_build_batch_size: int = 5

    # TTL (seconds) for cached Open-Meteo live/forecast responses (30-60 min band).
    live_cache_ttl: int = 1800
    weather_nowcast_cache_ttl: int = 300
    weather_marine_current_cache_ttl: int = 900
    weather_forecast_cache_ttl: int = 2700
    # Forecast captures are only a verification sample.  Quantising their
    # identity avoids treating every cache refresh as an independent model run.
    weather_forecast_sample_interval_hours: int = Field(default=6, ge=1, le=24)
    weather_forecast_sample_retention_days: int = Field(default=120, ge=120, le=730)
    weather_forecast_sample_retention_batch_size: int = Field(
        default=5000, ge=100, le=50_000
    )
    forecast_snapshot_retention_days: int = Field(default=7, ge=2, le=365)
    forecast_job_retention_days: int = Field(default=7, ge=2, le=730)
    forecast_failed_job_retention_days: int = Field(default=14, ge=2, le=730)
    recommendation_log_retention_days: int = Field(default=30, ge=7, le=1095)
    live_wind_job_retention_days: int = Field(default=7, ge=2, le=730)
    live_wind_failed_job_retention_days: int = Field(default=14, ge=2, le=730)
    operational_retention_batch_size: int = Field(default=5000, ge=100, le=50_000)
    # Fully assembled public responses. These avoid Postgres reads on cache hits;
    # forecast entries are additionally capped to the snapshot's valid_until.
    weather_public_live_cache_ttl: int = 300
    weather_public_forecast_cache_ttl: int = 10_800
    weather_polling_enabled: bool = False
    # Strict no-budget limits for direct-source shadow processing.
    forecast_job_batch_size: int = 3
    # A refresh cycle enqueues all due published spots but performs provider I/O
    # for only ``forecast_job_batch_size`` rows. Each spot currently needs up to
    # two free-provider requests (atmosphere + marine).
    forecast_refresh_interval_seconds: int = Field(default=1800, ge=300, le=21_600)
    forecast_refresh_request_budget: int = Field(default=200, ge=2, le=10_000)
    forecast_provider_daily_bytes: int = 250_000_000
    forecast_provider_run_bytes: int = 50_000_000
    forecast_provider_parallelism: int = 2
    forecast_raw_retention_hours: int = 18
    forecast_srtm_dir: str | None = None
    # Conservative maximum distance to Open-Meteo's selected sea cell.
    weather_marine_grid_max_km: float = 25.0

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
    app_password_min_length: int = 8
    account_public_origin: str = "http://localhost:5173"
    account_smtp_host: str | None = None
    account_smtp_port: int = 587
    account_smtp_username: str | None = None
    account_smtp_password: str | None = None
    account_smtp_from: str | None = None
    account_smtp_starttls: bool = True
    ugc_personal_data_retention_days: int = 90
    user_event_anon_retention_days: int = Field(default=180, ge=1, le=3650)
    scoring_calibration_min_profiles: int = Field(default=30, ge=5, le=10000)
    scoring_calibration_min_checkins: int = Field(default=20, ge=5, le=10000)
    scoring_social_min_group_size: int = Field(default=20, ge=5, le=10000)
    scoring_backtest_default_days: int = Field(default=90, ge=7, le=730)
    # Terminal image rows remain available to daily moderation first, then move
    # into a compressed, privacy-reduced evidence table in bounded batches.
    image_archive_retention_days: int = 180
    image_archive_batch_size: int = 250
    media_gc_grace_hours: int = 24
    media_gc_batch_size: int = 100
    media_blob_scan_batch_size: int = 250

    # Contact address surfaced by the take-down / image-report flow (Sprint C).
    takedown_contact_email: str | None = None

    # --- media picker (admin only) -----------------------------------------
    # Provider credentials for /admin/media/search. A missing key disables that
    # one tab with a clear message — it never breaks the overlay. Wikimedia and
    # Openverse work without credentials; Openverse only rate-limits harder.
    unsplash_access_key: str | None = None
    pexels_api_key: str | None = None
    openverse_client_id: str | None = None
    openverse_client_secret: str | None = None
    # Wikimedia's API policy requires a descriptive UA with a contact address;
    # a generic one gets throttled or blocked.
    wikimedia_user_agent: str = (
        "surfwinddata/1.0 (https://surfwinddata.com; admin@surfwinddata.com)"
    )
    # Upstream requests allowed per provider per clock hour. Unsplash's demo
    # tier is 50/h — the cache below is what makes that workable, not an
    # optimisation. Production access (after their review) is 5000/h.
    media_budget_per_hour: dict[str, int] = {
        "unsplash": 50,
        "pexels": 200,
        "wikimedia": 500,
        "openverse": 100,
    }
    # Warn in the response meta once a provider passes this share of its budget.
    media_budget_warn_ratio: float = 0.8
    media_search_cache_ttl: int = 86_400  # 24 h
    media_http_timeout: float = 10.0

    # Comma-separated extra terms that flag a tip/rating for review (on top of the
    # built-in spam/URL indicators). Content still publishes; it just shows up
    # flagged in the review panel. Case-insensitive substring match.
    banned_words: str = ""

    # --- Wind climatology V3 public rollout (Phase 5) -----------------------
    # Global switch for the public, read-only V3 weekly-reliability endpoint
    # and frontend module. Off by default: V2 stays the visible public
    # contract everywhere until a deployment explicitly opts in.
    wind_climatology_v3_public_enabled: bool = False
    # Optional pilot allowlist restricting which spots serve V3 publicly even
    # when the switch above is on (comma-separated spot UUIDs). Empty list =>
    # every published spot with a ready, active V3 run is eligible. This is
    # the only sanctioned pilot mechanism; never hard-code pilot spot names.
    wind_climatology_v3_public_spot_ids: Annotated[list[str], NoDecode] = []

    @field_validator(
        "weather_observation_providers",
        "weather_station_catalog_providers",
        mode="before",
    )
    @classmethod
    def _split_weather_station_providers(cls, v):
        if isinstance(v, str):
            return [item.strip().lower() for item in v.split(",") if item.strip()]
        return v

    @field_validator(
        "weather_observation_providers",
        "weather_station_catalog_providers",
        mode="after",
    )
    @classmethod
    def _validate_weather_station_providers(cls, v):
        allowed = {"dwd", "dmi", "awc_metar", "eumetnet_esoh"}
        unknown = set(v) - allowed
        if unknown:
            raise ValueError(f"unsupported weather station providers: {sorted(unknown)}")
        if len(v) != len(set(v)):
            raise ValueError("weather station providers must be unique")
        return v

    @field_validator("wind_climatology_v3_public_spot_ids", mode="before")
    @classmethod
    def _split_v3_public_spot_ids(cls, v):
        if isinstance(v, str):
            return [item.strip() for item in v.split(",") if item.strip()]
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()
