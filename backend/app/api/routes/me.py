from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import PurePosixPath

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, func, select
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.models import BioTemplate, Favorite, Package, Photographer, PhotographerStatus, PortfolioItem, User, UserRole
from app.db.session import get_db
from app.schemas.me import (
    CertificationStatusOut,
    MeIdentityOut,
    PhotographerApplyIn,
    TencentRealPersonVerifyIn,
    TencentRealPersonVerifyOut,
)
from app.schemas.photographer import PhotographerCardOut, PhotographerOut
from app.services.image_watermark import add_text_watermark
from app.services.media_url import object_key_to_url
from app.services.membership import can_view_contact
from app.services.media_url import object_key_from_url
from app.services.storage import get_object_stream, put_object_bytes

router = APIRouter()

# bio_templates 未迁移/为空时的兜底模板（开发环境避免 500）
_FALLBACK_BIO_TEMPLATES: list[str] = [
    "善于捕捉自然光影的记录者，偏爱真实与松弛的氛围。",
    "喜欢用镜头讲故事，擅长把情绪拍进画面里。",
    "温柔系摄影师，擅长引导，让你自然好看。",
    "注重构图与光线，成片干净耐看不浮夸。",
    "偏纪实风格，记录当下的细节与温度。",
]


# ---------- 有效拍摄类型白名单 ----------
# 注意：需与小程序端 miniprogram/pages/auth/apply/index.js 的 SHOOTING_TYPES 保持一致
VALID_SHOOTING_TYPES = {
    "人像",
    "写真",
    "街拍",
    "情侣",
    "亲子",
    "儿童",
    "孕妇",
    "新生儿",
    "全家福",
    "毕业照",
    "婚礼",
    "旅拍",
    "跟拍",
    "活动",
    "商拍",
    "证件照",
    "探店",
    "宠物",
    "美食",
    "建筑",
    "航拍",
}
VALID_EXPERIENCE_YEARS = {"1年内", "1-3年", "3年以上"}
VALID_PRICE_RANGES = {"199-399", "399-699", "699+"}
ID_CARD_PATTERN = re.compile(r"^\d{15}$|^\d{17}[\dXx]$")


def _build_certification_status(p: Photographer | None, db: Session) -> CertificationStatusOut:
    """根据摄影师数据构建认证状态详情"""
    if not p:
        return CertificationStatusOut(status="not_applied")

    identity_verified = bool(p.real_name and p.id_card_number)
    portfolio_count = db.scalar(
        select(PortfolioItem.id).where(PortfolioItem.photographer_id == p.id).limit(1)
    )
    portfolio_uploaded = bool(portfolio_count is not None)
    contact_verified = bool(p.phone and p.wechat_id)

    return CertificationStatusOut(
        status=p.status,
        certification_level=p.certification_level,
        reject_reason=p.reject_reason,
        identity_verified=identity_verified,
        portfolio_uploaded=portfolio_uploaded,
        contact_verified=contact_verified,
    )


def _parse_rate_card(text: str | None) -> list[dict]:
    if not text:
        return []
    try:
        items = json.loads(text)
    except json.JSONDecodeError:
        return []
    if not isinstance(items, list):
        return []
    out: list[dict] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        mode = str(item.get("mode") or "").strip()
        price_cents = item.get("price_cents")
        unit = item.get("unit")
        if mode == "item":
            mode = "photo"
        if not name or mode not in {"hour", "photo"}:
            continue
        if not isinstance(price_cents, int):
            continue
        out.append(
            {
                "name": name,
                "mode": mode,
                "price_cents": price_cents,
                "unit": str(unit).strip() if unit else None,
            }
        )
    return out


def _parse_csv(text: str | None) -> list[str]:
    return [x.strip() for x in (text or "").split(",") if x.strip()]


def _rate_min(items: list[dict], mode: str) -> int | None:
    prices = [x["price_cents"] for x in items if x.get("mode") == mode and isinstance(x.get("price_cents"), int)]
    return min(prices) if prices else None


