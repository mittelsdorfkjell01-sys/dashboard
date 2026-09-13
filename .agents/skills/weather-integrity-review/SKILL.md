---
name: weather-integrity-review
description: Review Surfwinddata changes that can alter station measurements, LiveWind, adaptive forecasts, wind values, provenance, timestamps, regional correction impulses, forecast snapshots, correction composition, verification, activation gates, or the public API/frontend weather contract. Use for wind or weather pull requests, diffs, architecture reviews, and release gates, including changes under app/live, app/weather, app/forecast, related models, schemas, APIs, migrations, workflows, tests, or frontend weather consumers. Do not use for visual-only weather presentation changes that cannot affect data meaning.
---

# Weather integrity review

Protect the meaning and reproducibility of every served wind value. Treat a value as valid only when its data kind, time semantics, vector math, corrections, provenance, version, and public presentation agree across the full path.

This is a review skill. Diagnose and report; do not change code, configuration, data, pull requests, or production state unless the user explicitly asks for implementation.

## Review workflow

1. Read the repository AGENTS.md files that govern the changed paths and the weather section of docs/architecture/repository-map.md.
2. Establish the complete review scope. For a PR or committed review, compare with the requested baseline or merge base. For a local review, include the committed delta plus staged, unstaged, and relevant untracked files unless the user explicitly restricts the scope. Exclude generated or ignored output under the repository rules.
3. Run `scripts/context.ps1 weather`. For cross-cutting architecture or blast-radius questions, query the existing Graphify graph for the changed symbols and products, then verify every claimed path with `rg`, assignments, and source code. Graph output is navigation, not evidence, and a stale graph must not hide a changed or untracked file.
4. Use [references/repository-map.md](references/repository-map.md) to expand changed files to every affected producer, persistence layer, serving path, contract, consumer, and test. Do not limit the review to filenames containing "wind".
5. Read [references/invariants.md](references/invariants.md) completely. When a public API or frontend weather consumer is affected, also read [references/display-contract.md](references/display-contract.md) completely. For each affected public wind field and forecast correction impulse, record the source kind, source time, valid time, transformations, correction stages, persisted identity, public provenance, and frontend consumer.
6. Trace measurements, model nowcasts, LiveWind, and forecasts separately. Comments and type names are claims, not evidence; verify assignments, serialization, cache behavior, database constraints, and UI selection logic.
7. Run the narrowest relevant checks from [references/repository-map.md](references/repository-map.md). A passing existing test suite does not override a demonstrated invariant violation. Report blocked or unavailable checks as NOT_PROVEN.
8. Produce the result using [references/report-format.md](references/report-format.md). Every failure needs a stable invariant ID and concrete file-and-line evidence.

## Decision rules

- Block when a change can make a public value misleading, non-reproducible, internally inconsistent, observation-leaking, or active without the required gate.
- Treat NOT_PROVEN as blocking for data-kind separation, snapshot leakage, time semantics, vector consistency, activation governance, reproducibility, and API/frontend contract equality.
- Mark observation-analysis and impulse-decay rules N/A only when observations influence neither model-derived LiveWind nor forecast values.
- Prefer an explicit unavailable or stale state over inferred freshness, invented model-run time, fabricated direction, or silent fallback.
- Require one correction ledger per wind value. Do not infer that two correction stages are independent merely because they live in different modules.
- A skill invocation is not automatic enforcement. Do not claim that every wind change is covered unless a repository workflow or webhook invokes this review and branch protection requires its result.

## Review boundary

Include climatology only when it feeds a served forecast, correction, station decision, or public provenance. Exclude purely editorial copy, styling, imagery, and historical climate presentation that cannot change live or forecast wind semantics.
