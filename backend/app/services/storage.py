from __future__ import annotations

import mimetypes
from dataclasses import dataclass

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

from app.core.config import settings


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
        config=Config(signature_version="s3v4"),
    )


def ensure_bucket() -> None:
    if settings.storage_backend != "s3":
        return
    s3 = _s3_client()
    bucket = settings.s3_bucket  # type: ignore[assignment]
    try:
        s3.head_bucket(Bucket=bucket)
    except Exception:
        s3.create_bucket(Bucket=bucket)


def presign_put(*, object_key: str, content_type: str | None = None, expires_seconds: int = 3600) -> PresignResult:
    """
    生成 S3 兼容的 PUT 预签名 URL（MinIO/OSS/COS/S3）。
    客户端直接 PUT 到 url；服务端只保存 object_key。
    """
    if settings.storage_backend != "s3":
        raise RuntimeError("Only s3 backend implemented for presign in MVP")

    s3 = _s3_client()
    bucket = settings.s3_bucket  # type: ignore[assignment]
    if not content_type:
        content_type, _ = mimetypes.guess_type(object_key)
    params = {"Bucket": bucket, "Key": object_key}
    if content_type:
        params["ContentType"] = content_type
    url = s3.generate_presigned_url("put_object", Params=params, ExpiresIn=expires_seconds)

    public_base = settings.s3_public_base_url
    public_url = f"{public_base.rstrip('/')}/{object_key}" if public_base else None
    headers = {"Content-Type": content_type} if content_type else {}
    return PresignResult(method="PUT", url=url, headers=headers, public_url=public_url, object_key=object_key)


def s3_get_object_stream(object_key: str):
    """
    返回 (file-like body, content_type) 供 StreamingResponse 使用。
    """
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


def s3_put_object_bytes(*, object_key: str, data: bytes, content_type: str | None = None) -> None:
    if settings.storage_backend != "s3":
        raise RuntimeError("Only s3 backend implemented for upload in MVP")
    s3 = _s3_client()
    bucket = settings.s3_bucket  # type: ignore[assignment]
    params: dict[str, object] = {"Bucket": bucket, "Key": object_key, "Body": data}
    if content_type:
        params["ContentType"] = content_type
    s3.put_object(**params)

