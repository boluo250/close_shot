from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field


class RateCardItemIn(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    mode: str = Field(description="计价模式：hour/photo")
    price_cents: int = Field(ge=0, le=10_000_000)
    unit: str | None = Field(default=None, max_length=64)

from app.schemas.photographer import PackageOut, PhotographerOut, PortfolioItemOut


class PhotographerUpdateIn(BaseModel):
    avatar_url: str | None = Field(default=None, max_length=512)
    avatar_object_key: str | None = Field(default=None, max_length=512)
    cover_url: str | None = Field(default=None, max_length=512)
    cover_object_key: str | None = Field(default=None, max_length=512)
    bio: str | None = Field(default=None, max_length=5000)
    tags: str | None = Field(default=None, max_length=2000)
    city: str | None = Field(default=None, max_length=64)
    service_center_lat: float | None = None
    service_center_lng: float | None = None
    service_radius_m: int | None = Field(default=None, ge=100, le=50000)
    # 设备清单 & 无人机型号（逗号分隔文本）
    equipment_list: str | None = Field(default=None, max_length=2000)
    drone_models: str | None = Field(default=None, max_length=1000)
    # 报价单：列表结构，后端会保存为 Photographer.rate_card_json
    rate_card: list[RateCardItemIn] | None = None


class StudioMeOut(BaseModel):
    photographer: PhotographerOut


class PortfolioCreateIn(BaseModel):
    title: str | None = Field(default=None, max_length=128)
    image_url: str = Field(min_length=1, max_length=512)
    image_object_key: str | None = Field(default=None, max_length=512)
    watermark_url: str | None = Field(default=None, max_length=512)
    watermark_object_key: str | None = Field(default=None, max_length=512)
    sort_order: int = 0
    tags: str = ""
    category: str = ""
    is_pinned: bool = False


class PortfolioUpdateIn(BaseModel):
    title: str | None = Field(default=None, max_length=128)
    image_url: str | None = Field(default=None, max_length=512)
    image_object_key: str | None = Field(default=None, max_length=512)
    watermark_url: str | None = Field(default=None, max_length=512)
    watermark_object_key: str | None = Field(default=None, max_length=512)
    sort_order: int | None = None
    tags: str | None = Field(default=None, max_length=2000)
    category: str | None = Field(default=None, max_length=64)
    is_pinned: bool | None = None


class PackageCreateIn(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    price_cents: int = Field(ge=0, le=10_000_000)
    duration_minutes: int | None = Field(default=None, ge=1, le=24 * 60)
    description: str | None = Field(default=None, max_length=5000)
    is_active: bool = True


class PackageUpdateIn(BaseModel):
    name: str | None = Field(default=None, max_length=128)
    price_cents: int | None = Field(default=None, ge=0, le=10_000_000)
    duration_minutes: int | None = Field(default=None, ge=1, le=24 * 60)
    description: str | None = Field(default=None, max_length=5000)
    is_active: bool | None = None


class PortfolioListOut(BaseModel):
    items: list[PortfolioItemOut]


class PackageListOut(BaseModel):
    items: list[PackageOut]


class ScheduleUpsertIn(BaseModel):
    date: date
    status: str = Field(min_length=1, max_length=16)


class ScheduleItemOut(BaseModel):
    date: date
    status: str


class ScheduleListOut(BaseModel):
    items: list[ScheduleItemOut]

