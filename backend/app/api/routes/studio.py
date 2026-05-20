from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import PurePosixPath

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.models import Package, Photographer, PortfolioItem, ScheduleBlock, User, UserRole
from app.db.session import get_db
from app.schemas.photographer import PackageOut, PhotographerOut, PortfolioItemOut
from app.schemas.studio import (
    PackageCreateIn,
    PackageListOut,
    PackageUpdateIn,
    PhotographerUpdateIn,
    PortfolioCreateIn,
    PortfolioListOut,
    PortfolioUpdateIn,
    ScheduleItemOut,
    ScheduleListOut,
    ScheduleUpsertIn,
    StudioMeOut,
)
from app.services.image_watermark import add_text_watermark
from app.services.media_url import object_key_from_url, object_key_to_url
from app.services.storage import get_object_stream, put_object_bytes

router = APIRouter()


def _require_photographer_user(me: User) -> None:
    if me.role not in (UserRole.photographer.value, UserRole.admin.value):
        raise HTTPException(status_code=403, detail="photographer role required")


def _get_my_photographer(db: Session, me: User) -> Photographer:
    p = db.scalar(select(Photographer).where(Photographer.user_id == me.id))
    if not p:
        raise HTTPException(status_code=404, detail="photographer profile not found")
    return p


def _resolve_portfolio_urls(*, image_url: str | None, image_object_key: str | None, watermark_url: str | None, watermark_object_key: str | None) -> tuple[str | None, str | None]:
    resolved_image = object_key_to_url(image_object_key) or image_url
    resolved_watermark = object_key_to_url(watermark_object_key) or watermark_url
    return resolved_image, resolved_watermark


@router.get("/me", response_model=StudioMeOut)
def get_me(me: User = Depends(get_current_user), db: Session = Depends(get_db)) -> StudioMeOut:
    _require_photographer_user(me)
    p = _get_my_photographer(db, me)
    payload = PhotographerOut.model_validate(p).model_dump()
    payload["display_name"] = p.user.display_name if p.user else None
    payload["avatar_url"] = p.user.avatar_url if p.user else None
    return StudioMeOut(photographer=PhotographerOut(**payload))


