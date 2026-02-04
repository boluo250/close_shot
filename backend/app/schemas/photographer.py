from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel, TimestampOut


class PortfolioItemOut(TimestampOut):
    id: int
    title: str | None = None
    image_url: str
    sort_order: int
    tags: str


class PackageOut(TimestampOut):
    id: int
    name: str
    price_cents: int
    duration_minutes: int | None = None
    description: str | None = None
    is_active: bool


class PhotographerOut(TimestampOut):
    id: int
    user_id: int
    # 来自 users 表（用于前端展示）
    display_name: str | None = None
    avatar_url: str | None = None
    bio: str | None = None
    tags: str
    is_accepting_orders: bool
    city: str | None = None
    service_center_lat: float | None = None
    service_center_lng: float | None = None
    service_radius_m: int
    last_active_at: datetime


class PhotographerNearbyOut(PhotographerOut):
    distance_m: float = Field(description="距离（米）")
    distance_km: float = Field(description="距离（公里）")
    distance_copy: str = Field(description="距离展示文案（非实时位置语义）")
    starting_price_cents: int | None = Field(default=None, description="起步价（分），可为空")
    rating_avg: float | None = None
    rating_count: int | None = None
    preview_image_urls: list[str] = Field(default_factory=list, description="首页样片预览（最多 3 张）")


class PhotographerDetailOut(PhotographerOut):
    portfolio_items: list[PortfolioItemOut]
    packages: list[PackageOut]
    rating_avg: float | None = None
    rating_count: int


class NearbyQuery(BaseModel):
    lat: float
    lng: float
    max_distance_m: int = Field(default=50000, ge=100, le=200000)
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0, le=10000)
    is_accepting_orders: bool | None = None
    tag: str | None = None

