from __future__ import annotations

import argparse
import json
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from app.core.config import settings
from app.db.session import SessionLocal
from app.services.analytics_report import build_daily_analytics_payload, post_daily_analytics_payload


def _resolve_target_date(date_text: str | None, timezone_name: str) -> date:
    if date_text:
        return date.fromisoformat(date_text)
    tz = ZoneInfo(timezone_name)
    now_local = datetime.now(tz)
    return (now_local - timedelta(days=1)).date()


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate and optionally push analytics daily report.")
    parser.add_argument("--date", help="Report date in YYYY-MM-DD. Defaults to yesterday in configured timezone.")
    parser.add_argument("--dry-run", action="store_true", help="Generate report only, do not send webhook.")
    parser.add_argument("--top-limit", type=int, default=30, help="Top photographers to include (1-100).")
    args = parser.parse_args()

    timezone_name = settings.analytics_report_timezone or "Asia/Shanghai"
    target_date = _resolve_target_date(args.date, timezone_name)

    db = SessionLocal()
    try:
        payload = build_daily_analytics_payload(
            db,
            target_date=target_date,
            timezone_name=timezone_name,
            top_limit=args.top_limit,
        )
    finally:
        db.close()

    webhook_url = settings.analytics_daily_report_webhook_url
    sent = False
    status_code = None
    if not args.dry_run and webhook_url:
        status_code = post_daily_analytics_payload(
            payload,
            webhook_url=webhook_url,
            webhook_secret=settings.analytics_daily_report_webhook_secret,
        )
        sent = True

    output = {
        "ok": True,
        "date": payload["date"],
        "timezone": payload["timezone"],
        "totals": payload["totals"],
        "top_count": len(payload["top_photographers"]),
        "sent": sent,
        "webhook_status_code": status_code,
    }
    print(json.dumps(output, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
