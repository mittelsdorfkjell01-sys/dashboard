# Public weather display contract

Read this reference only when a public API field, frontend weather adapter, or rendered weather consumer is affected.

## Product ownership

| Product | May appear | Must not appear as |
|---|---|---|
| Station measurement | A dedicated reference block under current conditions, with station identity/location, observation time, distance, quality, and source | The computed spot wind, a map flow field, a forecast sample, or a replacement for model/LiveWind provenance |
| LiveWind | Current wind maps, public live cards, and current-conditions views | A satellite/aerial locator value, static spot fact, station measurement, or future forecast hour |
| Adaptive forecast | Forecast charts/tables and a clearly selected forecast-time map state | A current measurement, current LiveWind, or silently updated historical publication |

Open-Meteo current weather is model output. Label it as a model nowcast until the full LiveWind analysis is present; never call it measured or use a station timestamp/source for it.

## Current frontend boundaries

- `frontend/src/pages/SpotDetail.tsx` fetches live/forecast weather only for the `daten` tab. The static `info` tab must stay independent of current weather.
- `frontend/src/components/LocatorMap.tsx` is the aerial/satellite-style location view. It shows location only and must not receive LiveWind, a measurement, forecast selection, wind color, or animated flow.
- `frontend/src/components/data/daten/WindSidebar.tsx` may show the computed current value and a station measurement only as separate, independently timestamped blocks.
- `frontend/src/components/SpotMap.tsx`, `frontend/src/pages/MapView.tsx`, and `frontend/src/components/SpotCard.tsx` may show LiveWind/current model analysis. A selected forecast hour may replace the computed map state only with an explicit forecast kind and valid time.
- `frontend/src/lib/spotMapReading.ts`, `frontend/src/lib/directionSnapshot.ts`, `frontend/src/lib/forecastNormalization.ts`, `frontend/src/lib/api.ts`, and `frontend/src/state/SpotDataScope.tsx` must preserve product kind and select a complete snapshot without borrowing fields from another product or time.

## Required checks

For an affected surface, prove:

1. A station measurement never changes the current computed speed, gust, direction, u/v, spread, trend, classification, timestamp, or provenance.
2. Single and batch live endpoints behave identically on cache hit and cache miss while keeping model-nowcast and measurement caches separate.
3. The data tab renders the station reference with its own observation time and source.
4. The info tab and `LocatorMap` neither fetch nor render LiveWind, station measurements, or forecasts.
5. A selected forecast hour changes the map only as one complete forecast snapshot with its own valid time and label.
