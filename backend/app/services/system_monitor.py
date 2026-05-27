from __future__ import annotations

import json
import shutil
import socket
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote

from sqlalchemy import func, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import SystemMonitorEvent


STATUS_OK = "ok"
STATUS_WARNING = "warning"
STATUS_CRITICAL = "critical"
STATUS_UNKNOWN = "unknown"

SEVERITY_RANK = {
    STATUS_OK: 0,
    STATUS_UNKNOWN: 1,
    STATUS_WARNING: 2,
    STATUS_CRITICAL: 3,
}

HTTP_5XX_MONITOR_KEY = "http_5xx"
BACKUP_JOB_MONITOR_KEY = "backup_job"


def persist_system_monitor_event(
    db: Session,
    *,
    monitor_key: str,
    severity: str,
    title: str,
    message: str,
    status: str = "firing",
    source: str | None = None,
    metric_value: float | None = None,
    detail: dict[str, Any] | None = None,
) -> None:
    db.add(
        SystemMonitorEvent(
            monitor_key=monitor_key,
            severity=severity,
            status=status,
            title=title,
            message=message,
            source=source,
            metric_value=metric_value,
            detail_json=json.dumps(detail or {}, ensure_ascii=False),
        )
    )


def build_system_monitor_summary(db: Session) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    containers: list[dict[str, Any]] = []

    checks.append(
        {
            "key": "api_health",
            "category": "availability",
            "title": "API 健康检查",
            "status": STATUS_OK,
            "summary": "应用进程在线",
            "message": f"{settings.app_name} 已启动，接口可响应监控汇总请求。",
            "detail": {"app_name": settings.app_name, "env": settings.env},
        }
    )

    checks.append(_build_database_readiness_check(db))
    checks.append(_build_database_capacity_check(db))
    checks.extend(_build_disk_checks())

    container_payload = _build_container_checks()
    checks.extend(container_payload["checks"])
    containers = container_payload["containers"]

    checks.append(_build_5xx_check(db))
    checks.append(_build_backup_check(db))

    recent_events = _load_recent_events(db)
    summary_counts = {
        STATUS_OK: sum(1 for item in checks if item["status"] == STATUS_OK),
        STATUS_WARNING: sum(1 for item in checks if item["status"] == STATUS_WARNING),
        STATUS_CRITICAL: sum(1 for item in checks if item["status"] == STATUS_CRITICAL),
        STATUS_UNKNOWN: sum(1 for item in checks if item["status"] == STATUS_UNKNOWN),
    }
    overall_status = _worst_status([item["status"] for item in checks])

    return {
        "generated_at": datetime.now(timezone.utc),
        "overall_status": overall_status,
        "summary": {
            "total_checks": len(checks),
            "ok_count": summary_counts[STATUS_OK],
            "warning_count": summary_counts[STATUS_WARNING],
            "critical_count": summary_counts[STATUS_CRITICAL],
            "unknown_count": summary_counts[STATUS_UNKNOWN],
        },
        "checks": checks,
        "containers": containers,
        "recent_events": recent_events,
    }


def _build_database_readiness_check(db: Session) -> dict[str, Any]:
    try:
        db.execute(text("SELECT 1"))
    except Exception as exc:
        return {
            "key": "database_ready",
            "category": "database",
            "title": "数据库连通性",
            "status": STATUS_CRITICAL,
            "summary": "数据库不可用",
            "message": str(exc),
            "detail": {},
        }
    return {
        "key": "database_ready",
        "category": "database",
        "title": "数据库连通性",
        "status": STATUS_OK,
        "summary": "数据库连接正常",
        "message": "数据库就绪检查通过。",
        "detail": {},
    }


