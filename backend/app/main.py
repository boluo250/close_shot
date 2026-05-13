from __future__ import annotations

import json
import logging
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from jose import JWTError, jwt
from sqlalchemy import text
from starlette.requests import Request
from starlette.responses import Response

from app.api.router import api_router
from app.core.config import settings
from app.db.models import AdminOperationLog, User, UserOperationLog
from app.db.session import SessionLocal


_SUSPICIOUS_404_PREFIXES = (
    "/admin",
    "/login",
    "/wp-admin",
    "/wp-login.php",
    "/webfig",
    "/console",
    "/phpmyadmin",
    "/jenkins",
    "/manager",
    "/jasperserver",
    "/sici.cgi",
    "/actuator",
    "/api/session/properties",
    "/inventry",
    "/.env",
    "/.git",
)
_LOGIN_PATHS = {"/auth/login", "/auth/wechat", "/auth/wechat/studio"}
_USER_FAVORITE_RE = re.compile(r"^/photographers/(?P<photographer_id>\d+)/favorite$")
_STUDIO_PORTFOLIO_RE = re.compile(r"^/studio/portfolio/(?P<item_id>\d+)$")
_STUDIO_PACKAGE_RE = re.compile(r"^/studio/packages/(?P<package_id>\d+)$")
_STUDIO_SCHEDULE_RE = re.compile(r"^/studio/schedule/(?P<item_date>[^/]+)$")
_UPLOAD_PUT_RE = re.compile(r"^/upload/put/(?P<object_key>.+)$")
_SENSITIVE_KEYS = {
    "access_token",
    "authorization",
    "code",
    "id_card_number",
    "password",
    "password_hash",
    "phone",
    "raw",
    "real_name",
    "token",
    "transaction_id",
    "wechat_id",
    "wechat_openid",
    "wechat_unionid",
    "x_callback_secret",
}


@dataclass
class _ActorContext:
    user_id: int | None = None
    actor_name: str | None = None
    actor_role: str | None = None


@dataclass
class _UserAuditMeta:
    channel: str
    action: str
    action_label: str
    resource_type: str
    resource_id: str | None = None


def _is_suspicious_404_path(path: str) -> bool:
    normalized = (path or "/").split("?", 1)[0].lower()
    return any(
        normalized == prefix
        or normalized.startswith(f"{prefix}/")
        or normalized.startswith(f"{prefix}.")
        or normalized.startswith(f"{prefix}-")
        for prefix in _SUSPICIOUS_404_PREFIXES
    )


class _UvicornAccessNoiseFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        args = record.args
        if not isinstance(args, tuple) or len(args) < 5:
            return True
        try:
            path = str(args[2])
            status_code = int(args[4])
        except (ValueError, TypeError):
            return True
        # Suppress noisy scanner probes that only generate expected 404s.
        if status_code == 404 and _is_suspicious_404_path(path):
            return False
        return True


def _install_uvicorn_access_log_filter() -> None:
    access_logger = logging.getLogger("uvicorn.access")
    if any(isinstance(existing, _UvicornAccessNoiseFilter) for existing in access_logger.filters):
        return
    access_logger.addFilter(_UvicornAccessNoiseFilter())


def _extract_client_ip(request: Request) -> str | None:
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    if request.client:
        return request.client.host
    return None


def _actor_from_user(user: User | None) -> _ActorContext:
    if not user:
        return _ActorContext()
    actor_name = user.username or user.display_name or f"user:{user.id}"
    return _ActorContext(user_id=int(user.id), actor_name=actor_name, actor_role=user.role)


def _resolve_user_from_bearer_token(token: str | None) -> _ActorContext:
    if not token:
        return _ActorContext()
    db = SessionLocal()
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_alg])
        user_id = int(payload.get("sub"))
        return _actor_from_user(db.get(User, user_id))
    except (JWTError, ValueError, TypeError, Exception):
        return _ActorContext()
    finally:
        db.close()


