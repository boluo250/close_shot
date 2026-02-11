from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.models import Favorite, Photographer, PhotographerStatus, PortfolioItem, User, UserRole
from app.db.session import get_db
from app.schemas.me import (
    CertificationStatusOut,
    MeIdentityOut,
    PhotographerApplyIn,
    TencentRealPersonVerifyIn,
    TencentRealPersonVerifyOut,
)
from app.schemas.photographer import PhotographerOut

router = APIRouter()

# ---------- 有效拍摄类型白名单 ----------
VALID_SHOOTING_TYPES = {"人像", "情侣", "亲子", "商拍", "活动", "婚礼", "旅拍", "宠物", "美食", "建筑"}
VALID_EXPERIENCE_YEARS = {"1年内", "1-3年", "3年以上"}
VALID_PRICE_RANGES = {"199-399", "399-699", "699+"}
ID_CARD_PATTERN = re.compile(r"^\d{15}$|^\d{17}[\dXx]$")


def _build_certification_status(p: Photographer | None, db: Session) -> CertificationStatusOut:
    """根据摄影师数据构建认证状态详情"""
    if not p:
        return CertificationStatusOut(status="not_applied")

    identity_verified = bool(p.real_name and p.id_card_number)
    portfolio_count = db.scalar(
        select(PortfolioItem.id).where(PortfolioItem.photographer_id == p.id).limit(1)
    )
    has_shooting_types = bool(p.shooting_types and p.shooting_types.strip())
    portfolio_uploaded = bool(portfolio_count is not None or has_shooting_types)
    contact_verified = bool(p.phone and p.wechat_id)

    return CertificationStatusOut(
        status=p.status,
        certification_level=p.certification_level,
        reject_reason=p.reject_reason,
        identity_verified=identity_verified,
        portfolio_uploaded=portfolio_uploaded,
        contact_verified=contact_verified,
    )


@router.get("/favorites", response_model=list[PhotographerOut])
def my_favorites(
    me: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[PhotographerOut]:
    stmt = (
        select(Photographer)
        .join(Favorite, Favorite.photographer_id == Photographer.id)
        .where(Favorite.user_id == me.id)
        .order_by(Favorite.created_at.desc())
    )
    ps = db.scalars(stmt).all()
    return [PhotographerOut.model_validate(p) for p in ps]


@router.get("/identity", response_model=MeIdentityOut)
def my_identity(me: User = Depends(get_current_user)) -> MeIdentityOut:
    status = "not_applied"
    reason = None
    cert_level = 0
    if me.role == UserRole.admin.value:
        status = PhotographerStatus.approved.value
    elif me.photographer:
        status = me.photographer.status
        reason = me.photographer.reject_reason
        cert_level = me.photographer.certification_level
    return MeIdentityOut(
        role=me.role,
        photographer_status=status,
        photographer_reject_reason=reason,
        certification_level=cert_level,
    )


@router.get("/photographer/certification", response_model=CertificationStatusOut)
def get_certification_status(
    me: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CertificationStatusOut:
    """查询当前用户的摄影师认证状态"""
    p = db.scalar(select(Photographer).where(Photographer.user_id == me.id))
    return _build_certification_status(p, db)


@router.post("/photographer/apply", response_model=CertificationStatusOut)
def apply_photographer(
    payload: PhotographerApplyIn,
    me: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CertificationStatusOut:
    """提交摄影师入驻认证"""
    if not ID_CARD_PATTERN.match(payload.id_card_number):
        raise HTTPException(status_code=400, detail="身份证号格式不正确")

    if me.role == UserRole.admin.value:
        return CertificationStatusOut(
            status=PhotographerStatus.approved.value,
            certification_level=3,
            identity_verified=True,
            portfolio_uploaded=True,
            contact_verified=True,
        )

    # 校验拍摄类型
    if len(payload.shooting_types) > 3:
        raise HTTPException(status_code=400, detail="拍摄类型最多选择3个")

    for st in payload.shooting_types:
        if st not in VALID_SHOOTING_TYPES:
            raise HTTPException(status_code=400, detail=f"不支持的拍摄类型：{st}")

    if payload.experience_years and payload.experience_years not in VALID_EXPERIENCE_YEARS:
        raise HTTPException(status_code=400, detail=f"不支持的从业年限选项：{payload.experience_years}")

    if payload.price_range and payload.price_range not in VALID_PRICE_RANGES:
        raise HTTPException(status_code=400, detail=f"不支持的报价区间：{payload.price_range}")

    p = db.scalar(select(Photographer).where(Photographer.user_id == me.id))
    if not p:
        p = Photographer(
            user_id=me.id,
            tags="",
            is_accepting_orders=False,
            service_radius_m=5000,
        )
        db.add(p)

    # 写入认证字段
    p.real_name = payload.real_name
    p.id_card_number = payload.id_card_number
    if payload.id_card_front_url is not None:
        p.id_card_front_url = payload.id_card_front_url
    if payload.id_card_back_url is not None:
        p.id_card_back_url = payload.id_card_back_url
    p.shooting_types = ",".join(payload.shooting_types)
    p.experience_years = payload.experience_years
    p.portfolio_link = payload.portfolio_link
    p.phone = payload.phone
    p.wechat_id = payload.wechat_id
    p.city = payload.city
    p.price_range = payload.price_range

    # 设为待审核
    p.status = PhotographerStatus.pending.value
    p.reject_reason = None

    db.commit()
    db.refresh(p)

    return _build_certification_status(p, db)


@router.post("/photographer/tencent-realname/verify", response_model=TencentRealPersonVerifyOut)
def verify_tencent_real_person(
    payload: TencentRealPersonVerifyIn,
    me: User = Depends(get_current_user),
) -> TencentRealPersonVerifyOut:
    """
    腾讯云实名实人认证预留接口（占位）。
    当前仅做基础参数校验，后续在此处接入腾讯云官方 API。
    """
    _ = me  # 触发登录校验
    if not ID_CARD_PATTERN.match(payload.id_card_number):
        raise HTTPException(status_code=400, detail="身份证号格式不正确")
    return TencentRealPersonVerifyOut()

