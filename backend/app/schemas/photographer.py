from __future__ import annotations

import json
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import ORMModel, TimestampOut
from app.schemas.review import ReviewOut


class PortfolioItemOut(TimestampOut):
    id: int
    title: str | None = None
    image_url: str
    watermark_url: str | None = None
    sort_order: int
    tags: str
    category: str
    is_pinned: bool


class PackageOut(TimestampOut):
    id: int
    name: str
    price_cents: int
    duration_minutes: int | None = None
    description: str | None = None
    is_active: bool


class RateCardItemOut(BaseModel):
    name: str
    mode: str = Field(description="计价模式：hour/photo")
    price_cents: int
    unit: str | None = None


class PhotographerOut(TimestampOut):
    id: int
    user_id: int
    # 来自 users 表（用于前端展示）
    display_name: str | None = None
    avatar_url: str | None = None
    cover_url: str | None = None
    bio: str | None = None
    tags: str
    equipment_list: list[str] = Field(default_factory=list, description="设备清单")
    drone_models: list[str] = Field(default_factory=list, description="无人机型号")
    rate_card: list[RateCardItemOut] = Field(default_factory=list, description="服务报价单")
    is_accepting_orders: bool
    city: str | None = None
    phone: str | None = None
    wechat_id: str | None = None
    service_center_lat: float | None = None
    service_center_lng: float | None = None
    service_radius_m: int
    last_active_at: datetime
    status: str
    reject_reason: str | None = None
    can_view_contact: bool = True
    contact_access_mode: str = "all"
    contact_lock_reason: str | None = None

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


class PhotographerCardOut(PhotographerOut):
    distance_m: float | None = Field(default=None, description="距离（米）")
    distance_km: float | None = Field(default=None, description="距离（公里）")
    distance_copy: str = Field(default="", description="距离展示文案（非实时位置语义）")
    starting_price_cents: int | None = Field(default=None, description="起步价（分），可为空")
    preview_image_urls: list[str] = Field(default_factory=list, description="首页样片预览（最多 3 张）")
    portfolio_count: int = Field(default=0, description="作品集数量")
    rate_hour_min_cents: int | None = Field(default=None, description="小时起步价（分）")
    rate_item_min_cents: int | None = Field(default=None, description="按张数起步价（分）")


class PhotographerNearbyOut(PhotographerCardOut):
    distance_m: float = Field(description="距离（米）")
    distance_km: float = Field(description="距离（公里）")
    distance_copy: str = Field(description="距离展示文案（非实时位置语义）")


class PhotographerDetailOut(PhotographerOut):
    is_favorited: bool = Field(default=False, description="当前登录用户是否已收藏该摄影师")
    portfolio_items: list[PortfolioItemOut]
    packages: list[PackageOut]
    reviews: list[ReviewOut] = Field(default_factory=list)


class NearbyQuery(BaseModel):
    lat: float
    lng: float
    max_distance_m: int = Field(default=5000, ge=100, le=200000)
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0, le=10000)
    tag: str | None = None
    auto_expand: bool = False


# ---- 管理后台认证审核 Schema ----

class CertificationDetailOut(TimestampOut):
    """管理端查看的摄影师认证详情"""
    id: int
    user_id: int
    display_name: str | None = None
    avatar_url: str | None = None
    status: str
    is_accepting_orders: bool = False
    reject_reason: str | None = None
    pending_reject_reason: str | None = None
    certification_level: int = 0
    quality_score: float = 5.0
    sort_score: float = 50.0
    trust_score: int = 70
    risk_level: str = "low"
    blacklist_status: str = "normal"

    # 补充实名信息（可选）
    real_name: str | None = None
    id_card_number: str | None = None
    id_card_front_url: str | None = None
    id_card_back_url: str | None = None

    # 资料完善（拍摄类型已移除）
    experience_years: str | None = None
    portfolio_link: str | None = None

    # 联系方式
    phone: str | None = None
    wechat_id: str | None = None

    # 可选
    city: str | None = None
    price_range: str | None = None
    bio: str | None = None
    equipment_list: list[str] = Field(default_factory=list)
    drone_models: list[str] = Field(default_factory=list)
    service_center_lat: float | None = None
    service_center_lng: float | None = None
    service_radius_m: int | None = None
    packages: list[PackageOut] = Field(default_factory=list)
    # 作品图（审核评分用）
    portfolio_image_urls: list[str] = Field(default_factory=list)
    has_pending_changes: bool = False
    pending_review_submitted_at: datetime | None = None

    @field_validator("equipment_list", "drone_models", mode="before")
    @classmethod
    def _parse_review_csv_list(cls, value: object) -> list[str]:
        if value is None:
            return []
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            return [x.strip() for x in value.split(",") if x.strip()]
        return []

class CertificationReviewIn(BaseModel):
    """管理端审核操作"""
    action: str = Field(description="approve 或 reject")
    reject_reason: str | None = Field(default=None, max_length=500, description="驳回原因（reject 时必填）")


class PhotographerAvailabilityIn(BaseModel):
    is_accepting_orders: bool


class CertificationListOut(BaseModel):
    items: list[CertificationDetailOut]
    total: int