def _build_database_capacity_check(db: Session) -> dict[str, Any]:
    try:
        size_bytes = _resolve_database_size_bytes(db)
    except Exception as exc:
        return {
            "key": "database_capacity",
            "category": "database",
            "title": "数据库容量",
            "status": STATUS_UNKNOWN,
            "summary": "暂时无法获取数据库容量",
            "message": str(exc),
            "metric_value": None,
            "threshold_value": settings.monitor_db_size_warn_bytes,
            "unit": "bytes",
            "detail": {},
        }

    status = _threshold_status(
        size_bytes,
        warn=settings.monitor_db_size_warn_bytes,
        critical=settings.monitor_db_size_critical_bytes,
    )
    return {
        "key": "database_capacity",
        "category": "database",
        "title": "数据库容量",
        "status": status,
        "summary": f"当前数据库占用 {_format_bytes(size_bytes)}",
        "message": (
            f"已使用 {_format_bytes(size_bytes)}；告警阈值 "
            f"{_format_bytes(settings.monitor_db_size_warn_bytes)} / {_format_bytes(settings.monitor_db_size_critical_bytes)}。"
        ),
        "metric_value": float(size_bytes),
        "threshold_value": float(settings.monitor_db_size_warn_bytes),
        "unit": "bytes",
        "detail": {"size_bytes": int(size_bytes)},
    }


def _build_disk_checks() -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    for raw_path in _split_csv(settings.monitor_disk_paths):
        path = raw_path or "/"
        if not Path(path).exists():
            checks.append(
                {
                    "key": f"disk_usage:{path}",
                    "category": "storage",
                    "title": f"磁盘空间 {path}",
                    "status": STATUS_UNKNOWN,
                    "summary": "监控路径不存在",
                    "message": f"磁盘监控路径不存在：{path}",
                    "detail": {"path": path},
                }
            )
            continue

        usage = shutil.disk_usage(path)
        used_percent = (usage.used / usage.total * 100.0) if usage.total else 0.0
        status = _threshold_status(
            used_percent,
            warn=settings.monitor_disk_warn_percent,
            critical=settings.monitor_disk_critical_percent,
        )
        checks.append(
            {
                "key": f"disk_usage:{path}",
                "category": "storage",
                "title": f"磁盘空间 {path}",
                "status": status,
                "summary": f"已使用 {used_percent:.1f}%",
                "message": (
                    f"总容量 {_format_bytes(usage.total)}，已用 {_format_bytes(usage.used)}，剩余 {_format_bytes(usage.free)}。"
                ),
                "metric_value": round(used_percent, 2),
                "threshold_value": settings.monitor_disk_warn_percent,
                "unit": "percent",
                "detail": {
                    "path": path,
                    "total_bytes": int(usage.total),
                    "used_bytes": int(usage.used),
                    "free_bytes": int(usage.free),
                },
            }
        )
    return checks


