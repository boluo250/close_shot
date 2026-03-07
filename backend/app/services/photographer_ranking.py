from __future__ import annotations

import math
from collections.abc import Iterable
from datetime import datetime, timedelta, timezone

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.db.models import AnalyticsEvent, Favorite, Photographer, PhotographerStatus

# 四维模型（距离在查询时实时扣减）：
# - quality: 人工照片质量分 + 履约信誉（contact/click）
# - popularity: 收藏 + 点击 + 浏览（同口径热度）
# - activity: 最近活跃时间衰减
QUALITY_WEIGHT = 0.45
POPULARITY_WEIGHT = 0.30
ACTIVITY_WEIGHT = 0.25


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _as_utc(value: datetime | None, fallback: datetime) -> datetime:
    if value is None:
        return fallback
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def recalculate_photographer_sort_scores(
    db: Session,
    *,
    lookback_days: int = 30,
    photographer_ids: Iterable[int] | None = None,
) -> dict[str, int]:
    since = datetime.now(timezone.utc) - timedelta(days=max(1, lookback_days))
    favorite_sq = (
        select(
            Favorite.photographer_id.label("pid"),
            func.count(Favorite.id).label("favorite_count"),
        )
        .group_by(Favorite.photographer_id)
        .subquery()
    )
    analytics_sq = (
        select(
            AnalyticsEvent.photographer_id.label("pid"),
            func.sum(case((AnalyticsEvent.event_type == "photographer_exposure", 1), else_=0)).label("exposure_count"),
            func.sum(case((AnalyticsEvent.event_type == "photographer_click", 1), else_=0)).label("click_count"),
            func.sum(case((AnalyticsEvent.event_type == "photographer_contact", 1), else_=0)).label("contact_count"),
        )
        .where(AnalyticsEvent.created_at >= since, AnalyticsEvent.photographer_id.is_not(None))
        .group_by(AnalyticsEvent.photographer_id)
        .subquery()
    )

    stmt = (
        select(
            Photographer.id,
            Photographer.quality_score,
            Photographer.last_active_at,
            func.coalesce(favorite_sq.c.favorite_count, 0),
            func.coalesce(analytics_sq.c.exposure_count, 0),
            func.coalesce(analytics_sq.c.click_count, 0),
            func.coalesce(analytics_sq.c.contact_count, 0),
        )
        .outerjoin(favorite_sq, favorite_sq.c.pid == Photographer.id)
        .outerjoin(analytics_sq, analytics_sq.c.pid == Photographer.id)
        .where(Photographer.status == PhotographerStatus.approved.value)
    )
    if photographer_ids:
        stmt = stmt.where(Photographer.id.in_(list(photographer_ids)))

    rows = db.execute(stmt).all()
    now = datetime.now(timezone.utc)
    updates: list[dict] = []
    for pid, quality_score, last_active_at, favorite_count, exposure_count, click_count, contact_count in rows:
        quality_norm = _clamp(float(quality_score or 5.0) / 10.0)

        # 履约信誉（平滑联系率，避免低样本剧烈波动）
        click = int(click_count or 0)
        contact = int(contact_count or 0)
        fulfillment_norm = _clamp((contact + 1.0) / (click + 3.0))

        # 质量维度：人工质量分主导，履约作为校准
        quality = _clamp(0.65 * quality_norm + 0.35 * fulfillment_norm)

        # 热度维度：收藏、点击、曝光合并；log 衰减防刷量级
        favorite = int(favorite_count or 0)
        exposure = int(exposure_count or 0)
        heat_raw = 1.2 * favorite + 0.5 * click + 0.1 * exposure
        popularity = _clamp(1.0 - math.exp(-max(0.0, heat_raw) / 25.0))

        # 活跃维度：越近活跃越高
        active_at = _as_utc(last_active_at, now)
        days_since_active = max((now - active_at).total_seconds() / 86400.0, 0.0)
        activity = _clamp(math.exp(-days_since_active / 7.0))

        score = 100.0 * (
            QUALITY_WEIGHT * quality
            + POPULARITY_WEIGHT * popularity
            + ACTIVITY_WEIGHT * activity
        )
        updates.append({"id": int(pid), "sort_score": round(score, 4)})

    if updates:
        db.bulk_update_mappings(Photographer, updates)
    db.commit()
    return {"updated": len(updates)}
