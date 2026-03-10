#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
COMPOSE_FILE="${SCRIPT_DIR}/docker-compose.deploy.yml"
BACKEND_ENV_EXAMPLE="${REPO_ROOT}/backend/.env.example"
BACKEND_ENV="${REPO_ROOT}/backend/.env"
INFRA_ENV="${SCRIPT_DIR}/.env"

DOMAIN="${DOMAIN:-bianpai.xyz}"
EMAIL="${EMAIL:-}"
CERT_DIR="${CERT_DIR:-}"

command="${1:-init}"
if [[ $# -gt 0 ]]; then
  shift
fi

while [[ $# -gt 0 ]]; do
  case "$1" in
    --domain)
      DOMAIN="$2"
      shift 2
      ;;
    --email)
      EMAIL="$2"
      shift 2
      ;;
    --cert-dir)
      CERT_DIR="$2"
      shift 2
      ;;
    *)
      echo "Unknown arg: $1"
      exit 1
      ;;
  esac
done

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing command: $1"
    exit 1
  fi
}

gen_secret() {
  if command -v openssl >/dev/null 2>&1; then
    openssl rand -hex 24
  else
    date +%s%N | shasum | awk '{print $1}' | cut -c1-48
  fi
}

upsert_env() {
  local file="$1"
  local key="$2"
  local value="$3"
  if [[ -f "$file" ]] && grep -qE "^${key}=" "$file"; then
    sed -i.bak "s|^${key}=.*|${key}=${value}|" "$file"
    rm -f "${file}.bak"
  else
    echo "${key}=${value}" >>"$file"
  fi
}

read_env_value() {
  local file="$1"
  local key="$2"
  if [[ ! -f "$file" ]]; then
    echo ""
    return
  fi
  local value
  value="$(grep -E "^${key}=" "$file" | tail -n 1 | cut -d'=' -f2- || true)"
  echo "$value"
}

