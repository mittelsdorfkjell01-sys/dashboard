# Runtime language decision

Status: accepted (2026-11-12)

## Decision

Surfwinddata keeps React/TypeScript for the browser and FastAPI/Python for the
API, workers and scientific weather pipelines. A broad Rust rewrite is not an
approved optimization.

The current bottlenecks are I/O and architecture concerns: repeated database
queries, cache freshness, provider request coalescing and oversized modules.
Changing the implementation language would not remove those costs and would
duplicate SQL, validation, geospatial and weather-provider contracts.

## When Rust may be reconsidered

A Rust component is considered only for one isolated kernel when all of these
conditions are met:

1. A repeatable production-like profile attributes at least 20% of the
   affected request or worker runtime to that CPU-bound kernel.
2. Database, network and serialization time have been measured separately.
3. The candidate has a stable, versioned input/output contract and a Python
   reference implementation with fixtures.
4. A benchmark demonstrates at least a 2x end-to-end improvement for the
   affected workload, including boundary serialization.
5. Failure falls back safely to the Python implementation and deployment does
   not introduce a second public API or schema owner.

Good candidates could be a binary field decoder or a numerically intensive
raster transform. Route handlers, SQL orchestration, cache policy and provider
clients are explicitly poor candidates.

## Review evidence

- React already provides lazy route and map-engine loading for the interactive
  dashboard and maps.
- Python owns SQLAlchemy/Pydantic contracts and the NumPy/SciPy/rasterio/eccodes
  weather toolchain.
- The prioritized performance work is set-based SQL loading and bounded caches,
  both independent of the runtime language.

Revisit this decision only with a benchmark artifact containing the baseline,
candidate, dataset, hardware, commands and correctness comparison.
