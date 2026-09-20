# LiveWind station-source register

Checked: 2026-09-18. This register describes provider documentation, **not** a
validated production station inventory. Counts and delays must be measured by the
local status report; operator-published catalogue counts may change without notice.

| Source | Wind and metadata | Timeliness / format | License and reuse | Operational decision |
| --- | --- | --- | --- | --- |
| [DWD CDC 10-minute wind](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/10_minutes/wind/DESCRIPTION_obsgermany_climate_10min_wind_en.pdf) | Germany; 10-min mean speed/direction in m/s/degrees, station location/elevation; separate [sensor metadata ZIPs](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/10_minutes/wind/meta_data/) contain dated wind measurement heights. Gusts are a [separate extreme-wind dataset](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/10_minutes/extreme_wind/DESCRIPTION_obsgermany_climate_10min_extreme_wind_en.pdf). No WIGOS/ICAO is guaranteed by the basic catalogue. | `now/` hourly refresh; `recent/` daily; `historical/` quality-checked; ZIP/semicolon text. Per-station latency and count: measure live. No authentication, undocumented fixed rate limit; bounded requests/backoff. | [CDC terms](https://opendata.dwd.de/climate_environment/CDC/Terms_of_use.txt): CC BY 4.0, including commercial reuse with attribution. Free download. | Pilot source. Import speed/direction only; do not invent gusts or sensor heights when metadata is absent. `now/` is not fully quality-checked. |
| [DMI metObs v2](https://www.dmi.dk/friedata/dokumentation/meteorological-observation-api) | Denmark, Greenland and Faroe Islands: GeoJSON station features with owner/type/elevation; `wind_speed`, `wind_dir`, `wind_max` are [documented](https://www.dmi.dk/friedata/dokumentation/meteorological-observations-data) as 10-min mean / highest 3-s mean within 10 min, nominally 10 m above terrain. Per-station sensor height may be absent; keep unknown. API carries `observed` and `created`, but `created` is not our `received_at`. | 10-min parameter cadence; API GeoJSON/JSON and bulk download; actual receipt latency must be measured. API limit/pagination documented; bounded client limit 1000. [Authentication page](https://www.dmi.dk/friedata/dokumentation/authentication) says no key since 2025-12-02. | [DMI terms](https://www.dmi.dk/friedata/dokumentation/terms-of-use): CC BY 4.0, commercial reuse permitted, source and retrieval-time attribution; fair-use bandwidth may be imposed. Free API. | Pilot source. Restrict to `country=DNK`; do not label Greenland as Denmark. Nominal 10 m is not proof of a particular sensor height. |
| [AWC METAR API](https://aviationweather.gov/data/api/) | European airports, METAR knots and coded gusts; station height available, sensor height/representativeness and legal status must be checked per source. | Usually hourly or half-hourly, sometimes special reports; API/JSON. | Per-feed downstream redistribution rights not proven here; no pilot activation. | Existing adapter retained but excluded from the two-source pilot. |
| [KNMI 10-minute in-situ observations](https://dataplatform.knmi.nl/en/dataset/10-minute-in-situ-meteorological-observations-1-0) | Netherlands and BES, land/sea/airport stations; speed, direction and other station variables in NetCDF. Station count and individual sensor heights need separate verification. | 10-minute records typically available a few minutes later; [Open Data API](https://developer.dataplatform.knmi.nl/open-data-api) lists anonymous shared quota 50/min, registered free-key quota 200/s and 1000/h. | Dataset CC BY 4.0, commercial reuse and attribution permitted; API key required, but anonymous key is possible. | Good later expansion candidate; existing KNMI adapter is not included in this pilot/cron until keys, metadata and raw revision flow are checked. |
| [EUMETNET MeteoGate](https://www.eumetnet.eu/observations/observations-data-sharing-2/) | Federation of national holdings, including SYNOP-adjacent data. | Catalogue and access policy vary by member. | Source-specific ownership/license; no blanket redistribution grant. | No connector until a concrete collection, stable endpoint and per-dataset license are verified. |

Pilot geography: German–Danish North Sea/Baltic coast and adjacent inland terrain,
53–56.5°N, 7.5–12.5°E. This intersects two official national networks, coastal
exposure and nonzero inland elevation. It is a **candidate** region, not proof of
independent station groups or LiveWind skill. The live catalogue fetched during
development returned 281 DWD wind catalogue records and 122 DMI wind-capable active
records across DMI territories; those are unfiltered provider counts, not pilot
coverage or import success. DMI records in Greenland demonstrate why country
filtering is mandatory.

Source attribution for derived output must include “Deutscher Wetterdienst (DWD)”
and, where DMI contributes, “Baseret på data fra DMI og efterfølgende bearbejdet”,
plus DMI retrieval time and CC BY 4.0 link. Public product activation remains gated
until this attribution is visible in the consuming interface.

Unknowns: provider-specific rate ceilings, actual receipt-delay distribution,
completeness per station, DWD metadata relocation history and DMI sensor height.
Neither `Open-Meteo current` nor reanalysis is a station observation.

Disposable pilot smoke on 2026-09-17 (`surfwind_pilot_v3_test`, **not** the
application database): one synthetic Kiel spot was used only as a station-search
target. Four real station records (2 DE/DWD, 2 DK/DMI), four immutable station
metadata snapshots, 349 accepted observations and 349 observation revisions
were stored, with no import errors in this retrieval. All observations have the
QC stage `accepted_for_storage`. Both DWD stations had documented
10 m sensor heights; both DMI station-specific sensor heights remained unknown.
No stations were approved, no physical/dependency groups were reviewed and zero
observations were residual-eligible. These counts are one retrieval snapshot,
not coverage or skill evidence. The DWD `now` ZIP uses the
`produkt_zehn_now_ff_...` member name; the parser test preserves this case.

Local disposable-db commands (PowerShell; never point these at production):

```powershell
$env:DATABASE_URL='postgresql+psycopg://surf:surf@localhost:5432/surfwind_pilot_v3_test'
python -m alembic upgrade head
python scripts/observation_import.py catalog --dry-run --limit 5
python scripts/observation_import.py catalog --apply --limit 5
python scripts/observation_import.py import --dry-run --limit 5
python scripts/observation_import.py import --apply --limit 5
python scripts/observation_import.py status
```

The bounded cron importer can resume observations for configured stations, and
the separate `/cron/station-catalog` job now refreshes DWD/DMI metadata. A station
import is not an approval. DWD `ETag`/`Last-Modified` validators and the validated
response body are persisted per exact resource and request variant in PostgreSQL.
A throttling
response waits for the next cron cycle with bounded jittered scheduling.
The common selector has separate `measurement` and `residual` purposes:
an approved reference measurement may remain visible without gaining residual
or holdout eligibility. Forecast values are not changed by this importer.
Identity, exposure, license, completeness and scoped approvals require an authorised
review. `received_at` is the first local fetch; historical backfills cannot be
retroactively available to an older analysis cutoff. Old pre-0060 observations
remain stored but are not eligible for the stricter residual/Holdout path. A
normal idempotent replay does **not** rewrite their QC history; only new
observations after metadata/identity review can pass the new gate. Scoped
approval requires an explicitly configured versioned temporal-quality policy;
no threshold is silently inferred from the first pilot observations.

Capture origin and LiveWind freshness are separate. A sample fetched by a
previously running collector remains `captured_operationally` even when provider
publication took 34 minutes; its actual latency remains in the provider and
qualification statistics, while `live-observation-freshness-v1` rejects it for
the 30-minute LiveWind input role. The first bootstrap poll is backfill, and
missing job/epoch/first-receipt proof stays `availability_unproven`.
A separately audited historical reprocessing policy is still missing. Do not
migrate the local `surfwind` database at 0056 as part of this pilot.

## Qualification pilot snapshot, 2026-09-18

[DMI documents](https://www.dmi.dk/friedata/dokumentation/meteorological-observation-api)
that `status=Active` without a datetime filter includes formerly active
stations. Its `operationTo` is therefore checked; a past value marks the
record inactive. DWD dated wind-sensor heights are current only when the
official `Von_Datum`–`Bis_Datum` interval covers the retrieval day. An expired
sensor row stays in raw provenance but cannot establish a current height.

The disposable `surfwind_pilot_v3_test` database was upgraded from `0060` to
`0061`. The configurable 53–56.5°N, 7.5–12.5°E catalog fetch found 42 DWD
and 49 DMI records, including 1 and 6 inactive/historically-active records.
For one synthetic Kiel search spot, 20 active candidates per provider were
selected within 250 km. Two import cycles per provider stored 3,675 new rows
in their first cycles (2,606 DWD; 1,069 DMI) and zero in the immediate
second cycles; three DMI raw rows were rejected. Earlier smoke rows remain.
At 00:09 UTC, 4,004 observations fell in the previous 24 hours: 51
operationally captured, 3,606 historical backfill, 347 legacy
availability-unproven. These are transient snapshots, not 14-day coverage.
After the DMI activity-semantics fix and a later, non-immediate cycle, 73
additional current-epoch DMI rows were stored. This later capture does not
change the immediate replay result and is not evidence of long-term uptime.

After validating metadata date ranges and retiring two formerly-active DMI
records, **all 40 selected active station records have unknown current
individual wind measurement height** at this timestamp. This is an honest
source-data gap, not a reason to assume 10 m. No epoch, dependency group or
station was approved; residual and holdout yield is zero. Example dossiers
were generated: an earlier DWD dossier belongs to a superseded
metadata-validity epoch, and a current DMI dossier contains one operational
observation but remains blocked by unknown height and unreviewed groups.
A dossier is not a freigabe.

Use a dedicated local `*_test` database, not `surfwind_test` while pytest is
running. Migration `0060`, `0061` and dependent files are currently untracked
or uncommitted; until versioned together, no external runner is reproducible.

```powershell
$env:DATABASE_URL='postgresql+psycopg://surf:surf@localhost:5432/surfwind_pilot_v3_test'
python -m alembic upgrade head
python scripts/observation_import.py catalog --dry-run --limit 1 --candidate-limit 20 --max-km 250
python scripts/observation_import.py cycle --apply --limit 20 --candidate-limit 20
python scripts/observation_import.py import --apply --providers dwd --limit 20
python scripts/observation_import.py backfill --dry-run --providers dmi --limit 5
python scripts/observation_import.py pause --apply --providers dmi
python scripts/observation_import.py resume --apply --providers dmi
python scripts/observation_import.py status
python scripts/observation_import.py groups
python scripts/observation_import.py dossier --apply --station-id <uuid> --window-days 14
python scripts/observation_import.py dossier-show --station-id <uuid>
python scripts/observation_import.py approval-preview --station-id <uuid> --scope residual_source
python scripts/observation_import.py audit --station-id <uuid>
python scripts/observation_import.py readiness
```

`group-review`, `epoch-review`, `approve` and `revoke` require `--apply`, an
active admin email via `--actor`, interactive password, reason and evidence.
Approval additionally needs `--dossier-hash` and an operator-authored
`--policy-file` containing every threshold; group review requires
`--evidence-file`. No threshold template is approved in the repository.
The CLI performs bounded cycles, not an endless service. Observation and catalog
jobs have separate authenticated scheduler endpoints and schedules. The checked-in
catalog workflow remains disabled until its non-production runner, endpoint and
secret are explicitly configured. Recent provider windows and
the database watermark plus overlap protect idempotence but do not recover
an outage longer than the provider's accessible recent history. Continuous
capture and independent group review remain necessary before any Canary.