def _normalize_rate_card(items: list[dict]) -> list[dict]:
    normalized: list[dict] = []
    for item in items:
        copied = dict(item)
        mode = copied.get("mode")
        if mode == "item":
            mode = "photo"
            copied["mode"] = "photo"
        if mode not in ("hour", "photo"):
            raise HTTPException(status_code=400, detail="invalid rate_card.mode")
        normalized.append(copied)
    return normalized


def _build_portfolio_submission_items(payload: PhotographerApplyIn) -> list[dict]:
    prepared: list[dict] = []
    for raw in payload.portfolio_items:
        item = raw.model_dump()
        image_object_key = item.get("image_object_key") or object_key_from_url(item.get("image_url"))
        if not image_object_key:
            raise HTTPException(status_code=400, detail="作品图片缺少 image_object_key")
        try:
            stream, _ = get_object_stream(image_object_key)
            image_bytes = stream.read()
        except FileNotFoundError as exc:
            raise HTTPException(status_code=400, detail="作品图片文件不存在，请重新上传") from exc

        watermark_key = str(PurePosixPath("watermark") / PurePosixPath(image_object_key))
        watermark_bytes, watermark_content_type = add_text_watermark(image_bytes, watermark_text="边拍")
        put_object_bytes(object_key=watermark_key, data=watermark_bytes, content_type=watermark_content_type)
        item["image_object_key"] = image_object_key
        item["image_url"] = object_key_to_url(image_object_key) or item.get("image_url")
        item["watermark_object_key"] = watermark_key
        item["watermark_url"] = object_key_to_url(watermark_key)
        prepared.append(item)
    return prepared


