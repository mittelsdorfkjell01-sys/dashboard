# Geoprofile phase 3 — gated tile-centred backfill

Status 2026-08-12: `blocked_prerequisite`. Phase 3 has a reproducible inventory and immutable dry-run plan, but neither live pilot nor backfill was executed because an approved CDSE S3 access/secret key pair is not locally configured. WorldCover/SRTM alone cannot pass the gate.

## Official access decision

The selected repeatable path is official CDSE S3 at `https://eodata.dataspace.copernicus.eu`. Product discovery remains through the official OData catalogue, whose result supplies the S3 path. Generated S3 credentials are configured strictly as `CDSE_S3_ACCESS_KEY` and `CDSE_S3_SECRET_KEY`; OAuth client credentials are not silently treated as S3 keys. The former ambiguous `COPERNICUS_CDSE_CLIENT_*` configuration was removed.

Manual prerequisites: register/login, enable CCM interest, accept the GLO-30/GLO-90 terms, generate expiring S3 credentials in the CDSE key manager, and place them only in the local secret environment. Secrets are never returned by APIs, stored in PostgreSQL, reports or logs.

Official account quotas are account-dependent and time-dependent. Surfwinddata retains its stricter local caps; it does not encode CDSE's currently published general-user numbers as universal guarantees.

## Gate

Before execution the intended sequence is account check, one known product catalogue resolution, one smallest asset read, then the complete five-spot plan. Auth/licence failures do not retry. Unknown asset sizes and budget violations block before data bytes. With absent credentials the current run performs zero network requests.

Phase 2 cold/warm acceptance remains required: real GLO-30 DEM, WBM and quality layers for all five pilot spots; then a strict cache-only run with no network fallback, identical input hashes and identical scientific values. Until then `execution_allowed=false` for every backfill plan.

## Inventory and planner

`scripts/geodata_backfill_plan.py` snapshots the live inventory without assuming 52 records, validates coordinates and calculates a 100-km halo. Each signature contains pinned DEM/WBM/HEM/EDM/FLM 1° geocells, WorldCover v200 3° tiles, analysis CRS and Shadow algorithm. Dateline longitudes wrap before tile creation.

The deterministic greedy planner prioritises profile-free spots and then maximum shared assets. It bounds chain clusters and stages batches as three-spot canary, five-spot validation, then at most ten. Ten is a ceiling. The plan key hashes plan version, sorted spots and assets; no planning request downloads data or creates a profile.

Current snapshot: 52 eligible spots, zero excluded, seven batches (3, 5, then batches up to 10), all `blocked_provider`. Exact memberships and signatures are in `reports/geodata-backfill-plan.json`.

## Operational controls

Pure circuit-breaker rules are implemented for terminal auth/licence errors, actual bytes above 125% of plan, insufficient free storage, repeated rate/provider errors, technical failure rate above 20% after five items, hard geometry quarantine and excessive D profiles. They are covered by deterministic tests.

Execution persistence, distributed locks, per-spot transactions, pinning/quarantine and resume are intentionally not claimed as complete while the prerequisite gate prevents execution. Implementing a second speculative job architecture before observing real assets would be unsafe. Those pieces are the first follow-up after the accepted five-spot cold/warm pilot.

## Public isolation and Phase 4

Planning reads Spot and Shadow status only. It never calls publisher/physics, changes snapshots or exposes asset details publicly. Phase 4 is not started. Candidate reference types remain Baleal (open), Brouwersdam (dam/islands), Mundaka or Lo Stagnone (complex), and Pozo Izquierdo (mountain); observation-station suitability must be established later by more than distance alone.
