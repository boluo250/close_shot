from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.photographer import PackageOut, PhotographerOut, PortfolioItemOut


class PhotographerUpdateIn(BaseModel):
    bio: str | None = Field(default=None, max_length=5000)
    tags: str | None = Field(default=None, max_length=2000)
    city: str | None = Field(default=None, max_length=64)
    is_accepting_orders: bool | None = None
    service_center_lat: float | None = None
    service_center_lng: float | None = None
    service_radius_m: int | None = Field(default=None, ge=100, le=50000)


class StudioMeOut(BaseModel):
    photographer: PhotographerOut


class PortfolioCreateIn(BaseModel):
    title: str | None = Field(default=None, max_length=128)
    image_url: str = Field(min_length=1, max_length=512)
    sort_order: int = 0
    tags: str = ""


class PortfolioUpdateIn(BaseModel):
    title: str | None = Field(default=None, max_length=128)
    image_url: str | None = Field(default=None, max_length=512)
    sort_order: int | None = None
    tags: str | None = Field(default=None, max_length=2000)


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

