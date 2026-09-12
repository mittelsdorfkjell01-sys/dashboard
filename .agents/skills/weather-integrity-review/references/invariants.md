# Wind integrity invariants

Apply every affected invariant. Use PASS, FAIL, WARN, N/A, or NOT_PROVEN. Missing evidence is never a pass.

## Product contract

- **Station measurement:** a quality-controlled, unit-normalized observation from one public station without model or terrain correction, including station identity and location, observation time, distance, quality, and source.
- **LiveWind:** multi-model current wind plus a regionally analyzed current measurement error plus local physical corrections.
- **Adaptive forecast:** multi-model forecast plus local physical corrections plus a quality-gated regional correction impulse that is frozen at publication and decays with forecast lead time.

These are separate public products even when one product supplies evidence for another. A derived correction never turns a station observation into a forecast sample.

## WIR-001 — Data-kind separation

- Keep station measurement, LiveWind, and adaptive forecast as distinct data products.
- If a public aggregate combines them, expose the kind and per-field provenance explicitly.
- A station value must not overwrite model speed, gust, or direction while leaving model u/v, spread, trend, classification, timestamps, or confidence attached.
- Measurement residuals may influence LiveWind or an adaptive forecast only through an explicitly versioned regional vector analysis with its own confidence and uncertainty.
- Caches, serializers, schemas, and frontend normalization must preserve the distinction.
- Fail hybrids and labels that imply a model value is measured, or a measurement is forecast.

## WIR-002 — No direct or future observation leakage into forecasts

- Raw station values must never become forecast samples or directly overwrite a forecast member.
- A published forecast may contain a derived regional vector impulse only when its observation cutoff is no later than this system's forecast generation/publication time, its quality policy and analysis version are recorded, and its lead-time decay is frozen with the publication.
- Later observations must never mutate an already published forecast snapshot. Historical backtests must reconstruct the information that was available at the original publication cutoff.
- Observation-trained calibration may appear only through an immutable version whose training cutoff is earlier than the forecast generation/publication time.
- Training, activation evaluation, and later verification must use explicitly separated cohorts.
- Private lineage may reference contributing station observations, but the served forecast value and public provenance must identify the derived analysis rather than present a station value as forecast.
- Inspect the serialized snapshot and persisted payload, not only the producer interface or final scalar value.

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
- age, distance, elevation difference, terrain similarity, coastal setting, wind sector, exposure, installation quality, and known station problems considered where available;
- every available relevance dimension represented in weights when a station affects LiveWind, a regional forecast impulse, or calibration;
- multiple observations selected deterministically, deduplicated, and tied to stable station identity.

Stations must not overwrite one another. Conflicting eligible observations must reduce confidence or increase uncertainty instead of being hidden by winner-takes-all selection. Never rely on incidental database order. Verification and calibration station pools require the same explicit eligibility policy or a documented stricter one.

## WIR-006 — Regional observation analysis and temporal decay

When observations affect a model-derived value, first combine eligible station residuals into a versioned regional vector analysis. Preserve each station's independent contribution and the uncertainty created by disagreement.

- LiveWind may use the current analyzed error with reliability bounded by observation age and quality.
- An adaptive forecast may use a correction impulse derived from that analysis, frozen at publication and applied through u/v components.
- Forecast impulse magnitude must be monotonically non-increasing with forecast lead time and reach zero at the configured maximum horizon. Persistent, separately validated terrain and model corrections may continue beyond that horizon.
- Record the analysis version, observation cutoff, decay-rule version, confidence/uncertainty, and internal lineage to contributing observations.
- New publications must omit observations as soon as freshness or eligibility fails; existing immutable publications remain unchanged for honest verification.
- Never copy a raw observation into a forecast or recompute an old snapshot with newer observations.

Mark this invariant N/A only when WIR-001 proves that no observation adjusts model-derived LiveWind or forecast values.

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
- regional analysis version, observation cutoff, impulse confidence/uncertainty, and lead-time decay-rule version when an adaptive correction is present;
- issue, capture, generation, valid, and expiry times;
- the complete forecast valid-time axis.

Verification rows must reference that publication identity and a fixed cohort. Do not call a cache timestamp a provider issue time. Distinguish a theoretical replay from a forecast proven to have been published.

## WIR-010 — API/frontend contract equality

Compare all four layers: serialized backend response/OpenAPI, frontend types, normalization/adapters, and rendered consumers/fixtures.

Require equality for wind speed, gust, direction, u/v, data kind, provenance, timestamps, stale state, correction state, availability, and source maps. Fail a frontend field that is silently dropped, defaulted to a different meaning, or paired with a source/timestamp from another value. Prefer generated types or an automated structural comparison where practical.
