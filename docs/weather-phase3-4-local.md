# Weather phases 3–4: local preparation

## Phase 3

DWD and DMI observations share a normalized UTC contract. A measurement may
replace only wind, gust and direction after the station is active, editorially
approved, unblocked and marked representative. The observation must be no more
than 30 minutes old, not materially in the future, provider-accepted and
physically plausible. Air and marine provenance always remain independent.

The import foundation batches inserts with the existing station/time unique
constraint and can publish the latest accepted value to Redis. Provider and
station failures are isolated and retries are bounded. The CLI is dry-run only.
Retention is configurable in design but no deletion is implemented: any first
production cleanup requires a separate review and approval.

Migration `0041_station_observations` is prepared and tested only against the
disposable local test database. Production migration, catalog synchronization,
coverage measurement and the ten-minute schedule are blocked until the database
limit is reset and an operator explicitly approves them.

## Phase 4

Hard boundary validation rejects non-finite and physically impossible wind,
gust, precipitation, temperature, pressure, wave and direction values. Time
axes must be strictly increasing and provider arrays aligned. One remaining
valid model is an explicitly degraded fallback, not evidence of an independent
multi-model consensus.

Rolling verification exposes wind MAE/bias, circular direction MAE and gust MAE.
Calibration now requires at least 60 training observations plus a chronological
holdout of at least 20 observations. A decision is approved only when holdout
wind MAE improves and direction quality does not regress. Decision contract:
`holdout-v1`. This prepares evaluation only; it does not activate calibration.

`python scripts/weather_monitor.py --snapshot <local-json>` evaluates a local
snapshot and emits structured, redacted JSON plus stable incident fingerprints.
No network fetch, GitHub write, database connection or schedule is included.

The final 30-day SLO targets are API availability ≥99.5%, detection ≤15 min,
≥99% atmosphere forecasts under three hours, zero unmarked stale forecasts,
zero measurements over 30 minutes as primary values, ≥99% successful observation
runs, complete public provenance and verified holdout improvement for every
activated calibration. Every target remains `pending_evidence` until 30 days of
production observations exist.

Marine comparison is available only through the pure `marine-shadow-v1`
evaluator. It records availability and height/period/direction errors without
changing public output. A second provider is not configured: availability,
licensing, attribution requirements, spatial resolution and free-use quotas
must be reviewed before any fixture adapter is connected. Consequently marine
uncertainty remains `not_determined` and no local measurement accuracy is
claimed.

## Manual steps after the database limit resets

1. Review and run the production migration through the protected readiness flow.
2. Sync station catalogs in dry-run, review candidates, then import a bounded batch.
3. Approve representative stations editorially; never bulk-approve recommendations.
4. Warm and verify Redis latest-observation keys and public provenance.
5. Measure catalog/forecast/station coverage before enabling any schedule.
6. Enable workers separately with budget, runtime and alert limits; observe a full cycle.
7. Run the monitoring command from a protected environment, then separately review
   any future GitHub issue writer and schedule before activation.
