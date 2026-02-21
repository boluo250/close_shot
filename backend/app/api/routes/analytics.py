from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Header
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import AnalyticsEvent, Photographer, User
from app.db.session import get_db
from app.schemas.analytics import AnalyticsTrackBatchIn, AnalyticsTrackBatchOut

router = APIRouter()


def _resolve_optional_user_id(db: Session, authorization: str | None) -> int | None:
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization.removeprefix("Bearer ").strip()
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_alg])
        user_id = int(payload.get("sub"))
    except (JWTError, ValueError, TypeError):
        return None
    user = db.scalar(select(User.id).where(User.id == user_id))
    return int(user) if user else None


@router.post("/events/batch", response_model=AnalyticsTrackBatchOut)
def track_events(
    payload: AnalyticsTrackBatchIn,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> AnalyticsTrackBatchOut:
    if not payload.events:
        return AnalyticsTrackBatchOut(accepted=0, skipped=0)

    user_id = _resolve_optional_user_id(db, authorization)
    photographer_ids = {e.photographer_id for e in payload.events if e.photographer_id}
    valid_photographer_ids: set[int] = set()
    if photographer_ids:
        valid_photographer_ids = set(
            db.scalars(select(Photographer.id).where(Photographer.id.in_(photographer_ids))).all()
        )

    accepted = 0
    skipped = 0
    for event in payload.events:
        if event.photographer_id and event.photographer_id not in valid_photographer_ids:
            skipped += 1
            continue
        db.add(
            AnalyticsEvent(
                event_type=event.event_type,
                channel=event.channel,
                user_id=user_id,
                photographer_id=event.photographer_id,
                client_lat=event.lat,
                client_lng=event.lng,
                extra_json=json.dumps(event.extra or {}, ensure_ascii=False),
            )
        )
        accepted += 1

    db.commit()
    return AnalyticsTrackBatchOut(accepted=accepted, skipped=skipped)
