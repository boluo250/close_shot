"""管理后台：摄影师认证审核"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.models import AnalyticsEvent, Photographer, PhotographerStatus, User, UserRole
from app.db.session import get_db
from app.schemas.analytics import AnalyticsEventListOut, AnalyticsEventOut, AnalyticsSummaryItemOut, AnalyticsSummaryOut
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


@router.get("/analytics/summary", response_model=AnalyticsSummaryOut)
def analytics_summary(
    days: int = Query(default=7, ge=1, le=90),
    limit: int = Query(default=30, ge=1, le=100),
    me: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AnalyticsSummaryOut:
    _require_admin(me)
    since = datetime.now(timezone.utc) - timedelta(days=days)

    base_where = [AnalyticsEvent.created_at >= since]
    total_exposure = db.scalar(
        select(func.count(AnalyticsEvent.id)).where(*base_where, AnalyticsEvent.event_type == "photographer_exposure")
    ) or 0
    total_click = db.scalar(
        select(func.count(AnalyticsEvent.id)).where(*base_where, AnalyticsEvent.event_type == "photographer_click")
    ) or 0
    total_contact = db.scalar(
        select(func.count(AnalyticsEvent.id)).where(*base_where, AnalyticsEvent.event_type == "photographer_contact")
    ) or 0

    exposure_count = func.sum(
        case((AnalyticsEvent.event_type == "photographer_exposure", 1), else_=0)
    ).label("exposure_count")
    click_count = func.sum(case((AnalyticsEvent.event_type == "photographer_click", 1), else_=0)).label("click_count")
    contact_count = func.sum(
        case((AnalyticsEvent.event_type == "photographer_contact", 1), else_=0)
    ).label("contact_count")

    rows = db.execute(
        select(
            AnalyticsEvent.photographer_id,
            User.display_name,
            exposure_count,
            click_count,
            contact_count,
        )
        .join(Photographer, Photographer.id == AnalyticsEvent.photographer_id)
        .join(User, User.id == Photographer.user_id)
        .where(*base_where, AnalyticsEvent.photographer_id.is_not(None))
        .group_by(AnalyticsEvent.photographer_id, User.display_name)
        .order_by(contact_count.desc(), click_count.desc(), exposure_count.desc())
        .limit(limit)
    ).all()

    items: list[AnalyticsSummaryItemOut] = []
    for photographer_id, display_name, exp_cnt, click_cnt, contact_cnt in rows:
        exposure = int(exp_cnt or 0)
        click = int(click_cnt or 0)
        contact = int(contact_cnt or 0)
        ctr = round(click / exposure, 4) if exposure > 0 else 0.0
        contact_rate = round(contact / click, 4) if click > 0 else 0.0
        items.append(
            AnalyticsSummaryItemOut(
                photographer_id=int(photographer_id),
                display_name=display_name,
                exposure_count=exposure,
                click_count=click,
                contact_count=contact,
                ctr=ctr,
                contact_rate=contact_rate,
            )
        )

    return AnalyticsSummaryOut(
        days=days,
        total_exposure=int(total_exposure),
        total_click=int(total_click),
        total_contact=int(total_contact),
        items=items,
    )


@router.get("/analytics/events", response_model=AnalyticsEventListOut)
def analytics_events(
    days: int = Query(default=7, ge=1, le=90),
    event_type: str | None = Query(default=None),
    keyword: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    me: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AnalyticsEventListOut:
    _require_admin(me)
    since = datetime.now(timezone.utc) - timedelta(days=days)

    stmt = (
        select(AnalyticsEvent, User.display_name)
        .outerjoin(Photographer, Photographer.id == AnalyticsEvent.photographer_id)
        .outerjoin(User, User.id == Photographer.user_id)
        .where(AnalyticsEvent.created_at >= since)
    )
    count_stmt = (
        select(func.count(AnalyticsEvent.id))
        .select_from(AnalyticsEvent)
        .outerjoin(Photographer, Photographer.id == AnalyticsEvent.photographer_id)
        .outerjoin(User, User.id == Photographer.user_id)
        .where(AnalyticsEvent.created_at >= since)
    )

    if event_type:
        stmt = stmt.where(AnalyticsEvent.event_type == event_type)
        count_stmt = count_stmt.where(AnalyticsEvent.event_type == event_type)
    if keyword:
        like_pattern = f"%{keyword}%"
        stmt = stmt.where(User.display_name.ilike(like_pattern))
        count_stmt = count_stmt.where(User.display_name.ilike(like_pattern))

    total = int(db.scalar(count_stmt) or 0)
    rows = db.execute(stmt.order_by(AnalyticsEvent.created_at.desc()).limit(limit).offset(offset)).all()

    items: list[AnalyticsEventOut] = []
    for event, display_name in rows:
        try:
            extra = json.loads(event.extra_json) if event.extra_json else {}
            if not isinstance(extra, dict):
                extra = {}
        except json.JSONDecodeError:
            extra = {}
        items.append(
            AnalyticsEventOut(
                id=event.id,
                event_type=event.event_type,
                photographer_id=event.photographer_id,
                display_name=display_name,
                channel=event.channel,
                user_id=event.user_id,
                client_lat=event.client_lat,
                client_lng=event.client_lng,
                extra=extra,
                created_at=event.created_at,
            )
        )

    return AnalyticsEventListOut(items=items, total=total)