def _redact_payload(value: Any) -> Any:
    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}
        for key, item in value.items():
            normalized_key = str(key).strip().lower()
            if normalized_key in _SENSITIVE_KEYS:
                sanitized[str(key)] = "***"
            else:
                sanitized[str(key)] = _redact_payload(item)
        return sanitized
    if isinstance(value, list):
        return [_redact_payload(item) for item in value]
    return value


def _parse_json_dict(raw: bytes) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        parsed = json.loads(raw.decode("utf-8", errors="ignore"))
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _sanitize_request_body(raw: bytes) -> str:
    if not raw:
        return ""
    text = raw.decode("utf-8", errors="ignore")
    if len(text) > 4000:
        text = text[:4000] + "...(truncated)"
    try:
        body = json.loads(text)
    except json.JSONDecodeError:
        return text
    body = _redact_payload(body)
    serialized = json.dumps(body, ensure_ascii=False)
    if len(serialized) > 4000:
        serialized = serialized[:4000] + "...(truncated)"
    return serialized


def _extract_bearer_token(request: Request) -> str | None:
    authorization = request.headers.get("authorization") or ""
    if not authorization.startswith("Bearer "):
        return None
    token = authorization.removeprefix("Bearer ").strip()
    return token or None


def _infer_upload_channel(value: str | None) -> str:
    normalized = (value or "").strip().lower()
    if normalized.startswith(("portfolio", "watermark", "studio", "avatar", "cover")):
        return "studio_web"
    return "mini_program"


def _normalize_upload_channel(value: str | None) -> str | None:
    normalized = (value or "").strip().lower()
    if normalized in {"mini_program", "studio_web", "ops_web"}:
        return normalized
    return None


