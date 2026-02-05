from __future__ import annotations

from datetime import datetime, timedelta, timezone

from jose import jwt
from passlib.context import CryptContext

from app.core.config import settings

# NOTE:
# 早期开发环境中，passlib + bcrypt 版本组合在 macOS 上容易出现兼容性问题（seed/login 会直接 500）。
# 这里改用纯 Python 的 pbkdf2_sha256，避免对 bcrypt 本地扩展的依赖。
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)


def create_access_token(*, subject: str, expires_minutes: int | None = None) -> str:
    expires = timedelta(minutes=expires_minutes or settings.jwt_expires_minutes)
    exp = datetime.now(timezone.utc) + expires
    payload = {"sub": subject, "exp": exp}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_alg)

