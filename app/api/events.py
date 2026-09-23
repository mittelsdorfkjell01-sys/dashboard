"""First-party interaction-event intake for signed-in and anonymous visitors."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.account.deps import optional_account
from app.community.ratelimit import RateLimiter, enforce, get_rate_limiter
from app.db.session import get_db
from app.models import AppUser, RecommendationLog, Spot, UserEvent

router = APIRouter(prefix="/events", tags=["events"])

EVENT_TYPES = {
    "impression", "click", "favorite_add", "favorite_remove", "dismiss",
    "search", "session_checkin",
}
RESERVED_EVENT_TYPES = {
    "notification_sent", "notification_opened", "notification_dismissed",
}
MAX_CONTEXT_BYTES = 4096


class EventIn(BaseModel):
    type: str = Field(min_length=1, max_length=40)
    anon_id: uuid.UUID | None = Field(default=None, alias="anonId")
    spot_id: uuid.UUID | None = Field(default=None, alias="spotId")
    surface: str | None = Field(default=None, max_length=40)
    context: dict[str, Any] = Field(default_factory=dict, max_length=30)

    model_config = {"populate_by_name": True, "extra": "forbid"}

    @field_validator("type")
    @classmethod
    def allowed_type(cls, value: str) -> str:
        if value in RESERVED_EVENT_TYPES:
            raise ValueError("notification events are reserved for a later phase")
        if value not in EVENT_TYPES:
            raise ValueError("unknown event type")
        return value

    @field_validator("context")
    @classmethod
    def small_context(cls, value: dict[str, Any]) -> dict[str, Any]:
        try:
            encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        except (TypeError, ValueError) as exc:
            raise ValueError("event context must be JSON serializable") from exc
        if len(encoded.encode("utf-8")) > MAX_CONTEXT_BYTES:
            raise ValueError(f"event context exceeds {MAX_CONTEXT_BYTES} bytes")
        return value

    @model_validator(mode="after")
    def valid_checkin(self) -> "EventIn":
        if self.type != "session_checkin":
            return self
        if self.spot_id is None:
            raise ValueError("session_checkin requires spotId")
        outcome = self.context.get("outcome")
        if outcome not in {None, "worthwhile", "not_worthwhile"}:
            raise ValueError("invalid session_checkin outcome")
        return self


class EventBatch(BaseModel):
    events: list[EventIn] = Field(min_length=1, max_length=50)

    model_config = {"extra": "forbid"}


@router.post("", status_code=status.HTTP_202_ACCEPTED)
def create_events(
    body: EventBatch,
    request: Request,
    db: Session = Depends(get_db),
    account: AppUser | None = Depends(optional_account),
    limiter: RateLimiter = Depends(get_rate_limiter),
) -> dict[str, int]:
    enforce(limiter, request, "events", limit=30, window=60)
    if account is None and any(item.anon_id is None for item in body.events):
        raise HTTPException(status_code=422, detail="anonId is required without a session")

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=72)
    for item in body.events:
        if item.spot_id is not None and db.get(Spot, item.spot_id) is None:
            raise HTTPException(status_code=422, detail=f"unknown spotId: {item.spot_id}")
        recommendation_log_id = None
        if item.type in {"session_checkin", "favorite_add"} and item.spot_id is not None:
            actor_filter = (
                UserEvent.app_user_id == account.id
                if account is not None
                else UserEvent.anon_id == str(item.anon_id)
            )
            impression = db.scalar(
                select(UserEvent)
                .where(
                    actor_filter,
                    UserEvent.type == "impression",
                    UserEvent.spot_id == item.spot_id,
                    UserEvent.created_at >= cutoff,
                )
                .order_by(UserEvent.created_at.desc())
                .limit(1)
            )
            if impression is not None:
                log_stmt = select(RecommendationLog.id).where(
                    RecommendationLog.spot_id == item.spot_id,
                    RecommendationLog.surface == impression.surface,
                    RecommendationLog.created_at >= cutoff,
                    RecommendationLog.created_at <= impression.created_at,
                )
                if account is not None:
                    log_stmt = log_stmt.where(
                        RecommendationLog.app_user_id == account.id
                    )
                else:
                    log_stmt = log_stmt.where(
                        RecommendationLog.app_user_id.is_(None)
                    )
                recommendation_log_id = db.scalar(
                    log_stmt.order_by(RecommendationLog.created_at.desc()).limit(1)
                )
        elif (
            item.type in {"impression", "click", "favorite_add"}
            and item.spot_id is not None
            and item.surface
        ):
            log_stmt = select(RecommendationLog.id).where(
                RecommendationLog.spot_id == item.spot_id,
                RecommendationLog.surface == item.surface,
                RecommendationLog.created_at >= cutoff,
                RecommendationLog.created_at <= now,
            )
            if account is not None:
                log_stmt = log_stmt.where(RecommendationLog.app_user_id == account.id)
            else:
                log_stmt = log_stmt.where(RecommendationLog.app_user_id.is_(None))
            recommendation_log_id = db.scalar(
                log_stmt.order_by(RecommendationLog.created_at.desc()).limit(1)
            )
        db.add(UserEvent(
            app_user_id=account.id if account is not None else None,
            anon_id=None if account is not None else str(item.anon_id),
            type=item.type,
            spot_id=item.spot_id,
            surface=item.surface,
            context=item.context,
            recommendation_log_id=recommendation_log_id,
        ))
    db.commit()
    return {"accepted": len(body.events)}
