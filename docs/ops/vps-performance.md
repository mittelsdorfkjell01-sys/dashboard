# VPS performance baseline

The production Compose stack is sized for a single 4-8 GB VPS. Its defaults
bound Redis and database connections, give PostgreSQL an explicit memory model,
keep geodata on a persistent volume, and move provider, retention and cache
warmup work out of the request-serving process. An Nginx sidecar provides the
shared anonymous API cache; Caddy remains the public TLS/static entry point.

## Storage sizing

Measured workspace data at the September 2026 baseline:

- geodata cache: about 3.2 GB;
- active Neon branch: about 0.25 GB;
- application static output and source media: currently well below 1 GB;
- database backups: allow at least 14 daily compressed generations.

Do not size a server from the current 3.5 GB footprint alone. Use at least a
40 GB SSD for a small production instance; 80 GB is the recommended starting
point when Phase-2 geodata (configured for up to 10 GB), Docker image retention,
PostgreSQL growth, WAL/headroom and local backups share the host. Alert at 70%
and investigate at 80% disk utilisation.

The named volumes that must survive container replacement are `pgdata`,
`media`, `geodata`, `caddy_data` and `caddy_config`. The `api_cache` volume is
disposable and may be rebuilt. The `./backups` bind mount
must live on durable storage and should also be copied off-host.

## Runtime checks after deployment

1. Confirm `docker compose ... ps` reports `db`, `redis`, `app`, `api-cache`,
   `cache-warmup`, `maintenance-worker`, `weather-field-worker` and `caddy`
   healthy/running.
2. Confirm Redis reports the configured `maxmemory` and `allkeys-lru` policy.
3. Confirm PostgreSQL reports the configured memory values and fewer than 50
   connections under normal traffic.
4. Verify `/assets/*` responses carry a one-year immutable cache header, while
   HTML revalidates. Two anonymous requests to `/api/spots/landing` should show
   `X-Proxy-Cache: MISS` and then `HIT`; authenticated/cookie requests bypass it.
5. Watch p95 API latency, DB pool wait time, Redis evictions and free disk for
   at least one full traffic day before changing the defaults.
6. Apply Alembic migrations before switching traffic. The retention worker uses
   the indexes from `0071_retention_indexes` and removes only bounded
   batches of inactive snapshots, terminal jobs and old recommendation logs.
7. When weather fields are enabled, confirm `weather-field-worker` shares the
   `weather_fields` volume with `app` and Caddy. Its logs should show immediate
   backlog draining followed by zero-job polls; long model processing must not
   delay tasks logged by `maintenance-worker`.
8. For wave publication, verify `/api/weather-fields/waves/health` reports both
   `primary` (EWAM), `fallback` (GWAM) and `extended` (NOAA GFS-Wave) as `ok`.
   The maintenance worker logs
   their combined health every 15 minutes, while rejected replacement runs leave
   the previous active publication untouched.
9. Run `python scripts/weather_field_doctor.py --require-public --fail-on-alert`
   inside `weather-field-worker`. The same command backs its Docker healthcheck;
   operational rollout and the 24-hour soak are defined in
   `docs/ops/weather-field-runbook.md`.
