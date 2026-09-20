#!/usr/bin/env bash
set -euo pipefail

job="${1:-}"
repo="${LIVE_WIND_REPOSITORY_DIR:?LIVE_WIND_REPOSITORY_DIR is required}"
expected_commit="${LIVE_WIND_DEPLOYED_COMMIT:?LIVE_WIND_DEPLOYED_COMMIT is required}"
probe_sha="${LIVE_WIND_CAPTURE_PROBE_SHA256:?LIVE_WIND_CAPTURE_PROBE_SHA256 is required}"

cd "$repo"
test "$(git rev-parse HEAD)" = "$expected_commit"
git diff --quiet
git diff --cached --quiet
test -z "$(git ls-files --others --exclude-standard)"

export TZ=UTC
export LIVE_WIND_RUNNER_JOB_ID="systemd-${job}-$(date -u +%Y%m%dT%H%M%SZ)-$$"

preflight() {
  python -m scripts.exact_run_preflight \
    --persistence verify \
    --require-new-job \
    --expected-probe-sha256 "$probe_sha"
  python -m scripts.station_capture_worker status >/dev/null
}

case "$job" in
  capture)
    preflight
    python -m scripts.exact_run_worker capture
    python -m scripts.exact_run_worker status
    python -m scripts.station_capture_worker observations
    python -m scripts.station_capture_worker doctor
    ;;
  catalog)
    preflight
    python -m scripts.station_capture_worker catalog
    python -m scripts.station_capture_worker status
    ;;
  doctor)
    preflight
    python -m scripts.exact_run_worker status
    python -m scripts.station_capture_worker doctor
    ;;
  *)
    echo "usage: $0 {capture|catalog|doctor}" >&2
    exit 64
    ;;
esac
