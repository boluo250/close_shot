from __future__ import annotations

import json
import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.db.models import MembershipOrder, User
from app.db.session import get_db
from app.schemas.membership import (
    MembershipMeOut,
    MembershipOrderCreateIn,
    MembershipOrderCreateOut,
    MembershipPaymentCallbackIn,
    MembershipPaymentCallbackOut,
    MembershipPlanOut,
)
from app.services.membership import extend_member_expiry, get_membership_plan, get_membership_plans, is_member_active

router = APIRouter()


@router.get("/plans", response_model=list[MembershipPlanOut])
def list_plans() -> list[MembershipPlanOut]:
    return [MembershipPlanOut(**x) for x in get_membership_plans()]


@router.get("/me", response_model=MembershipMeOut)
def membership_me(me: User = Depends(get_current_user)) -> MembershipMeOut:
    return MembershipMeOut(
        is_member=is_member_active(me),
        member_expires_at=me.member_expires_at,
        server_time=datetime.now(timezone.utc),
    )


@router.post("/orders", response_model=MembershipOrderCreateOut)
def create_order(
    payload: MembershipOrderCreateIn,
    me: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MembershipOrderCreateOut:
    plan = get_membership_plan(payload.plan_code)
    if not plan:
        raise HTTPException(status_code=400, detail="invalid membership plan")

    out_trade_no = f"MBR{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}{secrets.token_hex(4)}"
    order = MembershipOrder(
        user_id=me.id,
        plan_code=plan["code"],
        months=int(plan["months"]),
        amount_cents=int(plan["price_cents"]),
        channel="wechat_mini",
        status="pending",
        out_trade_no=out_trade_no,
    )
    db.add(order)
    db.commit()
    db.refresh(order)

    # 此处返回小程序支付参数占位；后续接微信支付统一下单后替换。
    pay_params = {
        "provider": "wechat_mini",
        "mock": True,
        "out_trade_no": out_trade_no,
        "amount_cents": order.amount_cents,
    }
    return MembershipOrderCreateOut(
        order_id=order.id,
        out_trade_no=out_trade_no,
        plan_code=order.plan_code,
        amount_cents=order.amount_cents,
        channel=order.channel,
        status=order.status,
        pay_params=pay_params,
    )


@router.post("/callback/wechat", response_model=MembershipPaymentCallbackOut)
def wechat_callback(
    payload: MembershipPaymentCallbackIn,
    x_callback_secret: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> MembershipPaymentCallbackOut:
    if x_callback_secret != settings.membership_callback_secret:
        raise HTTPException(status_code=401, detail="invalid callback secret")

    order = db.scalar(select(MembershipOrder).where(MembershipOrder.out_trade_no == payload.out_trade_no))
    if not order:
        raise HTTPException(status_code=404, detail="order not found")

    # 回调幂等：已支付直接返回当前状态
    if order.status == "paid":
        user = db.scalar(select(User).where(User.id == order.user_id))
        return MembershipPaymentCallbackOut(order_status=order.status, member_expires_at=user.member_expires_at if user else None)

    if payload.result != "SUCCESS":
        order.status = "failed"
        order.notify_raw_json = json.dumps(payload.raw or {}, ensure_ascii=False)
        db.commit()
        return MembershipPaymentCallbackOut(order_status=order.status, member_expires_at=None)

    user = db.scalar(select(User).where(User.id == order.user_id))
    if not user:
        raise HTTPException(status_code=404, detail="user not found")

    order.status = "paid"
    order.transaction_id = payload.transaction_id
    order.paid_at = payload.paid_at or datetime.now(timezone.utc)
    order.notify_raw_json = json.dumps(payload.raw or {}, ensure_ascii=False)
    member_expires_at = extend_member_expiry(user, order.months)

    db.commit()
    return MembershipPaymentCallbackOut(order_status=order.status, member_expires_at=member_expires_at)
