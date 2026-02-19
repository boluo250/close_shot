from __future__ import annotations

from datetime import datetime, timedelta, timezone

import httpx
from fastapi import HTTPException

from app.core.config import settings

_token_cache: dict[str, object] = {"token": None, "expires_at": datetime.min.replace(tzinfo=timezone.utc)}


def _is_enabled() -> bool:
    return bool(settings.wechat_appid and settings.wechat_secret)


def _require_wechat_config() -> None:
    if _is_enabled():
        return
    # 开发/测试环境允许跳过（避免本地必须配置微信密钥）
    if (settings.env or "").lower() not in ("prod", "production"):
        return
    if not settings.wechat_appid or not settings.wechat_secret:
        raise HTTPException(status_code=500, detail="wechat security config missing")


def _get_access_token() -> str:
    _require_wechat_config()
    if not _is_enabled():
        raise HTTPException(status_code=500, detail="wechat security config missing")
    now = datetime.now(timezone.utc)
    token = _token_cache.get("token")
    expires_at = _token_cache.get("expires_at")
    if isinstance(token, str) and isinstance(expires_at, datetime) and now < expires_at:
        return token

    url = "https://api.weixin.qq.com/cgi-bin/token"
    params = {"grant_type": "client_credential", "appid": settings.wechat_appid, "secret": settings.wechat_secret}
    resp = httpx.get(url, params=params, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    if data.get("errcode"):
        raise HTTPException(status_code=500, detail=f"wechat token error: {data}")
    token = data.get("access_token")
    expires_in = int(data.get("expires_in", 7200))
    if not token:
        raise HTTPException(status_code=500, detail="wechat token missing")
    _token_cache["token"] = token
    _token_cache["expires_at"] = now + timedelta(seconds=max(0, expires_in - 120))
    return token


def ensure_text_safe(text: str) -> None:
    if not text or not text.strip():
        return
    _require_wechat_config()
    if not _is_enabled():
        return
    token = _get_access_token()
    url = f"https://api.weixin.qq.com/wxa/msg_sec_check?access_token={token}"
    payload = {"content": text.strip(), "version": 2, "scene": 2}
    resp = httpx.post(url, json=payload, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    if data.get("errcode"):
        raise HTTPException(status_code=400, detail="content security check failed")
    result = data.get("result") or {}
    suggest = result.get("suggest")
    if suggest in ("risky", "block", "review"):
        raise HTTPException(status_code=400, detail="content security check failed")


def ensure_image_safe_bytes(image_bytes: bytes) -> None:
    _require_wechat_config()
    if not _is_enabled():
        return
    token = _get_access_token()
    url = f"https://api.weixin.qq.com/wxa/img_sec_check?access_token={token}"
    files = {"media": ("image.jpg", image_bytes, "image/jpeg")}
    resp = httpx.post(url, files=files, timeout=20)
    resp.raise_for_status()
    data = resp.json()
    if data.get("errcode"):
        raise HTTPException(status_code=400, detail="content security check failed")
