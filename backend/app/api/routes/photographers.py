from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Header
from jose import JWTError, jwt
from sqlalchemy import Float, case, delete, func, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_user
from app.core.config import settings
from app.db.models import Favorite, Package, Photographer, PhotographerStatus, PortfolioItem, Review, ReviewStatus, User, UserRole
from app.db.session import get_db
from app.schemas.me import MeIdentityOut
from app.schemas.photographer import (
    NearbyQuery,
    PhotographerCardOut,
    PhotographerDetailOut,
    PhotographerOut,
    PackageOut,
    PortfolioItemOut,
)
from app.schemas.review import ReviewOut
from app.services.geo import haversine_distance_m
from app.services.media_url import object_key_to_url
from app.services.membership import can_view_contact

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
        if mode == "item":
            mode = "photo"
        if not name or mode not in {"hour", "photo"}:
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


def _resolve_optional_user(db: Session, authorization: str | None) -> User | None:
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization.removeprefix("Bearer ").strip()
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_alg])
        user_id = int(payload.get("sub"))
    except (JWTError, ValueError, TypeError):
        return None
    return db.scalar(select(User).where(User.id == user_id))


@router.post("/apply", response_model=MeIdentityOut)
def apply_photographer(me: User = Depends(get_current_user), db: Session = Depends(get_db)) -> MeIdentityOut:
    if me.role == UserRole.admin.value:
        return MeIdentityOut(
            role=me.role,
            photographer_status=PhotographerStatus.approved.value,
            photographer_reject_reason=None,
            is_member=me.is_member,
            member_expires_at=me.member_expires_at,
        )

    photographer = db.scalar(select(Photographer).where(Photographer.user_id == me.id))
    if photographer and photographer.status == PhotographerStatus.approved.value:
        return MeIdentityOut(
            role=me.role,
            photographer_status=photographer.status,
            photographer_reject_reason=photographer.reject_reason,
            is_member=me.is_member,
            member_expires_at=me.member_expires_at,
        )

    if not photographer:
        photographer = Photographer(
            user_id=me.id,
            tags="",
            is_accepting_orders=False,
            service_radius_m=5000,
            status=PhotographerStatus.pending.value,
        )
        db.add(photographer)
    else:
        photographer.status = PhotographerStatus.pending.value
        photographer.reject_reason = None

    if me.role != UserRole.photographer.value:
        me.role = UserRole.photographer.value

    db.commit()
    db.refresh(me)
    db.refresh(photographer)
    return MeIdentityOut(
        role=me.role,
        photographer_status=photographer.status,
        photographer_reject_reason=photographer.reject_reason,
        is_member=me.is_member,
        member_expires_at=me.member_expires_at,
    )


def _rate_min(items: list[dict], mode: str) -> int | None:
    prices = [x["price_cents"] for x in items if x.get("mode") == mode and isinstance(x.get("price_cents"), int)]
    return min(prices) if prices else None


def _build_nearby_stmt(
    *,
    lat: float,
    lng: float,
    radius_m: int,
    limit: int,
    offset: int,
    tag: str | None,
    sort_mode: str,
):
    dist = haversine_distance_m(
        lat_col=Photographer.service_center_lat,
        lng_col=Photographer.service_center_lng,
        lat=lat,
        lng=lng,
    ).label("distance_m")

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

    base_score = func.coalesce(Photographer.sort_score, 50.0)
    if sort_mode == "far":
        distance_ratio_far = func.least(dist / 300000.0, 1.0).cast(Float)
        distance_penalty = (12.0 * distance_ratio_far).cast(Float)
        travel_bonus = case(
            (Photographer.service_radius_m >= 50000, 5.0),
            (Photographer.service_radius_m >= 20000, 2.5),
            else_=0.0,
        ).cast(Float)
        score = (base_score - distance_penalty + travel_bonus).label("score")
    else:
        # 近距离排序使用固定 50km 惩罚基准，避免因搜索半径变大导致近距优势被稀释
        distance_ratio_near = func.least(dist / 50000.0, 1.0).cast(Float)
        distance_penalty = (35.0 * distance_ratio_near).cast(Float)
        score = (base_score - distance_penalty).label("score")

    stmt = (
        select(
            Photographer,
            User.display_name,
            User.avatar_url,
            dist,
            score,
            price_sq.c.starting_price_cents,
            portfolio_count_sq.c.portfolio_count,
        )
        .join(User, User.id == Photographer.user_id)
        .outerjoin(price_sq, price_sq.c.pid == Photographer.id)
        .outerjoin(portfolio_count_sq, portfolio_count_sq.c.pid == Photographer.id)
        .where(
            Photographer.status == PhotographerStatus.approved.value,
            Photographer.is_accepting_orders.is_(True),
            Photographer.service_center_lat.is_not(None),
            Photographer.service_center_lng.is_not(None),
            dist <= radius_m,
        )
        .order_by(score.desc(), dist.asc())
        .limit(limit)
        .offset(offset)
    )
    if tag:
        stmt = stmt.where(Photographer.tags.ilike(f"%{tag}%"))
    return stmt


