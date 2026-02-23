from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class MembershipPlanOut(BaseModel):
    code: str
    title: str
    months: int
    price_cents: int
    original_price_cents: int | None = None
    badge: str | None = None


class MembershipMeOut(BaseModel):
    is_member: bool
    member_expires_at: datetime | None = None
    server_time: datetime


class MembershipOrderCreateIn(BaseModel):
    plan_code: str = Field(min_length=1, max_length=32)


class MembershipOrderCreateOut(BaseModel):
    order_id: int
    out_trade_no: str
    plan_code: str
    amount_cents: int
    channel: str
    status: str
    pay_params: dict


class MembershipPaymentCallbackIn(BaseModel):
    out_trade_no: str = Field(min_length=8, max_length=64)
    transaction_id: str | None = Field(default=None, max_length=128)
    paid_at: datetime | None = None
    result: str = Field(default="SUCCESS", description="SUCCESS 或 FAIL")
    raw: dict | None = None


class MembershipPaymentCallbackOut(BaseModel):
    ok: bool = True
    order_status: str
    member_expires_at: datetime | None = None
