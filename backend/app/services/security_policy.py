from __future__ import annotations

import re

from fastapi import HTTPException, status

from app.core.config import settings

_WEAK_PASSWORDS = {
    "123456",
    "12345678",
    "password",
    "qwerty",
    "admin123",
    "admin123456",
    "111111",
}
_WEAK_ADMIN_USERNAMES = {"admin", "administrator", "root", "test", "demo"}
_ADMIN_USERNAME_RE = re.compile(r"^(?=.*[A-Za-z])(?=.*\d)[A-Za-z\d_.-]{10,64}$")


def validate_admin_password_strength(password: str) -> None:
    p = (password or "").strip()
    if len(p) < settings.admin_min_password_length:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"管理员密码长度至少 {settings.admin_min_password_length} 位",
        )
    if p.lower() in _WEAK_PASSWORDS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="管理员密码过于简单")
    if not re.search(r"[A-Z]", p):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="管理员密码需包含大写字母")
    if not re.search(r"[a-z]", p):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="管理员密码需包含小写字母")
    if not re.search(r"\d", p):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="管理员密码需包含数字")
    if not re.search(r"[^A-Za-z0-9]", p):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="管理员密码需包含特殊字符")


def validate_admin_username(username: str) -> None:
    u = (username or "").strip()
    if u.lower() in _WEAK_ADMIN_USERNAMES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="管理员账号过于简单，请使用复杂账号")
    if not _ADMIN_USERNAME_RE.fullmatch(u):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="管理员账号需为 10-64 位，且至少包含字母和数字（可含 _.-）",
        )

