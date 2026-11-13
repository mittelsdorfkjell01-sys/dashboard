# Europe wave backtest

The public wave forecast and this backtest are independent. The backtest is a
shadow-only evidence pipeline: it never blocks or activates a forecast, changes
public wave values or creates a suitability rating. It uses only the existing
free DWD/NOAA fields and free Copernicus Marine observations.

## Evidence flow

```text
Copernicus wave observation CSV
  -> wave_observation_platforms + wave_observations
  -> each future DWD/NOAA wave-field run samples its native grid at active platforms
  -> immutable wave_forecast_samples survive weather-field asset retention
  -> scripts.wave_backtest matches equal physical parameters and writes a sealed report
  -> manual review may create/update DecisionSupportGate evidence later
```

Only point samples are retained. Full historical GRIB files are not duplicated,
which keeps the workflow within the existing database and object-storage budget.

## Free observation source

Use Copernicus Marine products:

- near-real-time: `INSITU_GLO_PHYBGCWAV_DISCRETE_MYNRT_013_030`;
- delayed-mode/history: `INSITU_GLO_WAV_DISCRETE_MY_013_045`.

Copernicus registration and downloads are free. Keep its credentials in the
Copernicus client configuration or process environment; never put them in this
repository or the database.

Export a normalized CSV with these columns:

```text
platform_id,platform_name,observed_at,latitude,longitude,location_class,significant_height_m,period_s,period_semantic,direction_from_deg,direction_semantic,qc_status
```

Supported Copernicus mappings:

| Source parameter | Canonical field | Semantic |
|---|---|---|
| `VHM0` / valid significant height | `significant_height_m` | combined significant height |
| `VTM10` | `period_s` | `energy_period_tm10` |
| `VTM02` | `period_s` | `spectral_period_tm02` |
| `VTPK` | `period_s` | `peak_period` |
| mean wave-from direction | `direction_from_deg` | `mean_direction_from` |

Do not rename one period type to another. NOAA `PERPW`/`DIRPW` are archived as
primary-wave semantics and therefore do not get compared with DWD `TM10`/`MWD`.

## Import

After upgrading the local database:

```powershell
$env:DATABASE_URL='postgresql+psycopg://surf:surf@localhost:5432/surfwind'
alembic upgrade head
python -m scripts.wave_observation_import observations.csv `
  --region-code north-sea `
  --source-revision copernicus-2026-11
```

Run once with `--dry-run` first. Import the European sea regions separately so
coverage gaps remain visible. Recommended region codes are `north-sea`,
`baltic`, `atlantic-ibi`, `mediterranean`, `black-sea` and `arctic-norwegian`.

Once platforms exist, every successfully processed wave-field source slice
automatically stores bilinearly collocated point samples. Disable that shadow
capture only for incident response with `WAVE_BACKTEST_ARCHIVE_ENABLED=false`.

## Evaluate

```powershell
python -m scripts.wave_backtest `
  --start 2026-11-01 `
  --end 2027-01-31 `
  --model dwd-ewam `
  --model dwd-gwam `
  --model noaa-gfs-wave `
  --output local-evidence/wave-backtest-2026-11_2027-01.json
```

The report separates model, lead bucket, sea region, location class and physical
parameter. Height uses ±0.5 m and period ±2 s as descriptive tolerances. Wave
direction is scored circularly and only when observed significant height is at
least 0.5 m. These statistics are evidence, not an automatic release decision.
The `coverage.regions` matrix lists active, sampled, observation-bearing and
actually matched platforms for every configured sea region. A region with zero
matches is a visible coverage gap, not a successful result.

Start with a 90-day shadow pilot. A full seasonal claim requires at least one
complete year and independent review. Offshore field verification does not
validate surf-break transformation; nearshore accuracy remains a separate
bathymetry and pilot-spot workflow.