def _build_container_checks() -> dict[str, list[dict[str, Any]]]:
    names = _split_csv(settings.monitor_container_names)
    socket_path = (settings.monitor_docker_socket or "").strip()
    if not socket_path:
        return {
            "checks": [
                {
                    "key": "container_runtime",
                    "category": "container",
                    "title": "容器运行时",
                    "status": STATUS_UNKNOWN,
                    "summary": "未配置 Docker Socket",
                    "message": "monitor_docker_socket 为空，无法获取容器重启、CPU、内存等指标。",
                    "detail": {},
                }
            ],
            "containers": [],
        }

    checks: list[dict[str, Any]] = []
    containers: list[dict[str, Any]] = []
    client = _DockerSocketClient(socket_path)
    runtime_error: str | None = None

    for name in names:
        try:
            inspect_data = client.get_json(f"/containers/{quote(name, safe='')}/json")
            stats_data = client.get_json(f"/containers/{quote(name, safe='')}/stats?stream=0")
        except Exception as exc:
            runtime_error = str(exc)
            containers.append(
                {
                    "name": name,
                    "status": STATUS_UNKNOWN,
                    "state": "unknown",
                    "health_status": None,
                    "restart_count": None,
                    "started_at": None,
                    "cpu_percent": None,
                    "memory_usage_bytes": None,
                    "memory_limit_bytes": None,
                    "memory_percent": None,
                    "message": runtime_error,
                }
            )
            continue

        state = inspect_data.get("State") or {}
        restart_count = int(state.get("RestartCount") or 0)
        running = bool(state.get("Running"))
        health_status = ((state.get("Health") or {}).get("Status") or "").strip() or None
        started_at = _parse_docker_datetime(state.get("StartedAt"))
        cpu_percent = _calculate_docker_cpu_percent(stats_data)
        memory_usage_bytes, memory_limit_bytes, memory_percent = _calculate_docker_memory(stats_data)

        container_status = STATUS_OK
        messages: list[str] = []
        if not running:
            container_status = STATUS_CRITICAL
            messages.append("容器未处于 running 状态")
        if health_status == "unhealthy":
            container_status = STATUS_CRITICAL
            messages.append("容器健康检查失败")
        elif health_status in {"starting", "created"} and container_status != STATUS_CRITICAL:
            container_status = STATUS_WARNING
            messages.append(f"容器健康状态为 {health_status}")

        if cpu_percent is not None:
            cpu_status = _threshold_status(
                cpu_percent,
                warn=settings.monitor_cpu_warn_percent,
                critical=settings.monitor_cpu_critical_percent,
            )
            container_status = _worst_status([container_status, cpu_status])
            if cpu_status != STATUS_OK:
                messages.append(f"CPU 使用率 {cpu_percent:.1f}%")

        if memory_percent is not None:
            memory_status = _threshold_status(
                memory_percent,
                warn=settings.monitor_memory_warn_percent,
                critical=settings.monitor_memory_critical_percent,
            )
            container_status = _worst_status([container_status, memory_status])
            if memory_status != STATUS_OK:
                messages.append(f"内存使用率 {memory_percent:.1f}%")

        restart_recent = bool(
            restart_count > 0
            and started_at is not None
            and datetime.now(timezone.utc) - started_at
            <= timedelta(minutes=settings.monitor_container_restart_recent_minutes)
        )
        restart_status = STATUS_WARNING if restart_recent else STATUS_OK
        checks.append(
            {
                "key": f"container_restart:{name}",
                "category": "container",
                "title": f"容器重启 {name}",
                "status": restart_status,
                "summary": "最近检测到容器重启" if restart_recent else "最近未检测到容器重启",
                "message": (
                    f"累计重启 {restart_count} 次，最近启动时间 "
                    f"{started_at.isoformat() if started_at else '-'}。"
                ),
                "metric_value": float(restart_count),
                "threshold_value": 1.0,
                "unit": "count",
                "detail": {
                    "name": name,
                    "restart_count": restart_count,
                    "started_at": started_at.isoformat() if started_at else None,
                },
            }
        )
        checks.append(
            {
                "key": f"container_status:{name}",
                "category": "container",
                "title": f"容器状态 {name}",
                "status": container_status,
                "summary": "运行正常" if container_status == STATUS_OK else "需要关注",
                "message": "；".join(messages) if messages else "容器运行、健康检查、CPU、内存均正常。",
                "detail": {
                    "name": name,
                    "running": running,
                    "health_status": health_status,
                    "restart_count": restart_count,
                },
            }
        )
        containers.append(
            {
                "name": name,
                "status": container_status,
                "state": "running" if running else str(state.get("Status") or "stopped"),
                "health_status": health_status,
                "restart_count": restart_count,
                "started_at": started_at,
                "cpu_percent": cpu_percent,
                "memory_usage_bytes": memory_usage_bytes,
                "memory_limit_bytes": memory_limit_bytes,
                "memory_percent": memory_percent,
                "message": "；".join(messages) if messages else "正常",
            }
        )

    if runtime_error and all(item["status"] == STATUS_UNKNOWN for item in containers):
        checks.insert(
            0,
            {
                "key": "container_runtime",
                "category": "container",
                "title": "容器运行时",
                "status": STATUS_UNKNOWN,
                "summary": "无法访问 Docker Runtime",
                "message": runtime_error,
                "detail": {"socket_path": socket_path},
            },
        )

    return {"checks": checks, "containers": containers}


def _build_5xx_check(db: Session) -> dict[str, Any]:
    since = datetime.now(timezone.utc) - timedelta(minutes=settings.monitor_5xx_window_minutes)
    count = int(
        db.scalar(
            select(func.count(SystemMonitorEvent.id)).where(
                SystemMonitorEvent.monitor_key == HTTP_5XX_MONITOR_KEY,
                SystemMonitorEvent.created_at >= since,
            )
        )
        or 0
    )
    status = _threshold_status(
        count,
        warn=settings.monitor_5xx_warn_count,
        critical=settings.monitor_5xx_critical_count,
    )
    return {
        "key": "http_5xx",
        "category": "availability",
        "title": "5xx 告警",
        "status": status,
        "summary": f"最近 {settings.monitor_5xx_window_minutes} 分钟共 {count} 次 5xx",
        "message": (
            f"告警阈值 {settings.monitor_5xx_warn_count} / {settings.monitor_5xx_critical_count} 次；"
            "详情可在下方事件列表查看。"
        ),
        "metric_value": float(count),
        "threshold_value": float(settings.monitor_5xx_warn_count),
        "unit": "count",
        "detail": {"window_minutes": settings.monitor_5xx_window_minutes, "count": count},
    }


