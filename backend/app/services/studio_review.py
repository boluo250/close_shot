from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.models import Package, Photographer, PortfolioItem
from app.services.media_url import object_key_to_url

_PROFILE_FIELDS = (
    "display_name",
    "avatar_url",
    "cover_url",
    "bio",
    "tags",
    "city",
    "service_center_lat",
    "service_center_lng",
    "service_radius_m",
    "equipment_list",
    "drone_models",
    "rate_card",
)

_PORTFOLIO_FIELDS = (
    "id",
    "title",
    "image_url",
    "image_object_key",
    "watermark_url",
    "watermark_object_key",
    "sort_order",
    "tags",
    "category",
    "is_pinned",
    "created_at",
    "updated_at",
)

_PACKAGE_FIELDS = (
    "id",
    "name",
    "price_cents",
    "duration_minutes",
    "description",
    "is_active",
    "created_at",
    "updated_at",
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_rate_card_json(text: str | None) -> list[dict[str, Any]]:
    if not text:
        return []
    try:
        items = json.loads(text)
    except json.JSONDecodeError:
        return []
    return items if isinstance(items, list) else []


def load_pending_submission_snapshot(photographer: Photographer) -> dict[str, Any] | None:
    raw = (getattr(photographer, "pending_submission_json", None) or "").strip()
    if not raw:
        return None
    try:
        snapshot = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return snapshot if isinstance(snapshot, dict) else None


def build_live_submission_snapshot(*, db: Session, photographer: Photographer) -> dict[str, Any]:
    portfolio_items = db.scalars(
        select(PortfolioItem)
        .where(PortfolioItem.photographer_id == photographer.id)
        .order_by(PortfolioItem.is_pinned.desc(), PortfolioItem.sort_order.asc(), PortfolioItem.id.asc())
    ).all()
    packages = db.scalars(
        select(Package).where(Package.photographer_id == photographer.id).order_by(Package.id.asc())
    ).all()

    profile = {
        "display_name": photographer.user.display_name if photographer.user else None,
        "avatar_url": photographer.user.avatar_url if photographer.user else None,
        "cover_url": photographer.cover_url,
        "bio": photographer.bio,
        "tags": photographer.tags,
        "city": photographer.city,
        "service_center_lat": photographer.service_center_lat,
        "service_center_lng": photographer.service_center_lng,
        "service_radius_m": photographer.service_radius_m,
        "equipment_list": photographer.equipment_list,
        "drone_models": photographer.drone_models,
        "rate_card": parse_rate_card_json(photographer.rate_card_json),
    }
    portfolio = [
        {
            "id": int(item.id),
            "title": item.title,
            "image_url": object_key_to_url(item.image_object_key) or item.image_url,
            "image_object_key": item.image_object_key,
            "watermark_url": object_key_to_url(item.watermark_object_key) or item.watermark_url,
            "watermark_object_key": item.watermark_object_key,
            "sort_order": item.sort_order,
            "tags": item.tags,
            "category": item.category,
            "is_pinned": bool(item.is_pinned),
            "created_at": item.created_at.isoformat(),
            "updated_at": item.updated_at.isoformat(),
        }
        for item in portfolio_items
    ]
    package_list = [
        {
            "id": int(item.id),
            "name": item.name,
            "price_cents": item.price_cents,
            "duration_minutes": item.duration_minutes,
            "description": item.description,
            "is_active": bool(item.is_active),
            "created_at": item.created_at.isoformat(),
            "updated_at": item.updated_at.isoformat(),
        }
        for item in packages
    ]
    return {
        "profile": profile,
        "portfolio_items": portfolio,
        "packages": package_list,
    }


def merge_submission_snapshot_with_live(
    snapshot: dict[str, Any] | None,
    *,
    live_snapshot: dict[str, Any],
) -> dict[str, Any]:
    if not snapshot:
        return live_snapshot

    merged = dict(live_snapshot)
    merged["profile"] = {
        **(live_snapshot.get("profile") if isinstance(live_snapshot.get("profile"), dict) else {}),
        **snapshot_profile(snapshot),
    }

    if "portfolio_items" in snapshot and isinstance(snapshot.get("portfolio_items"), list):
        merged["portfolio_items"] = snapshot_portfolio_items(snapshot)
    if "packages" in snapshot and isinstance(snapshot.get("packages"), list):
        merged["packages"] = snapshot_packages(snapshot)
    return merged


def get_effective_submission_snapshot(*, db: Session, photographer: Photographer) -> dict[str, Any]:
    live_snapshot = build_live_submission_snapshot(db=db, photographer=photographer)
    pending_snapshot = load_pending_submission_snapshot(photographer)
    return merge_submission_snapshot_with_live(pending_snapshot, live_snapshot=live_snapshot)


def save_pending_submission_snapshot(
    photographer: Photographer,
    snapshot: dict[str, Any],
    *,
    submitted_at: datetime | None = None,
) -> None:
    photographer.pending_submission_json = json.dumps(snapshot, ensure_ascii=False)
    photographer.pending_submission_submitted_at = submitted_at or datetime.now(timezone.utc)
    photographer.pending_reject_reason = None


def clear_pending_submission_snapshot(photographer: Photographer) -> None:
    photographer.pending_submission_json = None
    photographer.pending_submission_submitted_at = None


def pending_review_status(photographer: Photographer) -> str:
    if (getattr(photographer, "pending_submission_json", None) or "").strip():
        return "pending"
    if getattr(photographer, "pending_reject_reason", None):
        return "rejected"
    return "none"


def snapshot_profile(snapshot: dict[str, Any] | None) -> dict[str, Any]:
    profile = (snapshot or {}).get("profile")
    return profile if isinstance(profile, dict) else {}


def snapshot_portfolio_items(snapshot: dict[str, Any] | None) -> list[dict[str, Any]]:
    items = (snapshot or {}).get("portfolio_items")
    return [item for item in items if isinstance(item, dict)] if isinstance(items, list) else []


def snapshot_packages(snapshot: dict[str, Any] | None) -> list[dict[str, Any]]:
    items = (snapshot or {}).get("packages")
    return [item for item in items if isinstance(item, dict)] if isinstance(items, list) else []


def next_snapshot_item_id(items: list[dict[str, Any]]) -> int:
    numeric_ids = [int(item["id"]) for item in items if isinstance(item.get("id"), int)]
    return min(numeric_ids + [0]) - 1


def touch_snapshot_item(item: dict[str, Any], *, is_new: bool = False) -> None:
    now = _now_iso()
    if is_new and not item.get("created_at"):
        item["created_at"] = now
    item["updated_at"] = now


def apply_submission_snapshot(*, db: Session, photographer: Photographer, snapshot: dict[str, Any]) -> None:
    profile = snapshot_profile(snapshot)
    if photographer.user:
        photographer.user.display_name = profile.get("display_name")
        photographer.user.avatar_url = profile.get("avatar_url")

    photographer.cover_url = profile.get("cover_url")
    photographer.bio = profile.get("bio")
    photographer.tags = profile.get("tags") or ""
    photographer.city = profile.get("city")
    photographer.service_center_lat = profile.get("service_center_lat")
    photographer.service_center_lng = profile.get("service_center_lng")
    photographer.service_radius_m = int(profile.get("service_radius_m") or photographer.service_radius_m or 5000)
    photographer.equipment_list = profile.get("equipment_list") or ""
    photographer.drone_models = profile.get("drone_models") or ""
    photographer.rate_card_json = json.dumps(profile.get("rate_card") or [], ensure_ascii=False)
    photographer.last_active_at = datetime.now(timezone.utc)

    db.execute(delete(PortfolioItem).where(PortfolioItem.photographer_id == photographer.id))
    for item in snapshot_portfolio_items(snapshot):
        db.add(
            PortfolioItem(
                photographer_id=photographer.id,
                title=item.get("title"),
                image_url=item.get("image_url") or "",
                image_object_key=item.get("image_object_key"),
                watermark_url=item.get("watermark_url"),
                watermark_object_key=item.get("watermark_object_key"),
                sort_order=int(item.get("sort_order") or 0),
                tags=item.get("tags") or "",
                category=item.get("category") or "",
                is_pinned=bool(item.get("is_pinned")),
            )
        )

    db.execute(delete(Package).where(Package.photographer_id == photographer.id))
    for item in snapshot_packages(snapshot):
        db.add(
            Package(
                photographer_id=photographer.id,
                name=item.get("name") or "",
                price_cents=int(item.get("price_cents") or 0),
                duration_minutes=item.get("duration_minutes"),
                description=item.get("description"),
                is_active=bool(item.get("is_active", True)),
            )
        )


def overlay_base_payload_with_snapshot(base_payload: dict[str, Any], snapshot: dict[str, Any] | None) -> dict[str, Any]:
    profile = snapshot_profile(snapshot)
    for field in _PROFILE_FIELDS:
        if field in profile:
            base_payload[field] = profile.get(field)
    return base_payload


def snapshot_preview_urls(snapshot: dict[str, Any] | None, *, limit: int = 9) -> list[str]:
    urls: list[str] = []
    for item in snapshot_portfolio_items(snapshot):
        url = item.get("image_url") or item.get("watermark_url")
        if not url or url in urls:
            continue
        urls.append(url)
        if len(urls) >= limit:
            break
    return urls


def pick_snapshot_item_fields(item: dict[str, Any], *, kind: str) -> dict[str, Any]:
    fields = _PORTFOLIO_FIELDS if kind == "portfolio" else _PACKAGE_FIELDS
    return {field: item.get(field) for field in fields}
