from __future__ import annotations

import os
import re
import time
from pathlib import PurePosixPath

from fastapi import APIRouter

from app.schemas.upload import PresignIn, PresignOut
from app.services.storage import ensure_bucket, presign_put

router = APIRouter()


def _safe_filename(name: str) -> str:
    name = os.path.basename(name)
    name = re.sub(r"[^a-zA-Z0-9._-]+", "-", name).strip("-")
    return name or "file"


@router.post("/presign", response_model=PresignOut)
def presign(payload: PresignIn) -> PresignOut:
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