def _build_backup_check(db: Session) -> dict[str, Any]:
    event = db.scalar(
        select(SystemMonitorEvent)
        .where(SystemMonitorEvent.monitor_key == BACKUP_JOB_MONITOR_KEY)
        .order_by(SystemMonitorEvent.created_at.desc(), SystemMonitorEvent.id.desc())
        .limit(1)
    )
    max_age = timedelta(hours=settings.monitor_backup_max_age_hours)

    if event is None:
        return {
            "key": "backup_job",
            "category": "backup",
            "title": "备份任务",
            "status": STATUS_CRITICAL,
            "summary": "尚未收到备份上报",
            "message": "请检查 pg-backup 定时任务与 MONITOR_REPORT_SECRET 配置。",
            "detail": {},
        }

    age = datetime.now(timezone.utc) - event.created_at
    detail = _load_event_detail(event)
    if event.severity == STATUS_CRITICAL:
        status = STATUS_CRITICAL
    elif age > max_age:
        status = STATUS_WARNING
    else:
        status = STATUS_OK

    return {
        "key": "backup_job",
        "category": "backup",
        "title": "备份任务",
        "status": status,
        "summary": event.title,
        "message": (
            f"{event.message or '-'}；最近上报时间 {event.created_at.isoformat()}；"
            f"距今约 {int(age.total_seconds() // 3600)} 小时。"
        ),
        "detail": detail | {"last_reported_at": event.created_at.isoformat()},
    }


def _load_recent_events(db: Session, limit: int = 30) -> list[dict[str, Any]]:
    rows = db.scalars(
        select(SystemMonitorEvent)
        .where(SystemMonitorEvent.monitor_key.in_([HTTP_5XX_MONITOR_KEY, BACKUP_JOB_MONITOR_KEY]))
        .order_by(SystemMonitorEvent.created_at.desc(), SystemMonitorEvent.id.desc())
        .limit(limit)
    ).all()
    return [
        {
            "id": int(item.id),
            "monitor_key": item.monitor_key,
            "severity": item.severity,
            "status": item.status,
            "title": item.title,
            "message": item.message,
            "source": item.source,
            "metric_value": item.metric_value,
            "detail": _load_event_detail(item),
            "created_at": item.created_at,
        }
        for item in rows
    ]


def _resolve_database_size_bytes(db: Session) -> int:
    dialect = (getattr(getattr(db, "bind", None), "dialect", None) or getattr(db, "dialect", None))
    dialect_name = getattr(dialect, "name", "")
    if dialect_name == "postgresql":
        size = db.scalar(select(func.pg_database_size(func.current_database())))
        return int(size or 0)

    if dialect_name == "sqlite":
        engine = getattr(db, "bind", None)
        if engine is None:
            raise RuntimeError("sqlite engine unavailable")
        url = make_url(str(engine.url))
        database = url.database or ""
        if database in {"", ":memory:"}:
            return 0
        path = Path(database)
        return path.stat().st_size if path.exists() else 0

    raise RuntimeError(f"unsupported database dialect: {dialect_name or 'unknown'}")


