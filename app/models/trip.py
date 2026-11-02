"""Manual trip plans owned by public visitor accounts."""

import uuid
from datetime import date

from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class Trip(Base, TimestampMixin):
    __tablename__ = "trips"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()"))
    app_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("app_users.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    checklist: Mapped[list] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    days: Mapped[list] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'draft'"))
    share_token: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), unique=True)
    share_notes: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    stops: Mapped[list["TripStop"]] = relationship(back_populates="trip", cascade="all, delete-orphan", order_by="TripStop.position")

    __table_args__ = (
        CheckConstraint("end_date >= start_date", name="ck_trips_date_order"),
        CheckConstraint("status IN ('draft','planned','completed','cancelled')", name="ck_trips_status"),
        CheckConstraint("jsonb_typeof(checklist) = 'array'", name="ck_trips_checklist_array"),
        CheckConstraint("jsonb_typeof(days) = 'array'", name="ck_trips_days_array"),
        Index("ix_trips_user_dates", "app_user_id", "start_date", "end_date"),
    )


class TripStop(Base, TimestampMixin):
    __tablename__ = "trip_stops"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()"))
    trip_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("trips.id", ondelete="CASCADE"), nullable=False)
    spot_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("spots.id", ondelete="SET NULL"))
    spot_name: Mapped[str] = mapped_column(String(200), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    planned_date: Mapped[date | None] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(Text)
    role: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'alternative'"))
    spot_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    trip: Mapped[Trip] = relationship(back_populates="stops")
    spot: Mapped["Spot | None"] = relationship()  # noqa: F821

    __table_args__ = (
        CheckConstraint("position >= 0", name="ck_trip_stops_position"),
        CheckConstraint("role IN ('main','alternative')", name="ck_trip_stops_role"),
        UniqueConstraint("trip_id", "position", name="uq_trip_stops_position"),
        Index("ix_trip_stops_spot", "spot_id"),
    )
