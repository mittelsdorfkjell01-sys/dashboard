# Review output format

Lead with one verdict:

- PASS — every affected invariant is proven and required checks passed.
- PASS WITH WARNINGS — no blocking integrity failure; bounded non-blocking risks remain.
- FAIL — at least one affected blocking invariant failed.
- INCOMPLETE — required evidence or validation is unavailable. Treat as blocking for release.

## Findings

Order findings by severity.

- P0: corrupts or mislabels public wind, leaks observations into forecasts, breaks persistence, or defeats activation/governance.
- P1: can create stale, non-reproducible, double-corrected, vector-inconsistent, or frontend/backend-divergent output.
- P2: weakens observability, test coverage, or an important guardrail without a demonstrated incorrect public value.
- P3: maintainability or documentation issue with no current integrity impact.

Use this shape for every finding:

### [P1][WIR-004] Short title

- Defect: one precise claim.
- Evidence: file and line references showing the complete reachable path.
- Consequence: the user-visible, scientific, operational, or verification impact.
- Regression proof: the smallest test or fixture that would fail before the fix and pass after it.
- Remediation direction: the invariant to restore, without prescribing an unnecessary rewrite.

Do not report a merely theoretical issue as a defect unless the code shows a reachable path. Comments, names, and intended architecture are not proof.

## Scope record

State the requested baseline and whether committed changes, staged changes, unstaged changes, and relevant untracked files were included. Name any excluded paths or unavailable artifacts.

## Invariant matrix

Always include all ten rows.

| Invariant | Status | Evidence |
|---|---|---|
| WIR-001 Data-kind separation | | |
| WIR-002 Snapshot leakage | | |
| WIR-003 Time semantics | | |
| WIR-004 Vector/direction integrity | | |
| WIR-005 Station eligibility/weighting | | |
| WIR-006 Regional analysis / forecast decay | | |
| WIR-007 Correction composition | | |
| WIR-008 Activation/governance | | |
| WIR-009 Snapshot/version verification | | |
| WIR-010 API/frontend equality | | |

Use N/A only with a reason. Use NOT_PROVEN when the relevant path or test could not be inspected.

## Validation record

State exactly what was performed:

- static producer-to-consumer trace;
- unit tests and their result;
- PostgreSQL/PostGIS integration tests and their result;
- frontend typecheck/build/tests and their result;
- live provider smoke test only when authorized and safe.

Never imply a check ran when it was only inspected or recommended.

## Positive controls and residual risk

Close with:

- existing controls that materially reduce risk;
- remaining untested or operational risks;
- the smallest next action needed for a release decision.
