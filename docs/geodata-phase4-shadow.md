# Phase 4 — internal forecast/observation shadow study

Status 2026-08-14: `collecting_with_observation_gaps`. Study cohort `swd-phase4-shadow-v1` binds the five accepted class-A profile IDs, input hashes, algorithm versions and provider run times. Forecast records are immutable “as issued”; a conflicting insert fails and an identical model run deduplicates before provider access.

The initial cycle stored separate `gfs_raw`, `consensus_uncorrected` and `consensus_geo_candidate` variants for all five spots. The candidate currently has no correction effect because phase-2 features remain diagnostic pending measurement evidence. Existing active Surfwinddata snapshots were archived as `public_baseline` where available. Missing baseline data is not invented. ICON-EU is `blocked_provider_budget`; Pozo Izquierdo is additionally `not_covered` by the verified EU bounding box.

No suitable official observation binding is yet verified for the reference spots. DWD and DMI adapters and the KNMI access seam exist, but country, coastal exposure, elevation and completeness rules prevent treating a merely nearby station as truth. Forecast collection continues; evaluation remains blocked. The implemented metrics include sample counts, speed bias/MAE/RMSE, vector error, circular direction error above weak-wind conditions, gust errors and the 14-kn event matrix across fixed lead bands.

The existing authenticated cron router exposes `POST /cron/weather-shadow`. Configure the external scheduler to call it approximately every six hours. Missed cycles remain gaps. The protected admin endpoint `GET /admin/weather/shadow-study/status` exposes sanitized status and budgets only. Public routes, forecast weights, Open-Meteo fallback, ten-day horizon and product name are unchanged.

No final scientific assessment is valid before 14–30 real collection days with representative observations. See `reports/geodata-phase4-readiness.json` and `reports/geodata-phase4-initial-cycle.json`.
