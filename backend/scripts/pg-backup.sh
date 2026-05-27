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
DOCKER_BIN="${DOCKER_BIN:-docker}"
DOCKER_USE_SUDO="${DOCKER_USE_SUDO:-0}"
S3_PREFIX="${S3_PREFIX:-pg-backup}"
KEEP_LOCAL_DAYS="${KEEP_LOCAL_DAYS:-3}"
KEEP_REMOTE_DAYS="${KEEP_REMOTE_DAYS:-14}"
LOG_DIR="${LOG_DIR:-${BACKEND_DIR}/.backups/logs}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
AWS_CONFIG_TMP_FILE=""
MONITOR_REPORT_URL="${MONITOR_REPORT_URL:-http://127.0.0.1/ops/monitor/backup-report}"
MONITOR_JOB_NAME="${MONITOR_JOB_NAME:-pg-backup}"
BACKUP_STARTED_AT="$(date -Iseconds)"
BACKUP_STARTED_EPOCH="$(date +%s)"
BACKUP_FINISHED_AT=""
BACKUP_DURATION_SECONDS=""
BACKUP_SUCCESS="0"
LAST_RESULT_MESSAGE=""
LAST_DUMP_FILE=""
LAST_REMOTE_OBJECT_KEY=""
UPLOAD_SKIPPED="0"

docker_cmd() {
  if [[ "$DOCKER_USE_SUDO" == "1" ]]; then
    sudo "$DOCKER_BIN" "$@"
  else
    "$DOCKER_BIN" "$@"
  fi
}

cleanup() {
  local exit_code=$?
  trap - EXIT
  BACKUP_FINISHED_AT="$(date -Iseconds)"
  BACKUP_DURATION_SECONDS="$(( $(date +%s) - BACKUP_STARTED_EPOCH ))"
  if [[ "$exit_code" == "0" ]]; then
    BACKUP_SUCCESS="1"
    if [[ -z "$LAST_RESULT_MESSAGE" ]]; then
      if [[ "$UPLOAD_SKIPPED" == "1" ]]; then
        LAST_RESULT_MESSAGE="备份完成，但未上传对象存储（缺少 S3 凭证）"
      else
        LAST_RESULT_MESSAGE="备份完成并已上报"
      fi
    fi
  elif [[ -z "$LAST_RESULT_MESSAGE" ]]; then
    LAST_RESULT_MESSAGE="备份任务失败，请检查 pg-backup.log"
  fi
  report_status || true
  if [[ -n "$AWS_CONFIG_TMP_FILE" && -f "$AWS_CONFIG_TMP_FILE" ]]; then
    rm -f "$AWS_CONFIG_TMP_FILE"
  fi
  exit "$exit_code"
}

trap cleanup EXIT