@router.put("/me", response_model=StudioMeOut)
def update_me(
    payload: PhotographerUpdateIn,
    me: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> StudioMeOut:
    _require_photographer_user(me)
    p = _get_my_photographer(db, me)
    data = payload.model_dump(exclude_unset=True)
    # 报价单安全检查（文本 + mode）
    if data.get("rate_card") is not None:
        normalized: list[dict] = []
        for it in data.get("rate_card") or []:
            mode = it.get("mode")
            # 兼容旧值 item → photo（按张数）
            if mode == "item":
                mode = "photo"
                it["mode"] = "photo"
            if mode not in ("hour", "photo"):
                raise HTTPException(status_code=400, detail="invalid rate_card.mode")
            normalized.append(it)
        data["rate_card"] = normalized
    if data.get("avatar_object_key"):
        stream, _ = get_object_stream(data["avatar_object_key"])
        if p.user and data.get("avatar_url") is None:
            data["avatar_url"] = object_key_to_url(data["avatar_object_key"])
    if data.get("cover_object_key"):
        stream, _ = get_object_stream(data["cover_object_key"])
        if data.get("cover_url") is None:
            data["cover_url"] = object_key_to_url(data["cover_object_key"])
    if "display_name" in data and p.user:
        display_name = (data.pop("display_name") or "").strip() or None
        p.user.display_name = display_name
    if data.get("avatar_url") is not None and p.user:
        p.user.avatar_url = data.pop("avatar_url")
    data.pop("avatar_object_key", None)
    data.pop("cover_object_key", None)
    # 处理 rate_card：保存为 json 文本
    if "rate_card" in data:
        p.rate_card_json = json.dumps(data.pop("rate_card") or [], ensure_ascii=False)
    for k, v in data.items():
        setattr(p, k, v)
    # 作为“活跃度”的输入：摄影师主动维护资料/接单范围时更新活跃时间
    p.last_active_at = datetime.now(timezone.utc)
    db.add(p)
    db.commit()
    db.refresh(p)
    payload = PhotographerOut.model_validate(p).model_dump()
    payload["display_name"] = p.user.display_name if p.user else None
    payload["avatar_url"] = p.user.avatar_url if p.user else None
    return StudioMeOut(photographer=PhotographerOut(**payload))


@router.get("/portfolio", response_model=PortfolioListOut)
def list_portfolio(me: User = Depends(get_current_user), db: Session = Depends(get_db)) -> PortfolioListOut:
    _require_photographer_user(me)
    p = _get_my_photographer(db, me)
    items = db.scalars(
        select(PortfolioItem)
        .where(PortfolioItem.photographer_id == p.id)
        .order_by(PortfolioItem.is_pinned.desc(), PortfolioItem.sort_order.asc(), PortfolioItem.id.asc())
    ).all()
    out: list[PortfolioItemOut] = []
    for i in items:
        image_url, watermark_url = _resolve_portfolio_urls(
            image_url=i.image_url,
            image_object_key=i.image_object_key,
            watermark_url=i.watermark_url,
            watermark_object_key=i.watermark_object_key,
        )
        payload = PortfolioItemOut.model_validate(i).model_dump()
        payload["image_url"] = image_url or i.image_url
        payload["watermark_url"] = watermark_url
        out.append(PortfolioItemOut(**payload))
    return PortfolioListOut(items=out)


@router.post("/portfolio", response_model=PortfolioItemOut)
def create_portfolio(
    payload: PortfolioCreateIn,
    me: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PortfolioItemOut:
    _require_photographer_user(me)
    p = _get_my_photographer(db, me)
    data = payload.model_dump()
    image_object_key = data.get("image_object_key") or object_key_from_url(data.get("image_url"))
    if not image_object_key:
        raise HTTPException(status_code=400, detail="image_object_key required for security checks")
    stream, _ = get_object_stream(image_object_key)
    image_bytes = stream.read()
    watermark_key = str(PurePosixPath("watermark") / PurePosixPath(image_object_key))
    watermark_bytes, watermark_content_type = add_text_watermark(image_bytes, watermark_text="边拍")
    put_object_bytes(object_key=watermark_key, data=watermark_bytes, content_type=watermark_content_type)
    data["image_object_key"] = image_object_key
    data["image_url"] = object_key_to_url(image_object_key) or data.get("image_url")
    data["watermark_object_key"] = watermark_key
    data["watermark_url"] = object_key_to_url(watermark_key)
    item = PortfolioItem(photographer_id=p.id, **data)
    db.add(item)
    db.commit()
    db.refresh(item)
    return PortfolioItemOut.model_validate(item)


@router.put("/portfolio/{item_id}", response_model=PortfolioItemOut)
def update_portfolio(
    item_id: int,
    payload: PortfolioUpdateIn,
    me: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PortfolioItemOut:
    _require_photographer_user(me)
    p = _get_my_photographer(db, me)
    item = db.scalar(select(PortfolioItem).where(PortfolioItem.id == item_id, PortfolioItem.photographer_id == p.id))
    if not item:
        raise HTTPException(status_code=404, detail="portfolio item not found")
    data = payload.model_dump(exclude_unset=True)
    if data.get("image_object_key") or data.get("image_url"):
        image_object_key = data.get("image_object_key") or object_key_from_url(data.get("image_url"))
        if not image_object_key:
            raise HTTPException(status_code=400, detail="image_object_key required for security checks")
        stream, _ = get_object_stream(image_object_key)
        image_bytes = stream.read()
        watermark_key = str(PurePosixPath("watermark") / PurePosixPath(image_object_key))
        watermark_bytes, watermark_content_type = add_text_watermark(image_bytes, watermark_text="边拍")
        put_object_bytes(object_key=watermark_key, data=watermark_bytes, content_type=watermark_content_type)
        data["image_object_key"] = image_object_key
        data["image_url"] = object_key_to_url(image_object_key) or data.get("image_url")
        data["watermark_object_key"] = watermark_key
        data["watermark_url"] = object_key_to_url(watermark_key)
    for k, v in data.items():
        setattr(item, k, v)
    db.add(item)
    db.commit()
    db.refresh(item)
    return PortfolioItemOut.model_validate(item)


@router.delete("/portfolio/{item_id}")
def delete_portfolio(
    item_id: int,
    me: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    _require_photographer_user(me)
    p = _get_my_photographer(db, me)
    db.execute(delete(PortfolioItem).where(PortfolioItem.id == item_id, PortfolioItem.photographer_id == p.id))
    db.commit()
    return {"ok": True}


@router.get("/packages", response_model=PackageListOut)
def list_packages(me: User = Depends(get_current_user), db: Session = Depends(get_db)) -> PackageListOut:
    _require_photographer_user(me)
    p = _get_my_photographer(db, me)
    items = db.scalars(
        select(Package).where(Package.photographer_id == p.id).order_by(Package.id.desc())
    ).all()
    return PackageListOut(items=[PackageOut.model_validate(i) for i in items])


@router.post("/packages", response_model=PackageOut)
def create_package(
    payload: PackageCreateIn,
    me: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PackageOut:
    _require_photographer_user(me)
    p = _get_my_photographer(db, me)
    item = Package(photographer_id=p.id, **payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return PackageOut.model_validate(item)


@router.put("/packages/{package_id}", response_model=PackageOut)
def update_package(
    package_id: int,
    payload: PackageUpdateIn,
    me: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PackageOut:
    _require_photographer_user(me)
    p = _get_my_photographer(db, me)
    item = db.scalar(select(Package).where(Package.id == package_id, Package.photographer_id == p.id))
    if not item:
        raise HTTPException(status_code=404, detail="package not found")
    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(item, k, v)
    db.add(item)
    db.commit()
    db.refresh(item)
    return PackageOut.model_validate(item)


@router.delete("/packages/{package_id}")
def delete_package(
    package_id: int,
    me: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    _require_photographer_user(me)
    p = _get_my_photographer(db, me)
    db.execute(delete(Package).where(Package.id == package_id, Package.photographer_id == p.id))
    db.commit()
    return {"ok": True}


@router.get("/schedule", response_model=ScheduleListOut)
def list_schedule(
    start_date: date | None = None,
    end_date: date | None = None,
    me: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ScheduleListOut:
    _require_photographer_user(me)
    p = _get_my_photographer(db, me)
    q = select(ScheduleBlock).where(ScheduleBlock.photographer_id == p.id)
    if start_date:
        q = q.where(ScheduleBlock.date >= start_date)
    if end_date:
        q = q.where(ScheduleBlock.date <= end_date)
    items = db.scalars(q.order_by(ScheduleBlock.date.asc())).all()
    return ScheduleListOut(items=[ScheduleItemOut(date=i.date, status=i.status) for i in items])


@router.put("/schedule", response_model=ScheduleItemOut)
def upsert_schedule(
    payload: ScheduleUpsertIn,
    me: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ScheduleItemOut:
    _require_photographer_user(me)
    p = _get_my_photographer(db, me)
    item = db.scalar(
        select(ScheduleBlock).where(ScheduleBlock.photographer_id == p.id, ScheduleBlock.date == payload.date)
    )
    if item:
        item.status = payload.status
    else:
        item = ScheduleBlock(photographer_id=p.id, date=payload.date, status=payload.status)
    db.add(item)
    db.commit()
    return ScheduleItemOut(date=item.date, status=item.status)


@router.delete("/schedule/{item_date}")
def delete_schedule(
    item_date: date,
    me: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    _require_photographer_user(me)
    p = _get_my_photographer(db, me)
    db.execute(
        delete(ScheduleBlock).where(ScheduleBlock.photographer_id == p.id, ScheduleBlock.date == item_date)
    )
    db.commit()
    return {"ok": True}
