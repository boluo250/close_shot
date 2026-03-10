#!/usr/bin/env bash
# PostgreSQL 每日备份：docker exec 到 db 容器执行 pg_dump -> 本地 -> 上传至 S3/COS，并清理本地/远端过期备份
# 依赖：docker, aws-cli（或 pip install awscli）
# 使用：在 backend 目录执行，或设置 BACKEND_DIR；可被 cron 每日调用

set -euo pipefail

# 若未设置，则假定在 backend 目录的上一级（项目根）或 backend 目录
BACKEND_DIR="${BACKEND_DIR:-$(cd "$(dirname "$0")/.." && pwd)}"
ENV_FILE="${BACKEND_DIR}/.env"
# 默认本地备份目录（可改为 /var/backups/close_shot_pg 等需 root 的路径）
LOCAL_BACKUP_DIR="${LOCAL_BACKUP_DIR:-${BACKEND_DIR}/.backups/pg}"
DB_CONTAINER_NAME="${DB_CONTAINER_NAME:-close-shot-db}"
S3_PREFIX="${S3_PREFIX:-pg-backup}"
KEEP_LOCAL_DAYS="${KEEP_LOCAL_DAYS:-3}"
KEEP_REMOTE_DAYS="${KEEP_REMOTE_DAYS:-14}"
LOG_DIR="${LOG_DIR:-${BACKEND_DIR}/.backups/logs}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# 加载 .env（只导出非注释、非空行中的 KEY=VALUE）
load_env() {
  if [[ ! -f "$ENV_FILE" ]]; then
    echo "[$(date -Iseconds)] ERROR: .env not found: $ENV_FILE" >&2
    exit 1
  fi
  set -a
  while IFS= read -r line; do
    [[ "$line" =~ ^#.*$ ]] && continue
    [[ -z "${line// /}" ]] && continue
    if [[ "$line" =~ ^([A-Za-z_][A-Za-z0-9_]*)=(.*)$ ]]; then
      export "$line"
    fi
  done < "$ENV_FILE"
  set +a
}

# 从 DATABASE_URL 解析 PG 认证信息（格式：postgresql+psycopg://user:pass@host:port/dbname）
parse_db_url() {
  local url="${DATABASE_URL:-}"
  if [[ -z "$url" ]]; then
    echo "[$(date -Iseconds)] ERROR: DATABASE_URL not set in .env" >&2
    exit 1
  fi
  local rest="${url#*//}"
  local userpass="${rest%%@*}"
  local hostportdb="${rest#*@}"
  export PGUSER="${userpass%%:*}"
  export PGPASSWORD="${userpass#*:}"
  export DBNAME="${hostportdb#*/}"
  DBNAME="${DBNAME%%\?*}"
  export PGPASSWORD
}

check_commands() {
  local missing=()
  command -v docker >/dev/null 2>&1 || missing+=(docker)
  command -v aws >/dev/null 2>&1 || missing+=(aws)
  if [[ ${#missing[@]} -gt 0 ]]; then
    echo "[$(date -Iseconds)] ERROR: missing commands: ${missing[*]}. Install: docker, awscli" >&2
    exit 1
  fi
}

check_db_container() {
  if ! docker inspect "$DB_CONTAINER_NAME" >/dev/null 2>&1; then
    echo "[$(date -Iseconds)] ERROR: DB container not found: $DB_CONTAINER_NAME" >&2
    exit 1
  fi
  local running
  running="$(docker inspect -f '{{.State.Running}}' "$DB_CONTAINER_NAME" 2>/dev/null || true)"
  if [[ "$running" != "true" ]]; then
    echo "[$(date -Iseconds)] ERROR: DB container is not running: $DB_CONTAINER_NAME" >&2
    exit 1
  fi
}

# 在 db 容器内执行 pg_dump，并将 dump 输出到宿主机文件
do_dump() {
  mkdir -p "$LOCAL_BACKUP_DIR"
  local dump_file="${LOCAL_BACKUP_DIR}/close_shot_${TIMESTAMP}.dump"
  echo "[$(date -Iseconds)] pg_dump from container ${DB_CONTAINER_NAME} to $dump_file ..." >&2
  docker exec \
    -e PGPASSWORD="$PGPASSWORD" \
    "$DB_CONTAINER_NAME" \
    pg_dump -U "$PGUSER" -d "$DBNAME" -F c >"$dump_file"
  echo "$dump_file"
}

upload_s3() {
  local dump_file="$1"
  local object_key="${S3_PREFIX}/close_shot_${TIMESTAMP}.dump"
  export AWS_ACCESS_KEY_ID="${S3_ACCESS_KEY_ID:-}"
  export AWS_SECRET_ACCESS_KEY="${S3_SECRET_ACCESS_KEY:-}"
  if [[ -z "$AWS_ACCESS_KEY_ID" || -z "$AWS_SECRET_ACCESS_KEY" ]]; then
    echo "[$(date -Iseconds)] WARN: S3 credentials not set, skip upload" >&2
    return 0
  fi
  if [[ ! -f "$dump_file" ]]; then
    echo "[$(date -Iseconds)] ERROR: dump file not found: $dump_file" >&2
    exit 1
  fi
  echo "[$(date -Iseconds)] Uploading to s3://${S3_BUCKET}/${object_key} ..."
  aws s3 cp "$dump_file" "s3://${S3_BUCKET}/${object_key}" \
    --endpoint-url "${S3_ENDPOINT_URL}" \
    --region "${S3_REGION:-ap-shanghai}" \
    --only-show-errors
  echo "[$(date -Iseconds)] Upload done."
}

clean_local() {
  if [[ ! -d "$LOCAL_BACKUP_DIR" ]]; then return; fi
  echo "[$(date -Iseconds)] Cleaning local backups older than ${KEEP_LOCAL_DAYS} days ..."
  find "$LOCAL_BACKUP_DIR" -name 'close_shot_*.dump' -type f -mtime +"$((KEEP_LOCAL_DAYS - 1))" -delete
}

clean_remote() {
  export AWS_ACCESS_KEY_ID="${S3_ACCESS_KEY_ID:-}"
  export AWS_SECRET_ACCESS_KEY="${S3_SECRET_ACCESS_KEY:-}"
  if [[ -z "$AWS_ACCESS_KEY_ID" ]]; then return; fi
  echo "[$(date -Iseconds)] Cleaning remote backups older than ${KEEP_REMOTE_DAYS} days ..."
  local cutoff
  cutoff=$(date -d "${KEEP_REMOTE_DAYS} days ago" +%Y%m%d 2>/dev/null) || true
  if [[ -z "$cutoff" ]]; then return; fi
  aws s3 ls "s3://${S3_BUCKET}/${S3_PREFIX}/" --recursive --endpoint-url "${S3_ENDPOINT_URL}" --region "${S3_REGION:-ap-shanghai}" 2>/dev/null | while read -r _ _ _ key; do
    [[ -z "$key" ]] && continue
    local basename="${key##*/}"
    local date_part="${basename#close_shot_}"
    date_part="${date_part%%_*}"
    if [[ "$basename" == close_shot_*.dump && "$date_part" < "$cutoff" ]]; then
      echo "[$(date -Iseconds)] Deleting s3://${S3_BUCKET}/${key}"
      aws s3 rm "s3://${S3_BUCKET}/${key}" --endpoint-url "${S3_ENDPOINT_URL}" --region "${S3_REGION:-ap-shanghai}" 2>/dev/null || true
    fi
  done
}

main() {
  mkdir -p "$LOG_DIR"
  local log_file="${LOG_DIR}/pg-backup.log"
  {
    check_commands
    load_env
    parse_db_url
    check_db_container
    dump_file=$(do_dump)
    [[ -f "$dump_file" ]] || { echo "[$(date -Iseconds)] ERROR: dump file not created" >&2; exit 1; }
    upload_s3 "$dump_file"
    clean_local
    clean_remote
    echo "[$(date -Iseconds)] Backup finished: $dump_file"
  } 2>&1 | tee -a "$log_file"
}

main "$@"
