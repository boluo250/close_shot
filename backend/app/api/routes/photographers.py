from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Header
from jose import JWTError, jwt
from sqlalchemy import Float, case, delete, func, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_user
from app.core.config import settings
from app.db.models import Favorite, Package, Photographer, PhotographerStatus, PortfolioItem, User, UserRole
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
from app.services.geo import haversine_distance_m
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


@router.get("/nearby", response_model=list[PhotographerCardOut])
def nearby(
    lat: float,
    lng: float,
    max_distance_m: int = 5000,
    limit: int = 20,
    offset: int = 0,
    tag: str | None = None,
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
    )

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

    # 排序：距离权重 + 活跃度 + 作品数量
    d_km = (dist / 1000.0).cast(Float)
    f_distance = func.exp(-(d_km / 8.0))
    days_since_active = (func.extract("epoch", func.now() - Photographer.last_active_at) / 86400.0).cast(Float)
    f_activity = func.exp(-(days_since_active / 14.0))
    f_portfolio = case(
        (func.coalesce(portfolio_count_sq.c.portfolio_count, 0) >= 40, 1.0),
        else_=(func.coalesce(portfolio_count_sq.c.portfolio_count, 0) / 40.0),
    ).cast(Float)
    score = (0.5 * f_distance + 0.35 * f_activity + 0.15 * f_portfolio).label("score")

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
            Photographer.service_center_lat.is_not(None),
            Photographer.service_center_lng.is_not(None),
            dist <= max_distance_m,
        )
        .order_by(score.desc(), dist.asc())
        .limit(limit)
        .offset(offset)
    )

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
            _sp,
            _pc,
        ) in rows
    ]
    preview_map: dict[int, list[str]] = {pid: [] for pid in pids}
    if pids:
        items = db.execute(
            select(PortfolioItem.photographer_id, PortfolioItem.watermark_url, PortfolioItem.image_url)
            .where(PortfolioItem.photographer_id.in_(pids))
            .order_by(PortfolioItem.photographer_id.asc(), PortfolioItem.sort_order.asc(), PortfolioItem.id.asc())
        ).all()
        for pid, watermark_url, image_url in items:
            preview_url = watermark_url or image_url
            if pid in preview_map and len(preview_map[pid]) < 3:
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
            distance_copy = "覆盖你所在区域"
        else:
            km = 1 if distance_km < 1 else round(distance_km, 1)
            distance_copy = f"服务于你附近 · 约 {km} km"

        out.append(
            PhotographerCardOut(
                # `PhotographerOut` 里包含 display_name/avatar_url（来自 users 表），
                # 但 `p` 是 Photographer ORM，本身没有这两个字段。
                # 这里需要排除，避免再显式传入时出现重复关键字错误。
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
        portfolio_items=[PortfolioItemOut.model_validate(i) for i in portfolio],
        packages=[PackageOut.model_validate(i) for i in packages],
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

