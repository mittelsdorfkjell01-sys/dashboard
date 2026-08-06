from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

Quality = Literal["unavailable", "model_only", "reviewed_anchor", "manual_calibrated", "gauge_calibrated"]


class TideEventRead(BaseModel):
    id: uuid.UUID
    event_type: Literal["high", "low"]
    raw_time: datetime | None = None
    time: datetime
    uncertainty_minutes: int
    profile_version: int
    overridden: bool = False


class PublicTideEventRead(BaseModel):
    id: uuid.UUID
    event_type: Literal["high", "low"]
    time: datetime
    uncertainty_minutes: int


class PublicTideRead(BaseModel):
    available: bool
    message: str | None = None
    timezone: str | None = None
    phase: Literal["rising", "high", "falling", "low", "unavailable"] = "unavailable"
    cycle_position: float | None = None
    quality: Quality = "unavailable"
    approximate: bool = True
    last_calculated_at: datetime | None = None
    valid_until: datetime | None = None
    events: list[PublicTideEventRead] = Field(default_factory=list)


class TideProfileUpdate(BaseModel):
    enabled: bool | None = None
    public_enabled: bool | None = None
    timezone: str | None = Field(default=None, max_length=80)
    global_offset_minutes: int | None = None
    high_offset_minutes: int | None = None
    low_offset_minutes: int | None = None
    manual_uncertainty_minutes: int | None = Field(default=None, ge=0, le=720)
    note: str | None = Field(default=None, max_length=10_000)
    correction_reason: str | None = Field(default=None, max_length=2_000)
    correction_source: str | None = Field(default=None, max_length=2_000)
    review_anchor: bool = False


class ManualAnchorRequest(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    reason: str = Field(min_length=3, max_length=2_000)


class TidePreviewRequest(BaseModel):
    global_offset_minutes: int = 0
    high_offset_minutes: int = 0
    low_offset_minutes: int = 0


class TideOverrideRequest(BaseModel):
    event_id: uuid.UUID
    manual_time: datetime
    scope: Literal["single", "high_profile", "low_profile", "calibration_input"]
    reason: str = Field(min_length=3, max_length=2_000)
    source: str | None = Field(default=None, max_length=2_000)


class ApplySuggestionRequest(BaseModel):
    apply_high: bool = True
    apply_low: bool = True
    reason: str = Field(min_length=3, max_length=2_000)

    @model_validator(mode="after")
    def _at_least_one(self):
        if not self.apply_high and not self.apply_low:
            raise ValueError("Mindestens ein Ereignistyp muss übernommen werden")
        return self


class TideRollbackRequest(BaseModel):
    version: int = Field(ge=1)
    reason: str = Field(min_length=3, max_length=2_000)
