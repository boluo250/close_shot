# 操作日志回收

任务入口：`python -m app.jobs.cleanup_operation_logs`

用于定期清理以下两张表中过期的线上操作日志，避免持续膨胀：

- `admin_operation_logs`
- `user_operation_logs`

默认策略：

- 管理员操作日志保留 `180` 天
- 用户操作日志保留 `90` 天
- 每批删除 `1000` 条，降低长事务和锁表风险

## 配置

在 `backend/.env` 中可配置：

```env
ADMIN_OPERATION_LOG_RETENTION_DAYS=180
USER_OPERATION_LOG_RETENTION_DAYS=90
OPERATION_LOG_CLEANUP_BATCH_SIZE=1000
```

说明：

- 保留天数 `<= 0` 时，对应范围不会执行回收
- `OPERATION_LOG_CLEANUP_BATCH_SIZE` 越大，清得越快，但单批事务更重

## 上线前准备

先执行数据库迁移，给日志表补 `created_at` 索引：

```bash
cd /path/to/close_shot/backend
alembic upgrade head
```

## 手动演练

先看会删多少，不实际删除：

```bash
cd /path/to/close_shot/backend
python -m app.jobs.cleanup_operation_logs --dry-run
```

返回示例：

```json
{
  "ok": true,
  "dry_run": true,
  "batch_size": 1000,
  "executed_at": "2026-06-02T03:00:00+00:00",
  "admin": {
    "scope": "admin",
    "retention_days": 180,
    "affected_rows": 3200
  },
  "user": {
    "scope": "user",
    "retention_days": 90,
    "affected_rows": 18642
  }
}
```

确认数量合理后，再正式执行：

```bash
cd /path/to/close_shot/backend
python -m app.jobs.cleanup_operation_logs
```

如果想临时覆盖策略：

```bash
python -m app.jobs.cleanup_operation_logs \
  --admin-retention-days 365 \
  --user-retention-days 120 \
  --batch-size 2000
```

## cron 示例

推荐顺序：

1. 手动执行一次 `--dry-run`
2. 手动执行一次正式删除
3. 再加入 `crontab`

编辑当前用户的 `crontab`：

```bash
crontab -e
```

每天凌晨 4:20 执行一次：

```cron
20 4 * * * cd /path/to/close_shot/backend && /usr/bin/python3 -m app.jobs.cleanup_operation_logs >> /var/log/close_shot_operation_log_cleanup.log 2>&1
```

如果你的生产环境使用虚拟环境，可改成：

```cron
20 4 * * * cd /path/to/close_shot/backend && /path/to/close_shot/backend/.venv/bin/python -m app.jobs.cleanup_operation_logs >> /var/log/close_shot_operation_log_cleanup.log 2>&1
```

如果希望先连续观察几天，只做演练：

```cron
20 4 * * * cd /path/to/close_shot/backend && /usr/bin/python3 -m app.jobs.cleanup_operation_logs --dry-run >> /var/log/close_shot_operation_log_cleanup.log 2>&1
```

## 线上建议

- 初次正式执行建议放在低峰时段
- 如果历史日志量已经非常大，可以先临时把 `--batch-size` 调小，例如 `500`
- 如果一次运行删除量仍然很大，可以一天跑多次，逐步削峰
- PostgreSQL 大量删除后，表空间不会立刻完全回收；如果后续仍觉得膨胀明显，再结合业务低峰安排 `VACUUM (ANALYZE)` 或更进一步的维护
