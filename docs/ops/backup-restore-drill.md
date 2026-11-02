# Isolated backup restore drill

This drill verifies recoverability without writing to production. Run it only
against an isolated disposable PostgreSQL/PostGIS instance with no production
network route and with credentials created for the drill.

## Preconditions

- Select a completed, non-empty `db-*.sql.gz` whose `gzip -t` check passes.
- Record the backup timestamp and source outside public logs; do not copy DSNs.
- Confirm enough isolated storage and matching PostgreSQL/PostGIS major
  versions. Decide product RPO/RTO with the operator and provider only after a
  measured drill; do not invent either target in advance.
- Use an empty drill database. Never point `DATABASE_URL` at production.

## Procedure

1. Start the isolated database and enable PostGIS.
2. Stream-decompress the selected SQL dump into `psql` with stop-on-error.
3. Read `alembic_version`; it must have one row and a revision known to the
   checked-out repository.
4. With the isolated URL set only in the process environment, run
   `alembic upgrade head`, `python -m scripts.verify_content`, and read-only
   health/catalogue checks.
5. Verify representative regions, spots, accounts, moderation records and
   media references by counts and non-sensitive samples. Do not send mail,
   notifications or provider writes.
6. Record restore time, validation time, backup age, failures and any manual
   intervention. Destroy the isolated database after the report is accepted
   under the provider's retention policy.

## Acceptance

- Restore and validation finish without ignored errors.
- The restored database reaches the expected single Alembic head.
- Content checks and read-only API smoke checks pass in isolation.
- Observed recovery-point age and elapsed recovery time are recorded. RPO/RTO
  targets are approved only after this evidence and provider capabilities are
  reviewed.

The Compose backup service writes `.last-success` only after a verified gzip
archive is atomically installed. Its healthcheck fails when the marker is older
than 26 hours, the newest dump is empty, or gzip integrity fails. Container
health must be connected to the chosen external alerting system by an operator.
