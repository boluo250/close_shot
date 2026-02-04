from __future__ import annotations

from pydantic import BaseModel, Field


class PresignIn(BaseModel):
    filename: str = Field(min_length=1, max_length=256)
    content_type: str | None = Field(default=None, max_length=128)
    prefix: str = Field(default="uploads", max_length=64)


class PresignOut(BaseModel):
    method: str
    url: str
    headers: dict[str, str]
    public_url: str | None = None
    proxy_url: str | None = None
    object_key: str

