from __future__ import annotations

from datetime import datetime, timezone

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
    ReviewStatus,
    ScheduleBlock,
    User,
    UserRole,
)
from app.db.session import get_db
from app.schemas.appointment import (
    AppointmentCreateIn,
    AppointmentDecisionIn,
    AppointmentListOut,
    AppointmentOut,
    AppointmentSubscribeConfigOut,
    AppointmentSummaryOut,
)
from app.schemas.review import ReviewCreateIn, ReviewOut
from app.services import wechat_subscribe

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


def _viewer_flags(item: AppointmentRequest, me: User, db: Session) -> tuple[bool, bool]:
    is_customer = me.role == UserRole.admin.value or int(item.customer_user_id) == int(me.id)
    if is_customer:
        return True, False
    photographer = _get_my_approved_photographer(db, me)
    return False, int(item.photographer_id) == int(photographer.id)


def _ensure_appointment_visible(item: AppointmentRequest, me: User, db: Session) -> tuple[bool, bool]:
    is_customer, is_photographer = _viewer_flags(item, me, db)
    if is_customer or is_photographer or me.role == UserRole.admin.value:
        return is_customer, is_photographer
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


def _ensure_photographer_available(
    db: Session,
    *,
    photographer: Photographer,
    scheduled_at: datetime,
    appointment_id: int | None = None,
) -> None:
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
        AppointmentRequest.status.in_(
            (
                AppointmentStatus.accepted_pending_customer.value,
                AppointmentStatus.confirmed.value,
                AppointmentStatus.completed.value,
            )
        ),
        func.date(AppointmentRequest.scheduled_at) == scheduled_day,
    )
    if appointment_id is not None:
        conflict_stmt = conflict_stmt.where(AppointmentRequest.id != appointment_id)
    conflict = db.scalar(conflict_stmt)
    if conflict is not None:
        raise HTTPException(status_code=409, detail="photographer already has an appointment on selected date")


