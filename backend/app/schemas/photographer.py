from __future__ import annotations

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
    bio: str | None = None
    tags: str
    is_online: bool
    city: str | None = None
    lat: float | None = None
    lng: float | None = None
    service_radius_m: int


class PhotographerNearbyOut(PhotographerOut):
    distance_m: float = Field(description="距离（米）")


class PhotographerDetailOut(PhotographerOut):
    portfolio_items: list[PortfolioItemOut]
    packages: list[PackageOut]
    rating_avg: float | None = None
    rating_count: int


class NearbyQuery(BaseModel):
    lat: float
    lng: float
    radius_m: int = Field(default=5000, ge=100, le=50000)
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0, le=10000)
    is_online: bool | None = None
    tag: str | None = None

