from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import Float, delete, func, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_user
from app.db.models import Favorite, Package, Photographer, PortfolioItem, Review, User
from app.db.session import get_db
from app.schemas.photographer import (
    NearbyQuery,
    PhotographerDetailOut,
    PhotographerNearbyOut,
    PhotographerOut,
    PackageOut,
    PortfolioItemOut,
)
from app.schemas.review import ReviewCreateIn, ReviewOut
from app.services.geo import haversine_distance_m

router = APIRouter()


def _parse_csv(text: str | None) -> list[str]:
    return [x.strip() for x in (text or "").split(",") if x.strip()]


def _parse_rate_card(text: str | None) -> list[dict]:
    if not text:
        return []
    try:
        items = json.loads(text)
    except json.JSONDecodeError:
        return []
    if not isinstance(items, list):
        return []
    out: list[dict] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        mode = str(item.get("mode") or "").strip()
        price_cents = item.get("price_cents")
        unit = item.get("unit")
        if not name or mode not in {"hour", "item"}:
            continue
        if not isinstance(price_cents, int):
            continue
        out.append(
            {
                "name": name,
                "mode": mode,
                "price_cents": price_cents,
                "unit": str(unit).strip() if unit else None,
            }
        )
    return out


def _rate_min(items: list[dict], mode: str) -> int | None:
    prices = [x["price_cents"] for x in items if x.get("mode") == mode and isinstance(x.get("price_cents"), int)]
    return min(prices) if prices else None


@router.get("/nearby", response_model=list[PhotographerNearbyOut])
def nearby(
    lat: float,
    lng: float,
    max_distance_m: int = 50000,
    limit: int = 20,
    offset: int = 0,
    is_accepting_orders: bool | None = None,
    include_paused: bool = False,
    tag: str | None = None,
    db: Session = Depends(get_db),
) -> list[PhotographerNearbyOut]:
    # 参数校验复用 schema 的约束
    _ = NearbyQuery(
        lat=lat,
        lng=lng,
        max_distance_m=max_distance_m,
        limit=limit,
        offset=offset,
        is_accepting_orders=is_accepting_orders,
        tag=tag,
    )

    dist = haversine_distance_m(
        lat_col=Photographer.service_center_lat,
        lng_col=Photographer.service_center_lng,
        lat=lat,
        lng=lng,
    ).label("distance_m")

    rating_sq = (
        select(
            Review.photographer_id.label("pid"),
            func.avg(Review.rating).label("rating_avg"),
            func.count(Review.id).label("rating_count"),
        )
        .group_by(Review.photographer_id)
        .subquery()
    )
    price_sq = (
        select(Package.photographer_id.label("pid"), func.min(Package.price_cents).label("starting_price_cents"))
        .where(Package.is_active.is_(True))
        .group_by(Package.photographer_id)
        .subquery()
    )
    portfolio_count_sq = (
        select(
            PortfolioItem.photographer_id.label("pid"),
            func.count(PortfolioItem.id).label("portfolio_count"),
        )
        .group_by(PortfolioItem.photographer_id)
        .subquery()
    )

    # 排序：距离权重 + 活跃度 + 评分（成交量后续接订单再加）
    d_km = (dist / 1000.0).cast(Float)
    f_distance = func.exp(-(d_km / 8.0))
    days_since_active = (func.extract("epoch", func.now() - Photographer.last_active_at) / 86400.0).cast(Float)
    f_activity = func.exp(-(days_since_active / 14.0))
    rating_avg = func.coalesce(rating_sq.c.rating_avg, 0.0).cast(Float)
    f_rating = func.least(func.greatest((rating_avg - 4.0) / 1.0, 0.0), 1.0)
    score = (0.35 * f_distance + 0.25 * f_activity + 0.25 * f_rating).label("score")

    stmt = (
        select(
            Photographer,
            User.display_name,
            User.avatar_url,
            dist,
            score,
            rating_sq.c.rating_avg,
            rating_sq.c.rating_count,
            price_sq.c.starting_price_cents,
            portfolio_count_sq.c.portfolio_count,
        )
        .join(User, User.id == Photographer.user_id)
        .outerjoin(rating_sq, rating_sq.c.pid == Photographer.id)
        .outerjoin(price_sq, price_sq.c.pid == Photographer.id)
        .outerjoin(portfolio_count_sq, portfolio_count_sq.c.pid == Photographer.id)
        .where(Photographer.service_center_lat.is_not(None), Photographer.service_center_lng.is_not(None))
        # 临时放宽距离限制：不做服务半径和最大距离过滤
        .order_by(score.desc(), dist.asc())
        .limit(limit)
        .offset(offset)
    )

    if is_accepting_orders is not None:
        stmt = stmt.where(Photographer.is_accepting_orders == is_accepting_orders)
    elif not include_paused:
        stmt = stmt.where(Photographer.is_accepting_orders.is_(True))
    if tag:
        # MVP：tags 字段为逗号分隔文本，简单 contains
        stmt = stmt.where(Photographer.tags.ilike(f"%{tag}%"))

    rows = db.execute(stmt).all()

    # 一次性取出这些摄影师的前 3 张作品，用于首页卡片预览（避免 N+1）
    pids = [
        p.id
        for (
            p,
            _display_name,
            _avatar_url,
            _distance_m,
            _score,
            _ra,
            _rc,
            _sp,
            _pc,
        ) in rows
    ]
    preview_map: dict[int, list[str]] = {pid: [] for pid in pids}
    if pids:
        items = db.execute(
            select(PortfolioItem.photographer_id, PortfolioItem.image_url)
            .where(PortfolioItem.photographer_id.in_(pids))
            .order_by(PortfolioItem.photographer_id.asc(), PortfolioItem.sort_order.asc(), PortfolioItem.id.asc())
        ).all()
        for pid, image_url in items:
            if pid in preview_map and len(preview_map[pid]) < 3:
                preview_map[pid].append(image_url)

    out: list[PhotographerNearbyOut] = []
    for (
        p,
        display_name,
        avatar_url,
        distance_m,
        _score,
        _rating_avg,
        _rating_count,
        starting_price_cents,
        _portfolio_count,
    ) in rows:
        distance_m_f = float(distance_m)
        distance_km = distance_m_f / 1000.0
        rate_card = _parse_rate_card(p.rate_card_json)
        rate_hour_min = _rate_min(rate_card, "hour")
        rate_item_min = _rate_min(rate_card, "item")

        # 距离文案：明确是“服务中心点/服务范围”语义，避免暗示实时位置
        if p.service_radius_m >= 20000:
            distance_copy = "覆盖你所在区域"
        else:
            km = 1 if distance_km < 1 else round(distance_km, 1)
            distance_copy = f"服务于你附近 · 约 {km} km"

        out.append(
            PhotographerNearbyOut(
                # `PhotographerOut` 里包含 display_name/avatar_url（来自 users 表），
                # 但 `p` 是 Photographer ORM，本身没有这两个字段。
                # 这里需要排除，避免再显式传入时出现重复关键字错误。
                **PhotographerOut.model_validate(p).model_dump(
                    exclude={"display_name", "avatar_url", "equipment_list", "drone_models", "rate_card"}
                ),
                display_name=display_name,
                avatar_url=avatar_url,
                equipment_list=_parse_csv(p.equipment_list),
                drone_models=_parse_csv(p.drone_models),
                rate_card=rate_card,
                distance_m=distance_m_f,
                distance_km=float(distance_km),
                distance_copy=distance_copy,
                starting_price_cents=int(starting_price_cents) if starting_price_cents is not None else None,
                rating_avg=float(_rating_avg) if _rating_avg is not None else None,
                rating_count=int(_rating_count) if _rating_count is not None else None,
                preview_image_urls=preview_map.get(p.id, []),
                portfolio_count=int(_portfolio_count or 0),
                rate_hour_min_cents=rate_hour_min,
                rate_item_min_cents=rate_item_min,
            )
        )
    return out


