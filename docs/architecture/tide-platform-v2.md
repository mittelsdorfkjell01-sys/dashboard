# Tide Platform v2: 10-day forecast, Europe map and gauge network

## Status and decision

This document defines the technical foundation. It does not activate a public
product or authorize unverified station data.

The product must keep four different quantities separate:

1. **Astronomical tide**: deterministic tide prediction from a harmonic/ocean
   tide model. This is the only product that can be offered consistently for a
   full ten-day horizon across European marine coasts.
2. **Total water level forecast**: astronomical tide plus meteorological surge,
   pressure, wind, river and regional hydrodynamic effects. Its horizon and
   quality vary by regional model and must never inherit the ten-day claim from
   the astronomical product.
3. **Observed water level**: a recent gauge measurement relative to the
   station's own vertical datum.
4. **Locally corrected astronomical tide**: the astronomical model adjusted by
   a validated station-derived harmonic correction at the target location.

The first public release targets a ten-day **astronomical tide forecast**. A
total-water-level forecast is an additive, separately labelled regional
product. Observations are shown as observations, not as the current tide
forecast.

## Existing foundation and required separation

The current FES2022b worker, reviewed anchors, profile revisions and public
fail-closed gate remain the spot-level foundation. The immutable publication,
object storage, series-tile and map-loading mechanisms in `app/spatial_fields/`
are reusable.

The current `weather-field-v2` contract is not reusable unchanged: it requires
a paired wind or wave vector and vector interpolation. Tide elevation is a
scalar field with different datum and interpolation rules. Tide therefore gets
a sibling `marine-field-v1` contract while sharing storage, publication,
checksums, retention, health and immutable-generation patterns.

## Product contract

### Spot forecast

`GET /spots/{spot_id}/tides?days=10` returns hourly values plus extrema for ten
UTC days. The response contains independent products rather than one blended
number:

```json
{
  "generated_at": "...",
  "timezone": "Europe/Lisbon",
  "astronomical": {
    "status": "available",
    "model": "FES2022b",
    "calibration": "none|local|regional",
    "datum": "model_datum",
    "navigational": false,
    "valid_until": "...",
    "uncertainty_minutes": 30,
    "series": [],
    "events": []
  },
  "total_water_level": {
    "status": "available|partial|unavailable",
    "model": "...",
    "datum": "...",
    "valid_until": "...",
    "series": []
  },
  "observation": {
    "status": "fresh|delayed|stale|unavailable",
    "station_id": "...",
    "observed_at": "...",
    "value_m": 0.0,
    "datum": "station_datum",
    "quality": "raw|automatic_qc|validated"
  },
  "provenance": [],
  "warnings": []
}
```

Rules:

- `astronomical.series` is hourly; event times retain the finer internal
  sampling and parabolic extrema refinement.
- The response includes the preceding and following extrema around `now`, so a
  current phase and curve can be drawn correctly.
- A station height and a model height are never added, subtracted or displayed
  on one absolute axis unless their vertical datum transformation is known.
- `navigational` remains `false`; no chart-datum or safe-depth claim is made.
- A shorter total-water-level horizon is visible as `partial`; missing hours
  are not filled with astronomical values under the same label.

### Europe map

The map has two independent layers:

- **Tide field**: model-derived relative elevation/phase over marine pixels.
- **Gauge markers**: station state and latest observation.

`marine-field-v1` variables:

- `tide_elevation_model_m`
- `tide_level_normalized` (`0` low, `1` high)
- `tide_phase_rate` (signed rate of change)
- `tide_range_model_m`
- optional `total_water_level_model_m` with an explicit model datum
- optional `non_tidal_residual_m`

The field uses immutable XYZ series tiles, scalar bilinear interpolation only
inside one connected wet mask, hourly valid times, explicit model datum, source
run, quality status and attribution. Interpolation across land or between tidal
basins is forbidden. Gauge markers come from the station API and are not baked
into field tiles.

Proposed endpoints:

- `GET /marine-fields/tides/active`
- `GET /marine-fields/tides/sample/series?lat=&lon=&days=10`
- `GET /tide-stations?bbox=&status=&freshness=`
- `GET /tide-stations/{id}`
- `GET /tide-stations/{id}/observations?from=&to=`

## Gauge-source strategy

