# Public wind-observation sources

Reviewed: 2026-09-13. This is the evidence and operating record for observation
connectors. A provider is not enabled merely because an endpoint is reachable.

## Decision

| Priority | Source | Coverage and access | Reuse evidence | Decision |
|---|---|---|---|---|
| 1 | NOAA Aviation Weather Center (AWC) METAR Data API | Official worldwide METAR/SPECI API and daily worldwide station cache; anonymous HTTPS | WMO core surface observations are exchanged “free and unrestricted”; WMO defines that as use, reuse and sharing without charge or conditions. NWS web information is public domain unless marked otherwise and may be used without charge for lawful purposes. Attribution is retained. | **Implemented as `awc_metar`**, filtered to European countries/ICAO regions. |
| 2 | EUMETNET MeteoGate E-SOH | Public OGC API EDR for European land-surface observations; anonymous access was reachable during review | The collection advertises CC BY 4.0. EUMETNET states that high-value meteorological datasets are free, openly licensed, machine-readable and available through API/bulk access. | Qualified next connector. Deferred because the requested METAR priority is now covered and one new provider was requested. |
| 3 | National services | DWD CDC and DMI Open Data already implemented | DWD and DMI provenance/terms are retained per observation. | Continue as independent sources and cross-provider evidence. |
| 4 | Private networks | Not evaluated | Per-station rights, siting and redistribution terms vary. | Not allowed until a separate legal and quality review passes. |

This is an engineering source assessment, not a transfer of ownership or a
legal opinion. If a record is explicitly marked with different source-owner
terms, those record-specific terms take precedence and the provider must be
disabled pending review.

## Primary evidence

- AWC API documentation: <https://aviationweather.gov/data/api/>. It documents
  the `/api/data/metar` and station-info endpoints, worldwide station coverage,
  JSON fields, a 400-row response maximum, 100 requests/minute, a custom
  User-Agent, once-per-minute METAR caches and a daily station cache.
- NOAA/NWS disclaimer: <https://www.weather.gov/disclaimer>. It permits lawful
  use of unmarked NWS web information without charge, forbids false ownership,
  endorsement or presenting modifications as official, and requires clients to
  respect refresh cadence and service errors.
- WMO Unified Data Policy Resolution 1:
  <https://wmo.int/wmo-unified-data-policy-resolution-res1>. Annex 1 includes
  core surface observations; Annex 4 defines free and unrestricted as use,
  reuse and sharing without charge and without conditions. Attribution is
  strongly encouraged.
- EUMETNET MeteoGate principles and HVD statement:
  <https://www.eumetnet.eu/forecasting-and-climate/>.
- MeteoGate architecture and access levels:
  <https://eumetnet.github.io/meteogate-documentation/1-overview/>.

## `awc_metar` operating contract

- Direct documented API use only; no HTML scraping and no API key.
- Per-station queries are bounded to 24 hours (three hours by default). The
  worker processes a bounded configured-station batch, so it never asks the API
  for an unbounded European dump.
- The connector sets `Surfwinddata/1.0 (+https://surfwinddata.com)` as its
  User-Agent and caps itself at 90 requests/minute below AWC's published 100.
- ETag and Last-Modified are retained and sent with conditional requests. A 304
  reuses only an already cached response. A 204 is a successful empty result.
- 429 and transient 5xx responses open a process-local exponential backoff
  (minimum 60 seconds, maximum 15 minutes, honoring a longer `Retry-After`). It
  never sleeps in a request/cron worker.
- Timeouts are 5 seconds to connect and 20 seconds overall. Exceptions contain
  only a class/status marker in operational state; response bodies and secrets
  are not persisted.
- A provider failure is isolated per station and provider. DWD/DMI stations in
  the same job continue. Replays remain idempotent through the normalized
  observation uniqueness contract.
- AWC wind and gust units are knots and are converted once to m/s at ingestion.
  `obsTime` is the observation time. The application fetch completion is
  `received_at`; normalization time is `imported_at`. AWC's own `receiptTime`
  remains upstream provenance and is not relabelled as application receipt.
- AWC does not expose the actual anemometer height or a reliable gust sampling
  period in this API. Both stay `null` rather than being guessed as 10 m or a
  particular national METAR averaging window.
- `qcField` is retained as opaque provider quality (`awc_qc:<value>`). It is not
  interpreted as an ordinal score because the public OpenAPI schema does not
  define that semantic.

## Coverage report

### Source-catalogue snapshot (2026-09-13)

The connector was exercised read-only against the official daily AWC station
cache after implementation. The European filter returned 1,176 unique
METAR-capable ICAO records across 44 country codes:

`AL=2, AT=15, BA=4, BE=21, BG=10, BY=8, CH=19, CY=5, CZ=13, DE=92, DK=32,
EE=6, ES=68, FI=34, FO=1, FR=148, GB=127, GI=1, GR=33, HR=10, HU=11,
IE=10, IS=15, IT=129, LT=4, LU=1, LV=4, MD=4, ME=3, MK=2, MT=1,
NL=32, NO=77, PL=16, PT=19, RO=19, RS=6, SE=56, SI=5, SJ=4, SK=10,
TR=75, UA=23, XK=1`.

AWC documents a typical hourly METAR cadence. All 1,176 catalogue records had
station elevation; all 1,176 lacked an explicit anemometer measurement height,
which the connector reports honestly. Provider-internal station IDs were
deduplicated during parsing. Cross-provider duplicates, empirical interval and
receipt-delay medians, and current import errors require configured database
records and are therefore intentionally not invented in this source snapshot.
The live read-only EDDH probe returned five normalized, accepted rows. No
production database was queried.

`GET /admin/weather/observation-coverage` reports the currently configured
database state without contacting a provider. It includes:

- active station records and deduplicated physical stations per country;
- median observed interval and receipt delay per provider over the last 24h;
- station identities missing elevation or measurement height;
- ICAO/WIGOS/provider/spatial duplicate groups;
- license counts and commercial-reuse metadata; and
- the latest sanitized per-station import errors and consecutive failure count.

The report cannot state production coverage until stations are configured and
the additive migration has been applied. No production database was queried or
changed during implementation.

## Selection boundary

`GET /admin/weather/spots/{spot_id}/station-selection` returns every gathered
candidate, hard exclusion reasons, component scores, policy weights, weighted
values, correlation group, total weight, normalized weight, policy version and
configuration SHA-256. It selects the measurement shown for a spot but does not
calculate LiveWind, a station correction or an adaptive forecast.

Terrain class, roughness, surface context, mountain side, exposure and historic
reliability are read from reviewed station/profile metadata. Missing evidence
receives a neutral or explicit missing-data score; it is never inferred from a
station name. The optional `wind_direction_deg` query parameter supplies the
target nowcast sector. Without it, the selector uses each current observation's
sector only for that station's versioned sector-history lookup.

Any threshold or component-weight change must bump `station-selection-v1`.
Every result includes both the complete policy snapshot and its SHA-256, so a
stored diagnostic remains checkable even if a future version changes defaults.
Sanitized import success/failure history contributes to the history component;
reviewed long-term provider/station reliability in provenance remains separate.
