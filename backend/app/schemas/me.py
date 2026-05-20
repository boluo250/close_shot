from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class MeIdentityOut(BaseModel):
    role: str
    photographer_status: str | None = None
    photographer_reject_reason: str | None = None
    certification_level: int = 0
    is_member: bool = False
    member_expires_at: datetime | None = None
    trust_score: int = 70
    risk_level: str = "low"
    blacklist_status: str = "normal"


class PhotographerApplyIn(BaseModel):
    """摄影师入驻认证提交表单"""

    # 可选补充实名（高风险用户后续可引导补充）
    real_name: str | None = Field(default=None, min_length=2, max_length=64, description="真实姓名")
    id_card_number: str | None = Field(default=None, min_length=15, max_length=18, description="身份证号")
    id_card_front_url: str | None = Field(default=None, max_length=512, description="身份证正面照片（预留）")
    id_card_back_url: str | None = Field(default=None, max_length=512, description="身份证反面照片（预留）")

    # Step 2: 基础资料（昵称必填；其余字段可选）
    display_name: str | None = Field(default=None, max_length=128, description="摄影师昵称/展示名")
    shooting_types: list[str] = Field(default_factory=list, max_length=3, description="拍摄类型（可选，最多三种）")
    experience_years: str | None = Field(default=None, max_length=16, description="从业年限（可选）")
    portfolio_link: str | None = Field(default=None, max_length=512, description="个人摄影主页链接（可选）")

    # Step 3: 联系方式（必填）
    phone: str = Field(min_length=11, max_length=20, description="手机号")
    wechat_id: str = Field(min_length=1, max_length=64, description="微信号")

    # 可选字段
    city: str | None = Field(default=None, max_length=64, description="常驻城市")
    price_range: str | None = Field(default=None, max_length=32, description="报价区间")
    service_center_lat: float | None = Field(default=None, ge=-90, le=90, description="服务中心纬度")
    service_center_lng: float | None = Field(default=None, ge=-180, le=180, description="服务中心经度")
    service_radius_m: int | None = Field(default=None, ge=100, le=50000, description="服务半径（米）")

    # Step 2: 个人资料（提交审核时一并原子保存）
    avatar_url: str | None = Field(default=None, max_length=512)
    avatar_object_key: str | None = Field(default=None, max_length=512)
    bio: str | None = Field(default=None, max_length=5000)
    equipment_list: str | None = Field(default=None, max_length=2000)
    drone_models: str | None = Field(default=None, max_length=1000)

    # 作品与报价
    rate_card: list["CertificationRateCardItemIn"] = Field(default_factory=list)
    portfolio_items: list["CertificationPortfolioItemIn"] = Field(default_factory=list)
    packages: list["CertificationPackageItemIn"] = Field(default_factory=list)


class CertificationRateCardItemIn(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    mode: str = Field(description="计价模式：hour/photo")
    price_cents: int = Field(ge=0, le=10_000_000)
    unit: str | None = Field(default=None, max_length=64)


class CertificationPortfolioItemIn(BaseModel):
    title: str | None = Field(default=None, max_length=128)
    image_url: str | None = Field(default=None, max_length=512)
    image_object_key: str | None = Field(default=None, max_length=512)
    tags: str = Field(default="", max_length=2000)
    category: str = Field(default="", max_length=64)
    is_pinned: bool = False
    sort_order: int = 0


class CertificationPackageItemIn(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    price_cents: int = Field(ge=0, le=10_000_000)
    duration_minutes: int | None = Field(default=None, ge=1, le=24 * 60)
    description: str | None = Field(default=None, max_length=5000)
    is_active: bool = True


class TencentRealPersonVerifyIn(BaseModel):
    """腾讯云实名实人认证请求（占位接口）"""

    real_name: str = Field(min_length=2, max_length=64, description="真实姓名")
    id_card_number: str = Field(min_length=15, max_length=18, description="身份证号")


class TencentRealPersonVerifyOut(BaseModel):
    """腾讯云实名实人认证返回（占位）"""

    provider: str = "tencent_cloud"
    verified: bool = False
    code: str = "NOT_IMPLEMENTED"
    message: str = "腾讯云实名实人认证接口预留中，后续仅对高风险用户触发"


class CertificationStatusOut(BaseModel):
    """认证状态详情"""
    status: str  # pending / approved / rejected
    certification_level: int = 0
    reject_reason: str | None = None
    # 各步骤完成状态
    identity_verified: bool = False  # 是否已补充实名信息（可选）
    portfolio_uploaded: bool = False  # 作品是否已上传
    contact_verified: bool = False   # 联系方式是否已填
