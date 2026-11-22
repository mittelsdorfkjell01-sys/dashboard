"""Database schema revision expected by this application build."""

from hashlib import sha256

EXPECTED_DB_REVISION = "0100_app_user_identities"
EXPECTED_DB_FINGERPRINT = sha256(EXPECTED_DB_REVISION.encode("utf-8")).hexdigest()[:12]