def _build_nearby_cards(db: Session, rows) -> list[PhotographerCardOut]:
    # 一次性取出这些摄影师的前 3 张作品，用于首页卡片预览（避免 N+1）
    pids = [
        p.id
        for (
            p,
            _display_name,
            _avatar_url,
            _distance_m,
            _score,
            _sp,
            _pc,
        ) in rows
    ]
    preview_map: dict[int, list[str]] = {pid: [] for pid in pids}
    if pids:
        items = db.execute(
            select(
                PortfolioItem.photographer_id,
                PortfolioItem.watermark_object_key,
                PortfolioItem.watermark_url,
                PortfolioItem.image_object_key,
                PortfolioItem.image_url,
            )
            .where(PortfolioItem.photographer_id.in_(pids))
            .order_by(PortfolioItem.photographer_id.asc(), PortfolioItem.sort_order.asc(), PortfolioItem.id.asc())
        ).all()
        for pid, watermark_object_key, watermark_url, image_object_key, image_url in items:
            preview_url = (
                object_key_to_url(watermark_object_key)
                or watermark_url
                or object_key_to_url(image_object_key)
                or image_url
            )
            if preview_url and pid in preview_map and len(preview_map[pid]) < 3:
                preview_map[pid].append(preview_url)

    out: list[PhotographerCardOut] = []
    for (
        p,
        display_name,
        avatar_url,
        distance_m,
        _score,
        starting_price_cents,
        _portfolio_count,
    ) in rows:
        distance_m_f = float(distance_m)
        distance_km = distance_m_f / 1000.0
        rate_card = _parse_rate_card(p.rate_card_json)
        rate_hour_min = _rate_min(rate_card, "hour")
        rate_item_min = _rate_min(rate_card, "photo")
        can_view, mode, lock_reason = can_view_contact(db, viewer=None, photographer=p)

        # 距离文案：明确是“服务中心点/服务范围”语义，避免暗示实时位置
        if p.service_radius_m >= 20000:
            distance_copy = f"可覆盖你附近 · 约 {round(distance_km, 1)} km"
        else:
            km = 1 if distance_km < 1 else round(distance_km, 1)
            distance_copy = f"服务于你附近 · 约 {km} km"

        out.append(
            PhotographerCardOut(
                **PhotographerOut.model_validate(p).model_dump(
                    exclude={
                        "display_name",
                        "avatar_url",
                        "phone",
                        "wechat_id",
                        "can_view_contact",
                        "contact_access_mode",
                        "contact_lock_reason",
                        "equipment_list",
                        "drone_models",
                        "rate_card",
                    }
                ),
                display_name=display_name,
                avatar_url=avatar_url,
                phone=p.phone if can_view else None,
                wechat_id=p.wechat_id if can_view else None,
                can_view_contact=can_view,
                contact_access_mode=mode,
                contact_lock_reason=lock_reason,
                equipment_list=_parse_csv(p.equipment_list),
                drone_models=_parse_csv(p.drone_models),
                rate_card=rate_card,
                distance_m=distance_m_f,
                distance_km=float(distance_km),
                distance_copy=distance_copy,
                starting_price_cents=int(starting_price_cents) if starting_price_cents is not None else None,
                preview_image_urls=preview_map.get(p.id, []),
                portfolio_count=int(_portfolio_count or 0),
                rate_hour_min_cents=rate_hour_min,
                rate_item_min_cents=rate_item_min,
            )
        )
    return out


