from __future__ import annotations

import json
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

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


class RateCardItemOut(BaseModel):
    name: str
    mode: str = Field(description="计价模式：hour/item")
    price_cents: int
    unit: str | None = None


class PhotographerOut(TimestampOut):
    id: int
    user_id: int
    # 来自 users 表（用于前端展示）
    display_name: str | None = None
    avatar_url: str | None = None
    bio: str | None = None
    tags: str
    equipment_list: list[str] = Field(default_factory=list, description="设备清单")
    drone_models: list[str] = Field(default_factory=list, description="无人机型号")
    rate_card: list[RateCardItemOut] = Field(default_factory=list, description="服务报价单")
    is_accepting_orders: bool
    city: str | None = None
    service_center_lat: float | None = None
    service_center_lng: float | None = None
    service_radius_m: int
    last_active_at: datetime

    @field_validator("equipment_list", "drone_models", mode="before")
    @classmethod
    def _parse_csv_list(cls, value: object) -> list[str]:
        if value is None:
            return []
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            return [x.strip() for x in value.split(",") if x.strip()]
        return []

    @field_validator("rate_card", mode="before")
    @classmethod
    def _parse_rate_card(cls, value: object) -> list[dict]:
        if value is None:
            return []
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            if not value:
                return []
            try:
                items = json.loads(value)
            except json.JSONDecodeError:
                return []
            return items if isinstance(items, list) else []
        return []


class PhotographerNearbyOut(PhotographerOut):
    distance_m: float = Field(description="距离（米）")
    distance_km: float = Field(description="距离（公里）")
    distance_copy: str = Field(description="距离展示文案（非实时位置语义）")
    starting_price_cents: int | None = Field(default=None, description="起步价（分），可为空")
    rating_avg: float | None = None
    rating_count: int | None = None
    preview_image_urls: list[str] = Field(default_factory=list, description="首页样片预览（最多 3 张）")
    portfolio_count: int = Field(default=0, description="作品集数量")
    rate_hour_min_cents: int | None = Field(default=None, description="小时起步价（分）")
    rate_item_min_cents: int | None = Field(default=None, description="按件起步价（分）")


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

