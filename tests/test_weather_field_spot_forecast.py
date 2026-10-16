from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.spatial_fields.serving import FieldSampleUnavailable
from app.schemas.live import ValueProvenance
from app.spatial_fields.spot_forecast import (
    active_wave_publication_ids,
    apply_field_wind_to_payload,
    assess_spot_field_readiness,
)


def _settings(**overrides):
    values = {
        "weather_field_spot_rollout_stage": "shadow",
        "weather_field_spot_rollout_region_slugs": "",
        "wind_sector_blend": {},
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_active_wave_publication_ids_cover_the_ten_day_model_chain(monkeypatch) -> None:
    settings = _settings(
        wave_field_public_enabled=True,
        wave_field_scope_key="europe-waves",
        wave_field_primary_model="dwd-ewam",
        wave_field_fallback_model="dwd-gwam",
        wave_field_extended_model="noaa-gfs-wave",
    )
    states = {
        "europe-waves": SimpleNamespace(publication_id="ewam-publication"),
        "europe-waves:dwd-gwam": SimpleNamespace(publication_id="gwam-publication"),
        "europe-waves:noaa-gfs-wave": SimpleNamespace(
            publication_id="gfs-wave-publication"
        ),
    }
    monkeypatch.setattr(
        "app.spatial_fields.spot_forecast.active_publication_state",
        lambda db, scope_key, **kwargs: states.get(scope_key),
    )

    result = active_wave_publication_ids(object(), settings=settings)

    assert result == (
        "ewam-publication",
        "gfs-wave-publication",
        "gwam-publication",
    )


def test_marine_field_lineage_survives_public_schema_validation() -> None:
    provenance = ValueProvenance.model_validate(
        {
            "source_type": "forecast",
            "observation_type": "forecast",
            "source": "model",
            "provider": "Surfwinddata Forecast",
            "captured_at": "2026-10-09T12:00:00Z",
            "model_run_quality": "capture-time-only",
            "spot_timezone": "Europe/Berlin",
            "requested_coordinate": {"latitude": 54.4, "longitude": 11.2},
            "availability": "available",
            "quality_tier": "coordinates",
            "marine_source": "weather_field",
            "marine_provider": "Deutscher Wetterdienst",
            "marine_model": "dwd-ewam",
            "marine_model_run_at": "2026-10-09T06:00:00Z",
            "marine_publication_id": "7d7e9ac1-d6eb-44ed-bcb3-2a26e25fc5b7",
        }
    ).model_dump(mode="json")

    assert provenance["marine_source"] == "weather_field"
    assert provenance["marine_model"] == "dwd-ewam"
    assert provenance["marine_model_run_at"] == "2026-10-09T06:00:00Z"
    assert provenance["marine_publication_id"] == "7d7e9ac1-d6eb-44ed-bcb3-2a26e25fc5b7"


def test_shadow_stage_is_fail_closed_without_database_reads() -> None:
    class NoDatabaseReads:
        def scalar(self, *_args, **_kwargs):  # pragma: no cover - assertion helper
            raise AssertionError("shadow stage must not read rollout evidence")

    decision = assess_spot_field_readiness(
        NoDatabaseReads(),
        spot=SimpleNamespace(region=SimpleNamespace(slug="fehmarn")),
        settings=_settings(),
    )

    assert decision.enabled is False
    assert decision.unverified_override is False
    assert decision.reasons == ("rollout_stage_shadow",)
    assert decision.evidence.shadow_cycles == 0


def test_field_baseline_replaces_wind_and_preserves_auxiliary_and_tail() -> None:
    first = "2026-10-05T12:00:00+00:00"
    tail = "2026-10-11T12:00:00+00:00"
    payload = {
        "days": [
            {
                "date": "2026-10-05",
                "confidence": "hoch",
                "confidence_source": "spread",
                "summary": {"wind_avg": 10.0, "wind_low": 8.0, "wind_high": 12.0},
                "hours": [
                    {
                        "time": first,
                        "wind": 10.0,
                        "gust": 12.0,
                        "wind_ms": 5.0,
                        "gust_ms": 6.0,
                        "dir": 180.0,
                        "air": 17.0,
                        "swell": 1.2,
                        "wind_spread": {"median": 10.0, "low": 8.0, "high": 12.0, "n": 3},
                        "provenance": {"source": "model"},
                    }
                ],
            },
            {
                "date": "2026-10-11",
                "confidence": "niedrig",
                "confidence_source": "spread",
                "summary": {"wind_avg": 9.0, "wind_low": 7.0, "wind_high": 11.0},
                "hours": [{"time": tail, "wind": 9.0, "air": 16.0}],
            },
        ]
    }

    def sample(valid_at):
        if valid_at > datetime(2026, 10, 10, tzinfo=timezone.utc):
            raise FieldSampleUnavailable("outside field horizon")
        return {
            "publication_id": "publication-1",
            "run_id": "run-1",
            "model": "icon-eu",
            "model_run": datetime(2026, 10, 5, 6, tzinfo=timezone.utc),
            "valid_at": valid_at,
            "speed_ms": 8.0,
            "direction_from_deg": 270.0,
            "gust_ms": 10.0,
            "freshness": "fresh",
        }

    result, lineage = apply_field_wind_to_payload(
        payload,
        latitude=54.4,
        longitude=11.2,
        profile=None,
        sample=sample,
        settings=_settings(),
    )

    replaced = result["days"][0]
    hour = replaced["hours"][0]
    assert hour["wind_ms"] == 8.0
    assert hour["gust_ms"] == 10.0
    assert hour["dir"] == 270.0
    assert hour["air"] == 17.0
    assert hour["swell"] == 1.2
    assert hour["wind_spread"] is None
    assert hour["provenance"]["source"] == "weather_field"
    assert replaced["summary"]["wind_low"] is None
    assert replaced["confidence_source"] == "calendar"
    assert result["days"][1] == payload["days"][1]
    assert lineage == {
        "source": "weather-field",
        "publication_id": "publication-1",
        "run_id": "run-1",
        "model": "icon-eu",
        "replaced_hours": 1,
        "first_valid_at": first,
        "last_valid_at": first,
        "tail_fallback": "open-meteo",
    }
    assert payload["days"][0]["hours"][0]["wind_ms"] == 5.0


def test_field_baseline_rejects_a_payload_without_field_hours() -> None:
    with pytest.raises(FieldSampleUnavailable):
        apply_field_wind_to_payload(
            {"days": [{"hours": [{"time": "2026-10-11T12:00:00+00:00"}]}]},
            latitude=54.4,
            longitude=11.2,
            profile=None,
            sample=lambda _valid_at: (_ for _ in ()).throw(
                FieldSampleUnavailable("outside field horizon")
            ),
            settings=_settings(),
        )
