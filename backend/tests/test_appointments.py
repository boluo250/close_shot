from __future__ import annotations

from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_db
from app.core.config import settings
from app.core.security import create_access_token
from app.db.base import Base
from app.db.models import (
    AppointmentRequest,
    AppointmentStatus,
    Package,
    Photographer,
    Review,
    ReviewStatus,
    ScheduleBlock,
    User,
    UserRole,
)
from app.main import create_app


def _auth_headers(user_id: int) -> dict[str, str]:
    token = create_access_token(subject=str(user_id))
    return {"Authorization": f"Bearer {token}"}


def _build_test_client() -> tuple[TestClient, sessionmaker]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, class_=Session)
    Base.metadata.create_all(engine)

    app = create_app()

    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    return client, SessionLocal


def _seed_basic_data(session_factory: sessionmaker) -> None:
    with session_factory() as db:
        customer = User(id=1, role=UserRole.customer.value, display_name="客户甲")
        photographer_user = User(id=2, role=UserRole.photographer.value, display_name="摄影师乙")
        admin_user = User(id=99, role=UserRole.admin.value, display_name="管理员")
        photographer = Photographer(
            id=10,
            user_id=2,
            tags="",
            status="approved",
            is_accepting_orders=True,
            service_radius_m=5000,
            phone="13900139000",
            wechat_id="photo-ethan",
        )
        package = Package(id=20, photographer_id=10, name="基础套餐", price_cents=19900, is_active=True)
        db.add_all([customer, photographer_user, admin_user, photographer, package])
        db.commit()


def test_appointment_flow_requires_customer_confirm_before_contact_unlock_and_review():
    client, session_factory = _build_test_client()
    _seed_basic_data(session_factory)

    create_resp = client.post(
        "/appointments",
        headers=_auth_headers(1),
        json={
            "photographer_id": 10,
            "package_id": 20,
            "scheduled_at": "2026-06-01T10:00:00+08:00",
            "location_text": "上海静安寺",
            "contact_name": "张三",
            "contact_phone": "13800138000",
            "shooting_type": "人像",
            "budget_cents": 29900,
            "participant_count": 2,
            "note": "希望自然纪实风格",
        },
    )
    assert create_resp.status_code == 200
    appointment_id = create_resp.json()["id"]
    assert create_resp.json()["status"] == "pending"

    early_review = client.post(
        f"/appointments/{appointment_id}/review",
        headers=_auth_headers(1),
        json={"rating": 5, "content": "先试着评价"},
    )
    assert early_review.status_code == 409

    accept_resp = client.post(
        f"/appointments/{appointment_id}/accept",
        headers=_auth_headers(2),
        json={"response_note": "时间没问题，可以拍"},
    )
    assert accept_resp.status_code == 200
    assert accept_resp.json()["status"] == "accepted_pending_customer"

    detail_before_confirm = client.get(f"/appointments/{appointment_id}", headers=_auth_headers(1))
    assert detail_before_confirm.status_code == 200
    assert detail_before_confirm.json()["can_customer_confirm"] is True
    assert detail_before_confirm.json()["can_view_photographer_contact"] is False
    assert detail_before_confirm.json()["photographer_phone"] is None

    photographer_before_confirm = client.get(f"/appointments/{appointment_id}", headers=_auth_headers(2))
    assert photographer_before_confirm.status_code == 200
    assert photographer_before_confirm.json()["can_view_customer_contact"] is False
    assert photographer_before_confirm.json()["customer_contact_phone"] is None

    confirm_resp = client.post(
        f"/appointments/{appointment_id}/confirm",
        headers=_auth_headers(1),
    )
    assert confirm_resp.status_code == 200
    assert confirm_resp.json()["status"] == "confirmed"
    assert confirm_resp.json()["can_view_photographer_contact"] is True
    assert confirm_resp.json()["photographer_phone"] == "13900139000"

    complete_resp = client.post(
        f"/appointments/{appointment_id}/complete",
        headers=_auth_headers(2),
    )
    assert complete_resp.status_code == 200
    assert complete_resp.json()["status"] == "confirmed"

    customer_complete_resp = client.post(
        f"/appointments/{appointment_id}/complete",
        headers=_auth_headers(1),
    )
    assert customer_complete_resp.status_code == 200
    assert customer_complete_resp.json()["status"] == "completed"

    review_resp = client.post(
        f"/appointments/{appointment_id}/review",
        headers=_auth_headers(1),
        json={"rating": 5, "content": "沟通顺畅，成片也不错"},
    )
    assert review_resp.status_code == 201
    assert review_resp.json()["photographer_id"] == 10
    assert review_resp.json()["status"] == "pending"

    detail_before_review_approved = client.get("/photographers/10", headers=_auth_headers(1))
    assert detail_before_review_approved.status_code == 200
    assert detail_before_review_approved.json()["reviews"] == []

    approve_review_resp = client.post(
        f"{settings.admin_api_prefix}/reviews/{review_resp.json()['id']}/moderate",
        headers=_auth_headers(99),
        json={"action": "approve"},
    )
    assert approve_review_resp.status_code == 200
    assert approve_review_resp.json()["status"] == "approved"

    detail_after_review_approved = client.get("/photographers/10", headers=_auth_headers(1))
    assert detail_after_review_approved.status_code == 200
    assert len(detail_after_review_approved.json()["reviews"]) == 1
    assert detail_after_review_approved.json()["reviews"][0]["content"] == "沟通顺畅，成片也不错"

    with session_factory() as db:
        appointment = db.scalar(select(AppointmentRequest).where(AppointmentRequest.id == appointment_id))
        review = db.scalar(select(Review).where(Review.appointment_request_id == appointment_id))
        assert appointment is not None
        assert appointment.status == "completed"
        assert review is not None
        assert review.rating == 5
        assert review.status == ReviewStatus.approved.value
        assert review.appointment_request_id == appointment_id


