from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone

import httpx
from fastapi import HTTPException

from app.core.config import settings

_token_cache: dict[str, object] = {"token": None, "expires_at": datetime.min.replace(tzinfo=timezone.utc)}


def _is_enabled() -> bool:
    appid = (settings.wechat_appid or "").strip()
    secret = (settings.wechat_secret or "").strip()
    if not appid or not secret:
        return False
    # 占位符配置不视为有效配置
    if appid.startswith("你的小程序") or secret.startswith("你的小程序"):
        return False
    return True


def _build_mock_login_identity(code: str) -> dict[str, str]:
    digest = hashlib.sha256(code.encode("utf-8")).hexdigest()
    return {
        "openid": f"mock_{digest[:32]}",
        "unionid": f"mocku_{digest[:32]}",
        "session_key": f"mocksk_{digest[:32]}",
    }


def _require_wechat_config(*, strict: bool = False) -> None:
    if _is_enabled():
        return
    if not strict and (settings.env or "").lower() not in ("prod", "production"):
        return
    if not settings.wechat_appid or not settings.wechat_secret:
        raise HTTPException(status_code=500, detail="missing WECHAT_APPID/WECHAT_SECRET")


def _get_access_token() -> str:
    _require_wechat_config()
    if not _is_enabled():
        raise HTTPException(status_code=500, detail="missing WECHAT_APPID/WECHAT_SECRET")
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


def exchange_login_code(code: str) -> dict[str, str]:
    """使用小程序 wx.login code 交换 openid/unionid/session_key。"""
    env = (settings.env or "").lower()
    if env not in ("prod", "production") and (settings.wechat_login_allow_mock or not _is_enabled()):
        return _build_mock_login_identity(code)
    _require_wechat_config(strict=True)
    url = "https://api.weixin.qq.com/sns/jscode2session"
    params = {
        "appid": settings.wechat_appid,
        "secret": settings.wechat_secret,
        "js_code": code,
        "grant_type": "authorization_code",
    }
    try:
        resp = httpx.get(url, params=params, timeout=10)
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="wechat login request failed") from exc

    data = resp.json()
    if data.get("errcode"):
        raise HTTPException(status_code=400, detail=f"wechat login failed: {data.get('errmsg', 'unknown')}")

    openid = data.get("openid")
    session_key = data.get("session_key")
    if not openid or not session_key:
        raise HTTPException(status_code=400, detail="wechat login response missing openid/session_key")

    result = {"openid": openid, "session_key": session_key}
    unionid = data.get("unionid")
    if unionid:
        result["unionid"] = unionid
    return result


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
