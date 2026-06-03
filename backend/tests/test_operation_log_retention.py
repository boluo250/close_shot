from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.db.models import AdminOperationLog, UserOperationLog
from app.services.operation_log_retention import cleanup_operation_logs


def _build_session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, class_=Session)
    return session_factory()


def test_cleanup_operation_logs_deletes_expired_rows_in_batches():
    db = _build_session()
    now = datetime(2026, 6, 2, 12, 0, tzinfo=timezone.utc)
    old_admin_at = now - timedelta(days=200)
    old_user_at = now - timedelta(days=120)
    fresh_at = now - timedelta(days=5)

    db.add_all(
        [
            AdminOperationLog(
                id=1,
                admin_user_id=None,
                username="admin-1",
                method="POST",
                path="/admin-x8r7m2q4p9/users",
                query_string="",
                status_code=200,
                client_ip="127.0.0.1",
                user_agent="pytest",
                request_body="{}",
                created_at=old_admin_at,
                updated_at=old_admin_at,
            ),
            AdminOperationLog(
                id=2,
                admin_user_id=None,
                username="admin-2",
                method="PATCH",
                path="/admin-x8r7m2q4p9/users/2",
                query_string="",
                status_code=200,
                client_ip="127.0.0.1",
                user_agent="pytest",
                request_body="{}",
                created_at=fresh_at,
                updated_at=fresh_at,
            ),
            UserOperationLog(
                id=11,
                user_id=None,
                actor_name="user-1",
                actor_role="customer",
                channel="mini_program",
                action="submit_appointment",
                action_label="提交预约",
                resource_type="appointment_request",
                resource_id="1001",
                method="POST",
                path="/appointments",
                query_string="",
                status_code=200,
                client_ip="127.0.0.1",
                user_agent="pytest",
                request_body="{}",
                created_at=old_user_at,
                updated_at=old_user_at,
            ),
            UserOperationLog(
                id=12,
                user_id=None,
                actor_name="user-2",
                actor_role="photographer",
                channel="studio_web",
                action="update_profile",
                action_label="更新资料",
                resource_type="photographer_profile",
                resource_id="1002",
                method="PATCH",
                path="/studio/me",
                query_string="",
                status_code=200,
                client_ip="127.0.0.1",
                user_agent="pytest",
                request_body="{}",
                created_at=old_user_at - timedelta(minutes=1),
                updated_at=old_user_at - timedelta(minutes=1),
            ),
            UserOperationLog(
                id=13,
                user_id=None,
                actor_name="user-3",
                actor_role="photographer",
                channel="studio_web",
                action="update_profile",
                action_label="更新资料",
                resource_type="photographer_profile",
                resource_id="1003",
                method="PATCH",
                path="/studio/me",
                query_string="",
                status_code=200,
                client_ip="127.0.0.1",
                user_agent="pytest",
                request_body="{}",
                created_at=fresh_at,
                updated_at=fresh_at,
            ),
        ]
    )
    db.commit()

    result = cleanup_operation_logs(
        db,
        admin_retention_days=180,
        user_retention_days=90,
        batch_size=1,
        now=now,
    )

    assert result["admin"]["deleted_rows"] == 1
    assert result["admin"]["batches"] == 1
    assert result["user"]["deleted_rows"] == 2
    assert result["user"]["batches"] == 2

    remaining_admin_ids = db.scalars(select(AdminOperationLog.id).order_by(AdminOperationLog.id.asc())).all()
    remaining_user_ids = db.scalars(select(UserOperationLog.id).order_by(UserOperationLog.id.asc())).all()
    assert remaining_admin_ids == [2]
    assert remaining_user_ids == [13]


def test_cleanup_operation_logs_dry_run_only_reports_counts():
    db = _build_session()
    now = datetime(2026, 6, 2, 12, 0, tzinfo=timezone.utc)
    old_at = now - timedelta(days=181)

    db.add(
        AdminOperationLog(
            id=21,
            admin_user_id=None,
            username="admin-dry-run",
            method="DELETE",
            path="/admin-x8r7m2q4p9/users/21",
            query_string="",
            status_code=200,
            client_ip="127.0.0.1",
            user_agent="pytest",
            request_body="{}",
            created_at=old_at,
            updated_at=old_at,
        )
    )
    db.commit()

    result = cleanup_operation_logs(
        db,
        admin_retention_days=180,
        user_retention_days=90,
        batch_size=100,
        dry_run=True,
        now=now,
    )

    assert result["dry_run"] is True
    assert result["admin"]["affected_rows"] == 1
    assert result["admin"]["deleted_rows"] == 0
    assert db.scalar(select(AdminOperationLog.id).where(AdminOperationLog.id == 21)) == 21
