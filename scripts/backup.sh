#!/bin/sh
# Daily backup of the Postgres DB and the media volume, with N-day rotation.
#
# Writes to $BACKUP_DIR, which in docker-compose.prod.yml is a HOST bind mount
# (./backups) — NOT a named Docker volume — so `docker compose down -v` (which
# removes named volumes) can never delete the backups.
#
# Connection uses libpq PG* env vars (PGHOST/PGUSER/PGPASSWORD/PGDATABASE).
set -eu

BACKUP_DIR="${BACKUP_DIR:-/backups}"
MEDIA_SRC="${MEDIA_SRC:-/media}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"
ts="$(date +%Y%m%d-%H%M%S)"
plain_tmp="$BACKUP_DIR/db-${ts}.sql.tmp"
gzip_tmp="$BACKUP_DIR/db-${ts}.sql.gz.tmp"

cleanup() {
  rm -f "$plain_tmp" "$gzip_tmp"
}
trap cleanup EXIT HUP INT TERM

mkdir -p "$BACKUP_DIR"

echo "[backup] pg_dump -> db-${ts}.sql.gz"
# Write to a .tmp first, then rename, so a crash never leaves a half-written dump
# that the rotation/restore could pick up. Do not pipe pg_dump directly into
# gzip: POSIX sh has no pipefail, so gzip could hide a failed pg_dump.
pg_dump --no-owner --no-privileges --file "$plain_tmp"
test -s "$plain_tmp"
gzip -c "$plain_tmp" > "$gzip_tmp"
gzip -t "$gzip_tmp"
mv "$gzip_tmp" "$BACKUP_DIR/db-${ts}.sql.gz"
rm -f "$plain_tmp"

# Media backup — may be empty until the upload endpoint is used (Sprint 10). An
# empty/absent dir must not fail the run.
if [ -d "$MEDIA_SRC" ] && [ -n "$(ls -A "$MEDIA_SRC" 2>/dev/null || true)" ]; then
  echo "[backup] tar media -> media-${ts}.tar.gz"
  tar czf "$BACKUP_DIR/media-${ts}.tar.gz" -C "$MEDIA_SRC" .
else
  echo "[backup] media dir empty/absent — skipped"
fi

echo "[backup] rotating dumps older than ${RETENTION_DAYS} days"
find "$BACKUP_DIR" -maxdepth 1 -name 'db-*.sql.gz' -mtime +"$RETENTION_DAYS" -delete
find "$BACKUP_DIR" -maxdepth 1 -name 'media-*.tar.gz' -mtime +"$RETENTION_DAYS" -delete

date -u +%Y-%m-%dT%H:%M:%SZ > "$BACKUP_DIR/.last-success.tmp"
mv "$BACKUP_DIR/.last-success.tmp" "$BACKUP_DIR/.last-success"
echo "[backup] done ($(ls -1 "$BACKUP_DIR"/db-*.sql.gz 2>/dev/null | wc -l) db dump(s) retained)"