def _coerce_resource_id(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return text[:255]


def _classify_user_operation(request: Request, request_json: dict[str, Any]) -> _UserAuditMeta | None:
    path = request.url.path
    method = request.method.upper()

    if path == "/auth/login" and method == "POST":
        return _UserAuditMeta("ops_web", "password_login", "账号密码登录", "auth_session")
    if path == "/auth/wechat" and method == "POST":
        return _UserAuditMeta("mini_program", "wechat_login", "微信用户登录", "auth_session")
    if path == "/auth/wechat/studio" and method == "POST":
        return _UserAuditMeta("studio_web", "wechat_studio_login", "微信摄影师登录", "auth_session")
    if path == "/photographers/apply" and method == "POST":
        return _UserAuditMeta("mini_program", "apply_photographer", "申请成为摄影师", "photographer_profile")
    if path == "/me/photographer/apply" and method == "POST":
        return _UserAuditMeta("mini_program", "submit_certification", "提交摄影师认证", "photographer_certification")
    if path == "/me/photographer/tencent-realname/verify" and method == "POST":
        return _UserAuditMeta("mini_program", "verify_realname", "发起实名认证校验", "realname_verification")
    if path == "/membership/orders" and method == "POST":
        return _UserAuditMeta(
            "mini_program",
            "create_membership_order",
            "创建会员订单",
            "membership_order",
            _coerce_resource_id(request_json.get("plan_code")),
        )
    if path == "/upload/presign" and method == "POST":
        prefix = request_json.get("prefix")
        explicit_channel = _normalize_upload_channel(request_json.get("channel"))
        resource_id = "/".join(
            part for part in [request_json.get("prefix"), request_json.get("filename")] if isinstance(part, str) and part
        )
        return _UserAuditMeta(
            explicit_channel or _infer_upload_channel(prefix if isinstance(prefix, str) else None),
            "request_upload_presign",
            "申请上传凭证",
            "upload_object",
            _coerce_resource_id(resource_id),
        )
    if path == "/studio/me" and method == "PUT":
        return _UserAuditMeta("studio_web", "update_studio_profile", "更新摄影师资料", "studio_profile")
    if path == "/studio/portfolio" and method == "POST":
        return _UserAuditMeta("studio_web", "create_portfolio_item", "新增作品", "portfolio_item")
    if path == "/studio/packages" and method == "POST":
        return _UserAuditMeta("studio_web", "create_package", "新增套餐", "package")
    if path == "/studio/schedule" and method == "PUT":
        return _UserAuditMeta(
            "studio_web",
            "upsert_schedule",
            "更新档期",
            "schedule_block",
            _coerce_resource_id(request_json.get("date")),
        )

    favorite_match = _USER_FAVORITE_RE.match(path)
    if favorite_match:
        return _UserAuditMeta(
            "mini_program",
            "favorite_photographer" if method == "POST" else "unfavorite_photographer",
            "收藏摄影师" if method == "POST" else "取消收藏摄影师",
            "photographer",
            favorite_match.group("photographer_id"),
        )

    portfolio_match = _STUDIO_PORTFOLIO_RE.match(path)
    if portfolio_match:
        if method == "PUT":
            return _UserAuditMeta(
                "studio_web",
                "update_portfolio_item",
                "更新作品",
                "portfolio_item",
                portfolio_match.group("item_id"),
            )
        if method == "DELETE":
            return _UserAuditMeta(
                "studio_web",
                "delete_portfolio_item",
                "删除作品",
                "portfolio_item",
                portfolio_match.group("item_id"),
            )

    package_match = _STUDIO_PACKAGE_RE.match(path)
    if package_match:
        if method == "PUT":
            return _UserAuditMeta(
                "studio_web",
                "update_package",
                "更新套餐",
                "package",
                package_match.group("package_id"),
            )
        if method == "DELETE":
            return _UserAuditMeta(
                "studio_web",
                "delete_package",
                "删除套餐",
                "package",
                package_match.group("package_id"),
            )

    schedule_match = _STUDIO_SCHEDULE_RE.match(path)
    if schedule_match and method == "DELETE":
        return _UserAuditMeta(
            "studio_web",
            "delete_schedule",
            "删除档期",
            "schedule_block",
            schedule_match.group("item_date"),
        )

    upload_match = _UPLOAD_PUT_RE.match(path)
    if upload_match and method == "PUT":
        object_key = upload_match.group("object_key")
        return _UserAuditMeta(
            _infer_upload_channel(object_key),
            "upload_file",
            "上传文件",
            "upload_object",
            _coerce_resource_id(object_key),
        )

    return None


async def _extract_response_body(response: Response) -> tuple[Response, bytes]:
    body = getattr(response, "body", None)
    if body is not None:
        return response, bytes(body)

    chunks = [chunk async for chunk in response.body_iterator]
    response_body = b"".join(chunks)
    headers = dict(response.headers)
    headers.pop("content-length", None)
    rebuilt = Response(
        content=response_body,
        status_code=response.status_code,
        headers=headers,
        media_type=response.media_type,
        background=response.background,
    )
    return rebuilt, response_body


def _resolve_actor_from_response_body(response_body: bytes) -> _ActorContext:
    response_json = _parse_json_dict(response_body)
    token = response_json.get("access_token")
    if not isinstance(token, str) or not token.strip():
        return _ActorContext()
    return _resolve_user_from_bearer_token(token.strip())


def _should_audit_admin_request(request: Request) -> bool:
    return request.url.path.startswith(settings.admin_api_prefix)


def _fallback_actor_from_request(path: str, request_json: dict[str, Any]) -> _ActorContext:
    if path == "/auth/login":
        username = request_json.get("username")
        if isinstance(username, str) and username.strip():
            return _ActorContext(actor_name=username.strip())
    return _ActorContext()


def _merge_actor_context(primary: _ActorContext, fallback: _ActorContext) -> _ActorContext:
    return _ActorContext(
        user_id=primary.user_id if primary.user_id is not None else fallback.user_id,
        actor_name=primary.actor_name or fallback.actor_name,
        actor_role=primary.actor_role or fallback.actor_role,
    )


def _persist_admin_operation_log(
    *,
    request: Request,
    actor: _ActorContext,
    request_body_preview: str,
    status_code: int,
) -> None:
    db = SessionLocal()
    try:
        db.add(
            AdminOperationLog(
                admin_user_id=actor.user_id,
                username=actor.actor_name,
                method=request.method,
                path=request.url.path,
                query_string=request.url.query or "",
                status_code=status_code,
                client_ip=_extract_client_ip(request),
                user_agent=request.headers.get("user-agent"),
                request_body=request_body_preview,
            )
        )
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


def _persist_user_operation_log(
    *,
    request: Request,
    actor: _ActorContext,
    meta: _UserAuditMeta,
    request_body_preview: str,
    status_code: int,
) -> None:
    db = SessionLocal()
    try:
        db.add(
            UserOperationLog(
                user_id=actor.user_id,
                actor_name=actor.actor_name,
                actor_role=actor.actor_role,
                channel=meta.channel,
                action=meta.action,
                action_label=meta.action_label,
                resource_type=meta.resource_type,
                resource_id=meta.resource_id,
                method=request.method,
                path=request.url.path,
                query_string=request.url.query or "",
                status_code=status_code,
                client_ip=_extract_client_ip(request),
                user_agent=request.headers.get("user-agent"),
                request_body=request_body_preview,
            )
        )
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


def _create_operation_audit_middleware(app: FastAPI) -> None:
    @app.middleware("http")
    async def operation_audit_log_middleware(request: Request, call_next: Callable[[Request], Any]) -> Response:
        raw_body = b""
        request_json: dict[str, Any] = {}
        request_body_preview = ""
        bearer_actor = _ActorContext()
        user_meta: _UserAuditMeta | None = None
        should_audit_admin = _should_audit_admin_request(request)

        if should_audit_admin or request.method.upper() in {"POST", "PUT", "PATCH", "DELETE"}:
            raw_body = await request.body()
            request_json = _parse_json_dict(raw_body)
            request_body_preview = _sanitize_request_body(raw_body)
            bearer_actor = _resolve_user_from_bearer_token(_extract_bearer_token(request))
            user_meta = _classify_user_operation(request, request_json)

        response = await call_next(request)

        if not should_audit_admin and user_meta is None:
            return response

        response, response_body = await _extract_response_body(response)
        actor = bearer_actor
        if request.url.path in _LOGIN_PATHS and response.status_code < 400:
            actor = _merge_actor_context(_resolve_actor_from_response_body(response_body), actor)
        actor = _merge_actor_context(actor, _fallback_actor_from_request(request.url.path, request_json))

        if should_audit_admin:
            _persist_admin_operation_log(
                request=request,
                actor=actor,
                request_body_preview=request_body_preview,
                status_code=int(response.status_code),
            )
        if user_meta is not None:
            _persist_user_operation_log(
                request=request,
                actor=actor,
                meta=user_meta,
                request_body_preview=request_body_preview,
                status_code=int(response.status_code),
            )
        return response


def _check_database_readiness() -> None:
    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
    except Exception as exc:
        raise HTTPException(status_code=503, detail="db not ready") from exc
    finally:
        db.close()


def create_app() -> FastAPI:
    settings.ensure_runtime_safety()
    _install_uvicorn_access_log_filter()
    app = FastAPI(title=settings.app_name)

    # 开发联调：允许前端跨域访问
    if settings.is_dev:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=False,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    @app.get("/health")
    def health() -> dict:
        return {"ok": True, "name": settings.app_name, "env": settings.env}

    @app.get("/readyz")
    @app.get("/health/ready")
    def health_ready() -> dict:
        _check_database_readiness()
        return {"ok": True, "checks": {"database": "ok"}}

    _create_operation_audit_middleware(app)
    app.include_router(api_router)
    return app


app = create_app()
