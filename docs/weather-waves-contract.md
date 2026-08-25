# Weather and waves backend contract

## Active public path

The public point forecast currently uses the Open-Meteo transition path. The direct-provider and shadow pipelines are not public forecast sources. Modelled current conditions are `nowcast`; only station or buoy records are `measurement`.

The canonical point contract is `weather-v4`. UTC instants with an explicit offset are identity. `spot_timezone` is presentation metadata and local hour numbers are never identifiers.

## Direction and wave semantics

Wind and wave directions are bearings the vector comes **from**. Direction fields use the `_from_deg` suffix in the canonical wave contract.

Wave components are separate:

- `total_wave`: combined sea state;
- `wind_sea`: locally forced sea;
- `primary_swell` and `secondary_swell`: spectral swell partitions when supplied.

Deprecated `swell`, `period`, `swell_dir`, and `swell_max` fields contain primary swell only. They are never populated from total-wave fields. Missing components remain `null`. Phase/group speed and breaking information remain unavailable without depth-aware nearshore computation.

## Spatial fields and tiles

`GET /weather-fields/{wind|waves|nearshore}` returns a publication gate. No layer is public until it has an active `weather-field-v1` manifest. A manifest records model run, valid UTC times, bounds, zooms, format, units, scaling, quality, attribution and processing version. Wind products require paired u/v layers.

Copernicus Marine is only a planned provider. Production ingestion requires credentials, licence approval, storage/CDN selection and an operating-cost decision. Test grids are permitted only in isolated tests and must never be attached to a public manifest.

## Nearshore gate

The nearshore engine is an interface and is disabled publicly. Inputs must include offshore total wave, versioned bathymetry and coastline, model configuration and a valid time. A global ~100 m bathymetry layer is not classified as surf-break accurate. Publication requires pilot-spot validation against withheld observations and explicit quality thresholds.

## Quality levels and accuracy claims

`coordinates` and `provider_point` describe provenance, not verified accuracy. Wind calibration activates only after the configured minimum matched observations. Wave calibration is not active. No wind, wave, breaking-zone or surf-accuracy claim may be made without measurement-backed holdout results.

## Operations and rollback

`GET /admin/weather/spots/{spot_id}/operations` reports point-source state, used cells, validation, jobs, active snapshot and disabled-layer reasons. Existing forecast snapshots are atomically activated and retain the prior snapshot record for rollback. Raw forecast values are not editable; operators control configuration, geometry, jobs and publication gates.

