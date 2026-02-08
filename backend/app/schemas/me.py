from __future__ import annotations

from pydantic import BaseModel


class MeIdentityOut(BaseModel):
    role: str
    photographer_status: str | None = None
    photographer_reject_reason: str | None = None
