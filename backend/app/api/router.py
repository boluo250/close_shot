from __future__ import annotations

from fastapi import APIRouter

from app.api.routes import admin, analytics, auth, dev, me, media, membership, ops, photographers, studio, upload
from app.core.config import settings

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(photographers.router, prefix="/photographers", tags=["photographers"])
api_router.include_router(analytics.router, prefix="/analytics", tags=["analytics"])
api_router.include_router(me.router, prefix="/me", tags=["me"])
api_router.include_router(media.router, prefix="/media", tags=["media"])
api_router.include_router(studio.router, prefix="/studio", tags=["studio"])
api_router.include_router(upload.router, prefix="/upload", tags=["upload"])
api_router.include_router(membership.router, prefix="/membership", tags=["membership"])
api_router.include_router(ops.router, prefix="/ops", tags=["ops"])
api_router.include_router(admin.router, prefix=settings.admin_api_prefix, tags=["admin"])
if settings.is_dev:
    api_router.include_router(dev.router, prefix="/dev", tags=["dev"])
