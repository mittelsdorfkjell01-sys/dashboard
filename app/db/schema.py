"""Database schema revision expected by this application build."""

from hashlib import sha256

EXPECTED_DB_REVISION = "0093_trip_planner_v2"
EXPECTED_DB_FINGERPRINT = sha256(EXPECTED_DB_REVISION.encode("utf-8")).hexdigest()[:12]
