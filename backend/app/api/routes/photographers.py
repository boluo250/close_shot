from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_user
from app.db.models import Favorite, Photographer, Review, User
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


@router.get("/nearby", response_model=list[PhotographerNearbyOut])
def nearby(
    lat: float,
    lng: float,
    radius_m: int = 5000,
    limit: int = 20,
    offset: int = 0,
    is_online: bool | None = None,
    tag: str | None = None,
    db: Session = Depends(get_db),
) -> list[PhotographerNearbyOut]:
    # 参数校验复用 schema 的约束
    _ = NearbyQuery(lat=lat, lng=lng, radius_m=radius_m, limit=limit, offset=offset, is_online=is_online, tag=tag)

    dist = haversine_distance_m(lat_col=Photographer.lat, lng_col=Photographer.lng, lat=lat, lng=lng).label("distance_m")
    stmt = (
        select(Photographer, dist)
        .where(Photographer.lat.is_not(None), Photographer.lng.is_not(None))
        .where(dist <= radius_m)
        .order_by(dist.asc())
        .limit(limit)
        .offset(offset)
    )
    if is_online is not None:
        stmt = stmt.where(Photographer.is_online == is_online)
    if tag:
        # MVP：tags 字段为逗号分隔文本，简单 contains
        stmt = stmt.where(Photographer.tags.ilike(f"%{tag}%"))

    rows = db.execute(stmt).all()
    out: list[PhotographerNearbyOut] = []
    for p, distance_m in rows:
        out.append(PhotographerNearbyOut(**PhotographerOut.model_validate(p).model_dump(), distance_m=float(distance_m)))
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
    return PhotographerDetailOut(
        **PhotographerOut.model_validate(p).model_dump(),
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
        select(Review)
        .where(Review.photographer_id == photographer_id)
        .order_by(Review.created_at.desc())
        .limit(min(max(limit, 1), 100))
        .offset(max(offset, 0))
    )
    rs = db.scalars(stmt).all()
    return [ReviewOut.model_validate(r) for r in rs]

