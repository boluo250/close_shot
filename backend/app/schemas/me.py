from __future__ import annotations

from pydantic import BaseModel, Field


class MeIdentityOut(BaseModel):
    role: str
    photographer_status: str | None = None
    photographer_reject_reason: str | None = None
    certification_level: int = 0


class PhotographerApplyIn(BaseModel):
    """摄影师入驻认证提交表单"""

    # Step 1: 实名认证（必填）
    real_name: str = Field(min_length=2, max_length=64, description="真实姓名")
    id_card_number: str = Field(min_length=15, max_length=18, description="身份证号")
    id_card_front_url: str | None = Field(default=None, max_length=512, description="身份证正面照片（预留）")
    id_card_back_url: str | None = Field(default=None, max_length=512, description="身份证反面照片（预留）")

    # Step 2: 资料完善（历史字段，已改为可选；保留以兼容旧版本客户端）
    shooting_types: list[str] = Field(default_factory=list, max_length=3, description="拍摄类型（可选，最多三种）")
    experience_years: str | None = Field(default=None, max_length=16, description="从业年限（可选）")
    portfolio_link: str | None = Field(default=None, max_length=512, description="个人摄影主页链接（可选）")

    # Step 3: 联系方式（必填）
    phone: str = Field(min_length=11, max_length=20, description="手机号")
    wechat_id: str = Field(min_length=1, max_length=64, description="微信号")

    # 可选字段
    city: str | None = Field(default=None, max_length=64, description="常驻城市")
    price_range: str | None = Field(default=None, max_length=32, description="报价区间")


class TencentRealPersonVerifyIn(BaseModel):
    """腾讯云实名实人认证请求（占位接口）"""

    real_name: str = Field(min_length=2, max_length=64, description="真实姓名")
    id_card_number: str = Field(min_length=15, max_length=18, description="身份证号")


class TencentRealPersonVerifyOut(BaseModel):
    """腾讯云实名实人认证返回（占位）"""

    provider: str = "tencent_cloud"
    verified: bool = False
    code: str = "NOT_IMPLEMENTED"
    message: str = "腾讯云实名实人认证接口预留中，后续版本接入"


class CertificationStatusOut(BaseModel):
    """认证状态详情"""
    status: str  # pending / approved / rejected
    certification_level: int = 0
    reject_reason: str | None = None
    # 各步骤完成状态
    identity_verified: bool = False  # 实名认证是否已填
    portfolio_uploaded: bool = False  # 作品是否已上传
    contact_verified: bool = False   # 联系方式是否已填
