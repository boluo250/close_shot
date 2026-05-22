from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import PurePosixPath

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.models import Package, Photographer, PhotographerStatus, PortfolioItem, ScheduleBlock, User, UserRole
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
from app.services.studio_review import (
    get_effective_submission_snapshot,
    load_pending_submission_snapshot,
    next_snapshot_item_id,
    overlay_base_payload_with_snapshot,
    parse_rate_card_json,
    pending_review_status,
    pick_snapshot_item_fields,
    save_pending_submission_snapshot,
    snapshot_packages,
    snapshot_portfolio_items,
    snapshot_profile,
    touch_snapshot_item,
)

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


def _is_approved_photographer(p: Photographer) -> bool:
    return p.status == PhotographerStatus.approved.value


def _build_studio_me_out(p: Photographer, *, db: Session) -> StudioMeOut:
    snapshot = load_pending_submission_snapshot(p) if _is_approved_photographer(p) else None
    payload = PhotographerOut.model_validate(p).model_dump()
    payload["display_name"] = p.user.display_name if p.user else None
    payload["avatar_url"] = p.user.avatar_url if p.user else None
    overlay_base_payload_with_snapshot(payload, snapshot)
    return StudioMeOut(
        photographer=PhotographerOut(**payload),
        pending_review_status=pending_review_status(p),
        pending_reject_reason=getattr(p, "pending_reject_reason", None),
        pending_review_submitted_at=(
            p.pending_submission_submitted_at.isoformat()
            if getattr(p, "pending_submission_submitted_at", None)
            else None
        ),
    )


def _prepare_portfolio_payload(data: dict) -> dict:
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
    return data


def _ensure_submission_snapshot(db: Session, p: Photographer) -> dict:
    return get_effective_submission_snapshot(db=db, photographer=p)


@router.get("/me", response_model=StudioMeOut)
def get_me(me: User = Depends(get_current_user), db: Session = Depends(get_db)) -> StudioMeOut:
    _require_photographer_user(me)
    p = _get_my_photographer(db, me)
    return _build_studio_me_out(p, db=db)


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
        get_object_stream(data["avatar_object_key"])
        if p.user and data.get("avatar_url") is None:
            data["avatar_url"] = object_key_to_url(data["avatar_object_key"])
    if data.get("cover_object_key"):
        get_object_stream(data["cover_object_key"])
        if data.get("cover_url") is None:
            data["cover_url"] = object_key_to_url(data["cover_object_key"])
    display_name = (data.pop("display_name") or "").strip() or None if "display_name" in data else None
    avatar_url = data.pop("avatar_url", None) if "avatar_url" in data else None
    data.pop("avatar_object_key", None)
    data.pop("cover_object_key", None)

    if _is_approved_photographer(p):
        snapshot = _ensure_submission_snapshot(db, p)
        profile = snapshot_profile(snapshot)
        if "display_name" in payload.model_fields_set:
            profile["display_name"] = display_name
        if "avatar_url" in payload.model_fields_set:
            profile["avatar_url"] = avatar_url
        for key, value in data.items():
            profile[key] = value
        snapshot["profile"] = profile
        p.last_active_at = datetime.now(timezone.utc)
        save_pending_submission_snapshot(p, snapshot)
        db.add(p)
        db.commit()
        db.refresh(p)
        return _build_studio_me_out(p, db=db)

    if "display_name" in payload.model_fields_set and p.user:
        p.user.display_name = display_name
    if "avatar_url" in payload.model_fields_set and p.user:
        p.user.avatar_url = avatar_url
    if "rate_card" in data:
        p.rate_card_json = json.dumps(data.pop("rate_card") or [], ensure_ascii=False)
    for k, v in data.items():
        setattr(p, k, v)
    p.last_active_at = datetime.now(timezone.utc)
    db.add(p)
    db.commit()
    db.refresh(p)
    return _build_studio_me_out(p, db=db)


