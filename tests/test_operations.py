"""Operations summary: error classification + summary shape."""

from app.admin.operations import _error_category, operations_summary


def test_error_category_classification():
    assert _error_category(None) is None
    assert _error_category("Open-Meteo rate limit 429") == "quota"
    assert _error_category("no sea grid cell near coordinate") == "coordinates"
    assert _error_category("schema validation failed") == "validation"
    assert _error_category("connection timeout to provider") == "provider"
    assert _error_category("something odd happened") == "unknown"


def test_operations_summary_shape(db):
    summary = operations_summary(db)
    assert set(summary) == {"freshness", "queue_depth", "job_status", "recent_jobs", "public_update"}
    assert set(summary["freshness"]) == {"missing", "stale", "current", "failed"}
    assert isinstance(summary["queue_depth"], int)
    assert isinstance(summary["job_status"], dict)
    assert isinstance(summary["recent_jobs"], list)
    assert "climatology_cron" in summary["public_update"]
