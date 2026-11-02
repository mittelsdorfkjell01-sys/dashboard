# Europe wind measurement 2026-10 — stopped campaign evaluation

The campaign `europe-wind-shadow-2026-10` was stopped on 2026-10-31 and is not
valid calibration evidence. This record intentionally survives deletion of its
dedicated database so the failed experiment remains auditable.

## Evidence collected

- 280 stations; 277 had observations and 279 had exact bundles.
- 57,013 observations were stored, but 53,772 (94.3%) were historical backfill
  rows. Only 3,241 were captured operationally.
- 4,791 exact bundles and 19,164 compact model points were stored.
- Only 30 observations had provably pre-observation exact overlap. They yielded
  24 degraded and 6 unavailable residuals; none was activation-eligible.
- The 24 degraded comparisons had mean vector error 1.76 m/s, median 1.33 m/s,
  p90 4.55 m/s, maximum 5.28 m/s, speed MAE 1.08 m/s and speed bias +0.44 m/s.
  The sample is too small and structurally biased for a product decision.

## Structural failures

- GitHub Actions did not sustain the intended 30-minute cadence: across 100
  recorded runs the median gap was 264 minutes and the maximum was 436 minutes.
- The workflow captured exact points for only 16 targets per cycle and did not
  produce enough forecast/observation overlap.
- Overall observation totals obscured the distinction between operational
  captures and historical backfills.
- Country metadata was missing, and station identity, representativeness and
  dependency groups were not ready for a defensible independent sample.
- There was no database heartbeat for completed campaign cycles and therefore
  no alert after two missed intervals.

## Decision

Do not use this campaign to calibrate or activate forecast corrections. Its
dedicated Neon project may be deleted after this record is committed. GitHub
Actions run history should remain as the immutable operational audit trail.
