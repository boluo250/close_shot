from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import TimestampOut


class AppointmentCreateIn(BaseModel):
    photographer_id: int
    package_id: int | None = None
    scheduled_at: datetime
    location_text: str = Field(min_length=1, max_length=255)
    contact_name: str | None = Field(default=None, max_length=64)
    contact_phone: str | None = Field(default=None, max_length=20)
    shooting_type: str | None = Field(default=None, max_length=64)
    budget_cents: int | None = Field(default=None, ge=0, le=10_000_000)
    participant_count: int = Field(default=1, ge=1, le=50)
    note: str | None = Field(default=None, max_length=2000)


class AppointmentDecisionIn(BaseModel):
    response_note: str | None = Field(default=None, max_length=2000)


class AppointmentOut(TimestampOut):
    id: int
    customer_user_id: int
    photographer_id: int
    package_id: int | None = None
    status: str
    scheduled_at: datetime
    location_text: str
    contact_name: str | None = None
    contact_phone: str | None = None
    shooting_type: str | None = None
    budget_cents: int | None = None
    participant_count: int
    note: str | None = None
    response_note: str | None = None
    accepted_at: datetime | None = None
    customer_confirmed_at: datetime | None = None
    contact_unlocked_at: datetime | None = None
    rejected_at: datetime | None = None
    cancelled_at: datetime | None = None
    completed_at: datetime | None = None
    customer_completed_at: datetime | None = None
    photographer_completed_at: datetime | None = None
    customer_display_name: str | None = None
    customer_avatar_url: str | None = None
    photographer_display_name: str | None = None
    photographer_avatar_url: str | None = None
    photographer_phone: str | None = None
    photographer_wechat_id: str | None = None
    customer_contact_name: str | None = None
    customer_contact_phone: str | None = None
    can_view_customer_contact: bool = False
    can_view_photographer_contact: bool = False
    can_customer_confirm: bool = False
    can_customer_complete: bool = False
    can_photographer_complete: bool = False
    package_name: str | None = None
    has_review: bool = False
    can_review: bool = False


class AppointmentListOut(BaseModel):
    items: list[AppointmentOut]


class AppointmentSummaryOut(BaseModel):
    mine_waiting_customer_confirm: int = 0
    mine_waiting_completion_confirm: int = 0
    mine_completed_without_review: int = 0
    assigned_pending_decision: int = 0
    assigned_waiting_customer_confirm: int = 0
    assigned_waiting_completion_mark: int = 0


class AppointmentSubscribeConfigOut(BaseModel):
    photographer_new_appointment_template_id: str | None = None
    customer_appointment_accepted_template_id: str | None = None
    customer_appointment_completed_template_id: str | None = None