def _appointment_to_out(
    item: AppointmentRequest,
    *,
    reviewed_appointment_ids: set[int] | None = None,
    viewer_user: User | None = None,
    is_customer_owner: bool = False,
    is_photographer_owner: bool = False,
) -> AppointmentOut:
    reviewed_ids = reviewed_appointment_ids or set()
    customer = item.customer
    photographer = item.photographer
    photographer_user = photographer.user if photographer else None
    contact_unlocked = item.contact_unlocked_at is not None
    has_review = int(item.id) in reviewed_ids
    can_review = (
        item.status == AppointmentStatus.completed.value
        and is_customer_owner
        and not has_review
    )
    can_customer_confirm = is_customer_owner and item.status == AppointmentStatus.accepted_pending_customer.value
    can_photographer_complete = (
        is_photographer_owner
        and item.status == AppointmentStatus.confirmed.value
        and item.photographer_completed_at is None
    )
    can_customer_complete = (
        is_customer_owner
        and item.status == AppointmentStatus.confirmed.value
        and item.photographer_completed_at is not None
        and item.customer_completed_at is None
    )

    can_view_customer_contact = is_photographer_owner and contact_unlocked
    can_view_photographer_contact = is_customer_owner and contact_unlocked
    if viewer_user and viewer_user.role == UserRole.admin.value:
        can_view_customer_contact = True
        can_view_photographer_contact = True

    return AppointmentOut(
        id=int(item.id),
        customer_user_id=int(item.customer_user_id),
        photographer_id=int(item.photographer_id),
        package_id=int(item.package_id) if item.package_id is not None else None,
        status=item.status,
        scheduled_at=item.scheduled_at,
        location_text=item.location_text,
        contact_name=item.contact_name if is_customer_owner or can_view_customer_contact else None,
        contact_phone=item.contact_phone if is_customer_owner or can_view_customer_contact else None,
        shooting_type=item.shooting_type,
        budget_cents=item.budget_cents,
        participant_count=int(item.participant_count or 1),
        note=item.note,
        response_note=item.response_note,
        accepted_at=item.accepted_at,
        customer_confirmed_at=item.customer_confirmed_at,
        contact_unlocked_at=item.contact_unlocked_at,
        rejected_at=item.rejected_at,
        cancelled_at=item.cancelled_at,
        completed_at=item.completed_at,
        customer_completed_at=item.customer_completed_at,
        photographer_completed_at=item.photographer_completed_at,
        customer_display_name=customer.display_name if customer else None,
        customer_avatar_url=customer.avatar_url if customer else None,
        photographer_display_name=photographer_user.display_name if photographer_user else None,
        photographer_avatar_url=photographer_user.avatar_url if photographer_user else None,
        photographer_phone=(photographer.phone if photographer and can_view_photographer_contact else None),
        photographer_wechat_id=(photographer.wechat_id if photographer and can_view_photographer_contact else None),
        customer_contact_name=(item.contact_name if can_view_customer_contact else None),
        customer_contact_phone=(item.contact_phone if can_view_customer_contact else None),
        can_view_customer_contact=can_view_customer_contact,
        can_view_photographer_contact=can_view_photographer_contact,
        can_customer_confirm=can_customer_confirm,
        can_customer_complete=can_customer_complete,
        can_photographer_complete=can_photographer_complete,
        package_name=item.package.name if item.package else None,
        has_review=has_review,
        can_review=can_review,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


def _finalize_completion_if_ready(item: AppointmentRequest, now: datetime) -> None:
    if item.photographer_completed_at and item.customer_completed_at:
        item.status = AppointmentStatus.completed.value
        item.completed_at = item.completed_at or now


def accept_appointment_for_user(
    *,
    appointment_id: int,
    payload: AppointmentDecisionIn,
    me: User,
    db: Session,
) -> AppointmentOut:
    item = _load_appointment(db, appointment_id)
    if not item:
        raise HTTPException(status_code=404, detail="appointment not found")
    photographer = _ensure_photographer_owner(item, me, db)
    if item.status != AppointmentStatus.pending.value:
        raise HTTPException(status_code=409, detail="only pending appointments can be accepted")
    _ensure_photographer_available(db, photographer=photographer, scheduled_at=item.scheduled_at, appointment_id=item.id)
    now = datetime.now(timezone.utc)
    item.status = AppointmentStatus.accepted_pending_customer.value
    item.accepted_at = now
    item.response_note = (payload.response_note or "").strip() or None
    db.add(item)
    db.commit()
    loaded = _load_appointment(db, appointment_id)
    if not loaded:
        raise HTTPException(status_code=500, detail="appointment accept failed")
    wechat_subscribe.notify_customer_appointment_accepted(loaded)
    return _appointment_to_out(loaded, viewer_user=me, is_photographer_owner=True)


def reject_appointment_for_user(
    *,
    appointment_id: int,
    payload: AppointmentDecisionIn,
    me: User,
    db: Session,
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
    return _appointment_to_out(loaded, viewer_user=me, is_photographer_owner=True)


def confirm_appointment_for_user(
    *,
    appointment_id: int,
    me: User,
    db: Session,
) -> AppointmentOut:
    item = _load_appointment(db, appointment_id)
    if not item:
        raise HTTPException(status_code=404, detail="appointment not found")
    _ensure_customer_owner(item, me)
    if item.status != AppointmentStatus.accepted_pending_customer.value:
        raise HTTPException(status_code=409, detail="only accepted appointments can be confirmed by customer")
    now = datetime.now(timezone.utc)
    item.status = AppointmentStatus.confirmed.value
    item.customer_confirmed_at = now
    item.contact_unlocked_at = now
    db.add(item)
    db.commit()
    loaded = _load_appointment(db, appointment_id)
    if not loaded:
        raise HTTPException(status_code=500, detail="appointment confirm failed")
    return _appointment_to_out(loaded, viewer_user=me, is_customer_owner=True)


def cancel_appointment_for_user(
    *,
    appointment_id: int,
    payload: AppointmentDecisionIn,
    me: User,
    db: Session,
) -> AppointmentOut:
    item = _load_appointment(db, appointment_id)
    if not item:
        raise HTTPException(status_code=404, detail="appointment not found")
    _ensure_customer_owner(item, me)
    if item.status not in (
        AppointmentStatus.pending.value,
        AppointmentStatus.accepted_pending_customer.value,
        AppointmentStatus.confirmed.value,
    ):
        raise HTTPException(status_code=409, detail="only active appointments can be cancelled")
    item.status = AppointmentStatus.cancelled.value
    item.cancelled_at = datetime.now(timezone.utc)
    if not item.response_note:
        item.response_note = (payload.response_note or "").strip() or None
    db.add(item)
    db.commit()
    loaded = _load_appointment(db, appointment_id)
    if not loaded:
        raise HTTPException(status_code=500, detail="appointment cancel failed")
    return _appointment_to_out(loaded, viewer_user=me, is_customer_owner=True)


def complete_appointment_for_user(
    *,
    appointment_id: int,
    me: User,
    db: Session,
) -> AppointmentOut:
    item = _load_appointment(db, appointment_id)
    if not item:
        raise HTTPException(status_code=404, detail="appointment not found")
    if item.status not in (AppointmentStatus.confirmed.value, AppointmentStatus.completed.value):
        raise HTTPException(status_code=409, detail="only confirmed appointments can be completed")

    now = datetime.now(timezone.utc)
    should_notify_customer_completion = False
    if me.role == UserRole.admin.value:
        item.photographer_completed_at = item.photographer_completed_at or now
        item.customer_completed_at = item.customer_completed_at or now
        _finalize_completion_if_ready(item, now)
    elif int(item.customer_user_id) == int(me.id):
        if item.photographer_completed_at is None:
            raise HTTPException(status_code=409, detail="photographer has not marked appointment complete yet")
        if item.customer_completed_at is None:
            item.customer_completed_at = now
        _finalize_completion_if_ready(item, now)
    else:
        _ensure_photographer_owner(item, me, db)
        if item.photographer_completed_at is None:
            item.photographer_completed_at = now
            should_notify_customer_completion = True
        _finalize_completion_if_ready(item, now)

    db.add(item)
    db.commit()
    loaded = _load_appointment(db, appointment_id)
    if not loaded:
        raise HTTPException(status_code=500, detail="appointment complete failed")
    if should_notify_customer_completion:
        wechat_subscribe.notify_customer_appointment_completed(loaded)
    is_customer = int(item.customer_user_id) == int(me.id)
    is_photographer = not is_customer and me.role != UserRole.admin.value
    reviewed_ids = _load_reviewed_appointment_ids(db, [appointment_id])
    return _appointment_to_out(
        loaded,
        reviewed_appointment_ids=reviewed_ids,
        viewer_user=me,
        is_customer_owner=is_customer,
        is_photographer_owner=is_photographer,
    )


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
    wechat_subscribe.notify_photographer_new_appointment(loaded)
    return _appointment_to_out(loaded, viewer_user=me, is_customer_owner=True)


@router.get("/subscribe-config", response_model=AppointmentSubscribeConfigOut)
def get_appointment_subscribe_config(
    _: User = Depends(get_current_user),
) -> AppointmentSubscribeConfigOut:
    return AppointmentSubscribeConfigOut(**wechat_subscribe.get_appointment_subscribe_config())


@router.get("/summary", response_model=AppointmentSummaryOut)
def get_appointment_summary(
    me: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AppointmentSummaryOut:
    mine_items = db.scalars(
        select(AppointmentRequest).where(AppointmentRequest.customer_user_id == me.id)
    ).all()
    reviewed_ids = _load_reviewed_appointment_ids(db, [int(item.id) for item in mine_items])

    assigned_items: list[AppointmentRequest] = []
    if me.role in (UserRole.photographer.value, UserRole.admin.value):
        try:
            photographer = _get_my_approved_photographer(db, me)
        except HTTPException:
            photographer = None
        if photographer:
            assigned_items = db.scalars(
                select(AppointmentRequest).where(AppointmentRequest.photographer_id == photographer.id)
            ).all()

    return AppointmentSummaryOut(
        mine_waiting_customer_confirm=sum(
            1 for item in mine_items if item.status == AppointmentStatus.accepted_pending_customer.value
        ),
        mine_waiting_completion_confirm=sum(
            1
            for item in mine_items
            if item.status == AppointmentStatus.confirmed.value
            and item.photographer_completed_at is not None
            and item.customer_completed_at is None
        ),
        mine_completed_without_review=sum(
            1 for item in mine_items if item.status == AppointmentStatus.completed.value and int(item.id) not in reviewed_ids
        ),
        assigned_pending_decision=sum(1 for item in assigned_items if item.status == AppointmentStatus.pending.value),
        assigned_waiting_customer_confirm=sum(
            1 for item in assigned_items if item.status == AppointmentStatus.accepted_pending_customer.value
        ),
        assigned_waiting_completion_mark=sum(
            1
            for item in assigned_items
            if item.status == AppointmentStatus.confirmed.value and item.photographer_completed_at is None
        ),
    )


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
        items=[
            _appointment_to_out(item, reviewed_appointment_ids=reviewed_ids, viewer_user=me, is_customer_owner=True)
            for item in items
        ]
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
    return AppointmentListOut(
        items=[
            _appointment_to_out(item, reviewed_appointment_ids=reviewed_ids, viewer_user=me, is_photographer_owner=True)
            for item in items
        ]
    )


@router.get("/{appointment_id}", response_model=AppointmentOut)
def get_appointment_detail(
    appointment_id: int,
    me: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AppointmentOut:
    item = _load_appointment(db, appointment_id)
    if not item:
        raise HTTPException(status_code=404, detail="appointment not found")
    is_customer, is_photographer = _ensure_appointment_visible(item, me, db)
    reviewed_ids = _load_reviewed_appointment_ids(db, [appointment_id])
    return _appointment_to_out(
        item,
        reviewed_appointment_ids=reviewed_ids,
        viewer_user=me,
        is_customer_owner=is_customer,
        is_photographer_owner=is_photographer,
    )


@router.post("/{appointment_id}/accept", response_model=AppointmentOut)
def accept_appointment(
    appointment_id: int,
    payload: AppointmentDecisionIn,
    me: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AppointmentOut:
    return accept_appointment_for_user(appointment_id=appointment_id, payload=payload, me=me, db=db)


@router.post("/{appointment_id}/confirm", response_model=AppointmentOut)
def confirm_appointment(
    appointment_id: int,
    me: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AppointmentOut:
    return confirm_appointment_for_user(appointment_id=appointment_id, me=me, db=db)


@router.post("/{appointment_id}/reject", response_model=AppointmentOut)
def reject_appointment(
    appointment_id: int,
    payload: AppointmentDecisionIn,
    me: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AppointmentOut:
    return reject_appointment_for_user(appointment_id=appointment_id, payload=payload, me=me, db=db)


@router.post("/{appointment_id}/cancel", response_model=AppointmentOut)
def cancel_appointment(
    appointment_id: int,
    payload: AppointmentDecisionIn,
    me: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AppointmentOut:
    return cancel_appointment_for_user(appointment_id=appointment_id, payload=payload, me=me, db=db)


@router.post("/{appointment_id}/complete", response_model=AppointmentOut)
def complete_appointment(
    appointment_id: int,
    me: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AppointmentOut:
    return complete_appointment_for_user(appointment_id=appointment_id, me=me, db=db)


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
        status=ReviewStatus.pending.value,
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
        status=review.status,
        user_display_name=me.display_name,
        user_avatar_url=me.avatar_url,
        created_at=review.created_at,
        updated_at=review.updated_at,
    )
