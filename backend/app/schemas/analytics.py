from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class AnalyticsEventIn(BaseModel):
    event_type: str = Field(min_length=1, max_length=64)
    photographer_id: int | None = Field(default=None, ge=1)
    channel: str | None = Field(default=None, max_length=32)
    lat: float | None = None
    lng: float | None = None
    extra: dict | None = None


class AnalyticsTrackBatchIn(BaseModel):
    events: list[AnalyticsEventIn] = Field(default_factory=list, max_length=100)


class AnalyticsTrackBatchOut(BaseModel):
    accepted: int
    skipped: int


class AnalyticsSummaryItemOut(BaseModel):
    photographer_id: int
    display_name: str | None = None
    exposure_count: int
    click_count: int
    contact_count: int
    ctr: float = Field(description="点击率：click/exposure")
    contact_rate: float = Field(description="联系率：contact/click")


class AnalyticsSummaryOut(BaseModel):
    days: int
    total_exposure: int
    total_click: int
    total_contact: int
    items: list[AnalyticsSummaryItemOut]


class AnalyticsEventOut(BaseModel):
    id: int
    event_type: str
    photographer_id: int | None = None
    display_name: str | None = None
    channel: str | None = None
    user_id: int | None = None
    client_lat: float | None = None
    client_lng: float | None = None
    extra: dict = Field(default_factory=dict)
    created_at: datetime


class AnalyticsEventListOut(BaseModel):
    items: list[AnalyticsEventOut]
    total: int
