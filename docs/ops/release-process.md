# Release process

Surfwinddata releases one canonical repository to separate public and admin
Vercel projects. Version labels follow the project's release cadence; do not
claim semantic-versioning compatibility until API compatibility rules exist.

1. Open a PR from a task branch. Summarize behavior, migrations, operational
   steps, checks and rollback constraints.
2. Require one independent approval, resolved conversations and the protected
   backend, frontend and secrets checks. Confirm that no generated
   `frontend/tsconfig.tsbuildinfo` or secret entered the diff.
3. Add a dated entry to `CHANGELOG.md` containing user-visible changes,
   migrations, known limitations and operator actions.
4. Identify the approved commit SHA. Approve public and admin production
   deployments for that same commit; record deployment IDs privately.
5. If a migration is pending, confirm a recovery point, run the protected
   migration workflow, and require its database/API attestation.
6. Run the Public/Admin smoke checklist from the launch-readiness runbook.
   Legal review and production environment approval are independent gates.
7. Create the chosen release tag only after both deployments and smoke checks
   pass. Link the tag and commit from the release record.

Rollback application code to the last approved commit only when its schema is
compatible with the migrated database. Never run an automatic Alembic downgrade.
For data incidents, follow `docs/production-recovery-runbook.md` and the
provider-approved restore decision.
