"""Database-independent validation coverage for Phase B request contracts."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.api.account import GearItemPut, RiderProfilePut, RiderSportProfilePut
from app.api.admin import RiderModelDocument, RiderModelPreview
from app.api.events import EventBatch
from app.scoring.params import DEFAULT_RIDER_KITESURF, RIDER_MODEL_KITESURF


def _model_document() -> dict:
    return {
        "rider_model": RIDER_MODEL_KITESURF,
        "default_rider": DEFAULT_RIDER_KITESURF,
    }


@pytest.mark.parametrize("weight", [29, 161, float("nan")])
def test_rider_profile_rejects_invalid_weight(weight):
    with pytest.raises(ValidationError):
        RiderProfilePut.model_validate({"weightKg": weight})


@pytest.mark.parametrize("availability", [[0, 0], [-1], [7], [True]])
def test_rider_profile_rejects_invalid_availability(availability):
    with pytest.raises(ValidationError):
        RiderProfilePut.model_validate({"availability": availability})


@pytest.mark.parametrize(
    "payload",
    [
        {"level": "intermediate"},
        {"level": "advanced", "styleWeights": {"unknown": 1}},
        {"level": "advanced", "styleWeights": {"freeride": 4}},
        {"level": "advanced", "styleWeights": {"freeride": True}},
        {
            "level": "advanced",
            "preferredWaterCharacter": ["flach", "flach"],
        },
    ],
)
def test_rider_sport_profile_rejects_noncanonical_values(payload):
    with pytest.raises(ValidationError):
        RiderSportProfilePut.model_validate(payload)


def test_kite_requires_a_positive_size():
    with pytest.raises(ValidationError):
        GearItemPut.model_validate({"sport": "kitesurf", "kind": "kite"})
    with pytest.raises(ValidationError):
        GearItemPut.model_validate(
            {"sport": "kitesurf", "kind": "kite", "size": 0}
        )


@pytest.mark.parametrize(
    "event_type", ["notification_sent", "notification_opened", "unknown"]
)
def test_event_batch_rejects_reserved_and_unknown_types(event_type):
    with pytest.raises(ValidationError):
        EventBatch.model_validate({"events": [{"type": event_type}]})


def test_event_batch_enforces_size_and_small_context():
    with pytest.raises(ValidationError):
        EventBatch.model_validate({"events": []})
    with pytest.raises(ValidationError):
        EventBatch.model_validate(
            {"events": [{"type": "search", "context": {"query": "x" * 4097}}]}
        )


def test_admin_rider_model_requires_complete_calibration():
    payload = _model_document()
    payload["rider_model"] = {
        **payload["rider_model"],
        "k_board": {"twintip": 2.2},
    }
    with pytest.raises(ValidationError):
        RiderModelDocument.model_validate(payload)


@pytest.mark.parametrize(
    ("field", "value"),
    [("travel_mode", "teleport"), ("style_weights", {"freeride": 4})],
)
def test_admin_preview_rejects_invalid_preferences(field, value):
    payload = {
        **_model_document(),
        "weight_kg": 78,
        "level": "advanced",
        "quiver": [{"kind": "kite", "size": 9}],
        "style_weights": {"freeride": 2},
        "travel_mode": "day_trip",
    }
    payload[field] = value
    with pytest.raises(ValidationError):
        RiderModelPreview.model_validate(payload)