@router.get("/favorites", response_model=list[PhotographerCardOut])
def my_favorites(
    me: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[PhotographerCardOut]:
    price_sq = (
        select(Package.photographer_id.label("pid"), func.min(Package.price_cents).label("starting_price_cents"))
        .where(Package.is_active.is_(True))
        .group_by(Package.photographer_id)
        .subquery()
    )
    portfolio_count_sq = (
        select(
            PortfolioItem.photographer_id.label("pid"),
            func.count(PortfolioItem.id).label("portfolio_count"),
        )
        .group_by(PortfolioItem.photographer_id)
        .subquery()
    )

    stmt = (
        select(
            Photographer,
            User.display_name,
            User.avatar_url,
            price_sq.c.starting_price_cents,
            portfolio_count_sq.c.portfolio_count,
        )
        .join(Favorite, Favorite.photographer_id == Photographer.id)
        .join(User, User.id == Photographer.user_id)
        .outerjoin(price_sq, price_sq.c.pid == Photographer.id)
        .outerjoin(portfolio_count_sq, portfolio_count_sq.c.pid == Photographer.id)
        .where(Favorite.user_id == me.id)
        .order_by(Favorite.created_at.desc())
    )
    rows = db.execute(stmt).all()

    pids = [p.id for (p, _display_name, _avatar_url, _sp, _pc) in rows]
    preview_map: dict[int, list[str]] = {pid: [] for pid in pids}
    if pids:
        items = db.execute(
            select(
                PortfolioItem.photographer_id,
                PortfolioItem.watermark_object_key,
                PortfolioItem.watermark_url,
                PortfolioItem.image_object_key,
                PortfolioItem.image_url,
            )
            .where(PortfolioItem.photographer_id.in_(pids))
            .order_by(PortfolioItem.photographer_id.asc(), PortfolioItem.sort_order.asc(), PortfolioItem.id.asc())
        ).all()
        for pid, watermark_object_key, watermark_url, image_object_key, image_url in items:
            preview_url = (
                object_key_to_url(watermark_object_key)
                or watermark_url
                or object_key_to_url(image_object_key)
                or image_url
            )
            if preview_url and pid in preview_map and len(preview_map[pid]) < 3:
                preview_map[pid].append(preview_url)

    out: list[PhotographerCardOut] = []
    for p, display_name, avatar_url, starting_price_cents, portfolio_count in rows:
        rate_card = _parse_rate_card(p.rate_card_json)
        can_view, mode, lock_reason = can_view_contact(db, viewer=me, photographer=p)
        out.append(
            PhotographerCardOut(
                **PhotographerOut.model_validate(p).model_dump(
                    exclude={
                        "display_name",
                        "avatar_url",
                        "phone",
                        "wechat_id",
                        "can_view_contact",
                        "contact_access_mode",
                        "contact_lock_reason",
                        "equipment_list",
                        "drone_models",
                        "rate_card",
                    }
                ),
                display_name=display_name,
                avatar_url=avatar_url,
                phone=p.phone if can_view else None,
                wechat_id=p.wechat_id if can_view else None,
                can_view_contact=can_view,
                contact_access_mode=mode,
                contact_lock_reason=lock_reason,
                equipment_list=_parse_csv(p.equipment_list),
                drone_models=_parse_csv(p.drone_models),
                rate_card=rate_card,
                starting_price_cents=int(starting_price_cents) if starting_price_cents is not None else None,
                preview_image_urls=preview_map.get(p.id, []),
                portfolio_count=int(portfolio_count or 0),
                rate_hour_min_cents=_rate_min(rate_card, "hour"),
                rate_item_min_cents=_rate_min(rate_card, "photo"),
            )
        )
    return out


@router.get("/identity", response_model=MeIdentityOut)
def my_identity(me: User = Depends(get_current_user)) -> MeIdentityOut:
    status = "not_applied"
    reason = None
    cert_level = 0
    if me.role == UserRole.admin.value:
        status = PhotographerStatus.approved.value
    elif me.photographer:
        status = me.photographer.status
        reason = me.photographer.reject_reason
        cert_level = me.photographer.certification_level
    return MeIdentityOut(
        role=me.role,
        photographer_status=status,
        photographer_reject_reason=reason,
        certification_level=cert_level,
        is_member=me.is_member,
        member_expires_at=me.member_expires_at,
    )


@router.get("/photographer/certification", response_model=CertificationStatusOut)
def get_certification_status(
    me: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CertificationStatusOut:
    """查询当前用户的摄影师认证状态"""
    p = db.scalar(select(Photographer).where(Photographer.user_id == me.id))
    return _build_certification_status(p, db)


@router.get("/bio-templates", response_model=list[str])
def get_bio_templates(
    me: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[str]:
    """随机返回 3 条个人简介模板（用于一键填充）"""
    import random

    _ = me  # 触发登录校验
    try:
        rows = db.execute(select(BioTemplate.text).order_by(func.random()).limit(3)).all()
        templates = [r[0] for r in rows if r and r[0]]
        if templates:
            return templates
    except ProgrammingError:
        # 典型场景：新库未跑 alembic（bio_templates 表不存在）
        db.rollback()

    return random.sample(_FALLBACK_BIO_TEMPLATES, k=min(3, len(_FALLBACK_BIO_TEMPLATES)))


@router.post("/photographer/apply", response_model=CertificationStatusOut)
def apply_photographer(
    payload: PhotographerApplyIn,
    me: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CertificationStatusOut:
    """提交摄影师入驻认证（原子提交：全部校验通过后才进入待审核）"""
    if not ID_CARD_PATTERN.match(payload.id_card_number):
        raise HTTPException(status_code=400, detail="身份证号格式不正确")

    if me.role == UserRole.admin.value:
        return CertificationStatusOut(
            status=PhotographerStatus.approved.value,
            certification_level=3,
            identity_verified=True,
            portfolio_uploaded=True,
            contact_verified=True,
        )

    # 拍摄类型已从入驻必填中移除：保留字段仅做兼容校验（若传了则校验）
    if payload.shooting_types:
        if len(payload.shooting_types) > 3:
            raise HTTPException(status_code=400, detail="拍摄类型最多选择3个")
        for st in payload.shooting_types:
            if st not in VALID_SHOOTING_TYPES:
                raise HTTPException(status_code=400, detail=f"不支持的拍摄类型：{st}")

    if payload.experience_years and payload.experience_years not in VALID_EXPERIENCE_YEARS:
        raise HTTPException(status_code=400, detail=f"不支持的从业年限选项：{payload.experience_years}")

    if payload.price_range and payload.price_range not in VALID_PRICE_RANGES:
        raise HTTPException(status_code=400, detail=f"不支持的报价区间：{payload.price_range}")

    rate_card_items = _normalize_rate_card([item.model_dump() for item in payload.rate_card])
    if payload.avatar_object_key:
        try:
            get_object_stream(payload.avatar_object_key)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=400, detail="头像文件不存在，请重新上传") from exc

    portfolio_items = _build_portfolio_submission_items(payload)

    p = db.scalar(select(Photographer).where(Photographer.user_id == me.id))
    if not p:
        p = Photographer(
            user_id=me.id,
            tags="",
            is_accepting_orders=False,
            service_radius_m=5000,
        )
        db.add(p)

    # 全部校验通过后，再统一落库
    if me.role != UserRole.photographer.value:
        me.role = UserRole.photographer.value

    p.real_name = payload.real_name
    p.id_card_number = payload.id_card_number
    if payload.id_card_front_url is not None:
        p.id_card_front_url = payload.id_card_front_url
    if payload.id_card_back_url is not None:
        p.id_card_back_url = payload.id_card_back_url
    if payload.shooting_types:
        p.shooting_types = ",".join(payload.shooting_types)
    p.experience_years = payload.experience_years
    p.portfolio_link = payload.portfolio_link
    p.phone = payload.phone
    p.wechat_id = payload.wechat_id
    p.city = payload.city
    p.price_range = payload.price_range
    if payload.service_center_lat is not None:
        p.service_center_lat = payload.service_center_lat
    if payload.service_center_lng is not None:
        p.service_center_lng = payload.service_center_lng
    if payload.service_radius_m is not None:
        p.service_radius_m = payload.service_radius_m
    if payload.bio is not None:
        p.bio = payload.bio
    if payload.equipment_list is not None:
        p.equipment_list = payload.equipment_list
    if payload.drone_models is not None:
        p.drone_models = payload.drone_models
    p.rate_card_json = json.dumps(rate_card_items, ensure_ascii=False)
    p.last_active_at = datetime.now(timezone.utc)
    if payload.avatar_url is not None:
        me.avatar_url = payload.avatar_url
    elif payload.avatar_object_key:
        me.avatar_url = object_key_to_url(payload.avatar_object_key)

    # 设为待审核
    p.status = PhotographerStatus.pending.value
    p.reject_reason = None

    db.add(p)
    db.flush()

    db.execute(delete(PortfolioItem).where(PortfolioItem.photographer_id == p.id))
    db.execute(delete(Package).where(Package.photographer_id == p.id))

    for item in portfolio_items:
        db.add(
            PortfolioItem(
                photographer_id=p.id,
                title=item.get("title"),
                image_url=item.get("image_url"),
                image_object_key=item.get("image_object_key"),
                watermark_url=item.get("watermark_url"),
                watermark_object_key=item.get("watermark_object_key"),
                sort_order=item.get("sort_order") or 0,
                tags=item.get("tags") or "",
                category=item.get("category") or "",
                is_pinned=bool(item.get("is_pinned")),
            )
        )

    for pkg in payload.packages:
        db.add(Package(photographer_id=p.id, **pkg.model_dump()))

    db.commit()
    db.refresh(p)

    return _build_certification_status(p, db)


@router.post("/photographer/tencent-realname/verify", response_model=TencentRealPersonVerifyOut)
def verify_tencent_real_person(
    payload: TencentRealPersonVerifyIn,
    me: User = Depends(get_current_user),
) -> TencentRealPersonVerifyOut:
    """
    腾讯云实名实人认证预留接口（占位）。
    当前仅做基础参数校验，后续在此处接入腾讯云官方 API。
    """
    _ = me  # 触发登录校验
    if not ID_CARD_PATTERN.match(payload.id_card_number):
        raise HTTPException(status_code=400, detail="身份证号格式不正确")
    return TencentRealPersonVerifyOut()