def _parse_docker_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text_value = value.strip()
    if text_value.endswith("Z"):
        text_value = text_value[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(text_value)
    except ValueError:
        return None


def _calculate_docker_cpu_percent(stats_data: dict[str, Any]) -> float | None:
    cpu_stats = stats_data.get("cpu_stats") or {}
    precpu_stats = stats_data.get("precpu_stats") or {}
    cpu_total = ((cpu_stats.get("cpu_usage") or {}).get("total_usage")) or 0
    precpu_total = ((precpu_stats.get("cpu_usage") or {}).get("total_usage")) or 0
    system_total = cpu_stats.get("system_cpu_usage") or 0
    presystem_total = precpu_stats.get("system_cpu_usage") or 0
    cpu_delta = float(cpu_total - precpu_total)
    system_delta = float(system_total - presystem_total)
    online_cpus = int(cpu_stats.get("online_cpus") or 0)
    if online_cpus <= 0:
        per_cpu = (cpu_stats.get("cpu_usage") or {}).get("percpu_usage") or []
        online_cpus = len(per_cpu)
    if cpu_delta <= 0 or system_delta <= 0 or online_cpus <= 0:
        return None
    return round((cpu_delta / system_delta) * online_cpus * 100.0, 2)


def _calculate_docker_memory(stats_data: dict[str, Any]) -> tuple[int | None, int | None, float | None]:
    memory_stats = stats_data.get("memory_stats") or {}
    usage = memory_stats.get("usage")
    limit = memory_stats.get("limit")
    if usage is None or limit in (None, 0):
        return None, None, None
    usage_value = int(usage)
    limit_value = int(limit)
    return usage_value, limit_value, round(usage_value / limit_value * 100.0, 2)


def _load_event_detail(event: SystemMonitorEvent) -> dict[str, Any]:
    try:
        detail = json.loads(event.detail_json) if event.detail_json else {}
    except json.JSONDecodeError:
        detail = {}
    return detail if isinstance(detail, dict) else {}


def _threshold_status(value: float | int, *, warn: float, critical: float) -> str:
    numeric = float(value)
    if numeric >= float(critical):
        return STATUS_CRITICAL
    if numeric >= float(warn):
        return STATUS_WARNING
    return STATUS_OK


def _worst_status(statuses: list[str]) -> str:
    if not statuses:
        return STATUS_UNKNOWN
    return max(statuses, key=lambda item: SEVERITY_RANK.get(item, -1))


def _split_csv(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [item.strip() for item in raw.split(",") if item.strip()]


def _format_bytes(value: int | float | None) -> str:
    if value is None:
        return "-"
    size = float(value)
    units = ["B", "KB", "MB", "GB", "TB", "PB"]
    for unit in units:
        if abs(size) < 1024.0 or unit == units[-1]:
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{value} B"


def _decode_chunked_http_body(body: bytes) -> bytes:
    data = body
    chunks: list[bytes] = []
    while data:
        line_end = data.find(b"\r\n")
        if line_end < 0:
            break
        length_text = data[:line_end].split(b";", 1)[0].strip()
        try:
            length = int(length_text, 16)
        except ValueError:
            break
        data = data[line_end + 2 :]
        if length == 0:
            break
        chunks.append(data[:length])
        data = data[length + 2 :]
    return b"".join(chunks)


class _DockerSocketClient:
    def __init__(self, socket_path: str) -> None:
        self.socket_path = socket_path

    def get_json(self, path: str) -> dict[str, Any]:
        body = self._get(path)
        payload = json.loads(body.decode("utf-8"))
        if not isinstance(payload, dict):
            raise RuntimeError("docker api returned unexpected payload")
        return payload

    def _get(self, path: str) -> bytes:
        client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        client.settimeout(3.0)
        try:
            client.connect(self.socket_path)
            request = (
                f"GET {path} HTTP/1.1\r\n"
                "Host: docker\r\n"
                "User-Agent: close-shot-monitor\r\n"
                "Connection: close\r\n\r\n"
            )
            client.sendall(request.encode("utf-8"))
            data = b""
            while True:
                chunk = client.recv(65536)
                if not chunk:
                    break
                data += chunk
        finally:
            client.close()

        header_bytes, _, body = data.partition(b"\r\n\r\n")
        if not header_bytes:
            raise RuntimeError("docker api empty response")
        header_lines = header_bytes.decode("utf-8", errors="ignore").split("\r\n")
        status_line = header_lines[0]
        try:
            status_code = int(status_line.split()[1])
        except (IndexError, ValueError) as exc:
            raise RuntimeError(f"docker api invalid status line: {status_line}") from exc

        headers: dict[str, str] = {}
        for line in header_lines[1:]:
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            headers[key.strip().lower()] = value.strip()
        if headers.get("transfer-encoding", "").lower() == "chunked":
            body = _decode_chunked_http_body(body)
        if status_code >= 400:
            raise RuntimeError(body.decode("utf-8", errors="ignore") or f"docker api status {status_code}")
        return body
