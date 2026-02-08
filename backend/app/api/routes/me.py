from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.models import Favorite, Photographer, PhotographerStatus, User, UserRole
from app.db.session import get_db
from app.schemas.me import MeIdentityOut
from app.schemas.photographer import PhotographerOut

router = APIRouter()


@router.get("/favorites", response_model=list[PhotographerOut])
def my_favorites(
    me: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[PhotographerOut]:
    stmt = (
        select(Photographer)
        .join(Favorite, Favorite.photographer_id == Photographer.id)
        .where(Favorite.user_id == me.id)
        .order_by(Favorite.created_at.desc())
    )
    ps = db.scalars(stmt).all()
    return [PhotographerOut.model_validate(p) for p in ps]


@router.get("/identity", response_model=MeIdentityOut)
def my_identity(me: User = Depends(get_current_user)) -> MeIdentityOut:
    status = "not_applied"
    reason = None
    if me.role == UserRole.admin.value:
        status = PhotographerStatus.approved.value
    elif me.photographer:
        status = me.photographer.status
        reason = me.photographer.reject_reason
    return MeIdentityOut(role=me.role, photographer_status=status, photographer_reject_reason=reason)


@router.post("/photographer/apply", response_model=MeIdentityOut)
def apply_photographer(
    me: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MeIdentityOut:
    if me.role == UserRole.admin.value:
        return MeIdentityOut(
            role=me.role,
            photographer_status=PhotographerStatus.approved.value,
            photographer_reject_reason=None,
        )
    p = db.scalar(select(Photographer).where(Photographer.user_id == me.id))
    if not p:
        p = Photographer(
            user_id=me.id,
            tags="",
            is_accepting_orders=False,
            service_radius_m=5000,
            status=PhotographerStatus.pending.value,
            reject_reason=None,
        )
        db.add(p)
    else:
        p.status = PhotographerStatus.pending.value
        p.reject_reason = None
    db.commit()
    db.refresh(p)
    return MeIdentityOut(
        role=me.role,
        photographer_status=p.status,
        photographer_reject_reason=p.reject_reason,
    )

