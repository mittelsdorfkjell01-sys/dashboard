#!/bin/sh
set -eu

BACKUP_DIR="${BACKUP_DIR:-/backups}"
MAX_AGE_MINUTES="${BACKUP_MAX_AGE_MINUTES:-1560}"
marker="$BACKUP_DIR/.last-success"

test -f "$marker"
find "$marker" -mmin "-${MAX_AGE_MINUTES}" -print -quit | grep -q .

latest="$(ls -1t "$BACKUP_DIR"/db-*.sql.gz 2>/dev/null | head -n 1)"
test -n "$latest"
test -s "$latest"
gzip -t "$latest"