@router.get("/nearby", response_model=list[PhotographerCardOut])
def nearby(
    lat: float,
    lng: float,
    max_distance_m: int = 5000,
    limit: int = 20,
    offset: int = 0,
    tag: str | None = None,
    auto_expand: bool = False,
    db: Session = Depends(get_db),
) -> list[PhotographerCardOut]:
    # 参数校验复用 schema 的约束
    _ = NearbyQuery(
        lat=lat,
        lng=lng,
        max_distance_m=max_distance_m,
        limit=limit,
        offset=offset,
        tag=tag,
        auto_expand=auto_expand,
    )
    if not auto_expand:
        rows = db.execute(
            _build_nearby_stmt(
                lat=lat,
                lng=lng,
                radius_m=max_distance_m,
                limit=limit,
                offset=offset,
                tag=tag,
                sort_mode="near",
            )
        ).all()
        return _build_nearby_cards(db, rows)

    # 自动扩圈：近距离优先，不足则扩展到省内/跨省/全国可服务
    target_total = limit + offset
    tier_specs = [
        {"radius_m": 50000, "sort_mode": "near"},      # 0-50km
        {"radius_m": 300000, "sort_mode": "far"},      # 50-300km
        {"radius_m": 1000000, "sort_mode": "far"},     # 300-1000km
        {"radius_m": 5000000, "sort_mode": "far"},     # 全国兜底
    ]

    dedup_ids: set[int] = set()
    merged_rows = []
    per_tier_limit = min(max(20, target_total * 2), 100)
    for tier in tier_specs:
        if len(merged_rows) >= target_total:
            break
        rows = db.execute(
            _build_nearby_stmt(
                lat=lat,
                lng=lng,
                radius_m=tier["radius_m"],
                limit=per_tier_limit,
                offset=0,
                tag=tag,
                sort_mode=tier["sort_mode"],
            )
        ).all()
        for row in rows:
            photographer = row[0]
            if photographer.id in dedup_ids:
                continue
            dedup_ids.add(photographer.id)
            merged_rows.append(row)
            if len(merged_rows) >= target_total:
                break

    return _build_nearby_cards(db, merged_rows[offset : offset + limit])


@router.get("/{photographer_id}", response_model=PhotographerDetailOut)
def get_detail(
    photographer_id: int,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> PhotographerDetailOut:
    p = db.scalar(
        select(Photographer)
        .where(Photographer.id == photographer_id)
        .options(selectinload(Photographer.portfolio_items), selectinload(Photographer.packages))
    )
    if not p:
        raise HTTPException(status_code=404, detail="photographer not found")

    portfolio = sorted(p.portfolio_items, key=lambda x: (x.sort_order, x.id))
    packages = [x for x in p.packages if x.is_active]
    rate_card = _parse_rate_card(p.rate_card_json)
    viewer = _resolve_optional_user(db, authorization)
    is_favorited = False
    if viewer:
        is_favorited = bool(
            db.scalar(
                select(Favorite.id).where(Favorite.user_id == viewer.id, Favorite.photographer_id == photographer_id)
            )
        )
    can_view, mode, lock_reason = can_view_contact(db, viewer=viewer, photographer=p)
    portfolio_out: list[PortfolioItemOut] = []
    for item in portfolio:
        payload = PortfolioItemOut.model_validate(item).model_dump()
        payload["image_url"] = object_key_to_url(item.image_object_key) or item.image_url
        payload["watermark_url"] = object_key_to_url(item.watermark_object_key) or item.watermark_url
        portfolio_out.append(PortfolioItemOut(**payload))

    review_rows = db.execute(
        select(Review, User)
        .outerjoin(User, User.id == Review.user_id)
        .where(
            Review.photographer_id == photographer_id,
            Review.status == ReviewStatus.approved.value,
        )
        .order_by(Review.created_at.desc(), Review.id.desc())
        .limit(20)
    ).all()
    reviews = [
        ReviewOut(
            id=int(review.id),
            user_id=int(review.user_id) if review.user_id is not None else None,
            photographer_id=int(review.photographer_id),
            rating=int(review.rating),
            content=review.content,
            status=review.status,
            user_display_name=user.display_name if user else None,
            user_avatar_url=user.avatar_url if user else None,
            created_at=review.created_at,
            updated_at=review.updated_at,
        )
        for review, user in review_rows
    ]

    return PhotographerDetailOut(
        **PhotographerOut.model_validate(p).model_dump(
            exclude={
                "display_name",
                "avatar_url",
                "phone",
                "wechat_id",
                "can_view_contact",
                "contact_access_mode",
                "contact_lock_reason",
                "equipment_list",
                "drone_models",
                "rate_card",
            }
        ),
        display_name=p.user.display_name if p.user else None,
        avatar_url=p.user.avatar_url if p.user else None,
        phone=p.phone if can_view else None,
        wechat_id=p.wechat_id if can_view else None,
        can_view_contact=can_view,
        contact_access_mode=mode,
        contact_lock_reason=lock_reason,
        equipment_list=_parse_csv(p.equipment_list),
        drone_models=_parse_csv(p.drone_models),
        rate_card=rate_card,
        is_favorited=is_favorited,
        portfolio_items=portfolio_out,
        packages=[PackageOut.model_validate(i) for i in packages],
        reviews=reviews,
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
