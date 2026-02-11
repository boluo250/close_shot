"""管理后台：摄影师认证审核"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.models import Photographer, PhotographerStatus, User, UserRole
from app.db.session import get_db
from app.schemas.photographer import (
    CertificationDetailOut,
    CertificationListOut,
    CertificationReviewIn,
)

router = APIRouter()


def _require_admin(me: User) -> None:
    if me.role != UserRole.admin.value:
        raise HTTPException(status_code=403, detail="admin role required")


def _photographer_to_detail(p: Photographer) -> CertificationDetailOut:
    """将 ORM 对象转为输出 schema，附带 user 字段"""
    data = CertificationDetailOut.model_validate(p).model_dump()
    data["display_name"] = p.user.display_name if p.user else None
    data["avatar_url"] = p.user.avatar_url if p.user else None
    return CertificationDetailOut(**data)


# ---------- 认证列表 ----------

@router.get("/certifications", response_model=CertificationListOut)
def list_certifications(
    status: str | None = Query(default=None, description="按状态筛选: pending / approved / rejected"),
    keyword: str | None = Query(default=None, description="按姓名/手机号搜索"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    me: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CertificationListOut:
    """查询摄影师认证列表（管理员专用）"""
    _require_admin(me)

    q = select(Photographer).join(User, User.id == Photographer.user_id)
    count_q = select(func.count(Photographer.id)).join(User, User.id == Photographer.user_id)

    if status:
        q = q.where(Photographer.status == status)
        count_q = count_q.where(Photographer.status == status)

    if keyword:
        like_pattern = f"%{keyword}%"
        q = q.where(
            (Photographer.real_name.ilike(like_pattern))
            | (Photographer.phone.ilike(like_pattern))
            | (User.display_name.ilike(like_pattern))
        )
        count_q = count_q.where(
            (Photographer.real_name.ilike(like_pattern))
            | (Photographer.phone.ilike(like_pattern))
            | (User.display_name.ilike(like_pattern))
        )

    total = db.scalar(count_q) or 0
    photographers = db.scalars(
        q.order_by(Photographer.created_at.desc()).limit(limit).offset(offset)
    ).all()

    return CertificationListOut(
        items=[_photographer_to_detail(p) for p in photographers],
        total=total,
    )


# ---------- 认证详情 ----------

@router.get("/certifications/{photographer_id}", response_model=CertificationDetailOut)
def get_certification(
    photographer_id: int,
    me: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CertificationDetailOut:
    """查看某个摄影师的认证详情（管理员专用）"""
    _require_admin(me)
    p = db.scalar(select(Photographer).where(Photographer.id == photographer_id))
    if not p:
        raise HTTPException(status_code=404, detail="photographer not found")
    return _photographer_to_detail(p)


# ---------- 审核操作（通过 / 驳回） ----------

@router.post("/certifications/{photographer_id}/review", response_model=CertificationDetailOut)
def review_certification(
    photographer_id: int,
    payload: CertificationReviewIn,
    me: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CertificationDetailOut:
    """
    审核摄影师认证：
    - action=approve  → status=approved, certification_level=1, user.role=photographer
    - action=reject   → status=rejected, 附带 reject_reason
    """
    _require_admin(me)

    p = db.scalar(select(Photographer).where(Photographer.id == photographer_id))
    if not p:
        raise HTTPException(status_code=404, detail="photographer not found")

    if payload.action == "approve":
        p.status = PhotographerStatus.approved.value
        p.reject_reason = None
        p.certification_level = max(p.certification_level, 1)  # 至少 Lv1
        # 同步升级 user.role
        if p.user and p.user.role != UserRole.photographer.value:
            p.user.role = UserRole.photographer.value
    elif payload.action == "reject":
        if not payload.reject_reason:
            raise HTTPException(status_code=400, detail="驳回时必须填写原因")
        p.status = PhotographerStatus.rejected.value
        p.reject_reason = payload.reject_reason
    else:
        raise HTTPException(status_code=400, detail="action 必须是 approve 或 reject")

    db.commit()
    db.refresh(p)
    return _photographer_to_detail(p)
