# PostgreSQL 每日备份

脚本 `pg-backup.sh` 会从 `backend/.env` 读取数据库与对象存储配置，通过 `docker exec` 进入 PostgreSQL 容器执行 `pg_dump`，上传到腾讯云 COS（S3 兼容），并清理本地/远端过期备份。

## 依赖（Ubuntu）

在项目根目录执行（推荐）：

```bash
./infra/deploy.sh install-backup-deps
```

或手动安装：

```bash
sudo apt-get update
sudo apt-get install -y awscli
```

## 配置

- **数据库**：使用 `.env` 中的 `DATABASE_URL` 提取用户名、密码、库名；实际备份时不走 `host:port`，而是进入 `db` 容器执行 `pg_dump`。
- **对象存储**：使用 `.env` 中的 `S3_*`（腾讯云 COS 已兼容 S3 API）。脚本会自动强制 `awscli` 使用 COS 所需的 virtual-host-style，无需手动改 `~/.aws/config`。
- 无需改脚本即可使用当前 `.env`；若需覆盖路径或保留天数，可用环境变量（见下）。

## 可选环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `BACKEND_DIR` | 脚本所在目录的上一级 | backend 项目目录（含 `.env`） |
| `LOCAL_BACKUP_DIR` | `backend/.backups/pg` | 本地 dump 存放目录 |
| `LOG_DIR` | `backend/.backups/logs` | 日志目录 |
| `DB_CONTAINER_NAME` | `close-shot-db` | PostgreSQL 容器名 |
| `S3_PREFIX` | `pg-backup` | 对象存储前缀（目录） |
| `KEEP_LOCAL_DAYS` | 3 | 本地保留天数 |
| `KEEP_REMOTE_DAYS` | 14 | 远端 COS 保留天数 |

## 手动执行

```bash
cd /path/to/close_shot/backend
chmod +x scripts/pg-backup.sh
./scripts/pg-backup.sh
```

日志会追加到 `backend/.backups/logs/pg-backup.log`（默认）。

前提：
- `close-shot-db` 容器正在运行；若你改过容器名，可通过 `DB_CONTAINER_NAME=你的容器名` 覆盖。
- 宿主机用户要有执行 `docker` 的权限。

## 每天自动备份（cron）

1. 确认脚本可执行且手动跑通一次：

   ```bash
   cd /path/to/close_shot/backend
   chmod +x scripts/pg-backup.sh
   ./scripts/pg-backup.sh
   ```

2. 编辑当前用户的 crontab：

   ```bash
   crontab -e
   ```

3. 添加一行（每天凌晨 3 点执行，按实际路径改 `BACKEND_DIR`）：

   ```cron
   # 每天 03:00 执行 PG 备份（进入 db 容器导出后上传到 COS）
   0 3 * * * BACKEND_DIR=/path/to/close_shot/backend /path/to/close_shot/backend/scripts/pg-backup.sh
   ```

   若希望用 root 统一备份、日志放系统目录，可写成：

   ```cron
   0 3 * * * BACKEND_DIR=/path/to/close_shot/backend LOCAL_BACKUP_DIR=/var/backups/close_shot_pg LOG_DIR=/var/log/close_shot /path/to/close_shot/backend/scripts/pg-backup.sh
   ```

4. 保存退出。cron 会每天在该时间运行脚本。

## 恢复示例

从 COS 下载对应日期的 `.dump` 后，在同一台或新机恢复：

```bash
# 下载（或从 COS 控制台下载）
# 恢复（会覆盖当前库，慎用）
pg_restore -U close_shot -h localhost -d close_shot -c --if-exists -F c close_shot_20250310_030001.dump
```

建议先在测试库上做一次恢复演练。
