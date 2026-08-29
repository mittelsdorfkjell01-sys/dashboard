# Weather phase 2: local foundation

Status: locally testable, production activation blocked by the database limit.

Live atmosphere, current marine data and the ten-day forecast use distinct keys
and target TTLs of 5, 15 and 45 minutes. Redis is primary; bounded process memory
is a fail-open fallback. Cache envelopes preserve capture time. Forecast snapshot
freshness remains a separate three-hour domain rule; a stale snapshot is marked
and is served for at most another twelve hours.

`VITE_WEATHER_POLLING_ENABLED=false` is the safe default because spot resolution
still reads PostgreSQL. Once the public spot catalogue and forecast payloads are
proven Redis-first in production, enable it explicitly to poll current values at
five minutes and forecasts at 45 minutes, with jitter, visibility pause, focus
and reconnect revalidation.

The local-only command `python -m scripts.forecast_refresh_worker --dry-run`
plans published spots missing a snapshot or at least two hours old. It refuses a
production or remote database. No workflow or schedule activates it.

## Capacity baseline (local catalogue, 2026-08-26)

The disposable local database contains 11 published spots. One full refresh uses
one atmospheric and one marine request per due spot: 22 attempts. At a two-hour
cycle this is 264 requests/day. Even a deliberately conservative worst case in
which all 11 spots remain visibly open all day adds at most 3,168 five-minute
atmosphere and 1,056 fifteen-minute marine cache fills, for 4,488 total requests
or 44.88% of the current 10,000/day non-commercial limit. Real shared-cache use
should be lower. Warning starts at 7,000 and the application soft-stops at 8,000.

Provider payload bytes and production runtimes were not measured because real
mass requests are prohibited. The code-level reduction is deterministic: current
requests omit the ten-day daily payload and request only a three-hour alignment
horizon. Re-measure representative response bytes after the operational block is
lifted, before enabling polling or a schedule.

Open-Meteo's current free-use limits are documented at
https://open-meteo.com/en/terms (under 10,000/day, 5,000/hour, 600/minute).
