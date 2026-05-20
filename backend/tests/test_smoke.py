from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from botocore.exceptions import ClientError
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.api.deps import get_current_user
from app.api.routes import admin as admin_routes
from app.api.routes import membership as membership_routes
from app.api.routes import studio as studio_routes
from app.api.routes import upload as upload_routes
from app.core.security import create_access_token, hash_password
from app.db.session import get_db
from app.main import create_app
from app.schemas.studio import PhotographerUpdateIn
from app.services import storage as storage_service
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

    def refresh(self, _item) -> None:
        return None

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


def test_ensure_bucket_does_not_create_on_non_404_head_bucket_error(monkeypatch):
    calls: list[tuple[str, str]] = []

    class FakeS3:
        def head_bucket(self, *, Bucket):
            calls.append(("head_bucket", Bucket))
            raise ClientError(
                {"Error": {"Code": "403", "Message": "Forbidden"}, "ResponseMetadata": {"HTTPStatusCode": 403}},
                "HeadBucket",
            )

        def create_bucket(self, *, Bucket):
            calls.append(("create_bucket", Bucket))

    monkeypatch.setattr(storage_service, "_s3_client", lambda: FakeS3())
    monkeypatch.setattr(storage_service.settings, "storage_backend", "s3")
    monkeypatch.setattr(storage_service.settings, "s3_bucket", "bianpai-1256560950")

    storage_service.ensure_bucket()

    assert calls == [("head_bucket", "bianpai-1256560950")]


def test_admin_approve_enables_accepting_orders_when_location_ready(monkeypatch):
    photographer_user = SimpleNamespace(role="customer")
    photographer = SimpleNamespace(
        id=7,
        status="pending",
        reject_reason="old reason",
        certification_level=0,
        quality_score=admin_routes.DEFAULT_QUALITY_SCORE,
        is_accepting_orders=False,
        service_center_lat=31.2304,
        service_center_lng=121.4737,
        user=photographer_user,
    )
    db = FakeDB(scalar_results=[photographer])
    admin_user = SimpleNamespace(role="admin")
    payload = admin_routes.CertificationReviewIn(action="approve")
    calls: dict[str, object] = {}

    monkeypatch.setattr(admin_routes, "_build_portfolio_preview_map", lambda **_kwargs: {})
    monkeypatch.setattr(
        admin_routes,
        "_photographer_to_detail",
        lambda p, portfolio_preview_map=None: {"id": p.id, "status": p.status, "portfolio_preview_map": portfolio_preview_map},
    )
    monkeypatch.setattr(
        admin_routes,
        "recalculate_photographer_sort_scores",
        lambda _db, photographer_ids: calls.update({"photographer_ids": photographer_ids}),
    )

    result = admin_routes.review_certification(7, payload, admin_user, db)

    assert result["status"] == "approved"
    assert photographer.status == "approved"
    assert photographer.reject_reason is None
    assert photographer.certification_level == 1
    assert photographer.quality_score == admin_routes.INITIAL_APPROVED_QUALITY_SCORE
    assert photographer.is_accepting_orders is True
    assert photographer_user.role == "photographer"
    assert calls["photographer_ids"] == [7]
    assert db.commit_calls == 1


def test_studio_update_me_persists_display_name():
    user = SimpleNamespace(display_name="旧名字", avatar_url="https://example.com/old.jpg")
    photographer = SimpleNamespace(
        id=9,
        user_id=9,
        bio="旧简介",
        tags="",
        cover_url=None,
        rate_card_json="[]",
        is_accepting_orders=False,
        service_radius_m=5000,
        status="approved",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        user=user,
        last_active_at=None,
    )
    db = FakeDB(scalar_results=[photographer])
    me = SimpleNamespace(role="photographer", id=9)
    payload = PhotographerUpdateIn(display_name="  新摄影师名  ", bio="新简介")

    result = studio_routes.update_me(payload, me, db)

    assert user.display_name == "新摄影师名"
    assert photographer.bio == "新简介"
    assert result.photographer.display_name == "新摄影师名"
    assert db.commit_calls == 1


