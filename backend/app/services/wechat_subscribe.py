from __future__ import annotations

import logging
from datetime import datetime

import httpx

from app.core.config import settings
from app.db.models import AppointmentRequest
from app.services.wechat_security import _get_access_token

logger = logging.getLogger(__name__)


def get_appointment_subscribe_config() -> dict[str, str | None]:
    return {
        "photographer_new_appointment_template_id": _clean_template_id(
            settings.wechat_subscribe_photographer_new_appointment_template_id
        ),
        "customer_appointment_accepted_template_id": _clean_template_id(
            settings.wechat_subscribe_customer_appointment_accepted_template_id
        ),
        "customer_appointment_completed_template_id": _clean_template_id(
            settings.wechat_subscribe_customer_appointment_completed_template_id
        ),
    }


def notify_photographer_new_appointment(item: AppointmentRequest) -> bool:
    template_id = _clean_template_id(settings.wechat_subscribe_photographer_new_appointment_template_id)
    photographer_user = item.photographer.user if item.photographer else None
    if not photographer_user or not photographer_user.wechat_openid or not template_id:
        return False
    subject = item.shooting_type or (item.package.name if item.package else "") or "新预约申请"
    return _send_subscribe_message(
        openid=photographer_user.wechat_openid,
        template_id=template_id,
        page=f"pages/appointments/detail/index?id={int(item.id)}&mode=assigned",
        data={
            "thing1": {"value": _trim(subject, 20)},  # 预约内容
            "date7": {"value": _format_date(item.scheduled_at)},  # 预约时间
            "thing4": {"value": _trim(item.location_text or "待确认地点", 20)},  # 地点
            "thing9": {"value": _trim("请尽快处理预约申请", 20)},  # 温馨提示
        },
        log_label="photographer_new_appointment",
    )


def notify_customer_appointment_accepted(item: AppointmentRequest) -> bool:
    template_id = _clean_template_id(settings.wechat_subscribe_customer_appointment_accepted_template_id)
    customer = item.customer
    if not customer or not customer.wechat_openid or not template_id:
        return False
    photographer_name = item.photographer.user.display_name if item.photographer and item.photographer.user else "摄影师"
    return _send_subscribe_message(
        openid=customer.wechat_openid,
        template_id=template_id,
        page=f"pages/appointments/detail/index?id={int(item.id)}&mode=mine",
        data={
            "thing1": {"value": _trim(f"{photographer_name}已同意预约", 20)},  # 预约服务
            "date3": {"value": _format_date(item.scheduled_at)},  # 开始时间
            "thing10": {"value": _trim(item.location_text or "待确认地点", 20)},  # 地址
            "time14": {"value": _format_time_only(item.scheduled_at)},  # 预约时间
        },
        log_label="customer_appointment_accepted",
    )


def notify_customer_appointment_completed(item: AppointmentRequest) -> bool:
    template_id = _clean_template_id(settings.wechat_subscribe_customer_appointment_completed_template_id)
    customer = item.customer
    if not customer or not customer.wechat_openid or not template_id:
        return False
    photographer_name = item.photographer.user.display_name if item.photographer and item.photographer.user else "摄影师"
    return _send_subscribe_message(
        openid=customer.wechat_openid,
        template_id=template_id,
        page=f"pages/appointments/detail/index?id={int(item.id)}&mode=mine",
        data={
            "thing12": {"value": _trim(f"{photographer_name}拍摄服务已完成", 20)},  # 订单内容
            "time16": {"value": _format_time(item.photographer_completed_at or item.scheduled_at or datetime.now())},  # 完成时间
            "thing5": {"value": _trim("请确认完成并评价", 20)},  # 备注信息
            "time4": {"value": _format_time(item.scheduled_at)},  # 服务时间
        },
        log_label="customer_appointment_completed",
    )


def _clean_template_id(value: str | None) -> str | None:
    text = (value or "").strip()
    return text or None


def _trim(value: str | None, limit: int) -> str:
    text = (value or "").strip()
    if not text:
        return ""
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)] + "…"


def _format_time(value: datetime | None) -> str:
    if value is None:
        return ""
    local = value
    return local.strftime("%Y-%m-%d %H:%M")


def _format_date(value: datetime | None) -> str:
    if value is None:
        return ""
    local = value
    return local.strftime("%Y-%m-%d")


def _format_time_only(value: datetime | None) -> str:
    if value is None:
        return ""
    local = value
    return local.strftime("%H:%M")


def _send_subscribe_message(
    *,
    openid: str,
    template_id: str,
    page: str,
    data: dict[str, dict[str, str]],
    log_label: str,
) -> bool:
    try:
        token = _get_access_token()
    except Exception as exc:  # pragma: no cover - config/network branch
        logger.warning("wechat subscribe skipped (%s): %s", log_label, exc)
        return False

    payload = {
        "touser": openid,
        "template_id": template_id,
        "page": page,
        "data": data,
        "miniprogram_state": settings.wechat_subscribe_miniprogram_state or "formal",
        "lang": "zh_CN",
    }
    try:
        resp = httpx.post(
            f"https://api.weixin.qq.com/cgi-bin/message/subscribe/send?access_token={token}",
            json=payload,
            timeout=10,
        )
        resp.raise_for_status()
        body = resp.json()
    except Exception as exc:  # pragma: no cover - network branch
        logger.warning("wechat subscribe request failed (%s): %s", log_label, exc)
        return False

    errcode = int(body.get("errcode", 0) or 0)
    if errcode != 0:
        logger.warning("wechat subscribe rejected (%s): %s", log_label, body)
        return False
    return True
