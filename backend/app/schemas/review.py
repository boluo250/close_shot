from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.common import TimestampOut


class ReviewCreateIn(BaseModel):
    rating: int = Field(ge=1, le=5)
    content: str | None = Field(default=None, max_length=2000)


class ReviewOut(TimestampOut):
    id: int
    user_id: int | None = None
    photographer_id: int
    rating: int
    content: str | None = None
    user_display_name: str | None = None
    user_avatar_url: str | None = None

