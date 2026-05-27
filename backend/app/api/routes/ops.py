from __future__ import annotations

import json
from datetime import datetime
from typing import Any
from urllib.parse import parse_qs

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.services.system_monitor import BACKUP_JOB_MONITOR_KEY, STATUS_CRITICAL, persist_system_monitor_event

router = APIRouter()


def _parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    normalized = str(value or "").strip().lower()
    return normalized in {"1", "true", "yes", "y", "ok", "success"}


def _parse_datetime(value: Any) -> str | None:
    if not value:
        return None
    text_value = str(value).strip()
    if not text_value:
        return None
    probe = text_value[:-1] + "+00:00" if text_value.endswith("Z") else text_value
    try:
        datetime.fromisoformat(probe)
    except ValueError:
        return None
    return text_value


def _parse_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


async def _read_monitor_payload(request: Request) -> dict[str, Any]:
    payload: dict[str, Any] = dict(request.query_params)
    content_type = (request.headers.get("content-type") or "").lower()
    raw_body = await request.body()
    if not raw_body:
        return payload
    if "application/json" in content_type:
        try:
            body_payload = json.loads(raw_body.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=400, detail="invalid json payload") from exc
        if isinstance(body_payload, dict):
            payload.update(body_payload)
        return payload
    if "application/x-www-form-urlencoded" in content_type:
        form_payload = parse_qs(raw_body.decode("utf-8"), keep_blank_values=True)
        payload.update({key: values[-1] if values else "" for key, values in form_payload.items()})
        return payload
    return payload


@router.post("/monitor/backup-report")
async def report_backup_status(
    request: Request,
    db: Session = Depends(get_db),
) -> dict[str, bool]:
    secret = (settings.monitor_report_secret or "").strip()
    if not secret:
        raise HTTPException(status_code=503, detail="monitor report secret is not configured")
    if request.headers.get("x-monitor-secret", "").strip() != secret:
        raise HTTPException(status_code=403, detail="invalid monitor secret")

    payload = await _read_monitor_payload(request)
    success = _parse_bool(payload.get("success"))
    job_name = str(payload.get("job_name") or "pg-backup").strip() or "pg-backup"
    message = str(payload.get("message") or "").strip()
    title = "数据库备份成功" if success else "数据库备份失败"
    if not message:
        message = "备份任务执行成功。" if success else "备份任务执行失败。"

    detail = {
        "job_name": job_name,
        "success": success,
        "started_at": _parse_datetime(payload.get("started_at")),
        "finished_at": _parse_datetime(payload.get("finished_at")),
        "duration_seconds": payload.get("duration_seconds"),
        "dump_file": payload.get("dump_file"),
        "remote_object_key": payload.get("remote_object_key"),
    }

    persist_system_monitor_event(
        db,
        monitor_key=BACKUP_JOB_MONITOR_KEY,
        severity="info" if success else STATUS_CRITICAL,
        status="ok" if success else "firing",
        title=title,
        message=message,
        source=job_name,
        metric_value=_parse_float(payload.get("duration_seconds")),
        detail=detail,
    )
    db.commit()
    return {"ok": True}