@router.get("/{photographer_id}", response_model=PhotographerDetailOut)
def get_detail(photographer_id: int, db: Session = Depends(get_db)) -> PhotographerDetailOut:
    p = db.scalar(
        select(Photographer)
        .where(Photographer.id == photographer_id)
        .options(selectinload(Photographer.portfolio_items), selectinload(Photographer.packages))
    )
    if not p:
        raise HTTPException(status_code=404, detail="photographer not found")

    rating_avg, rating_count = db.execute(
        select(func.avg(Review.rating), func.count(Review.id)).where(Review.photographer_id == photographer_id)
    ).one()

    portfolio = sorted(p.portfolio_items, key=lambda x: (x.sort_order, x.id))
    packages = [x for x in p.packages if x.is_active]
    rate_card = _parse_rate_card(p.rate_card_json)
    return PhotographerDetailOut(
        **PhotographerOut.model_validate(p).model_dump(
            exclude={"display_name", "avatar_url", "equipment_list", "drone_models", "rate_card"}
        ),
        display_name=p.user.display_name if p.user else None,
        avatar_url=p.user.avatar_url if p.user else None,
        equipment_list=_parse_csv(p.equipment_list),
        drone_models=_parse_csv(p.drone_models),
        rate_card=rate_card,
        portfolio_items=[PortfolioItemOut.model_validate(i) for i in portfolio],
        packages=[PackageOut.model_validate(i) for i in packages],
        rating_avg=float(rating_avg) if rating_avg is not None else None,
        rating_count=int(rating_count or 0),
    )


@router.post("/{photographer_id}/favorite")
def favorite_add(
    photographer_id: int,
    me: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    exists = db.scalar(
        select(Favorite.id).where(Favorite.user_id == me.id, Favorite.photographer_id == photographer_id)
    )
    if not exists:
        db.add(Favorite(user_id=me.id, photographer_id=photographer_id))
        db.commit()
    return {"ok": True}


@router.delete("/{photographer_id}/favorite")
def favorite_remove(
    photographer_id: int,
    me: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    db.execute(
        delete(Favorite).where(Favorite.user_id == me.id, Favorite.photographer_id == photographer_id)
    )
    db.commit()
    return {"ok": True}


@router.post("/{photographer_id}/reviews", response_model=ReviewOut)
def create_review(
    photographer_id: int,
    payload: ReviewCreateIn,
    me: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ReviewOut:
    # MVP：不做“一个订单一个评价”等规则，仅允许登录用户直接评价
    r = Review(user_id=me.id, photographer_id=photographer_id, rating=payload.rating, content=payload.content)
    db.add(r)
    db.commit()
    db.refresh(r)
    return ReviewOut.model_validate(r)


@router.get("/{photographer_id}/reviews", response_model=list[ReviewOut])
def list_reviews(
    photographer_id: int,
    limit: int = 20,
    offset: int = 0,
    db: Session = Depends(get_db),
) -> list[ReviewOut]:
    stmt = (
        select(Review, User.display_name, User.avatar_url)
        .outerjoin(User, User.id == Review.user_id)
        .where(Review.photographer_id == photographer_id)
        .order_by(Review.created_at.desc())
        .limit(min(max(limit, 1), 100))
        .offset(max(offset, 0))
    )
    rows = db.execute(stmt).all()
    out: list[ReviewOut] = []
    for r, display_name, avatar_url in rows:
        out.append(
            ReviewOut.model_validate(r).model_copy(
                update={"user_display_name": display_name, "user_avatar_url": avatar_url}
            )
        )
    return out

