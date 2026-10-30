# Changelog

This file records release-relevant changes. A dated section becomes a release
record only after the referenced commit, deployments and operational gates are
approved.

## Unreleased

### Fixed

- Updated the image-processing dependency to the patched Pillow 13.0.0 release.
- Repaired six stale/ambiguous Playwright assertions around the spot locator and
  safety/location guidance.
- Updated the public score-contract test for the current DB-aware gear serializer.

### Operations

- Kept the admin deployment on `dashboardsurfwind.vercel.app` only, added an
  admin-build `noindex` directive and verified that the public build contains
  no admin bundle.
- Added read-only backtest, infrastructure and Vercel configuration status
  commands that never print environment values or mutate hosted services.
- Added frontend and backend coverage floors plus publishable CI artifacts.
- Added direct/pooled/API schema and catalogue attestation to the protected
  migration workflow.
- Made backup success observable and prevented a failed `pg_dump` from being
  hidden by a successful gzip process.
- Separated observation, receipt and processing timestamps in the Europe wind
  campaign monitor and made its 180-minute limit explicit.
- Added launch-readiness, monitoring, restore-drill and release runbooks.

### Required before release

- Complete the external P0 gates in
  `docs/ops/launch-readiness-2026-10-27.md`; this entry is not a launch approval.