def test_admin_reject_disables_accepting_orders(monkeypatch):
    photographer = SimpleNamespace(
        id=8,
        status="approved",
        reject_reason=None,
        certification_level=1,
        quality_score=7.0,
        is_accepting_orders=True,
        service_center_lat=31.2304,
        service_center_lng=121.4737,
        user=SimpleNamespace(role="photographer"),
    )
    db = FakeDB(scalar_results=[photographer])
    admin_user = SimpleNamespace(role="admin")
    payload = admin_routes.CertificationReviewIn(action="reject", reject_reason="资料不符合要求")

    monkeypatch.setattr(admin_routes, "_build_portfolio_preview_map", lambda **_kwargs: {})
    monkeypatch.setattr(
        admin_routes,
        "_photographer_to_detail",
        lambda p, portfolio_preview_map=None: {"id": p.id, "status": p.status, "is_accepting_orders": p.is_accepting_orders},
    )

    result = admin_routes.review_certification(8, payload, admin_user, db)

    assert result["status"] == "rejected"
    assert result["is_accepting_orders"] is False
    assert photographer.status == "rejected"
    assert photographer.is_accepting_orders is False
    assert photographer.reject_reason == "资料不符合要求"
    assert db.commit_calls == 1


def test_admin_can_offline_photographer(monkeypatch):
    photographer = SimpleNamespace(
        id=9,
        status="approved",
        is_accepting_orders=True,
        service_center_lat=31.2304,
        service_center_lng=121.4737,
    )
    db = FakeDB(scalar_results=[photographer])
    admin_user = SimpleNamespace(role="admin")
    payload = admin_routes.PhotographerAvailabilityIn(is_accepting_orders=False)

    monkeypatch.setattr(admin_routes, "_build_portfolio_preview_map", lambda **_kwargs: {})
    monkeypatch.setattr(
        admin_routes,
        "_photographer_to_detail",
        lambda p, portfolio_preview_map=None: {"id": p.id, "is_accepting_orders": p.is_accepting_orders},
    )

    result = admin_routes.update_photographer_availability(9, payload, admin_user, db)

    assert result["is_accepting_orders"] is False
    assert photographer.is_accepting_orders is False
    assert db.commit_calls == 1


def test_admin_cannot_restore_online_without_location(monkeypatch):
    photographer = SimpleNamespace(
        id=10,
        status="approved",
        is_accepting_orders=False,
        service_center_lat=None,
        service_center_lng=None,
    )
    db = FakeDB(scalar_results=[photographer])
    admin_user = SimpleNamespace(role="admin")
    payload = admin_routes.PhotographerAvailabilityIn(is_accepting_orders=True)

    monkeypatch.setattr(admin_routes, "_build_portfolio_preview_map", lambda **_kwargs: {})

    with pytest.raises(HTTPException) as exc_info:
        admin_routes.update_photographer_availability(10, payload, admin_user, db)

    assert exc_info.value.status_code == 400
    assert "补全服务中心点坐标" in exc_info.value.detail
    assert photographer.is_accepting_orders is False
    assert db.commit_calls == 0


def test_admin_can_delete_offline_photographer(monkeypatch):
    photographer = SimpleNamespace(
        id=11,
        user_id=1011,
        is_accepting_orders=False,
    )
    db = FakeDB(scalar_results=[photographer])
    admin_user = SimpleNamespace(role="admin")
    deleted_object_keys: list[str] = []

    monkeypatch.setattr(
        admin_routes,
        "_collect_photographer_media_object_keys",
        lambda _db, _photographer: ["portfolio/demo.jpg", "watermark/portfolio/demo.jpg"],
    )
    monkeypatch.setattr(
        admin_routes,
        "_delete_storage_objects",
        lambda object_keys: deleted_object_keys.extend(object_keys),
    )

    result = admin_routes.delete_photographer(11, admin_user, db)

    assert result == {"ok": True}
    assert deleted_object_keys == ["portfolio/demo.jpg", "watermark/portfolio/demo.jpg"]
    assert db.commit_calls == 1
    assert any("DELETE FROM analytics_events" in stmt for stmt in db.executed)
    assert any("DELETE FROM photographers" in stmt for stmt in db.executed)
    assert any("DELETE FROM users" in stmt for stmt in db.executed)


