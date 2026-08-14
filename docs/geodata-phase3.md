# Geoprofile phase 3 — cache-only backfill

Status 2026-08-14: completed within the available cache boundary. The immutable plan contains 50 currently published spots in eight tile-centred batches (maximum ten); three unpublished records are excluded. The accepted five reference grids were persisted through the same idempotent shadow path. All five retain class A and 16/16 valid sectors.

The remaining 45 published spots end in `blocked_cache_missing`. No CDSE request, fallback download or substitute raster was attempted. Their independent terminal states are retained in `forecast_processing_jobs`, keyed by plan, spot and coordinate hash. A later coordinate change cannot silently reuse the plan.

The three-spot canary (Baleal, Lo Stagnone, Pozo Izquierdo) and five-spot validation passed. Reprocessing returned `skipped_identical`; older profiles are not deleted. Shadow profiles remain isolated from `publisher.py`, `physics.py` and the public API. Active public snapshot payload hashes were identical before and after the run.

Authoritative reports are `reports/geodata-backfill-plan.json` and `reports/geodata-phase3-backfill.json`. Network usage was exactly zero requests and zero bytes. Expanding beyond five spots requires explicitly provisioning the missing cache assets in a separate budgeted operation and generating a new plan.
