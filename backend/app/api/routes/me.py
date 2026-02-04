from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.models import Favorite, Photographer, User
from app.db.session import get_db
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

