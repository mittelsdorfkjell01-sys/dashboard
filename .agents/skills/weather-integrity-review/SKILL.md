---
name: weather-integrity-review
description: Review Surfwinddata changes that can alter wind values, provenance, timestamps, station use, forecast snapshots, correction composition, verification, activation gates, or the public API/frontend weather contract. Use for wind or weather pull requests, diffs, architecture reviews, and release gates, including changes under app/live, app/weather, app/forecast, related models, schemas, APIs, migrations, workflows, tests, or frontend weather consumers. Do not use for visual-only weather presentation changes that cannot affect data meaning.
---

# Weather integrity review

Protect the meaning and reproducibility of every served wind value. Treat a value as valid only when its data kind, time semantics, vector math, corrections, provenance, version, and public presentation agree across the full path.

This is a review skill. Diagnose and report; do not change code, configuration, data, pull requests, or production state unless the user explicitly asks for implementation.

## Review workflow

1. Read the repository AGENTS.md files that govern the changed paths and the weather section of docs/architecture/repository-map.md.
2. Determine the diff against the merge base or requested baseline. Use [references/repository-map.md](references/repository-map.md) to expand changed files to every affected producer, persistence layer, serving path, contract, consumer, and test. Do not limit the review to filenames containing "wind".
3. Read [references/invariants.md](references/invariants.md) completely. For each affected public wind field, record the source kind, source time, valid time, transformations, correction stages, persisted identity, public provenance, and frontend consumer.
4. Trace measurements, model nowcasts, and forecasts separately. Comments and type names are claims, not evidence; verify assignments, serialization, cache behavior, database constraints, and UI selection logic.
5. Run the narrowest relevant checks from [references/repository-map.md](references/repository-map.md). A passing existing test suite does not override a demonstrated invariant violation. Report blocked or unavailable checks as NOT_PROVEN.
6. Produce the result using [references/report-format.md](references/report-format.md). Every failure needs a stable invariant ID and concrete file-and-line evidence.

## Decision rules

- Block when a change can make a public value misleading, non-reproducible, internally inconsistent, observation-leaking, or active without the required gate.
- Treat NOT_PROVEN as blocking for data-kind separation, snapshot leakage, time semantics, vector consistency, activation governance, reproducibility, and API/frontend contract equality.
- Mark a live-observation decay rule N/A only when observations remain strictly separate from model values and forecast snapshots.
- Prefer an explicit unavailable or stale state over inferred freshness, invented model-run time, fabricated direction, or silent fallback.
- Require one correction ledger per wind value. Do not infer that two correction stages are independent merely because they live in different modules.
- A skill invocation is not automatic enforcement. Do not claim that every wind change is covered unless a repository workflow or webhook invokes this review and branch protection requires its result.

## Review boundary

Include climatology only when it feeds a served forecast, correction, station decision, or public provenance. Exclude purely editorial copy, styling, imagery, and historical climate presentation that cannot change live or forecast wind semantics.