@router.get("/portfolio", response_model=PortfolioListOut)
def list_portfolio(me: User = Depends(get_current_user), db: Session = Depends(get_db)) -> PortfolioListOut:
    _require_photographer_user(me)
    p = _get_my_photographer(db, me)
    if _is_approved_photographer(p):
        snapshot = _ensure_submission_snapshot(db, p)
        return PortfolioListOut(items=[PortfolioItemOut(**item) for item in snapshot_portfolio_items(snapshot)])
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
    data = _prepare_portfolio_payload(data)
    if _is_approved_photographer(p):
        snapshot = _ensure_submission_snapshot(db, p)
        items = snapshot_portfolio_items(snapshot)
        item = pick_snapshot_item_fields(data, kind="portfolio")
        item["id"] = next_snapshot_item_id(items)
        touch_snapshot_item(item, is_new=True)
        items.insert(0, item)
        snapshot["portfolio_items"] = items
        save_pending_submission_snapshot(p, snapshot)
        p.last_active_at = datetime.now(timezone.utc)
        db.add(p)
        db.commit()
        return PortfolioItemOut(**item)
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
    if _is_approved_photographer(p):
        snapshot = _ensure_submission_snapshot(db, p)
        items = snapshot_portfolio_items(snapshot)
        item = next((entry for entry in items if int(entry.get("id")) == item_id), None)
        if not item:
            raise HTTPException(status_code=404, detail="portfolio item not found")
        data = payload.model_dump(exclude_unset=True)
        if data.get("image_object_key") or data.get("image_url"):
            data = _prepare_portfolio_payload(data)
        for k, v in data.items():
            item[k] = v
        touch_snapshot_item(item)
        snapshot["portfolio_items"] = items
        save_pending_submission_snapshot(p, snapshot)
        p.last_active_at = datetime.now(timezone.utc)
        db.add(p)
        db.commit()
        return PortfolioItemOut(**item)
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
    if _is_approved_photographer(p):
        snapshot = _ensure_submission_snapshot(db, p)
        items = [item for item in snapshot_portfolio_items(snapshot) if int(item.get("id")) != item_id]
        snapshot["portfolio_items"] = items
        save_pending_submission_snapshot(p, snapshot)
        p.last_active_at = datetime.now(timezone.utc)
        db.add(p)
        db.commit()
        return {"ok": True}
    db.execute(delete(PortfolioItem).where(PortfolioItem.id == item_id, PortfolioItem.photographer_id == p.id))
    db.commit()
    return {"ok": True}


@router.get("/packages", response_model=PackageListOut)
def list_packages(me: User = Depends(get_current_user), db: Session = Depends(get_db)) -> PackageListOut:
    _require_photographer_user(me)
    p = _get_my_photographer(db, me)
    if _is_approved_photographer(p):
        snapshot = _ensure_submission_snapshot(db, p)
        return PackageListOut(items=[PackageOut(**item) for item in snapshot_packages(snapshot)])
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
    if _is_approved_photographer(p):
        snapshot = _ensure_submission_snapshot(db, p)
        items = snapshot_packages(snapshot)
        item = pick_snapshot_item_fields(payload.model_dump(), kind="package")
        item["id"] = next_snapshot_item_id(items)
        touch_snapshot_item(item, is_new=True)
        items.insert(0, item)
        snapshot["packages"] = items
        save_pending_submission_snapshot(p, snapshot)
        p.last_active_at = datetime.now(timezone.utc)
        db.add(p)
        db.commit()
        return PackageOut(**item)
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
    if _is_approved_photographer(p):
        snapshot = _ensure_submission_snapshot(db, p)
        items = snapshot_packages(snapshot)
        item = next((entry for entry in items if int(entry.get("id")) == package_id), None)
        if not item:
            raise HTTPException(status_code=404, detail="package not found")
        for k, v in payload.model_dump(exclude_unset=True).items():
            item[k] = v
        touch_snapshot_item(item)
        snapshot["packages"] = items
        save_pending_submission_snapshot(p, snapshot)
        p.last_active_at = datetime.now(timezone.utc)
        db.add(p)
        db.commit()
        return PackageOut(**item)
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
    if _is_approved_photographer(p):
        snapshot = _ensure_submission_snapshot(db, p)
        snapshot["packages"] = [item for item in snapshot_packages(snapshot) if int(item.get("id")) != package_id]
        save_pending_submission_snapshot(p, snapshot)
        p.last_active_at = datetime.now(timezone.utc)
        db.add(p)
        db.commit()
        return {"ok": True}
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