report_status() {
  local secret="${MONITOR_REPORT_SECRET:-}"
  if [[ -z "$MONITOR_REPORT_URL" || -z "$secret" ]]; then
    return 0
  fi
  if ! command -v curl >/dev/null 2>&1; then
    echo "[$(date -Iseconds)] WARN: curl not found, skip monitor report" >&2
    return 0
  fi

  curl -fsS -m 10 -X POST \
    -H "X-Monitor-Secret: ${secret}" \
    -H "Content-Type: application/x-www-form-urlencoded" \
    --data-urlencode "job_name=${MONITOR_JOB_NAME}" \
    --data-urlencode "success=${BACKUP_SUCCESS}" \
    --data-urlencode "message=${LAST_RESULT_MESSAGE}" \
    --data-urlencode "started_at=${BACKUP_STARTED_AT}" \
    --data-urlencode "finished_at=${BACKUP_FINISHED_AT}" \
    --data-urlencode "duration_seconds=${BACKUP_DURATION_SECONDS}" \
    --data-urlencode "dump_file=${LAST_DUMP_FILE}" \
    --data-urlencode "remote_object_key=${LAST_REMOTE_OBJECT_KEY}" \
    "${MONITOR_REPORT_URL}" >/dev/null || {
      echo "[$(date -Iseconds)] WARN: failed to report backup status to monitor endpoint" >&2
      return 0
    }
}

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
  command -v "$DOCKER_BIN" >/dev/null 2>&1 || missing+=("$DOCKER_BIN")
  command -v aws >/dev/null 2>&1 || missing+=(aws)
  command -v mktemp >/dev/null 2>&1 || missing+=(mktemp)
  if [[ ${#missing[@]} -gt 0 ]]; then
    echo "[$(date -Iseconds)] ERROR: missing commands: ${missing[*]}. Install: docker, awscli" >&2
    exit 1
  fi
}

check_db_container() {
  local inspect_output
  if ! inspect_output="$(docker_cmd inspect "$DB_CONTAINER_NAME" 2>&1)"; then
    if grep -qi "permission denied" <<<"$inspect_output"; then
      echo "[$(date -Iseconds)] ERROR: cannot access Docker daemon. Current user lacks permission; use root crontab, add the user to the docker group, or rerun with DOCKER_USE_SUDO=1." >&2
      exit 1
    fi
    echo "[$(date -Iseconds)] ERROR: DB container not found: $DB_CONTAINER_NAME" >&2
    exit 1
  fi
  local running
  running="$(docker_cmd inspect -f '{{.State.Running}}' "$DB_CONTAINER_NAME" 2>/dev/null || true)"
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
  docker_cmd exec \
    -e PGPASSWORD="$PGPASSWORD" \
    "$DB_CONTAINER_NAME" \
    pg_dump -U "$PGUSER" -d "$DBNAME" -F c >"$dump_file"
  LAST_DUMP_FILE="$dump_file"
  echo "$dump_file"
}

setup_aws_cli_config() {
  AWS_CONFIG_TMP_FILE="$(mktemp)"
  cat >"$AWS_CONFIG_TMP_FILE" <<EOF
[default]
region = ${S3_REGION:-ap-shanghai}
s3 =
  addressing_style = virtual
EOF
}

aws_s3_cmd() {
  AWS_CONFIG_FILE="$AWS_CONFIG_TMP_FILE" aws "$@"
}

upload_s3() {
  local dump_file="$1"
  local object_key="${S3_PREFIX}/close_shot_${TIMESTAMP}.dump"
  export AWS_ACCESS_KEY_ID="${S3_ACCESS_KEY_ID:-}"
  export AWS_SECRET_ACCESS_KEY="${S3_SECRET_ACCESS_KEY:-}"
  if [[ -z "$AWS_ACCESS_KEY_ID" || -z "$AWS_SECRET_ACCESS_KEY" ]]; then
    echo "[$(date -Iseconds)] WARN: S3 credentials not set, skip upload" >&2
    UPLOAD_SKIPPED="1"
    LAST_RESULT_MESSAGE="备份文件已生成，但未上传对象存储（缺少 S3 凭证）"
    return 0
  fi
  if [[ ! -f "$dump_file" ]]; then
    echo "[$(date -Iseconds)] ERROR: dump file not found: $dump_file" >&2
    LAST_RESULT_MESSAGE="备份文件生成失败，未找到 dump 文件"
    exit 1
  fi
  echo "[$(date -Iseconds)] Uploading to s3://${S3_BUCKET}/${object_key} ..."
  aws_s3_cmd s3 cp "$dump_file" "s3://${S3_BUCKET}/${object_key}" \
    --endpoint-url "${S3_ENDPOINT_URL}" \
    --region "${S3_REGION:-ap-shanghai}" \
    --only-show-errors
  LAST_REMOTE_OBJECT_KEY="$object_key"
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
  aws_s3_cmd s3 ls "s3://${S3_BUCKET}/${S3_PREFIX}/" --recursive --endpoint-url "${S3_ENDPOINT_URL}" --region "${S3_REGION:-ap-shanghai}" 2>/dev/null | while read -r _ _ _ key; do
    [[ -z "$key" ]] && continue
    local basename="${key##*/}"
    local date_part="${basename#close_shot_}"
    date_part="${date_part%%_*}"
    if [[ "$basename" == close_shot_*.dump && "$date_part" < "$cutoff" ]]; then
      echo "[$(date -Iseconds)] Deleting s3://${S3_BUCKET}/${key}"
      aws_s3_cmd s3 rm "s3://${S3_BUCKET}/${key}" --endpoint-url "${S3_ENDPOINT_URL}" --region "${S3_REGION:-ap-shanghai}" 2>/dev/null || true
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
    setup_aws_cli_config
    dump_file=$(do_dump)
    [[ -f "$dump_file" ]] || { echo "[$(date -Iseconds)] ERROR: dump file not created" >&2; exit 1; }
    upload_s3 "$dump_file"
    clean_local
    clean_remote
    if [[ "$UPLOAD_SKIPPED" == "1" ]]; then
      LAST_RESULT_MESSAGE="备份完成，但对象存储上传被跳过"
    else
      LAST_RESULT_MESSAGE="备份完成并上传成功"
    fi
    echo "[$(date -Iseconds)] Backup finished: $dump_file"
  } 2>&1 | tee -a "$log_file"
}

main "$@"
