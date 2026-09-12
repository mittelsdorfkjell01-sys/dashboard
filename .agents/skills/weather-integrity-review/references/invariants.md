# Wind integrity invariants

Apply every affected invariant. Use PASS, FAIL, WARN, N/A, or NOT_PROVEN. Missing evidence is never a pass.

## WIR-001 — Data-kind separation

- Keep station measurement, LiveWind/model nowcast, and forecast as distinct data products.
- If a public aggregate combines them, expose the kind and per-field provenance explicitly.
- A station value must not overwrite model speed, gust, or direction while leaving model u/v, spread, trend, classification, timestamps, or confidence attached.
- Caches, serializers, schemas, and frontend normalization must preserve the distinction.
- Fail hybrids and labels that imply a model value is measured, or a measurement is forecast.

## WIR-002 — No observation leakage into forecast snapshots

- Forecast snapshots must not contain raw station values, station identifiers, station observation times, or live residual impulses.
- Observation-trained calibration may appear only through an immutable version whose training cutoff is earlier than the forecast issue/capture time.
- Training, activation evaluation, and later verification must use explicitly separated cohorts.
- Inspect the serialized snapshot and persisted payload, not only the producer interface.

## WIR-003 — Issue, capture, generation, and validity time

Use these meanings consistently:

- issue time: when the upstream provider/model issued the run;
- capture time: when this system obtained that source artifact;
- generation time: when this system created its derivative;
- valid time: when the value describes weather.

An unknown model-run time remains unknown. Do not substitute generation time for issue or capture time. Derive age and stale state from the actual source time. Bound snapshot expiry by source freshness; a newly generated wrapper must not rejuvenate old weather.

## WIR-004 — Vector and direction integrity

- Wind direction uses the meteorological "from" convention everywhere.
- Aggregate, interpolate, rotate, and blend through u/v components rather than scalar direction arithmetic.
- Test north wraparound, opposing vectors, interpolation, rotation, weighting, and calm wind.
- Calm wind direction is null or explicitly unavailable, never fabricated.
- Exported speed, direction, u, and v must reconstruct one another within documented tolerances.
- Calibration and verification code that claims to mirror serving must use the same vector convention and family weighting.

## WIR-005 — Station eligibility and weighting

Apply before selection or influence:

- active, approved, not blocked, representative, and acceptable provider quality;
- observation fresh enough, not too far in the future, and within a documented maximum distance;
- elevation, exposure, setting, and known station problems considered where available;
- age, distance, and quality represented in weights when a station affects live correction or calibration;
- multiple observations selected deterministically, deduplicated, and tied to stable station identity.

Never rely on incidental database order. Verification and calibration station pools require the same explicit eligibility policy or a documented stricter one.

## WIR-006 — Temporal decay of a live observation impulse

If a station residual adjusts LiveWind, the adjustment must be a versioned, bounded vector impulse that is live-only.

- Weight it by observation age and quality.
- Make its magnitude monotonically non-increasing with age and zero at the maximum horizon.
- Preserve internal lineage to the observation and rule version.
- Remove it as soon as freshness or eligibility fails.
- Never copy it into forecast snapshots.

Mark this invariant N/A only when WIR-001 proves strict separation and no observation adjusts a model-derived value.

## WIR-007 — Correction composition and double correction

Maintain one ordered correction ledger for every served wind value. Name stages such as:

1. model calibration;
2. GWA/background bias;
3. terrain or microscale transform;
4. reviewed sector correction;
5. manual override;
6. live observation impulse.

Each physical effect may be applied once. A replacement must not stack with the stage it replaces. Intentional composition requires a versioned order plus full-pipeline tests that include an untouched baseline and an independent holdout. Public provenance must name the producer that actually created the value.

## WIR-008 — Activation and governance

- Separate immutable candidate creation, evaluation, approval, and activation.
- Bind decisions to exact version/content hash and context hash.
- Require an independent holdout, non-zero central minimum improvement, and explicit regression limits.
- Record actor, reason, and timestamp.
- Activate atomically and invalidate affected snapshots/cache generations or republish.
- Rollback must select an evaluated immutable replacement.

Fail mutable in-place updates to an active calibration or a mismatch between the admin "active" threshold and the serving threshold.

## WIR-009 — Snapshot versioning and honest verification

An immutable publication record must identify the exact served product, including:

- source captures/model runs and their timestamps;
- snapshot checksum or immutable snapshot ID;
- model members and weights;
- public contract/product version;
- physics, calibration, sector, and correction-order versions;
- issue, capture, generation, valid, and expiry times;
- the complete forecast valid-time axis.

Verification rows must reference that publication identity and a fixed cohort. Do not call a cache timestamp a provider issue time. Distinguish a theoretical replay from a forecast proven to have been published.

## WIR-010 — API/frontend contract equality

Compare all four layers: serialized backend response/OpenAPI, frontend types, normalization/adapters, and rendered consumers/fixtures.

Require equality for wind speed, gust, direction, u/v, data kind, provenance, timestamps, stale state, correction state, availability, and source maps. Fail a frontend field that is silently dropped, defaulted to a different meaning, or paired with a source/timestamp from another value. Prefer generated types or an automated structural comparison where practical.