ensure_backend_env() {
  if [[ ! -f "$BACKEND_ENV" ]]; then
    cp "$BACKEND_ENV_EXAMPLE" "$BACKEND_ENV"
  fi

  upsert_env "$BACKEND_ENV" "ENV" "prod"
  upsert_env "$BACKEND_ENV" "STORAGE_BACKEND" "s3"
  local s3_region
  s3_region="$(read_env_value "$BACKEND_ENV" "S3_REGION")"
  if [[ -z "$s3_region" || "$s3_region" == "us-east-1" ]]; then
    s3_region="ap-shanghai"
    upsert_env "$BACKEND_ENV" "S3_REGION" "$s3_region"
  fi

  local s3_endpoint_url
  s3_endpoint_url="$(read_env_value "$BACKEND_ENV" "S3_ENDPOINT_URL")"
  if [[ -z "$s3_endpoint_url" || "$s3_endpoint_url" == "http://localhost:9000" || "$s3_endpoint_url" == "http://minio:9000" ]]; then
    upsert_env "$BACKEND_ENV" "S3_ENDPOINT_URL" "https://cos.${s3_region}.myqcloud.com"
  fi

  local jwt_secret
  jwt_secret="$(read_env_value "$BACKEND_ENV" "JWT_SECRET")"
  if [[ -z "$jwt_secret" || "$jwt_secret" == "change-me" || ${#jwt_secret} -lt 24 ]]; then
    upsert_env "$BACKEND_ENV" "JWT_SECRET" "$(gen_secret)"
  fi

  local callback_secret
  callback_secret="$(read_env_value "$BACKEND_ENV" "MEMBERSHIP_CALLBACK_SECRET")"
  if [[ -z "$callback_secret" || "$callback_secret" == "dev-membership-callback" || ${#callback_secret} -lt 24 ]]; then
    upsert_env "$BACKEND_ENV" "MEMBERSHIP_CALLBACK_SECRET" "$(gen_secret)"
  fi

  local s3_access_key
  s3_access_key="$(read_env_value "$BACKEND_ENV" "S3_ACCESS_KEY_ID")"
  if [[ -z "$s3_access_key" || "$s3_access_key" == "minioadmin" ]]; then
    upsert_env "$BACKEND_ENV" "S3_ACCESS_KEY_ID" "your-secret-id"
  fi

  local s3_secret_key
  s3_secret_key="$(read_env_value "$BACKEND_ENV" "S3_SECRET_ACCESS_KEY")"
  if [[ -z "$s3_secret_key" || "$s3_secret_key" == "minioadmin" ]]; then
    upsert_env "$BACKEND_ENV" "S3_SECRET_ACCESS_KEY" "your-secret-key"
  fi

  local s3_bucket
  s3_bucket="$(read_env_value "$BACKEND_ENV" "S3_BUCKET")"
  if [[ -z "$s3_bucket" || "$s3_bucket" == "close-shot" ]]; then
    upsert_env "$BACKEND_ENV" "S3_BUCKET" "your-bucket-appid"
    s3_bucket="your-bucket-appid"
  fi

  local s3_public_base_url
  s3_public_base_url="$(read_env_value "$BACKEND_ENV" "S3_PUBLIC_BASE_URL")"
  if [[ -z "$s3_public_base_url" || "$s3_public_base_url" == "http://localhost:9000/close-shot" || "$s3_public_base_url" == "https://${DOMAIN}" ]]; then
    upsert_env "$BACKEND_ENV" "S3_PUBLIC_BASE_URL" "https://${s3_bucket}.cos.${s3_region}.myqcloud.com"
  fi
}

ensure_infra_env() {
  touch "$INFRA_ENV"
  upsert_env "$INFRA_ENV" "DOMAIN" "$DOMAIN"
  upsert_env "$INFRA_ENV" "NGINX_HTTP_PORT" "80"
  upsert_env "$INFRA_ENV" "NGINX_HTTPS_PORT" "443"
}

require_email_for_init() {
  if [[ -z "$EMAIL" ]]; then
    cat <<EOF
EMAIL is required for Let's Encrypt.
Example:
  ./infra/deploy.sh init --email you@example.com
EOF
    exit 1
  fi
}

require_cert_dir_for_local_init() {
  if [[ -z "$CERT_DIR" ]]; then
    cat <<EOF
CERT_DIR is required for local certificate deploy.
Example:
  ./infra/deploy.sh init-local-cert --domain bianpai.xyz --cert-dir ./infra/certs
EOF
    exit 1
  fi
  if [[ ! -d "$CERT_DIR" ]]; then
    echo "CERT_DIR not found: $CERT_DIR"
    exit 1
  fi
}

compose() {
  docker compose -f "$COMPOSE_FILE" "$@"
}

issue_certificate() {
  echo "Requesting Let's Encrypt certificate for ${DOMAIN} ..."
  compose down || true
  compose --profile ops run --rm certbot certonly \
    --standalone \
    -d "$DOMAIN" \
    --agree-tos \
    --email "$EMAIL" \
    --no-eff-email \
    --non-interactive
}

resolve_local_cert_files() {
  local key_file=""
  local cert_file=""
  local cert_dir_abs
  cert_dir_abs="$(cd "$CERT_DIR" && pwd)"

  local key_candidates=(
    "${cert_dir_abs}/${DOMAIN}.key"
    "${cert_dir_abs}/${DOMAIN}_bundle.key"
  )
  local cert_candidates=(
    "${cert_dir_abs}/${DOMAIN}_bundle.pem"
    "${cert_dir_abs}/${DOMAIN}_bundle.crt"
    "${cert_dir_abs}/${DOMAIN}.pem"
    "${cert_dir_abs}/${DOMAIN}.crt"
    "${cert_dir_abs}/fullchain.pem"
    "${cert_dir_abs}/fullchain.crt"
  )

  for file in "${key_candidates[@]}"; do
    if [[ -f "$file" ]]; then
      key_file="$file"
      break
    fi
  done
  if [[ -z "$key_file" ]]; then
    for file in "${cert_dir_abs}"/*.key; do
      if [[ -f "$file" ]]; then
        key_file="$file"
        break
      fi
    done
  fi

  for file in "${cert_candidates[@]}"; do
    if [[ -f "$file" ]]; then
      cert_file="$file"
      break
    fi
  done
  if [[ -z "$cert_file" ]]; then
    for file in "${cert_dir_abs}"/*.pem "${cert_dir_abs}"/*.crt; do
      if [[ -f "$file" ]]; then
        cert_file="$file"
        break
      fi
    done
  fi

  if [[ -z "$key_file" ]]; then
    echo "No private key found in $CERT_DIR. Expected *.key"
    exit 1
  fi
  if [[ -z "$cert_file" ]]; then
    echo "No certificate chain found in $CERT_DIR. Expected *.pem or *.crt"
    exit 1
  fi

  LOCAL_CERT_KEY="$key_file"
  LOCAL_CERT_CHAIN="$cert_file"
}

install_local_certificate() {
  resolve_local_cert_files
  local cert_dir_abs
  cert_dir_abs="$(cd "$CERT_DIR" && pwd)"
  local key_name
  local cert_name
  key_name="$(basename "$LOCAL_CERT_KEY")"
  cert_name="$(basename "$LOCAL_CERT_CHAIN")"

  echo "Installing local certificate from ${cert_dir_abs} ..."
  echo "  cert: ${cert_name}"
  echo "  key : ${key_name}"

  compose --profile ops run --rm \
    -v "${cert_dir_abs}:/tmp/custom-cert:ro" \
    --entrypoint sh certbot -c "
      set -eu
      mkdir -p /etc/letsencrypt/live/${DOMAIN}
      cp /tmp/custom-cert/${cert_name} /etc/letsencrypt/live/${DOMAIN}/fullchain.pem
      cp /tmp/custom-cert/${key_name} /etc/letsencrypt/live/${DOMAIN}/privkey.pem
      chmod 600 /etc/letsencrypt/live/${DOMAIN}/privkey.pem
    "
}

init() {
  require_cmd docker
  require_email_for_init
  ensure_backend_env
  ensure_infra_env
  issue_certificate
  compose up -d --build
  echo ""
  echo "Deploy complete."
  echo "Check URLs:"
  echo "  https://${DOMAIN}/health"
  echo "  https://${DOMAIN}/docs"
  echo "  https://${DOMAIN}/ops-x8r7m2q4p9/login"
}

init_local_cert() {
  require_cmd docker
  require_cert_dir_for_local_init
  ensure_backend_env
  ensure_infra_env
  install_local_certificate
  compose up -d --build
  echo ""
  echo "Deploy complete (local cert)."
  echo "Check URLs:"
  echo "  https://${DOMAIN}/health"
  echo "  https://${DOMAIN}/docs"
  echo "  https://${DOMAIN}/ops-x8r7m2q4p9/login"
}

update() {
  require_cmd git
  require_cmd docker
  ensure_infra_env
  git -C "$REPO_ROOT" pull --ff-only
  compose up -d --build
}

renew() {
  require_cmd docker
  ensure_infra_env
  compose --profile ops run --rm certbot renew --non-interactive --quiet
  compose exec nginx nginx -s reload || true
}

status() {
  require_cmd docker
  ensure_infra_env
  compose ps
}

down() {
  require_cmd docker
  ensure_infra_env
  compose down
}

restart() {
  require_cmd docker
  ensure_infra_env
  compose restart
}

# 在 Ubuntu 宿主机安装定时备份依赖：postgresql-client, awscli（供 pg-backup.sh 使用）
install_backup_deps() {
  if command -v apt-get >/dev/null 2>&1; then
    echo "Installing backup deps (postgresql-client, awscli) ..."
    sudo apt-get update
    sudo apt-get install -y postgresql-client awscli
    echo "Done. Configure cron for daily backup: see backend/scripts/README-BACKUP.md"
  else
    echo "apt-get not found. On Ubuntu run: sudo apt-get install -y postgresql-client awscli"
    exit 1
  fi
}

case "$command" in
  init)
    init
    ;;
  init-local-cert)
    init_local_cert
    ;;
  update)
    update
    ;;
  renew)
    renew
    ;;
  status)
    status
    ;;
  down)
    down
    ;;
  restart)
    restart
    ;;
  install-backup-deps)
    install_backup_deps
    ;;
  *)
    cat <<EOF
Usage:
  ./infra/deploy.sh init --email you@example.com [--domain bianpai.xyz]
  ./infra/deploy.sh init-local-cert --cert-dir ./infra/certs [--domain bianpai.xyz]
  ./infra/deploy.sh update [--domain bianpai.xyz]
  ./infra/deploy.sh renew [--domain bianpai.xyz]
  ./infra/deploy.sh status [--domain bianpai.xyz]
  ./infra/deploy.sh restart [--domain bianpai.xyz]
  ./infra/deploy.sh down [--domain bianpai.xyz]
  ./infra/deploy.sh install-backup-deps   # 安装 pg_dump + awscli（Ubuntu，用于定时备份）
EOF
    exit 1
    ;;
esac
