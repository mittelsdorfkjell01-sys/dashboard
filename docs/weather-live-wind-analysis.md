# Regional LiveWind analysis

LiveWind is a separate current-wind analysis. It never overwrites the station
measurement, the model nowcast in `current`, a raw model value, or any forecast.

## Ordered calculation

```text
raw target-model consensus (u/v)
  + quality-checked station model residuals (u/v)
  -> robust regional background (u/v)
  -> reviewed local spot physics
  -> LiveWind public vector
```

The regional engine is `app/weather/live_wind_analysis.py`. It accepts only
residual vectors and has no observation-value input. `app/live/live_wind.py`
loads the latest `accepted` or `degraded` residual for each observation selected
by the versioned station selector. Residual and target model identities must
overlap; incompatible baselines receive zero weight.

## Robustness and uncertainty

- Station-selection weight is multiplied by smooth age, terrain, coast,
  elevation, air-mass, QC and uncertainty factors.
- Mountain barriers, incompatible coastal regimes and explicitly different air
  masses are excluded before aggregation.
- A robust spatial center and Tukey biweight remove isolated extreme residuals.
- Correlated station groups have a maximum share and contribute less independent
  evidence than geographically separate groups.
- Effective sample size, disagreement and model spread form a two-dimensional
  covariance. Measurement/representativeness uncertainty, station age,
  distance/geometry, terrain complexity, missing profile information and the
  correction magnitude add explicit non-negative uncertainty components.
- The public speed interval and direction uncertainty are projections of that
  covariance. Weak wind intentionally has no precise direction uncertainty.
- Low evidence shrinks continuously toward zero. Contradictory evidence falls
  back to the unchanged model baseline with an explicit cause.
- The correction magnitude uses a smooth `tanh` limiter based on both an absolute
  ceiling and the target-model speed.
- Inputs are canonically sorted, so database row order cannot change the result.

Four cache products remain separate: model nowcast, station measurement,
quality-checked station-residual bundle and final LiveWind analysis. Final keys
bind weather/input generations, model valid/capture identity, analysis version,
physics/profile version and rollout thresholds. A token-owned Redis lock (with
process-local outage fallback) prevents a stampede. New observations advance
only the LiveWind input generation; new model/profile generations invalidate
the corresponding analysis without mutating another product.

`app/weather/live_wind_verification.py` implements spatial leave-one-station-out
verification. It removes the hidden target, duplicate/dependent station IDs,
observation IDs and correlation groups before invoking the candidate. Results
use temporal blocks, country-balanced metrics, layer ablations and a day-block
bootstrap. Evidence is immutable in
`weather_live_wind_verification_evidence`; storing evidence never activates it.

Rich local-physics candidates use the offline-only contract in
`app/weather/live_wind_physics_profile.py`. Missing GLO-30, WorldCover or
geometry fields are marked `unavailable`; a missing layer is never interpreted
as neutral terrain. Candidates are persisted inactive and still require the
existing reviewed/enabled sector gate. A correction ledger rejects overlapping
model calibration, GWA/ERA5 and WP6 posterior speed-level layers.

Current analysis version: `regional-live-wind-uv-v2`.
