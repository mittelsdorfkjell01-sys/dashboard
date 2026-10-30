# Launch readiness verification — 2026-10-27

The source report was treated as a lead list, not current truth. Status values
were rechecked from the repository, current GitHub configuration and read-only
public endpoints, and repository fixes were revalidated on 2026-10-28.
External state must be reverified at release time.

| Finding | Status | Priority | Owner | Acceptance |
|---|---|---:|---|---|
| Production schema | **Confirmed:** public and admin report schema outdated | P0 | Production operation | Recovery point confirmed; protected migration reaches one head; direct, pooled and API attestations match. |
| Pillow advisory | **Confirmed; repository fix prepared** | P0 | Repository | Both requirements use patched compatible release; audit and media tests pass. |
| Six Playwright failures | **Confirmed; repository fix verified:** stale copy locators and an ambiguous accessible name were corrected; 196 passed, 8 intentionally skipped | P0 | Repository | Required checks pass again on the PR's Linux CI runner. |
| Gitleaks `cabrinha_2016` | **Not reproducible:** current secrets job passes | P0 | Repository/CI | Scanner stays enabled; reopen only with a current exact finding. |
| `gear_payload` test | **Confirmed; repository fix prepared** | P0 | Repository | Serializer test passes with current DB-dependent signature. |
| Public/Admin catalogue | **Earlier split not reproduced:** both expose the same version; both schemas remain outdated | P0 | Production/Vercel | Protected DB/API attestation plus both deployments at approved commit. |
| Admin address | **Intentional:** admin uses only `dashboardsurfwind.vercel.app`; no custom domain | P1 | Vercel | Root redirects to `/admin`, build is `noindex`, and unauthenticated admin APIs reject access. |
| Vercel configuration | **Verified:** both projects have the required production keys and release build guard; no deployment was triggered by the configuration update | P1 | Vercel/release owner | Reverify after the approved commit deploys; public stays on `surfwinddata.com`, admin stays on its sole Vercel domain. |
| Wind freshness | **Active gate:** campaign runs until 2026-11-02 | P0 | Weather operations | No untriaged freshness failures; formal evaluation accepted; no automatic activation. |
| Backup loop | **Confirmed gap; repository hardening prepared** | P1 | Repository + production | Verified dump, fresh marker, healthy container, external alert and isolated restore drill. |
| Branch protection | **Partly resolved:** one review and three checks required; admins may bypass | P1 | GitHub administration | No direct push for release actors; minimal bypass; periodic ruleset verification. |
| Deployment approvals | **Confirmed gap:** GitHub Production permits self-review; Vercel-specific production environments show no protection | P1 | GitHub/Vercel administration | Independent reviewer, self-review blocked, approved branches and matching Vercel controls. |
| Monitoring | **Confirmed gap:** component health exists, central ownership does not | P1 | Production operation | Policy signals routed to an owner and tested against the runbook. |
| Coverage | **Repository gates prepared:** frontend baseline is green with enforced floors; backend runs with a provisional 73% floor and both reports are uploaded | P1 | Repository/CI | Confirm the prepared gates on the PR's Linux runner, then treat that run as the accepted baseline. |
| Release process | **Confirmed gap; repository process prepared** | P1 | Repository/release owner | Changelog, approved SHA, dual deployment evidence, rollback reference and release record. |
| Legal guard | **Confirmed in repository** | P1 | Legal/operator | Required operator fields configured; authorized reviewer explicitly sets `VITE_LEGAL_REVIEW_APPROVED=true`. |

## Coverage baseline and proposed checks

The local frontend baseline on 2026-10-27 was 51.20% lines, 47.17%
statements, 43.20% branches and 36.10% functions across 373 passing tests. The
provisional backend run reported 74% overall across `app` and `scripts`, but it
is not an accepted baseline because that run still contained two DB-backed
test failures. `npm run test:coverage` now makes the frontend measurement
repeatable.

CI now publishes frontend JSON/LCOV and backend Cobertura XML and enforces the
initial floors: frontend 50% lines, 46% statements, 42% branches and 35%
functions; backend 73%. The frontend values are the observed baseline rounded
down by about one percentage point for platform variance. Accept the backend
floor only if the PR's first green Linux run confirms the provisional 74%
baseline. Ratchet floors upward from accepted baselines; do not lower them
merely to merge a regression.

## External operations in safe order

1. Obtain legal and release approval; select the exact commit.
2. Verify and record a restorable recovery point outside workflow logs.
3. Review the preflight current-to-target range, especially `0084` and `0085`
   if pending.
4. Approve the protected migration workflow; do not migrate from a developer shell.
5. Require direct/pooled schema and catalogue attestation, then public API smoke.
6. Deploy public and admin from the same commit and compare their attestations.
7. Confirm public admin routes are absent; confirm admin unauthenticated routes
   reject access and an authorized login can read the admin summary.
8. Verify the Vercel admin address, TLS, `noindex` directive and authenticated routing.
9. Execute the isolated restore drill; approve RPO/RTO only from evidence.
10. Enable independent approvals, monitoring ownership and backup alerts. Finish
    the wind evaluation before enabling measurement-based corrections.

The unused `kjellmittelsdorf.de` team-domain object was removed through the
Vercel API on 2026-10-30 and its absence was verified against the complete team
domain list. This Vercel cleanup is separate from any registrar contract that
may exist outside Vercel.

## Launch decision

**No-Go until the named P0 gates pass.** Green CI is necessary but does not
replace recovery readiness, dual-deployment attestation, DNS/TLS, authorized
smoke tests, legal approval or the wind-measurement launch gate.
