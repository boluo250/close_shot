from __future__ import annotations

from urllib.parse import urlparse

from app.core.config import settings


def _public_base_url() -> str | None:
    public_base = (settings.s3_public_base_url or "").strip()
    if not public_base or "your-bucket-appid" in public_base:
        return None
    return public_base.rstrip("/")


def object_key_to_url(object_key: str | None) -> str | None:
    if not object_key:
        return None
    object_key = object_key.lstrip("/")
    if settings.storage_backend == "local":
        return f"/media/{object_key}"
    public_base = _public_base_url()
    if public_base:
        return f"{public_base}/{object_key}"
    return f"/media/{object_key}"


def object_key_from_url(url: str | None) -> str | None:
    if not url:
        return None
    raw = url.strip()
    if not raw:
        return None
    if raw.startswith("/media/"):
        return raw.replace("/media/", "", 1)
    if "/media/" in raw:
        return raw.split("/media/", 1)[1]

    public_base = _public_base_url()
    if public_base and raw.startswith(public_base + "/"):
        return raw[len(public_base + "/") :]

    parsed = urlparse(raw)
    if not parsed.scheme or not parsed.netloc:
        return None
    path = parsed.path.lstrip("/")
    if not path:
        return None

    cos_host = None
    if settings.s3_bucket and settings.s3_region:
        cos_host = f"{settings.s3_bucket}.cos.{settings.s3_region}.myqcloud.com"
    if cos_host and parsed.netloc == cos_host:
        return path
    return None