def test_admin_cannot_delete_online_photographer():
    photographer = SimpleNamespace(
        id=12,
        user_id=1012,
        is_accepting_orders=True,
    )
    db = FakeDB(scalar_results=[photographer])
    admin_user = SimpleNamespace(role="admin")

    with pytest.raises(HTTPException) as exc_info:
        admin_routes.delete_photographer(12, admin_user, db)

    assert exc_info.value.status_code == 400
    assert "请先下线" in exc_info.value.detail
    assert db.commit_calls == 0


def test_delete_object_local_removes_file(tmp_path, monkeypatch):
    monkeypatch.setattr(storage_service.settings, "storage_backend", "local")
    monkeypatch.setattr(storage_service, "_local_base_dir", lambda: tmp_path)

    storage_service.local_put_object_bytes(object_key="portfolio/demo/test.jpg", data=b"hello")
    target = tmp_path / "portfolio" / "demo" / "test.jpg"
    assert target.exists()

    storage_service.delete_object("portfolio/demo/test.jpg")

    assert not target.exists()
    assert not (tmp_path / "portfolio" / "demo").exists()


def test_presign_put_s3_returns_presigned_url(monkeypatch):
    captured: dict[str, object] = {}

    class FakeS3:
        def generate_presigned_url(self, operation_name, *, Params, ExpiresIn):
            captured["operation_name"] = operation_name
            captured["params"] = Params
            captured["expires_in"] = ExpiresIn
            return "https://bianpai-1256560950.cos.ap-shanghai.myqcloud.com/avatar/test.jpg?signature=demo"

    monkeypatch.setattr(storage_service, "_s3_client", lambda: FakeS3())
    monkeypatch.setattr(storage_service.settings, "storage_backend", "s3")
    monkeypatch.setattr(storage_service.settings, "s3_bucket", "bianpai-1256560950")
    monkeypatch.setattr(
        storage_service.settings,
        "s3_public_base_url",
        "https://bianpai-1256560950.cos.ap-shanghai.myqcloud.com",
    )

    result = storage_service.presign_put(object_key="avatar/test.jpg", content_type="image/jpeg", expires_seconds=600)

    assert result.method == "PUT"
    assert result.url.startswith("https://bianpai-1256560950.cos.ap-shanghai.myqcloud.com/avatar/test.jpg")
    assert result.public_url == "https://bianpai-1256560950.cos.ap-shanghai.myqcloud.com/avatar/test.jpg"
    assert result.headers == {"Content-Type": "image/jpeg"}
    assert captured["operation_name"] == "put_object"
    assert captured["params"] == {
        "Bucket": "bianpai-1256560950",
        "Key": "avatar/test.jpg",
        "ContentType": "image/jpeg",
    }
    assert captured["expires_in"] == 600


def test_s3_client_uses_virtual_addressing_for_cos(monkeypatch):
    captured: dict[str, object] = {}

    def fake_boto3_client(service_name, **kwargs):
        captured["service_name"] = service_name
        captured["kwargs"] = kwargs
        return SimpleNamespace()

    monkeypatch.setattr(storage_service.boto3, "client", fake_boto3_client)
    monkeypatch.setattr(storage_service.settings, "s3_endpoint_url", "https://cos.ap-shanghai.myqcloud.com")
    monkeypatch.setattr(storage_service.settings, "s3_access_key_id", "test-ak")
    monkeypatch.setattr(storage_service.settings, "s3_secret_access_key", "test-sk")
    monkeypatch.setattr(storage_service.settings, "s3_bucket", "bianpai-1256560950")
    monkeypatch.setattr(storage_service.settings, "s3_region", "ap-shanghai")

    storage_service._s3_client()

    cfg = captured["kwargs"]["config"]
    assert captured["service_name"] == "s3"
    assert captured["kwargs"]["endpoint_url"] == "https://cos.ap-shanghai.myqcloud.com"
    assert captured["kwargs"]["region_name"] == "ap-shanghai"
    assert cfg.signature_version == "s3v4"
    assert cfg.s3.get("addressing_style") == "virtual"


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
