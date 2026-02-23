from __future__ import annotations

from calendar import monthrange
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.orm import Session

from app.db.models import AppSetting, Photographer, User, UserRole

CONTACT_ACCESS_MODE_ALL = "all"
CONTACT_ACCESS_MODE_MEMBER = "member"
CONTACT_ACCESS_MODE_VALUES = {CONTACT_ACCESS_MODE_ALL, CONTACT_ACCESS_MODE_MEMBER}
CONTACT_ACCESS_MODE_SETTING_KEY = "contact_access_mode"

MEMBERSHIP_PLAN_CATALOG = {
    "m1": {
        "code": "m1",
        "title": "月会员",
        "months": 1,
        "price_cents": 2900,
        "original_price_cents": 3900,
        "badge": "尝鲜",
    },
    "m3": {
        "code": "m3",
        "title": "季会员",
        "months": 3,
        "price_cents": 7900,
        "original_price_cents": 11700,
        "badge": "推荐",
    },
    "m12": {
        "code": "m12",
        "title": "年会员",
        "months": 12,
        "price_cents": 19900,
        "original_price_cents": 46800,
        "badge": "最划算",
    },
}


def get_contact_access_mode(db: Session) -> str:
    try:
        setting = db.scalar(select(AppSetting).where(AppSetting.key == CONTACT_ACCESS_MODE_SETTING_KEY))
    except ProgrammingError:
        # 兼容迁移尚未执行完成时的线上请求：缺表时回退为 all，避免接口 500。
        db.rollback()
        return CONTACT_ACCESS_MODE_ALL
    value = (setting.value if setting else CONTACT_ACCESS_MODE_ALL).strip().lower()
    if value not in CONTACT_ACCESS_MODE_VALUES:
        return CONTACT_ACCESS_MODE_ALL
    return value


def set_contact_access_mode(db: Session, mode: str) -> str:
    normalized = (mode or "").strip().lower()
    if normalized not in CONTACT_ACCESS_MODE_VALUES:
        normalized = CONTACT_ACCESS_MODE_ALL
    try:
        setting = db.scalar(select(AppSetting).where(AppSetting.key == CONTACT_ACCESS_MODE_SETTING_KEY))
        if not setting:
            setting = AppSetting(key=CONTACT_ACCESS_MODE_SETTING_KEY, value=normalized)
            db.add(setting)
        else:
            setting.value = normalized
        db.commit()
    except ProgrammingError:
        # 与读取逻辑保持一致：缺表时不抛 500，返回标准化结果。
        db.rollback()
    return normalized


def get_membership_plans() -> list[dict]:
    return [MEMBERSHIP_PLAN_CATALOG[k] for k in ("m1", "m3", "m12")]


def get_membership_plan(plan_code: str) -> dict | None:
    return MEMBERSHIP_PLAN_CATALOG.get((plan_code or "").strip())


def is_member_active(user: User | None) -> bool:
    if not user or not user.is_member:
        return False
    if user.member_expires_at is None:
        return True
    return user.member_expires_at > datetime.now(timezone.utc)


def _add_months(base: datetime, months: int) -> datetime:
    total = base.month - 1 + months
    year = base.year + total // 12
    month = total % 12 + 1
    day = min(base.day, monthrange(year, month)[1])
    return base.replace(year=year, month=month, day=day)


def extend_member_expiry(user: User, months: int, *, now: datetime | None = None) -> datetime:
    current_now = now or datetime.now(timezone.utc)
    if user.member_expires_at and user.member_expires_at > current_now:
        base = user.member_expires_at
    else:
        base = current_now
    new_expiry = _add_months(base, months)
    user.is_member = True
    user.member_expires_at = new_expiry
    return new_expiry


def can_view_contact(db: Session, *, viewer: User | None, photographer: Photographer) -> tuple[bool, str, str | None]:
    mode = get_contact_access_mode(db)
    if mode == CONTACT_ACCESS_MODE_ALL:
        return True, mode, None

    if not viewer:
        return False, mode, "login_required"
    if viewer.role == UserRole.admin.value:
        return True, mode, None
    if viewer.id == photographer.user_id:
        return True, mode, None
    if is_member_active(viewer):
        return True, mode, None
    return False, mode, "member_required"
