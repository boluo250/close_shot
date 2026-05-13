from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_current_user
from app.api.routes import membership as membership_routes
from app.api.routes import upload as upload_routes
from app.core.security import create_access_token, hash_password
from app.db.session import get_db
from app.main import create_app
from app.services.storage import create_upload_token


class FakeDB:
    def __init__(self, *, scalar_results: list[object] | None = None, user_by_id: dict[int, object] | None = None):
        self._scalar_results = list(scalar_results or [])
        self._user_by_id = dict(user_by_id or {})
        self.executed: list[str] = []
        self.commit_calls = 0
        self.added: list[object] = []

    def scalar(self, _statement):
        if not self._scalar_results:
            return None
        return self._scalar_results.pop(0)

    def get(self, _model, identity):
        return self._user_by_id.get(int(identity))

    def execute(self, statement):
        self.executed.append(str(statement))
        return 1

    def add(self, item) -> None:
        self.added.append(item)

    def commit(self) -> None:
        self.commit_calls += 1

    def rollback(self) -> None:
        return None

    def close(self) -> None:
        return None


@pytest.fixture()
def app():
    application = create_app()
    yield application
    application.dependency_overrides.clear()


@pytest.fixture()
def client(app):
    with TestClient(app) as test_client:
        yield test_client


def test_health_and_readiness(client, monkeypatch):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["ok"] is True

    fake_db = FakeDB()
    monkeypatch.setattr("app.main.SessionLocal", lambda: fake_db)
    ready_response = client.get("/health/ready")

    assert ready_response.status_code == 200
    assert ready_response.json() == {"ok": True, "checks": {"database": "ok"}}
    assert fake_db.executed == ["SELECT 1"]


