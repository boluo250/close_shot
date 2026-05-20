from __future__ import annotations

import mimetypes
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError
from jose import jwt

from app.core.config import settings


def _public_base_url() -> str | None:
    public_base = (settings.s3_public_base_url or "").strip()
    if not public_base or "your-bucket-appid" in public_base:
        return None
    return public_base.rstrip("/")


@dataclass(frozen=True)
class PresignResult:
    method: str
    url: str
    headers: dict[str, str]
    public_url: str | None
    object_key: str


def _s3_client():
    if not settings.s3_access_key_id or not settings.s3_secret_access_key or not settings.s3_bucket:
        raise RuntimeError("S3 config missing (S3_ACCESS_KEY_ID / S3_SECRET_ACCESS_KEY / S3_BUCKET)")

    return boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url,
        aws_access_key_id=settings.s3_access_key_id,
        aws_secret_access_key=settings.s3_secret_access_key,
        region_name=settings.s3_region or "us-east-1",
        config=Config(signature_version="s3v4", s3={"addressing_style": "virtual"}),
    )


def _local_base_dir() -> Path:
    # 存放在 backend/app/../../local_media（仓库内、便于开发）
    return Path(__file__).resolve().parents[2] / "local_media"


def _safe_object_key(object_key: str) -> str:
    """
    防止路径穿越：只允许相对 posix 路径，且不含 '..'。
    """
    p = PurePosixPath(object_key)
    if p.is_absolute() or ".." in p.parts:
        raise ValueError("invalid object_key")
    # 规范化：去掉前导 "./"
    return str(p)


def local_get_object_stream(object_key: str):
    object_key = _safe_object_key(object_key)
    fp = _local_base_dir() / object_key
    if not fp.exists() or not fp.is_file():
        raise FileNotFoundError(object_key)
    content_type, _ = mimetypes.guess_type(fp.name)
    # 交给 StreamingResponse 关闭
    return fp.open("rb"), content_type


def local_put_object_bytes(*, object_key: str, data: bytes, content_type: str | None = None) -> None:
    object_key = _safe_object_key(object_key)
    fp = _local_base_dir() / object_key
    fp.parent.mkdir(parents=True, exist_ok=True)
    fp.write_bytes(data)


def local_delete_object(object_key: str) -> None:
    object_key = _safe_object_key(object_key)
    fp = _local_base_dir() / object_key
    if not fp.exists() or not fp.is_file():
        return
    fp.unlink()
    parent = fp.parent
    base_dir = _local_base_dir()
    while parent != base_dir and parent.exists():
        try:
            parent.rmdir()
        except OSError:
            break
        parent = parent.parent


def ensure_bucket() -> None:
    if settings.storage_backend != "s3":
        return
    s3 = _s3_client()
    bucket = settings.s3_bucket  # type: ignore[assignment]
    try:
        s3.head_bucket(Bucket=bucket)
        return
    except ClientError as exc:
        error = exc.response.get("Error", {})
        code = str(error.get("Code") or "").strip()
        status = int(exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode") or 0)

        # 桶明确不存在时，才尝试创建；避免把 COS 的鉴权/兼容性异常误判成“不存在”。
        if code in {"404", "NoSuchBucket", "NotFound"} or status == 404:
            try:
                s3.create_bucket(Bucket=bucket)
            except ClientError as create_exc:
                create_code = str(create_exc.response.get("Error", {}).get("Code") or "").strip()
                # COS/S3 兼容层可能在桶已存在且归当前账号所有时仍返回 BucketAlreadyExists。
                if create_code in {"BucketAlreadyExists", "BucketAlreadyOwnedByYou"}:
                    return
                raise
            return

        # 对于 AccessDenied / SignatureDoesNotMatch / PermanentRedirect 等情况，不要继续 create_bucket。
        return


def create_upload_token(*, object_key: str, expires_seconds: int = 15 * 60) -> str:
    """
    上传代理使用的短期 token（无需登录也可 PUT，但只能上传指定 object_key）。
    """
    exp = datetime.now(timezone.utc) + timedelta(seconds=expires_seconds)
    payload = {"sub": "upload", "key": object_key, "exp": exp}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_alg)