def test_accept_appointment_respects_schedule_block():
    client, session_factory = _build_test_client()
    _seed_basic_data(session_factory)

    create_resp = client.post(
        "/appointments",
        headers=_auth_headers(1),
        json={
            "photographer_id": 10,
            "scheduled_at": "2026-06-03T09:00:00+08:00",
            "location_text": "上海徐汇",
            "participant_count": 1,
        },
    )
    assert create_resp.status_code == 200
    appointment_id = create_resp.json()["id"]

    with session_factory() as db:
        db.add(ScheduleBlock(id=1, photographer_id=10, date=date(2026, 6, 3), status="blocked"))
        db.commit()

    accept_resp = client.post(
        f"/appointments/{appointment_id}/accept",
        headers=_auth_headers(2),
        json={"response_note": "这天不在上海"},
    )
    assert accept_resp.status_code == 409
    assert accept_resp.json()["detail"] == "photographer unavailable on selected date"


def test_customer_cannot_complete_before_photographer_marks_done():
    client, session_factory = _build_test_client()
    _seed_basic_data(session_factory)

    create_resp = client.post(
        "/appointments",
        headers=_auth_headers(1),
        json={
            "photographer_id": 10,
            "scheduled_at": "2026-06-06T09:00:00+08:00",
            "location_text": "上海普陀",
            "participant_count": 1,
        },
    )
    appointment_id = create_resp.json()["id"]

    client.post(f"/appointments/{appointment_id}/accept", headers=_auth_headers(2), json={})
    client.post(f"/appointments/{appointment_id}/confirm", headers=_auth_headers(1))

    early_complete = client.post(
        f"/appointments/{appointment_id}/complete",
        headers=_auth_headers(1),
    )
    assert early_complete.status_code == 409
    assert early_complete.json()["detail"] == "photographer has not marked appointment complete yet"


def test_admin_appointment_action_routes_accept_pending_request():
    client, session_factory = _build_test_client()
    _seed_basic_data(session_factory)

    create_resp = client.post(
        "/appointments",
        headers=_auth_headers(1),
        json={
            "photographer_id": 10,
            "scheduled_at": "2026-06-08T09:00:00+08:00",
            "location_text": "上海浦东",
            "participant_count": 1,
        },
    )
    assert create_resp.status_code == 200
    appointment_id = create_resp.json()["id"]

    accept_resp = client.post(
        f"{settings.admin_api_prefix}/appointments/{appointment_id}/accept",
        headers=_auth_headers(99),
        json={},
    )
    assert accept_resp.status_code == 200
    assert accept_resp.json()["status"] == "accepted_pending_customer"

    with session_factory() as db:
        appointment = db.scalar(select(AppointmentRequest).where(AppointmentRequest.id == appointment_id))
        assert appointment is not None
        assert appointment.status == "accepted_pending_customer"


def test_appointment_status_column_length_covers_all_enum_values():
    status_column = AppointmentRequest.__table__.c.status
    max_status_len = max(len(item.value) for item in AppointmentStatus)
    assert status_column.type.length is not None
    assert status_column.type.length >= max_status_len


def test_subscribe_config_endpoint_returns_template_keys():
    client, session_factory = _build_test_client()
    _seed_basic_data(session_factory)

    resp = client.get("/appointments/subscribe-config", headers=_auth_headers(1))
    assert resp.status_code == 200
    assert "photographer_new_appointment_template_id" in resp.json()
    assert "customer_appointment_accepted_template_id" in resp.json()
    assert "customer_appointment_completed_template_id" in resp.json()


def test_appointment_flow_triggers_subscription_notifications(monkeypatch):
    client, session_factory = _build_test_client()
    _seed_basic_data(session_factory)

    calls: list[tuple[str, int]] = []

    monkeypatch.setattr(
        "app.api.routes.appointments.wechat_subscribe.notify_photographer_new_appointment",
        lambda item: calls.append(("create", int(item.id))) or True,
    )
    monkeypatch.setattr(
        "app.api.routes.appointments.wechat_subscribe.notify_customer_appointment_accepted",
        lambda item: calls.append(("accept", int(item.id))) or True,
    )
    monkeypatch.setattr(
        "app.api.routes.appointments.wechat_subscribe.notify_customer_appointment_completed",
        lambda item: calls.append(("complete", int(item.id))) or True,
    )

    create_resp = client.post(
        "/appointments",
        headers=_auth_headers(1),
        json={
            "photographer_id": 10,
            "scheduled_at": "2026-06-08T11:00:00+08:00",
            "location_text": "上海虹口",
            "participant_count": 1,
        },
    )
    appointment_id = create_resp.json()["id"]

    client.post(f"/appointments/{appointment_id}/accept", headers=_auth_headers(2), json={})
    client.post(f"/appointments/{appointment_id}/confirm", headers=_auth_headers(1))
    client.post(f"/appointments/{appointment_id}/complete", headers=_auth_headers(2))
    client.post(f"/appointments/{appointment_id}/complete", headers=_auth_headers(1))

    assert calls == [("create", appointment_id), ("accept", appointment_id), ("complete", appointment_id)]
