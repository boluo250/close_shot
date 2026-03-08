from __future__ import annotations

import ipaddress
import socket
from io import BytesIO
from urllib.parse import urljoin, urlparse

import httpx
from fastapi import APIRouter, HTTPException
from PIL import Image, ImageDraw, ImageOps
from starlette.responses import StreamingResponse

from app.core.config import settings
from app.services.storage import get_object_stream

router = APIRouter()


try:
    _LANCZOS = Image.Resampling.LANCZOS
except AttributeError:
    _LANCZOS = Image.LANCZOS

_MAX_REDIRECTS = 2


def _split_csv(raw: str) -> set[str]:
    return {x.strip().lower() for x in (raw or "").split(",") if x.strip()}


def _is_allowed_avatar_host(hostname: str) -> bool:
    host = (hostname or "").strip().lower()
    if not host:
        return False
    allowed = _split_csv(settings.media_avatar_allowed_hosts)
    return any(host == item or host.endswith(f".{item}") for item in allowed)


def _is_blocked_ip(ip_text: str) -> bool:
    ip = ipaddress.ip_address(ip_text)
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


def _assert_public_resolved_host(hostname: str) -> None:
    try:
        resolved = socket.getaddrinfo(hostname, None)
    except socket.gaierror as exc:
        raise HTTPException(status_code=400, detail="invalid avatar host") from exc
    for item in resolved:
        addr = item[4][0]
        if _is_blocked_ip(addr):
            raise HTTPException(status_code=400, detail="avatar host is not public")


def _validate_avatar_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise HTTPException(status_code=400, detail="invalid avatar url")
    if parsed.username or parsed.password:
        raise HTTPException(status_code=400, detail="invalid avatar url")
    host = parsed.hostname or ""
    if not _is_allowed_avatar_host(host):
        raise HTTPException(status_code=400, detail="avatar host is not allowed")
    _assert_public_resolved_host(host)
    return url


def _fetch_avatar_bytes(url: str) -> tuple[bytes, str]:
    current = _validate_avatar_url(url)
    with httpx.Client(timeout=8.0, follow_redirects=False) as client:
        for _ in range(_MAX_REDIRECTS + 1):
            try:
                resp = client.get(current)
            except Exception as exc:
                raise HTTPException(status_code=502, detail="fetch avatar failed") from exc
            if resp.status_code in {301, 302, 303, 307, 308}:
                location = resp.headers.get("location")
                if not location:
                    raise HTTPException(status_code=502, detail="fetch avatar failed")
                current = _validate_avatar_url(urljoin(current, location))
                continue
            if resp.status_code >= 400:
                raise HTTPException(status_code=502, detail="fetch avatar failed")
            content_type = (resp.headers.get("content-type") or "").split(";")[0].strip().lower()
            if not content_type.startswith("image/"):
                raise HTTPException(status_code=400, detail="avatar is not image")
            return resp.content, content_type
    raise HTTPException(status_code=502, detail="too many redirects")


def _render_map_avatar_marker(
    image_bytes: bytes, output_size: int = 144, border_px: int = 8, supersample: int = 4
) -> bytes:
    """
    将任意头像渲染为地图点位图：圆形头像 + 细白边。
    输出透明背景 PNG，供小程序 map marker 直接使用。
    """
    with Image.open(BytesIO(image_bytes)) as source:
        source = ImageOps.exif_transpose(source).convert("RGBA")
        target_size = max(48, int(output_size))
        ss = max(2, int(supersample))
        work_size = target_size * ss
        work_border = max(1, int(border_px) * ss)
        inner_size = max(1, work_size - work_border * 2)

        # 先在高分辨率下合成，再缩小，可显著降低圆边锯齿与头像模糊感。
        avatar = ImageOps.fit(source, (inner_size, inner_size), method=_LANCZOS)

        avatar_mask = Image.new("L", (inner_size, inner_size), 0)
        avatar_draw = ImageDraw.Draw(avatar_mask)
        avatar_draw.ellipse((0, 0, inner_size - 1, inner_size - 1), fill=255)

        canvas = Image.new("RGBA", (work_size, work_size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(canvas)
        draw.ellipse((0, 0, work_size - 1, work_size - 1), fill=(255, 255, 255, 255))
        canvas.paste(avatar, (work_border, work_border), avatar_mask)
        canvas = canvas.resize((target_size, target_size), _LANCZOS)

        out = BytesIO()
        canvas.save(out, format="PNG")
        return out.getvalue()


@router.get("/styled/avatar")
def get_styled_avatar(url: str, style: str | None = "map_avatar"):
    """
    外链头像样式代理：后端拉取远程图片后按地图样式渲染，避免小程序端直接处理。
    """
    raw, content_type = _fetch_avatar_bytes(url)
    headers = {"Cache-Control": "public, max-age=86400"}
    if style == "map_avatar":
        try:
            marker_png = _render_map_avatar_marker(raw)
            return StreamingResponse(BytesIO(marker_png), media_type="image/png", headers=headers)
        except Exception:
            return StreamingResponse(BytesIO(raw), media_type=content_type or "application/octet-stream", headers=headers)
    return StreamingResponse(BytesIO(raw), media_type=content_type or "application/octet-stream", headers=headers)


@router.get("/{object_key:path}")
def get_media(object_key: str, style: str | None = None):
    """
    通过后端域名访问对象存储文件（给小程序/前端一个统一可白名单的域名）。
    支持 s3 或 local。
    """
    try:
        stream, content_type = get_object_stream(object_key)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="not found")

    headers = {
        # 图片资源默认允许客户端与 CDN 缓存，减轻重复访问延迟
        "Cache-Control": "public, max-age=604800, immutable"
    }
    if style == "map_avatar":
        raw = stream.read()
        try:
            marker_png = _render_map_avatar_marker(raw)
            return StreamingResponse(BytesIO(marker_png), media_type="image/png", headers=headers)
        except Exception:
            # 转换失败时退回原图，避免影响线上可用性。
            return StreamingResponse(
                BytesIO(raw), media_type=content_type or "application/octet-stream", headers=headers
            )
    return StreamingResponse(stream, media_type=content_type or "application/octet-stream", headers=headers)

