from __future__ import annotations

import os
import re
import time
from pathlib import PurePosixPath

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from app.schemas.upload import PresignIn, PresignOut
from app.core.config import settings
from app.services.storage import ensure_bucket, presign_put, put_object_bytes, verify_upload_token

router = APIRouter()


def _safe_filename(name: str) -> str:
    name = os.path.basename(name)
    name = re.sub(r"[^a-zA-Z0-9._-]+", "-", name).strip("-")
    return name or "file"


@router.post("/presign", response_model=PresignOut)
def presign(payload: PresignIn) -> PresignOut:
    # s3 才需要 bucket；local 模式不依赖对象存储服务
    ensure_bucket()
    filename = _safe_filename(payload.filename)
    object_key = str(PurePosixPath(payload.prefix) / f"{int(time.time())}_{filename}")
    res = presign_put(object_key=object_key, content_type=payload.content_type)
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
    content_type = request.headers.get("content-type")
    put_object_bytes(object_key=object_key, data=body, content_type=content_type)
    return JSONResponse({"ok": True, "object_key": object_key})

