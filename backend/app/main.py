from __future__ import annotations

import json
import logging
from collections.abc import Callable
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from jose import JWTError, jwt
from sqlalchemy import text
from starlette.requests import Request
from starlette.responses import Response

from app.api.router import api_router
from app.core.config import settings
from app.db.models import AdminOperationLog, User
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

_USER_AUDIT_PREFIXES = (
    "/upload/",
    "/studio/",
    "/me/photographer/",
    "/membership/orders",
)


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


def _resolve_user_from_bearer_token(token: str | None) -> tuple[int | None, str | None]:
    if not token:
        return None, None
    db = SessionLocal()
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_alg])
        user_id = int(payload.get("sub"))
        user = db.get(User, user_id)
        if not user:
            return None, None
        actor_name = user.username or user.display_name or f"user:{user.id}"
        return user.id, actor_name
    except (JWTError, ValueError, TypeError):
        return None, None
    finally:
        db.close()


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
    if isinstance(body, dict):
        for key in ("password", "password_hash", "token", "authorization"):
            if key in body:
                body[key] = "***"
    return json.dumps(body, ensure_ascii=False)


def _extract_bearer_token(request: Request) -> str | None:
    authorization = request.headers.get("authorization") or ""
    if not authorization.startswith("Bearer "):
        return None
    token = authorization.removeprefix("Bearer ").strip()
    return token or None


def _should_audit_request(request: Request) -> bool:
    path = request.url.path
    if path.startswith(settings.admin_api_prefix):
        return True
    if request.method not in {"POST", "PUT", "PATCH", "DELETE"}:
        return False
    return any(path.startswith(prefix) for prefix in _USER_AUDIT_PREFIXES)


def _create_admin_audit_middleware(app: FastAPI) -> None:
    @app.middleware("http")
    async def admin_audit_log_middleware(request: Request, call_next: Callable[[Request], Any]) -> Response:
        should_audit = _should_audit_request(request)
        request_body_preview = ""
        admin_user_id: int | None = None
        username: str | None = None
        if should_audit:
            request_body_preview = _sanitize_request_body(await request.body())
            token = _extract_bearer_token(request)
            admin_user_id, username = _resolve_user_from_bearer_token(token)

        response = await call_next(request)

        if not should_audit:
            return response

        db = SessionLocal()
        try:
            db.add(
                AdminOperationLog(
                    admin_user_id=admin_user_id,
                    username=username,
                    method=request.method,
                    path=request.url.path,
                    query_string=request.url.query or "",
                    status_code=int(response.status_code),
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

    _create_admin_audit_middleware(app)
    app.include_router(api_router)
    return app


app = create_app()