"All freely accessible stations" is maintained as a continuously audited
provider registry, not a hard-coded promise. Providers change stations,
licences, authentication and latency. Every adapter declares terms, attribution,
discovery time, expected cadence, datum semantics and quality flags.

### Provider order

1. **Copernicus Marine In Situ NRT regional products** are the primary
   normalized European feed. They aggregate EuroGOOS and national sources and
   provide regional products for Arctic, Baltic, IBI, Black Sea,
   Mediterranean and North-West Shelf waters. Coverage is high in most
   European seas but weaker in the southern/eastern Mediterranean, Black Sea
   and Arctic.
2. **IOC Sea Level Station Monitoring Facility** is the broad near-real-time
   discovery and latency fallback. API v2 requires a free account/API key. Its
   fast data must be treated as raw until local QC has passed.
3. **EMODnet Physics** supplies European discovery, metadata and additional
   machine-to-machine access through WFS/WMS and ERDDAP.
4. **National authoritative APIs** override an aggregator when they provide
   lower latency, richer datum metadata or official forecasts. PEGELONLINE is
   the first direct adapter: it is unauthenticated, exposes stations, current
   values, recent measurements, gauge zero and some forecast series. Further
   national adapters enter only after API stability, licence, attribution and
   datum behaviour have been recorded.

Duplicate delivery is expected. The canonical identity is an operator station
and sensor, not a station name or rounded coordinate. One station can have
multiple provider aliases and sensors. Aggregator and national copies are
deduplicated but their raw provenance is preserved.

### Station persistence

Add new tables in a new Alembic revision:

- `tide_stations`: canonical operator identity, location, country, basin,
  operator, status and public eligibility.
- `tide_station_aliases`: provider key, provider station ID and source URL.
- `tide_sensors`: parameter, unit, cadence, vertical datum, gauge-zero metadata
  and active interval.
- `tide_observation_raw`: immutable provider payload hash, provider timestamps
  and retrieval evidence.
- `tide_observations`: normalized UTC observation, value in metres, datum,
  quality flags and rejection reason.
- `tide_station_health`: freshness, gaps, spikes, clock drift and current
  provider preference.
- `tide_harmonic_solutions`: immutable constituent amplitudes/phases, training
  interval, algorithm version and holdout metrics.
- `tide_correction_candidates`: regional correction version, station inputs,
  wet-connectivity graph version and verification result.
- `tide_forecast_runs`: source/model runs, horizon, assets, publication state
  and provenance.

Raw rows are append-only. Normalized observations may be superseded, never
silently rewritten. Provider aliases prevent the same physical sensor from
receiving artificial extra weight.

## Geocorrection decision

### Is it necessary?

Yes, when a station calibration or live residual is transferred to a different
location. No, when FES is evaluated directly at the target coordinate.

A nearest-station or straight-line-distance offset is not acceptable. Tidal
amplitude and phase change through channels, estuaries, islands, amphidromic
systems and shallow basins. Two close points separated by land can be less
related than two more distant points connected by the same water body.

### Correction model

The correction is constituent-based:

1. Fit harmonic constituents to quality-controlled observations. Thirty days
   is the minimum candidate window; one year is preferred for a production
   solution so seasonal and major astronomical constituents are represented.
2. Evaluate the same constituents from FES at each station.
3. Store the complex correction per constituent: amplitude ratio and phase
   difference, plus datum-independent residual statistics.
4. Transfer corrections only within one tidal basin and connected wet mask.
   Distance is shortest water-path distance over a bathymetry/coast graph, not
   haversine distance.
5. Interpolate amplitude ratio in log space and phase on the unit circle.
   Bound weights by station quality, record length, freshness, water-path
   distance and local bathymetric similarity.
6. Apply the interpolated constituent correction to the target's own FES
   constituents. Never copy a station's absolute height datum to the target.
7. Fall back to uncorrected FES whenever no correction candidate passes the
   holdout gate.

The present global/high/low minute offsets remain an editorial fallback, not
the Europe-wide correction engine.

### Live residual

`observed - astronomical` contains meteorological water level, datum offset and
sensor error. Remove the station's robust local datum bias before transfer.
Transfer a live residual only inside a validated residual region, and decay its
influence over hours. It must not be persisted across a ten-day forecast as a
constant correction. Where a regional hydrodynamic model is available, prefer
its total-water-level forecast and use gauges only for verified bias updating.

