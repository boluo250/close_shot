from __future__ import annotations

import mimetypes
import os
import re
import time
from pathlib import PurePosixPath

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from app.api.deps import get_current_user
from app.core.config import settings
from app.db.models import User
from app.schemas.upload import PresignIn, PresignOut
from app.services.storage import ensure_bucket, presign_put, put_object_bytes, verify_upload_token

router = APIRouter()


def _safe_filename(name: str) -> str:
    name = os.path.basename(name)
    name = re.sub(r"[^a-zA-Z0-9._-]+", "-", name).strip("-")
    return name or "file"


def _split_csv(raw: str) -> set[str]:
    return {x.strip().lower() for x in (raw or "").split(",") if x.strip()}


def _normalize_content_type(filename: str, content_type: str | None) -> str | None:
    normalized = (content_type or "").split(";")[0].strip().lower()
    if not normalized:
        guessed, _ = mimetypes.guess_type(filename)
        return guessed.lower() if guessed else "image/jpeg"
    if normalized == "image/jpg":
        return "image/jpeg"
    if normalized in {"image", "image/*", "image/image", "application/octet-stream", "binary/octet-stream"}:
        guessed, _ = mimetypes.guess_type(filename)
        return guessed.lower() if guessed else "image/jpeg"
    return normalized


def _validate_upload_constraints(prefix: str, content_type: str | None) -> None:
    allowed_prefixes = _split_csv(settings.upload_allowed_prefixes)
    if allowed_prefixes and prefix.lower() not in allowed_prefixes:
        raise HTTPException(status_code=400, detail="invalid upload prefix")

    if content_type:
        normalized = content_type.split(";")[0].strip().lower()
        allowed_types = _split_csv(settings.upload_allowed_content_types)
        if allowed_types and normalized not in allowed_types:
            raise HTTPException(status_code=400, detail="unsupported content type")


@router.post("/presign", response_model=PresignOut)
def presign(payload: PresignIn, _me: User = Depends(get_current_user)) -> PresignOut:
    # s3 才需要 bucket；local 模式不依赖对象存储服务
    ensure_bucket()
    content_type = _normalize_content_type(payload.filename, payload.content_type)
    _validate_upload_constraints(prefix=payload.prefix, content_type=content_type)
    filename = _safe_filename(payload.filename)
    object_key = str(PurePosixPath(payload.prefix) / f"{int(time.time())}_{filename}")
    res = presign_put(object_key=object_key, content_type=content_type)
    return PresignOut(
        method=res.method,
        url=res.url,
        headers=res.headers,
        public_url=res.public_url,
        proxy_url=f"/media/{res.object_key}",
        object_key=res.object_key,
    )


@router.put("/put/{object_key:path}")
async def put_local_object(object_key: str, request: Request, token: str | None = None):
    """
    local backend 的直传入口：小程序/前端用 wx.request PUT 二进制即可。
    - token: 由 /upload/presign 返回，绑定 object_key，短期有效
    """
    if settings.storage_backend != "local":
        raise HTTPException(status_code=400, detail="put only supported in local backend")
    if not token:
        raise HTTPException(status_code=401, detail="missing token")
    try:
        verify_upload_token(token=token, object_key=object_key)
    except ValueError:
        raise HTTPException(status_code=401, detail="invalid token")

    body = await request.body()
    if not body:
        raise HTTPException(status_code=400, detail="empty body")
    if len(body) > settings.upload_max_bytes:
        raise HTTPException(status_code=413, detail="file too large")
    content_type = request.headers.get("content-type")
    _validate_upload_constraints(prefix=PurePosixPath(object_key).parts[0], content_type=content_type)
    put_object_bytes(object_key=object_key, data=body, content_type=content_type)
    return JSONResponse({"ok": True, "object_key": object_key})
