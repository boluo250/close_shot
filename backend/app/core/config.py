from __future__ import annotations

import os
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, env_file_encoding="utf-8", extra="ignore")

    app_name: str = "close-shot-api"
    env: str = "dev"

    database_url: str

    jwt_secret: str = "change-me"
    jwt_alg: str = "HS256"
    jwt_expires_minutes: int = 60 * 24 * 7
    # 管理端安全配置：使用复杂路径，避免默认 /admin 被直接扫描
    admin_api_prefix: str = "/admin-x8r7m2q4p9"
    admin_min_password_length: int = 12

    # 开发默认使用 local，避免本地必须起 MinIO；生产用环境变量改回 s3/COS
    storage_backend: str = "local"  # s3|local
    s3_endpoint_url: str | None = None
    s3_access_key_id: str | None = None
    s3_secret_access_key: str | None = None
    s3_bucket: str | None = None
    s3_region: str | None = None
    s3_public_base_url: str | None = None
    storage_soft_delete_enabled: bool = True
    storage_soft_delete_prefix: str = "_recycle_bin"

    wechat_appid: str | None = None
    wechat_secret: str | None = None
    wechat_login_allow_mock: bool = False
    wechat_mock_openid_seed: str = "local-dev"
    membership_callback_secret: str = "dev-membership-callback"
    upload_max_bytes: int = 10 * 1024 * 1024
    upload_allowed_prefixes: str = "avatar,portfolio,watermark,uploads"
    upload_allowed_content_types: str = "image/jpeg,image/png,image/webp,image/heic,image/heif"
    media_avatar_allowed_hosts: str = "wx.qlogo.cn,thirdwx.qlogo.cn,mmbiz.qpic.cn"
    analytics_report_timezone: str = "Asia/Shanghai"
    analytics_daily_report_webhook_url: str | None = None
    analytics_daily_report_webhook_secret: str | None = None

    monitor_docker_socket: str | None = "/var/run/docker.sock"
    monitor_container_names: str = "close-shot-api,close-shot-db,close-shot-admin-web,close-shot-nginx"
    monitor_disk_paths: str = "/,/app/local_media"
    monitor_disk_warn_percent: float = 80.0
    monitor_disk_critical_percent: float = 90.0
    monitor_cpu_warn_percent: float = 70.0
    monitor_cpu_critical_percent: float = 90.0
    monitor_memory_warn_percent: float = 80.0
    monitor_memory_critical_percent: float = 90.0
    monitor_db_size_warn_bytes: int = 5 * 1024 * 1024 * 1024
    monitor_db_size_critical_bytes: int = 10 * 1024 * 1024 * 1024
    monitor_5xx_window_minutes: int = 15
    monitor_5xx_warn_count: int = 3
    monitor_5xx_critical_count: int = 10
    monitor_backup_max_age_hours: int = 30
    monitor_container_restart_recent_minutes: int = 24 * 60
    monitor_report_secret: str | None = None

    @property
    def env_lower(self) -> str:
        return (self.env or "").strip().lower()

    @property
    def is_dev(self) -> bool:
        return self.env_lower in {"dev", "develop", "development", "local"}

    @property
    def is_prod(self) -> bool:
        return self.env_lower in {"prod", "production"}

    def ensure_runtime_safety(self) -> None:
        if not self.is_prod:
            return
        if self.jwt_secret in {"", "change-me"}:
            raise RuntimeError("unsafe JWT_SECRET in production")
        if len(self.jwt_secret) < 24:
            raise RuntimeError("JWT_SECRET is too short in production")
        if self.membership_callback_secret in {"", "dev-membership-callback"}:
            raise RuntimeError("unsafe MEMBERSHIP_CALLBACK_SECRET in production")
        if len(self.membership_callback_secret) < 24:
            raise RuntimeError("MEMBERSHIP_CALLBACK_SECRET is too short in production")
        if self.storage_backend == "s3":
            missing = []
            if not self.s3_access_key_id:
                missing.append("S3_ACCESS_KEY_ID")
            if not self.s3_secret_access_key:
                missing.append("S3_SECRET_ACCESS_KEY")
            if not self.s3_bucket:
                missing.append("S3_BUCKET")
            if missing:
                raise RuntimeError(f"missing required S3 config in production: {', '.join(missing)}")


def _resolve_env_file() -> str:
    """
    环境变量加载优先级：
    1) 显式 ENV_FILE（推荐部署时指定）
    2) 开发环境默认 .env.develop（存在时）
    3) 默认 .env
    """
    explicit = (os.environ.get("ENV_FILE") or "").strip()
    if explicit:
        return explicit

    env_name = (os.environ.get("ENV") or "").strip().lower()
    if env_name in {"dev", "develop", "development", "local"} and Path(".env.develop").exists():
        return ".env.develop"
    return ".env"


settings = Settings(_env_file=_resolve_env_file())  # type: ignore[call-arg]