def test_login_smoke(client, app):
    user = SimpleNamespace(
        id=1,
        username="smoke-user",
        password_hash=hash_password("smoke-password"),
        role="customer",
    )

    def override_get_db():
        yield FakeDB(scalar_results=[user])

    app.dependency_overrides[get_db] = override_get_db

    response = client.post(
        "/auth/login",
        json={"username": "smoke-user", "password": "smoke-password"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["token_type"] == "bearer"
    assert payload["access_token"]


def test_unauthorized_smoke(client):
    response = client.post(
        "/upload/presign",
        json={"filename": "avatar.png", "prefix": "uploads", "content_type": "image/png"},
    )

    assert response.status_code == 401


def test_upload_presign_smoke(client, app, monkeypatch):
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=1)
    monkeypatch.setattr(upload_routes, "ensure_bucket", lambda: None)
    monkeypatch.setattr(
        upload_routes,
        "presign_put",
        lambda **kwargs: SimpleNamespace(
            method="PUT",
            url="https://example.com/upload",
            headers={"Content-Type": kwargs["content_type"]},
            public_url="https://cdn.example.com/uploads/avatar.png",
            object_key="uploads/avatar.png",
        ),
    )

    response = client.post(
        "/upload/presign",
        json={"filename": "avatar.png", "prefix": "uploads", "content_type": "image/png"},
        headers={"Authorization": "Bearer ignored-by-override"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["method"] == "PUT"
    assert payload["object_key"] == "uploads/avatar.png"


def test_upload_presign_normalizes_generic_image_type(client, app, monkeypatch):
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=1)
    monkeypatch.setattr(upload_routes, "ensure_bucket", lambda: None)

    captured: dict[str, str | None] = {}

    def fake_presign_put(**kwargs):
        captured["content_type"] = kwargs["content_type"]
        return SimpleNamespace(
            method="PUT",
            url="https://example.com/upload",
            headers={"Content-Type": kwargs["content_type"]},
            public_url="https://cdn.example.com/avatar.jpg",
            object_key="avatar/avatar.jpg",
        )

    monkeypatch.setattr(upload_routes, "presign_put", fake_presign_put)

    response = client.post(
        "/upload/presign",
        json={"filename": "avatar.jpg", "prefix": "avatar", "content_type": "image"},
        headers={"Authorization": "Bearer ignored-by-override"},
    )

    assert response.status_code == 200
    assert captured["content_type"] == "image/jpeg"
    assert response.json()["headers"]["Content-Type"] == "image/jpeg"


def test_upload_put_proxy_smoke(client, monkeypatch):
    captured: dict[str, object] = {}

    def fake_put_object_bytes(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(upload_routes, "put_object_bytes", fake_put_object_bytes)
    token = create_upload_token(object_key="avatar/test-avatar.jpg")

    response = client.put(
        "/upload/put/avatar/test-avatar.jpg",
        params={"token": token},
        content=b"fake-image-bytes",
        headers={"content-type": "image"},
    )

    assert response.status_code == 200
    assert response.json()["object_key"] == "avatar/test-avatar.jpg"
    assert captured["object_key"] == "avatar/test-avatar.jpg"
    assert captured["content_type"] == "image/jpeg"
    assert captured["data"] == b"fake-image-bytes"


def test_membership_callback_smoke(client, app, monkeypatch):
    expected_expiry = datetime(2030, 1, 1, tzinfo=timezone.utc)
    order = SimpleNamespace(
        status="pending",
        user_id=1,
        months=3,
        out_trade_no="MBR20260310000000abcd1234",
        transaction_id=None,
        paid_at=None,
        notify_raw_json="",
    )
    user = SimpleNamespace(id=1, is_member=False, member_expires_at=None)
    fake_db = FakeDB(scalar_results=[order, user])

    def override_get_db():
        yield fake_db

    def fake_extend_member_expiry(member_user, months: int):
        assert months == 3
        member_user.is_member = True
        member_user.member_expires_at = expected_expiry
        return expected_expiry

    app.dependency_overrides[get_db] = override_get_db
    monkeypatch.setattr(membership_routes, "extend_member_expiry", fake_extend_member_expiry)

    response = client.post(
        "/membership/callback/wechat",
        headers={"x-callback-secret": "test-membership-secret"},
        json={
            "out_trade_no": "MBR20260310000000abcd1234",
            "transaction_id": "wx-transaction-id",
            "result": "SUCCESS",
            "raw": {"trade_state": "SUCCESS"},
        },
    )

    assert response.status_code == 200
    assert response.json()["order_status"] == "paid"
    assert response.json()["member_expires_at"].startswith("2030-01-01T00:00:00")
    assert order.status == "paid"
    assert fake_db.commit_calls == 1


def test_user_operation_log_smoke(client, app, monkeypatch):
    current_user = SimpleNamespace(id=99, username=None, display_name="测试用户", role="customer")
    audit_db = FakeDB(user_by_id={99: current_user})

    app.dependency_overrides[get_current_user] = lambda: current_user
    monkeypatch.setattr("app.main.SessionLocal", lambda: audit_db)
    monkeypatch.setattr(upload_routes, "ensure_bucket", lambda: None)
    monkeypatch.setattr(
        upload_routes,
        "presign_put",
        lambda **kwargs: SimpleNamespace(
            method="PUT",
            url="https://example.com/upload",
            headers={"Content-Type": kwargs["content_type"]},
            public_url="https://cdn.example.com/uploads/avatar.png",
            object_key="uploads/avatar.png",
        ),
    )

    response = client.post(
        "/upload/presign",
        json={"filename": "avatar.png", "prefix": "avatar", "content_type": "image/png", "channel": "mini_program"},
        headers={"Authorization": f"Bearer {create_access_token(subject='99')}"},
    )

    assert response.status_code == 200
    user_logs = [item for item in audit_db.added if item.__class__.__name__ == "UserOperationLog"]
    assert len(user_logs) == 1
    assert user_logs[0].user_id == 99
    assert user_logs[0].action == "request_upload_presign"
    assert user_logs[0].channel == "mini_program"
    assert user_logs[0].resource_id == "avatar/avatar.png"
    assert user_logs[0].status_code == 200
