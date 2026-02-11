from __future__ import annotations

from fastapi import APIRouter

from app.api.routes import admin, auth, dev, me, media, photographers, studio, upload

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(photographers.router, prefix="/photographers", tags=["photographers"])
api_router.include_router(me.router, prefix="/me", tags=["me"])
api_router.include_router(media.router, prefix="/media", tags=["media"])
api_router.include_router(studio.router, prefix="/studio", tags=["studio"])
api_router.include_router(upload.router, prefix="/upload", tags=["upload"])
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])
api_router.include_router(dev.router, prefix="/dev", tags=["dev"])

