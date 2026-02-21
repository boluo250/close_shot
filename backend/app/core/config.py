from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "close-shot-api"
    env: str = "dev"

    database_url: str

    jwt_secret: str = "change-me"
    jwt_alg: str = "HS256"
    jwt_expires_minutes: int = 60 * 24 * 7

    # 开发默认使用 local，避免本地必须起 MinIO；生产用环境变量改回 s3/COS
    storage_backend: str = "local"  # s3|local
    s3_endpoint_url: str | None = None
    s3_access_key_id: str | None = None
    s3_secret_access_key: str | None = None
    s3_bucket: str | None = None
    s3_region: str | None = None
    s3_public_base_url: str | None = None

    wechat_appid: str | None = None
    wechat_secret: str | None = None
    wechat_login_allow_mock: bool = False


settings = Settings()  # type: ignore[call-arg]

