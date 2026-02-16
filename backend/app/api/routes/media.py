from __future__ import annotations

from fastapi import APIRouter, HTTPException
from starlette.responses import StreamingResponse

from app.services.storage import get_object_stream

router = APIRouter()


@router.get("/{object_key:path}")
def get_media(object_key: str):
    """
    通过后端域名访问对象存储文件（给小程序/前端一个统一可白名单的域名）。
    支持 s3 或 local。
    """
    try:
        stream, content_type = get_object_stream(object_key)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="not found")

    return StreamingResponse(stream, media_type=content_type or "application/octet-stream")

