from __future__ import annotations

import json
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
        return user.id, user.username
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


def _create_admin_audit_middleware(app: FastAPI) -> None:
    @app.middleware("http")
    async def admin_audit_log_middleware(request: Request, call_next: Callable[[Request], Any]) -> Response:
        is_admin_path = request.url.path.startswith(settings.admin_api_prefix)
        request_body_preview = ""
        admin_user_id: int | None = None
        username: str | None = None
        if is_admin_path:
            if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
                request_body_preview = _sanitize_request_body(await request.body())
            token = _extract_bearer_token(request)
            admin_user_id, username = _resolve_user_from_bearer_token(token)

        response = await call_next(request)

        if not is_admin_path:
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


def create_app() -> FastAPI:
    settings.ensure_runtime_safety()
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

    @app.get("/health/ready")
    def health_ready() -> dict:
        db = SessionLocal()
        try:
            db.execute(text("SELECT 1"))
            return {"ok": True}
        except Exception:
            raise HTTPException(status_code=503, detail="db not ready")
        finally:
            db.close()

    _create_admin_audit_middleware(app)
    app.include_router(api_router)
    return app


app = create_app()

