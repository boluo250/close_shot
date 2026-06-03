from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.db.models import AdminOperationLog, UserOperationLog


@dataclass
class CleanupScopeResult:
    scope: str
    retention_days: int
    cutoff_at: str | None
    batch_size: int
    dry_run: bool
    enabled: bool
    affected_rows: int = 0
    deleted_rows: int = 0
    batches: int = 0

    def to_dict(self) -> dict[str, int | str | bool | None]:
        return asdict(self)


def _normalize_now(now: datetime | None) -> datetime:
    if now is None:
        return datetime.now(timezone.utc)
    if now.tzinfo is None:
        return now.replace(tzinfo=timezone.utc)
    return now


def _cleanup_scope(
    db: Session,
    *,
    scope: str,
    model: type[AdminOperationLog] | type[UserOperationLog],
    retention_days: int,
    batch_size: int,
    dry_run: bool,
    now: datetime,
) -> CleanupScopeResult:
    enabled = retention_days > 0
    safe_batch_size = max(int(batch_size), 1)
    cutoff_at = None if not enabled else (now - timedelta(days=retention_days))
    result = CleanupScopeResult(
        scope=scope,
        retention_days=retention_days,
        cutoff_at=cutoff_at.isoformat() if cutoff_at else None,
        batch_size=safe_batch_size,
        dry_run=dry_run,
        enabled=enabled,
    )
    if not enabled or cutoff_at is None:
        return result

    count_stmt = select(func.count(model.id)).where(model.created_at < cutoff_at)
    result.affected_rows = int(db.scalar(count_stmt) or 0)
    if dry_run or result.affected_rows == 0:
        return result

    while True:
        ids = list(
            db.scalars(
                select(model.id)
                .where(model.created_at < cutoff_at)
                .order_by(model.created_at.asc(), model.id.asc())
                .limit(safe_batch_size)
            ).all()
        )
        if not ids:
            break
        db.execute(delete(model).where(model.id.in_(ids)))
        db.commit()
        result.deleted_rows += len(ids)
        result.batches += 1

    return result


def cleanup_operation_logs(
    db: Session,
    *,
    admin_retention_days: int,
    user_retention_days: int,
    batch_size: int,
    dry_run: bool = False,
    now: datetime | None = None,
) -> dict[str, object]:
    resolved_now = _normalize_now(now)
    admin = _cleanup_scope(
        db,
        scope="admin",
        model=AdminOperationLog,
        retention_days=admin_retention_days,
        batch_size=batch_size,
        dry_run=dry_run,
        now=resolved_now,
    )
    user = _cleanup_scope(
        db,
        scope="user",
        model=UserOperationLog,
        retention_days=user_retention_days,
        batch_size=batch_size,
        dry_run=dry_run,
        now=resolved_now,
    )
    return {
        "ok": True,
        "dry_run": dry_run,
        "batch_size": max(int(batch_size), 1),
        "executed_at": resolved_now.isoformat(),
        "admin": admin.to_dict(),
        "user": user.to_dict(),
    }
