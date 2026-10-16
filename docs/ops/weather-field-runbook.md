# Weather-field production runbook

This runbook covers the free, self-hosted wind and wave field pipeline. It does
not authorize measurement-based quality rollout; that evidence phase remains
separate.

## Required services and configuration

The production stack must run `db`, `redis`, `app`, `maintenance-worker`,
`weather-field-worker` and `caddy`. The API, Caddy and both workers must mount
the same persistent `weather_fields` volume.

Production configuration requires:

```text
WEATHER_FIELD_PIPELINE_ENABLED=true
WEATHER_FIELD_PUBLIC_ENABLED=true
WEATHER_FIELD_AUTO_ACTIVATE=true
WAVE_FIELD_PUBLIC_ENABLED=true
RUN_MAINTENANCE_CRONS=true        # maintenance-worker only
```

The application and weather-field worker keep maintenance crons disabled; the
dedicated maintenance worker is the single scheduler owner.

## Pre-deploy checks

```powershell
docker compose -f docker-compose.yml -f docker-compose.prod.yml config -q
python -m pytest tests/test_weather_field_doctor.py tests/test_weather_field_worker.py tests/test_wave_field_pipeline.py tests/test_forecast_refresh_worker.py tests/test_forecast_publication_cache.py -q
```

Apply Alembic migrations before replacing application containers. Never point a
development process at the production database.

## Deployment and immediate proof

```powershell
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d db redis app maintenance-worker weather-field-worker caddy
docker compose -f docker-compose.yml -f docker-compose.prod.yml ps
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs --tail 200 maintenance-worker weather-field-worker
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec weather-field-worker python scripts/weather_field_doctor.py --require-public --fail-on-alert --pretty
python -m scripts.production_readiness api-smoke --require-wave-fields
```

The doctor exits `2` when a critical alert exists. It checks:

- active wind, EWAM, GWAM and NOAA GFS-Wave publications and freshness;
- manifest, asset-index and tile presence/checksums;
- failed or stalled field work;
- public spot snapshots still referencing an older EWAM/GWAM/GFS-Wave set; and
- weather-field volume usage (warning at 70%, critical at 80%).

The public smoke check requires both wave publications, loads a European wave
manifest and samples a real manifest timestamp at an arbitrary point.

## 24-hour soak

Do not declare the deployment stable from a single successful run. During the
first 24 hours:

1. Keep `weather-field-worker` healthy after its 45-minute startup allowance.
2. Confirm discovery jobs recur every three hours and the worker drains each
   immutable process job.
3. Confirm at least one replacement publication activates without removing its
   immediate rollback predecessor.
4. Confirm the following forecast-refresh cycle reports zero
   `wave_context_changed` spots after processing its bounded batches.
5. Run the doctor at the start, after each activation and at the end of the
   window; retain its JSON output with deployment logs.
6. Watch disk use, failed/stalled jobs and API errors. Do not alter measurement
   gates or fabricate validation evidence during this soak.

## Failure and rollback

- A rejected candidate has no public effect; investigate its hard gate and keep
  the previous publication active.
- For missing/corrupt assets, stop automatic activation before repair and use
  the transactional publication rollback endpoint or service operation to
  restore the retained predecessor.
- If only spot forecasts lag, keep the field publication active and let the
  bounded forecast-refresh worker drain the reported context mismatch.
- At 80% storage usage the dedicated worker automatically blocks discovery,
  processing and stalled-job recovery. It continues to admit only bounded
  retention jobs so that obsolete immutable runs can free space. Expand or
  clean the persistent volume before normal ingestion resumes automatically.

After rollback, rerun the doctor and public wave smoke check. Both must pass
before the incident is closed.
