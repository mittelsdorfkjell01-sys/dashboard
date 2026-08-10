# Wind weather V1

## Product contract

- Coverage: Germany, the Netherlands and Denmark.
- Current values are labelled **Aktuell (berechnet)**. They are model results,
  never presented as measurements.
- Horizon: ten days. Days 1–5 contain hourly detail; days 6–10 contain only a
  coarse daily trend and uncertainty.
- V1 calculation is wind-only. Existing wave fields on the legacy `/live` and
  `/forecast` responses are a temporary compatibility facade and do not enter
  the wind calculation.
- Internal speed unit is m/s and internal time is UTC. The compatibility fields
  `wind`/`gust` are knots; `wind_ms`/`gust_ms` expose the canonical value.
- Provider responses are not stored wholesale. For spots explicitly linked to
  an official observation station, per-model hourly forecast samples are kept
  in PostgreSQL so later measurements can verify and calibrate them.

## Data flow

1. The model catalogue selects regional configurations for the coordinate plus
   independent IFS, GFS, AIFS and ICON-global families. Seamless blends are not
   counted as independent models.
2. Open-Meteo is requested server-side in UTC and m/s. Requests use bounded
   timeout, retry/backoff and an in-process quota guard.
3. Responses live for at most 15 minutes in a process-local TTL cache. A restart
   removes all cached weather.
4. Provider values are validated and local corrections are applied to each
   model before consensus.
5. Mean wind is combined in `u/v` vector space using lead-time family weights.
   AIFS is capped at 10% after missing-model renormalization.
6. Public responses contain end values, bands and quality labels. Authenticated
   `/admin/weather/spots/{id}/diagnostics` exposes volatile calculation details.
7. A configured DWD station supplies 10-minute observations. After at least 30
   matched samples per model and lead-time bucket, robust median bias correction
   and bounded error-based weight multipliers become active. Sparse data never
   changes the original forecast.

## Observation coverage and physics shadow

- DWD and DMI observation adapters require no API key. KNMI access is prepared
  through `KNMI_API_KEY`; secrets are environment-only.
- `POST /admin/weather/spots/{id}/station/auto?provider=dwd|dmi` ranks the three
  nearest wind-capable stations inside `WEATHER_STATION_MATCH_MAX_KM` and stores
  the nearest choice with its distance. Distance is only a first-stage match;
  elevation, exposure and coastal similarity must be added before bias goes live.
- Diagnostics contain a `physics_shadow` record for every spot. It recommends a
  land/sea grid preference and lists missing coast, elevation, roughness and
  reference-point inputs. It never changes wind values.
- Open-Meteo's current forecast response does not expose a trustworthy run time
  for every requested model. Samples therefore declare
  `model_run_quality=capture-time-only`; no synthetic run time is presented as
  meteorological provenance.

## Current calculation

Native 15-minute model data is preferred. Where it is absent, hourly wind is
interpolated in vector space. Gust is the maximum of the surrounding provider
windows and is never linearly interpolated. Trend compares the surrounding
hours with a 1.25 kn/h tolerance.

## Spot metadata and physics

`spot_weather_profiles` is deliberately separate from `spots.facing`; the old
field is not assumed to be a waterward coast normal. Quality tiers are:

1. `coordinates`: consensus only, no local physics.
2. `coastal`: reviewed waterward normal and coastal classification.
3. `extended`: reserved for reviewed reference points/roughness/fetch inputs.
4. `advanced`: reserved and currently disabled.

Missing metadata always lowers the tier and never produces invented values.
Conservative V1 classifies onshore/cross-shore/offshore but applies no
unvalidated physical multiplier. Advanced sector factors and direction changes
remain inactive even when legacy records contain them. Defensive caps remain
in code but are not an activation mechanism.

Every canonical spot with valid coordinates receives a non-persistent
`coordinates` configuration dynamically. No profile row, pilot entry, review,
manual UUID assignment or warm-up is required. A complete profile can add
conservative coastal classification; an incomplete profile safely falls back.

Roughness/fetch transfer, terrain shelter, nozzle/orographic effects, vertical
shear and thermal enhancement remain disabled until their formulas and
validation datasets are reviewed. In particular, no thermal constant is
invented merely to reach the allowed 3 kn cap.

## Administration

- `GET /admin/weather/spots/{id}/profile`
- `PUT /admin/weather/spots/{id}/profile`
- `GET /admin/weather/spots/{id}/diagnostics`

The profile endpoint validates tiers and coast-normal semantics. Advanced is
rejected until its meteorology has been independently validated.

## Outages

The backend has no stale fallback. If the provider is unavailable and the
process cache misses, the request fails. The frontend retains data already
loaded during the current JavaScript session, preserves its original timestamp
and marks it as not updated. Reloading the page does not restore weather from
local or session storage.

## Operations

Apply migration `0030_weather_verification` before deploying this code. The health
check expects that revision. For serverless deployments, budget calculations
must assume zero cache hits because caches are process-local and instances do
not share them. A long-running VPS process produces more predictable cache hit
rates. Open-Meteo free/non-commercial quota and attribution requirements must be
verified before every production/commercial launch.
