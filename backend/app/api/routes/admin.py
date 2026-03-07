"""管理后台：摄影师认证审核"""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import case, func, inspect, select, text
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
from app.services.membership import get_contact_access_mode, set_contact_access_mode
from app.services.photographer_ranking import recalculate_photographer_sort_scores

router = APIRouter()


def _require_admin(me: User) -> None:
    if me.role != UserRole.admin.value:
        raise HTTPException(status_code=403, detail="admin role required")


class ContactAccessSettingIn(BaseModel):
    mode: Literal["all", "member"]


class ContactAccessSettingOut(BaseModel):
    mode: str


class PhotographerQualityScoreIn(BaseModel):
    score: float


class DbTableListOut(BaseModel):
    tables: list[str]


class DbTableRowsOut(BaseModel):
    table: str
    columns: list[str]
    rows: list[dict[str, Any]]
    total: int
    limit: int
    offset: int


_DB_BROWSE_TABLES = {
    "users",
    "photographers",
    "portfolio_items",
    "packages",
    "favorites",
    "reviews",
    "analytics_events",
    "app_settings",
    "membership_orders",
    "schedule_blocks",
    "bio_templates",
}
_SAFE_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _require_safe_table_name(table: str) -> str:
    name = (table or "").strip()
    if not _SAFE_IDENT.match(name):
        raise HTTPException(status_code=400, detail="invalid table name")
    if name not in _DB_BROWSE_TABLES:
        raise HTTPException(status_code=403, detail="table is not allowed")
    return name


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


@router.put("/photographers/{photographer_id}/quality-score", response_model=CertificationDetailOut)
def update_photographer_quality_score(
    photographer_id: int,
    payload: PhotographerQualityScoreIn,
    me: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CertificationDetailOut:
    _require_admin(me)
    if payload.score < 1 or payload.score > 10:
        raise HTTPException(status_code=400, detail="score must be between 1 and 10")

    p = db.scalar(select(Photographer).where(Photographer.id == photographer_id))
    if not p:
        raise HTTPException(status_code=404, detail="photographer not found")

    p.quality_score = float(payload.score)
    db.commit()
    recalculate_photographer_sort_scores(db, photographer_ids=[photographer_id])
    db.refresh(p)
    return _photographer_to_detail(p)


@router.get("/settings/contact-access", response_model=ContactAccessSettingOut)
def get_contact_access_setting(
    me: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ContactAccessSettingOut:
    _require_admin(me)
    return ContactAccessSettingOut(mode=get_contact_access_mode(db))


@router.put("/settings/contact-access", response_model=ContactAccessSettingOut)
def update_contact_access_setting(
    payload: ContactAccessSettingIn,
    me: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ContactAccessSettingOut:
    _require_admin(me)
    mode = set_contact_access_mode(db, payload.mode)
    return ContactAccessSettingOut(mode=mode)


@router.get("/db/tables", response_model=DbTableListOut)
def list_db_tables(
    me: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DbTableListOut:
    _require_admin(me)
    try:
        existing = set(inspect(db.bind).get_table_names())
    except Exception as exc:  # pragma: no cover - metadata 兜底
        raise HTTPException(status_code=500, detail="read database metadata failed") from exc
    tables = sorted([name for name in _DB_BROWSE_TABLES if name in existing])
    return DbTableListOut(tables=tables)


@router.get("/db/table-preview", response_model=DbTableRowsOut)
def preview_db_table(
    table: str = Query(description="表名"),
    limit: int = Query(default=20, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    me: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DbTableRowsOut:
    _require_admin(me)
    table_name = _require_safe_table_name(table)

    columns = list(db.execute(text(f"SELECT * FROM {table_name} LIMIT 0")).keys())
    total = db.scalar(text(f"SELECT COUNT(*) FROM {table_name}")) or 0
    rows_raw = db.execute(
        text(
            f"SELECT * FROM {table_name} "
            f"ORDER BY id DESC NULLS LAST "
            f"LIMIT :limit OFFSET :offset"
        ),
        {"limit": limit, "offset": offset},
    ).mappings().all()
    rows = [dict(r) for r in rows_raw]
    return DbTableRowsOut(
        table=table_name,
        columns=columns,
        rows=rows,
        total=int(total),
        limit=limit,
        offset=offset,
    )


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