def verify_upload_token(*, token: str, object_key: str) -> None:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_alg])
    except Exception as e:
        raise ValueError("invalid token") from e
    if payload.get("sub") != "upload":
        raise ValueError("invalid token")
    if payload.get("key") != object_key:
        raise ValueError("token key mismatch")


def presign_put(*, object_key: str, content_type: str | None = None, expires_seconds: int = 3600) -> PresignResult:
    """
    生成 S3 兼容的 PUT 预签名 URL（MinIO/OSS/COS/S3）。
    客户端直接 PUT 到 url；服务端只保存 object_key。
    """
    if not content_type:
        content_type, _ = mimetypes.guess_type(object_key)

    # 本地模式：返回后端 PUT 地址（相对路径，客户端需要拼 base URL）
    if settings.storage_backend == "local":
        token = create_upload_token(object_key=object_key, expires_seconds=min(expires_seconds, 15 * 60))
        headers = {"Content-Type": content_type} if content_type else {}
        url = f"/upload/put/{object_key}?token={token}"
        return PresignResult(method="PUT", url=url, headers=headers, public_url=None, object_key=object_key)

    if settings.storage_backend != "s3":
        raise RuntimeError("Unsupported storage backend")

    s3 = _s3_client()
    bucket = settings.s3_bucket  # type: ignore[assignment]
    params = {"Bucket": bucket, "Key": object_key}
    if content_type:
        params["ContentType"] = content_type
    url = s3.generate_presigned_url("put_object", Params=params, ExpiresIn=expires_seconds)

    headers = {"Content-Type": content_type} if content_type else {}
    public_base = _public_base_url()
    public_url = f"{public_base}/{object_key}" if public_base else None
    return PresignResult(method="PUT", url=url, headers=headers, public_url=public_url, object_key=object_key)


def get_object_stream(object_key: str):
    """
    返回 (file-like body, content_type) 供 StreamingResponse 使用。
    """
    if settings.storage_backend == "local":
        return local_get_object_stream(object_key)

    if settings.storage_backend != "s3":
        raise RuntimeError("Unsupported storage backend")

    s3 = _s3_client()
    bucket = settings.s3_bucket  # type: ignore[assignment]
    try:
        obj = s3.get_object(Bucket=bucket, Key=object_key)
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code")
        if code in ("NoSuchKey", "404", "NotFound"):
            raise FileNotFoundError(object_key)
        raise
    body = obj["Body"]
    content_type = obj.get("ContentType")
    return body, content_type


def put_object_bytes(*, object_key: str, data: bytes, content_type: str | None = None) -> None:
    if settings.storage_backend == "local":
        return local_put_object_bytes(object_key=object_key, data=data, content_type=content_type)

    if settings.storage_backend != "s3":
        raise RuntimeError("Unsupported storage backend")

    s3 = _s3_client()
    bucket = settings.s3_bucket  # type: ignore[assignment]
    params: dict[str, object] = {"Bucket": bucket, "Key": object_key, "Body": data}
    if content_type:
        params["ContentType"] = content_type
    s3.put_object(**params)


def delete_object(object_key: str) -> None:
    object_key = _safe_object_key(object_key)
    if settings.storage_backend == "local":
        return local_delete_object(object_key)

    if settings.storage_backend != "s3":
        raise RuntimeError("Unsupported storage backend")

    s3 = _s3_client()
    bucket = settings.s3_bucket  # type: ignore[assignment]
    s3.delete_object(Bucket=bucket, Key=object_key)


# 兼容旧命名（被其他模块引用）
s3_get_object_stream = get_object_stream
s3_put_object_bytes = put_object_bytes
