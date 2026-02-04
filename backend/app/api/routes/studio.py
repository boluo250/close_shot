from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.models import Package, Photographer, PortfolioItem, User, UserRole
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
    StudioMeOut,
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


@router.get("/me", response_model=StudioMeOut)
def get_me(me: User = Depends(get_current_user), db: Session = Depends(get_db)) -> StudioMeOut:
    _require_photographer_user(me)
    p = _get_my_photographer(db, me)
    return StudioMeOut(photographer=PhotographerOut.model_validate(p))


@router.put("/me", response_model=StudioMeOut)
def update_me(
    payload: PhotographerUpdateIn,
    me: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> StudioMeOut:
    _require_photographer_user(me)
    p = _get_my_photographer(db, me)
    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(p, k, v)
    db.add(p)
    db.commit()
    db.refresh(p)
    return StudioMeOut(photographer=PhotographerOut.model_validate(p))


@router.get("/portfolio", response_model=PortfolioListOut)
def list_portfolio(me: User = Depends(get_current_user), db: Session = Depends(get_db)) -> PortfolioListOut:
    _require_photographer_user(me)
    p = _get_my_photographer(db, me)
    items = db.scalars(
        select(PortfolioItem)
        .where(PortfolioItem.photographer_id == p.id)
        .order_by(PortfolioItem.sort_order.asc(), PortfolioItem.id.asc())
    ).all()
    return PortfolioListOut(items=[PortfolioItemOut.model_validate(i) for i in items])


@router.post("/portfolio", response_model=PortfolioItemOut)
def create_portfolio(
    payload: PortfolioCreateIn,
    me: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PortfolioItemOut:
    _require_photographer_user(me)
    p = _get_my_photographer(db, me)
    item = PortfolioItem(photographer_id=p.id, **payload.model_dump())
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
    for k, v in payload.model_dump(exclude_unset=True).items():
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
    for k, v in payload.model_dump(exclude_unset=True).items():
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

