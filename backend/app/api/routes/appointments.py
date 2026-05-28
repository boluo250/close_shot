from __future__ import annotations

from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_user
from app.db.models import (
    AppointmentRequest,
    AppointmentStatus,
    BlacklistStatus,
    Package,
    Photographer,
    PhotographerStatus,
    Review,
    ScheduleBlock,
    User,
    UserRole,
)
from app.db.session import get_db
from app.schemas.appointment import AppointmentCreateIn, AppointmentDecisionIn, AppointmentListOut, AppointmentOut
from app.schemas.review import ReviewCreateIn, ReviewOut

router = APIRouter()


def _next_bigint_id(db: Session, model) -> int:
    current = db.scalar(select(func.max(model.id))) or 0
    return int(current) + 1


def _load_appointment(db: Session, appointment_id: int) -> AppointmentRequest | None:
    return db.scalar(
        select(AppointmentRequest)
        .where(AppointmentRequest.id == appointment_id)
        .options(
            selectinload(AppointmentRequest.customer),
            selectinload(AppointmentRequest.photographer).selectinload(Photographer.user),
            selectinload(AppointmentRequest.package),
        )
    )


def _load_reviewed_appointment_ids(db: Session, appointment_ids: list[int]) -> set[int]:
    if not appointment_ids:
        return set()
    return set(
        int(item)
        for item in db.scalars(
            select(Review.appointment_request_id).where(Review.appointment_request_id.in_(appointment_ids))
        ).all()
        if item is not None
    )


