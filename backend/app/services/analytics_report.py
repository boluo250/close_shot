from __future__ import annotations

import hashlib
import hmac
import json
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

import httpx
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.db.models import AnalyticsEvent, Photographer, User


def _local_day_range_utc(target_date: date, tz_name: str) -> tuple[datetime, datetime]:
    tz = ZoneInfo(tz_name)
    day_start_local = datetime.combine(target_date, time.min, tzinfo=tz)
    day_end_local = day_start_local + timedelta(days=1)
    return day_start_local.astimezone(timezone.utc), day_end_local.astimezone(timezone.utc)


def build_daily_analytics_payload(
    db: Session,
    *,
    target_date: date,
    timezone_name: str,
    top_limit: int = 30,
) -> dict:
    since_utc, until_utc = _local_day_range_utc(target_date, timezone_name)
    base_where = [AnalyticsEvent.created_at >= since_utc, AnalyticsEvent.created_at < until_utc]

    total_exposure = db.scalar(
        select(func.count(AnalyticsEvent.id)).where(*base_where, AnalyticsEvent.event_type == "photographer_exposure")
    ) or 0
    total_click = db.scalar(
        select(func.count(AnalyticsEvent.id)).where(*base_where, AnalyticsEvent.event_type == "photographer_click")
    ) or 0
    total_contact = db.scalar(
        select(func.count(AnalyticsEvent.id)).where(*base_where, AnalyticsEvent.event_type == "photographer_contact")
    ) or 0

    exposure_count = func.sum(
        case((AnalyticsEvent.event_type == "photographer_exposure", 1), else_=0)
    ).label("exposure_count")
    click_count = func.sum(case((AnalyticsEvent.event_type == "photographer_click", 1), else_=0)).label("click_count")
    contact_count = func.sum(
        case((AnalyticsEvent.event_type == "photographer_contact", 1), else_=0)
    ).label("contact_count")

    rows = db.execute(
        select(
            AnalyticsEvent.photographer_id,
            User.display_name,
            exposure_count,
            click_count,
            contact_count,
        )
        .join(Photographer, Photographer.id == AnalyticsEvent.photographer_id)
        .join(User, User.id == Photographer.user_id)
        .where(*base_where, AnalyticsEvent.photographer_id.is_not(None))
        .group_by(AnalyticsEvent.photographer_id, User.display_name)
        .order_by(contact_count.desc(), click_count.desc(), exposure_count.desc())
        .limit(max(1, min(top_limit, 100)))
    ).all()

    items = []
    for photographer_id, display_name, exp_cnt, click_cnt, contact_cnt in rows:
        exposure = int(exp_cnt or 0)
        click = int(click_cnt or 0)
        contact = int(contact_cnt or 0)
        items.append(
            {
                "photographer_id": int(photographer_id),
                "display_name": display_name,
                "exposure_count": exposure,
                "click_count": click,
                "contact_count": contact,
                "ctr": round(click / exposure, 4) if exposure > 0 else 0.0,
                "contact_rate": round(contact / click, 4) if click > 0 else 0.0,
            }
        )

    return {
        "report_type": "analytics_daily",
        "date": target_date.isoformat(),
        "timezone": timezone_name,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "totals": {
            "exposure": int(total_exposure),
            "click": int(total_click),
            "contact": int(total_contact),
        },
        "top_photographers": items,
    }


def post_daily_analytics_payload(
    payload: dict,
    *,
    webhook_url: str,
    webhook_secret: str | None = None,
    timeout_seconds: float = 10.0,
) -> int:
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    headers = {"Content-Type": "application/json"}
    if webhook_secret:
        signature = hmac.new(webhook_secret.encode("utf-8"), body.encode("utf-8"), hashlib.sha256).hexdigest()
        headers["X-CloseShot-Signature"] = signature
    with httpx.Client(timeout=timeout_seconds) as client:
        response = client.post(webhook_url, content=body.encode("utf-8"), headers=headers)
        response.raise_for_status()
        return response.status_code