## Forecast-source strategy

- **Ten-day astronomical baseline:** FES2022b at the target or on the marine
  field grid.
- **Regional total water level:** Copernicus Marine regional physics products
  where their source horizon and variable semantics pass verification. The
  Baltic product provides a ten-day 00Z forecast; the North-West Shelf product
  currently provides seven days. Therefore a Europe-wide ten-day
  total-water-level claim is not allowed.
- **National forecast series:** may be displayed at the originating gauge as a
  provider forecast. It is not spatially transferred unless a separate
  verification programme approves it.

## Quality gates

### Observation gate

- timezone-aware UTC and strictly monotonic sensor timestamps
- declared unit and vertical datum (or explicit `unknown`)
- freshness appropriate to provider cadence
- duplicate, flat-line, impossible-rate and robust spike detection
- provider quality flags preserved and mapped, never discarded
- gap and outage state visible
- raw/uncontrolled feeds cannot be labelled validated

### Harmonic/geocorrection gate

- training and holdout periods are time-separated
- compare against uncorrected FES at every holdout station
- report high/low timing MAE, elevation RMSE, phase error by constituent,
  coverage and worst-station degradation
- leave-one-station-out tests for every correction region
- explicit estuary, island/peninsula and cross-basin barrier cases
- activation only when the correction improves median and tail error without
  material regional regressions
- immutable activation evidence; no evaluator auto-activates a candidate

### Forecast/publication gate

- complete ten-day astronomical horizon
- source run, model version, processing version and checksums
- no land values and no interpolation across disconnected wet cells
- monotonic valid times and no mixed source runs
- stale/partial products remain labelled and cannot masquerade as fresh
- station and model datum compatibility checked before combined charts

Initial candidate thresholds must be learned from a shadow campaign; they are
not invented in this design. The production quality objective should be stated
per basin and product, rather than as one Europe-wide error number.

## Delivery phases

1. **Foundation:** new contracts, station registry/schema, provider adapter
   interface, provenance and quality vocabulary. No public serving.
2. **Station inventory:** Copernicus NRT, IOC and EMODnet discovery plus the
   first national adapter. Publish an internal coverage/duplication/licence
   report.
3. **Ten-day spot forecast:** hourly FES series, extrema, correct current curve,
   uncertainty and explicit astronomical/observed separation.
4. **Europe map:** scalar marine-field pipeline, tide tiles, station markers and
   point sampling using the existing immutable publication infrastructure.
5. **Geocorrection shadow:** harmonic fitting, wet-connectivity regions,
   leave-one-station-out evaluation and admin evidence. No automatic rollout.
6. **Regional total water level:** add verified Copernicus/national products
   basin by basin with source-specific horizons.

## Definition of done for the foundation phase

- contracts represent astronomical, observed and total water level separately
- station identity and datum semantics are lossless
- provider terms and attribution are machine-readable
- duplicate providers cannot double-count one sensor
- ten-day astronomical forecast and Europe scalar-map contracts are frozen
- geocorrection can be evaluated without being automatically activated
- operational monitoring exposes provider freshness, station coverage, datum
  coverage, rejected observations and publication horizon

## Primary references

- IOC SLSMF API: https://api.ioc-sealevelmonitoring.org/
- Copernicus Marine In Situ NRT quality information:
  https://documentation.marine.copernicus.eu/QUID/CMEMS-INS-QUID-013-030-036.pdf
- EMODnet machine-to-machine services:
  https://emodnet.ec.europa.eu/en/emodnet-web-service-documentation
- PEGELONLINE REST API:
  https://pegelonline.wsv.de/webservice/dokuRestapi
- Copernicus North-West Shelf physics forecast:
  https://data.marine.copernicus.eu/product/NWSHELF_ANALYSISFORECAST_PHY_004_013/description
- Copernicus Baltic physics forecast:
  https://data.marine.copernicus.eu/product/BALTICSEA_ANALYSISFORECAST_PHY_003_006/description
- NOAA harmonic constituent explanation:
  https://tidesandcurrents.noaa.gov/about_harmonic_constituents
- NOAA reference/subordinate station corrections:
  https://tidesandcurrents.noaa.gov/noaatidepredictionshelp.html