def _appointment_to_out(
    item: AppointmentRequest,
    *,
    reviewed_appointment_ids: set[int] | None = None,
    viewer_user_id: int | None = None,
) -> AppointmentOut:
    reviewed_ids = reviewed_appointment_ids or set()
    customer = item.customer
    photographer_user = item.photographer.user if item.photographer else None
    has_review = int(item.id) in reviewed_ids
    can_review = (
        item.status == AppointmentStatus.completed.value
        and viewer_user_id is not None
        and int(item.customer_user_id) == int(viewer_user_id)
        and not has_review
    )
    return AppointmentOut(
        id=int(item.id),
        customer_user_id=int(item.customer_user_id),
        photographer_id=int(item.photographer_id),
        package_id=int(item.package_id) if item.package_id is not None else None,
        status=item.status,
        scheduled_at=item.scheduled_at,
        location_text=item.location_text,
        contact_name=item.contact_name,
        contact_phone=item.contact_phone,
        shooting_type=item.shooting_type,
        budget_cents=item.budget_cents,
        participant_count=int(item.participant_count or 1),
        note=item.note,
        response_note=item.response_note,
        accepted_at=item.accepted_at,
        rejected_at=item.rejected_at,
        cancelled_at=item.cancelled_at,
        completed_at=item.completed_at,
        customer_completed_at=item.customer_completed_at,
        photographer_completed_at=item.photographer_completed_at,
        customer_display_name=customer.display_name if customer else None,
        customer_avatar_url=customer.avatar_url if customer else None,
        photographer_display_name=photographer_user.display_name if photographer_user else None,
        photographer_avatar_url=photographer_user.avatar_url if photographer_user else None,
        package_name=item.package.name if item.package else None,
        has_review=has_review,
        can_review=can_review,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


def _get_my_approved_photographer(db: Session, me: User) -> Photographer:
    photographer = db.scalar(
        select(Photographer).where(
            Photographer.user_id == me.id,
            Photographer.status == PhotographerStatus.approved.value,
        )
    )
    if not photographer:
        raise HTTPException(status_code=403, detail="approved photographer profile required")
    return photographer


def _ensure_appointment_visible(item: AppointmentRequest, me: User, db: Session) -> None:
    if me.role == UserRole.admin.value:
        return
    if int(item.customer_user_id) == int(me.id):
        return
    photographer = _get_my_approved_photographer(db, me)
    if int(item.photographer_id) == int(photographer.id):
        return
    raise HTTPException(status_code=403, detail="no permission to view this appointment")


def _ensure_customer_owner(item: AppointmentRequest, me: User) -> None:
    if me.role == UserRole.admin.value:
        return
    if int(item.customer_user_id) != int(me.id):
        raise HTTPException(status_code=403, detail="appointment customer required")


def _ensure_photographer_owner(item: AppointmentRequest, me: User, db: Session) -> Photographer:
    if me.role == UserRole.admin.value:
        photographer = db.scalar(select(Photographer).where(Photographer.id == item.photographer_id))
        if not photographer:
            raise HTTPException(status_code=404, detail="photographer not found")
        return photographer
    photographer = _get_my_approved_photographer(db, me)
    if int(item.photographer_id) != int(photographer.id):
        raise HTTPException(status_code=403, detail="appointment photographer required")
    return photographer


def _ensure_photographer_available(db: Session, *, photographer: Photographer, scheduled_at: datetime, appointment_id: int | None = None) -> None:
    scheduled_day = scheduled_at.astimezone(timezone.utc).date() if scheduled_at.tzinfo else scheduled_at.date()
    blocked = db.scalar(
        select(ScheduleBlock).where(
            ScheduleBlock.photographer_id == photographer.id,
            ScheduleBlock.date == scheduled_day,
            ScheduleBlock.status.in_(("busy", "blocked")),
        )
    )
    if blocked:
        raise HTTPException(status_code=409, detail="photographer unavailable on selected date")

    conflict_stmt = select(AppointmentRequest.id).where(
        AppointmentRequest.photographer_id == photographer.id,
        AppointmentRequest.status.in_((AppointmentStatus.accepted.value, AppointmentStatus.completed.value)),
        func.date(AppointmentRequest.scheduled_at) == scheduled_day,
    )
    if appointment_id is not None:
        conflict_stmt = conflict_stmt.where(AppointmentRequest.id != appointment_id)
    conflict = db.scalar(conflict_stmt)
    if conflict is not None:
        raise HTTPException(status_code=409, detail="photographer already has an appointment on selected date")


@router.post("", response_model=AppointmentOut)
def create_appointment(
    payload: AppointmentCreateIn,
    me: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AppointmentOut:
    if me.blacklist_status == BlacklistStatus.blocked.value:
        raise HTTPException(status_code=403, detail="account blocked from creating appointments")

    photographer = db.scalar(
        select(Photographer)
        .where(
            Photographer.id == payload.photographer_id,
            Photographer.status == PhotographerStatus.approved.value,
            Photographer.is_accepting_orders.is_(True),
        )
        .options(selectinload(Photographer.user))
    )
    if not photographer:
        raise HTTPException(status_code=404, detail="photographer not available")
    if int(photographer.user_id) == int(me.id):
        raise HTTPException(status_code=400, detail="cannot create appointment with yourself")

    package = None
    if payload.package_id is not None:
        package = db.scalar(
            select(Package).where(
                Package.id == payload.package_id,
                Package.photographer_id == photographer.id,
                Package.is_active.is_(True),
            )
        )
        if not package:
            raise HTTPException(status_code=404, detail="package not found")

    appointment = AppointmentRequest(
        id=_next_bigint_id(db, AppointmentRequest),
        customer_user_id=me.id,
        photographer_id=photographer.id,
        package_id=package.id if package else None,
        status=AppointmentStatus.pending.value,
        scheduled_at=payload.scheduled_at,
        location_text=payload.location_text.strip(),
        contact_name=(payload.contact_name or "").strip() or None,
        contact_phone=(payload.contact_phone or "").strip() or None,
        shooting_type=(payload.shooting_type or "").strip() or None,
        budget_cents=payload.budget_cents,
        participant_count=payload.participant_count,
        note=(payload.note or "").strip() or None,
    )
    db.add(appointment)
    db.commit()
    loaded = _load_appointment(db, int(appointment.id))
    if not loaded:
        raise HTTPException(status_code=500, detail="appointment create failed")
    return _appointment_to_out(loaded, viewer_user_id=me.id)


@router.get("/mine", response_model=AppointmentListOut)
def list_my_appointments(
    me: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AppointmentListOut:
    items = db.scalars(
        select(AppointmentRequest)
        .where(AppointmentRequest.customer_user_id == me.id)
        .order_by(AppointmentRequest.created_at.desc(), AppointmentRequest.id.desc())
        .options(
            selectinload(AppointmentRequest.customer),
            selectinload(AppointmentRequest.photographer).selectinload(Photographer.user),
            selectinload(AppointmentRequest.package),
        )
    ).all()
    reviewed_ids = _load_reviewed_appointment_ids(db, [int(item.id) for item in items])
    return AppointmentListOut(
        items=[_appointment_to_out(item, reviewed_appointment_ids=reviewed_ids, viewer_user_id=me.id) for item in items]
    )


@router.get("/assigned", response_model=AppointmentListOut)
def list_assigned_appointments(
    me: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AppointmentListOut:
    photographer = _get_my_approved_photographer(db, me)
    items = db.scalars(
        select(AppointmentRequest)
        .where(AppointmentRequest.photographer_id == photographer.id)
        .order_by(AppointmentRequest.created_at.desc(), AppointmentRequest.id.desc())
        .options(
            selectinload(AppointmentRequest.customer),
            selectinload(AppointmentRequest.photographer).selectinload(Photographer.user),
            selectinload(AppointmentRequest.package),
        )
    ).all()
    reviewed_ids = _load_reviewed_appointment_ids(db, [int(item.id) for item in items])
    return AppointmentListOut(items=[_appointment_to_out(item, reviewed_appointment_ids=reviewed_ids) for item in items])


@router.get("/{appointment_id}", response_model=AppointmentOut)
def get_appointment_detail(
    appointment_id: int,
    me: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AppointmentOut:
    item = _load_appointment(db, appointment_id)
    if not item:
        raise HTTPException(status_code=404, detail="appointment not found")
    _ensure_appointment_visible(item, me, db)
    reviewed_ids = _load_reviewed_appointment_ids(db, [appointment_id])
    return _appointment_to_out(item, reviewed_appointment_ids=reviewed_ids, viewer_user_id=me.id)


@router.post("/{appointment_id}/accept", response_model=AppointmentOut)
def accept_appointment(
    appointment_id: int,
    payload: AppointmentDecisionIn,
    me: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AppointmentOut:
    item = _load_appointment(db, appointment_id)
    if not item:
        raise HTTPException(status_code=404, detail="appointment not found")
    photographer = _ensure_photographer_owner(item, me, db)
    if item.status != AppointmentStatus.pending.value:
        raise HTTPException(status_code=409, detail="only pending appointments can be accepted")
    _ensure_photographer_available(db, photographer=photographer, scheduled_at=item.scheduled_at, appointment_id=item.id)
    now = datetime.now(timezone.utc)
    item.status = AppointmentStatus.accepted.value
    item.accepted_at = now
    item.response_note = (payload.response_note or "").strip() or None
    db.add(item)
    db.commit()
    loaded = _load_appointment(db, appointment_id)
    if not loaded:
        raise HTTPException(status_code=500, detail="appointment accept failed")
    return _appointment_to_out(loaded, viewer_user_id=me.id)


@router.post("/{appointment_id}/reject", response_model=AppointmentOut)
def reject_appointment(
    appointment_id: int,
    payload: AppointmentDecisionIn,
    me: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AppointmentOut:
    item = _load_appointment(db, appointment_id)
    if not item:
        raise HTTPException(status_code=404, detail="appointment not found")
    _ensure_photographer_owner(item, me, db)
    if item.status != AppointmentStatus.pending.value:
        raise HTTPException(status_code=409, detail="only pending appointments can be rejected")
    item.status = AppointmentStatus.rejected.value
    item.rejected_at = datetime.now(timezone.utc)
    item.response_note = (payload.response_note or "").strip() or None
    db.add(item)
    db.commit()
    loaded = _load_appointment(db, appointment_id)
    if not loaded:
        raise HTTPException(status_code=500, detail="appointment reject failed")
    return _appointment_to_out(loaded, viewer_user_id=me.id)


@router.post("/{appointment_id}/cancel", response_model=AppointmentOut)
def cancel_appointment(
    appointment_id: int,
    payload: AppointmentDecisionIn,
    me: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AppointmentOut:
    item = _load_appointment(db, appointment_id)
    if not item:
        raise HTTPException(status_code=404, detail="appointment not found")
    _ensure_customer_owner(item, me)
    if item.status not in (AppointmentStatus.pending.value, AppointmentStatus.accepted.value):
        raise HTTPException(status_code=409, detail="only pending or accepted appointments can be cancelled")
    item.status = AppointmentStatus.cancelled.value
    item.cancelled_at = datetime.now(timezone.utc)
    if not item.response_note:
        item.response_note = (payload.response_note or "").strip() or None
    db.add(item)
    db.commit()
    loaded = _load_appointment(db, appointment_id)
    if not loaded:
        raise HTTPException(status_code=500, detail="appointment cancel failed")
    return _appointment_to_out(loaded, viewer_user_id=me.id)


@router.post("/{appointment_id}/complete", response_model=AppointmentOut)
def complete_appointment(
    appointment_id: int,
    me: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AppointmentOut:
    item = _load_appointment(db, appointment_id)
    if not item:
        raise HTTPException(status_code=404, detail="appointment not found")

    is_customer = me.role == UserRole.admin.value or int(item.customer_user_id) == int(me.id)
    is_photographer = True
    if not is_customer:
        try:
            _ensure_photographer_owner(item, me, db)
        except HTTPException:
            is_photographer = False
        else:
            is_photographer = True
    if not is_customer and not is_photographer:
        raise HTTPException(status_code=403, detail="no permission to complete this appointment")
    if item.status not in (AppointmentStatus.accepted.value, AppointmentStatus.completed.value):
        raise HTTPException(status_code=409, detail="only accepted appointments can be completed")

    now = datetime.now(timezone.utc)
    if is_customer:
        item.customer_completed_at = item.customer_completed_at or now
    else:
        item.photographer_completed_at = item.photographer_completed_at or now
    item.completed_at = item.completed_at or now
    item.status = AppointmentStatus.completed.value
    db.add(item)
    db.commit()
    loaded = _load_appointment(db, appointment_id)
    if not loaded:
        raise HTTPException(status_code=500, detail="appointment complete failed")
    reviewed_ids = _load_reviewed_appointment_ids(db, [appointment_id])
    return _appointment_to_out(loaded, reviewed_appointment_ids=reviewed_ids, viewer_user_id=me.id)


@router.post("/{appointment_id}/review", response_model=ReviewOut, status_code=status.HTTP_201_CREATED)
def create_appointment_review(
    appointment_id: int,
    payload: ReviewCreateIn,
    me: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ReviewOut:
    item = _load_appointment(db, appointment_id)
    if not item:
        raise HTTPException(status_code=404, detail="appointment not found")
    _ensure_customer_owner(item, me)
    if item.status != AppointmentStatus.completed.value:
        raise HTTPException(status_code=409, detail="only completed appointments can be reviewed")

    existing = db.scalar(select(Review).where(Review.appointment_request_id == appointment_id))
    if existing:
        raise HTTPException(status_code=409, detail="appointment already reviewed")

    review = Review(
        id=_next_bigint_id(db, Review),
        user_id=me.id,
        photographer_id=item.photographer_id,
        appointment_request_id=item.id,
        rating=payload.rating,
        content=(payload.content or "").strip() or None,
    )
    db.add(review)
    db.commit()
    db.refresh(review)
    return ReviewOut(
        id=int(review.id),
        user_id=int(review.user_id) if review.user_id is not None else None,
        photographer_id=int(review.photographer_id),
        rating=int(review.rating),
        content=review.content,
        user_display_name=me.display_name,
        user_avatar_url=me.avatar_url,
        created_at=review.created_at,
        updated_at=review.updated_at,
    )
