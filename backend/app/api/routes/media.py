from __future__ import annotations

from fastapi import APIRouter, HTTPException
from starlette.responses import StreamingResponse

from app.core.config import settings
from app.services.storage import s3_get_object_stream

router = APIRouter()


@router.get("/{object_key:path}")
def get_media(object_key: str):
    """
    通过后端域名访问对象存储文件（给小程序/前端一个统一可白名单的域名）。
    MVP：仅支持 S3/MinIO。
    """
    if settings.storage_backend != "s3":
        raise HTTPException(status_code=400, detail="media proxy only supports s3 backend in MVP")

    try:
        stream, content_type = s3_get_object_stream(object_key)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="not found")

    return StreamingResponse(stream, media_type=content_type or "application/octet-stream")

