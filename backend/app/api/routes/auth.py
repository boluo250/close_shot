from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password, verify_password
from app.db.models import PhotographerStatus, User, UserRole
from app.db.session import get_db
from app.schemas.auth import AdminLoginIn, TokenOut, WechatLoginIn
from app.services.security_policy import validate_admin_password_strength, validate_admin_username
from app.services.wechat_security import exchange_login_code

router = APIRouter()


def _get_user_by_wechat_identity(db: Session, openid: str, unionid: str | None) -> User | None:
    filters = [User.wechat_openid == openid]
    if unionid:
        filters.append(User.wechat_unionid == unionid)
    return db.scalar(select(User).where(or_(*filters)))


def _save_user_with_conflict_retry(db: Session, user: User, openid: str, unionid: str | None) -> User:
    try:
        db.commit()
        db.refresh(user)
        return user
    except IntegrityError:
        db.rollback()
        existing = _get_user_by_wechat_identity(db, openid, unionid)
        if not existing:
            raise HTTPException(status_code=409, detail="wechat account already bound")
        return existing


def _resolve_wechat_user(
    db: Session,
    *,
    openid: str,
    unionid: str | None,
    default_role: str,
    default_display_name: str,
) -> User:
    user = _get_user_by_wechat_identity(db, openid, unionid)
    if not user:
        user = User(
            role=default_role,
            wechat_openid=openid,
            wechat_unionid=unionid,
            display_name=default_display_name,
        )
        db.add(user)
        return _save_user_with_conflict_retry(db, user, openid, unionid)

    if not user.wechat_openid:
        user.wechat_openid = openid
    if unionid and not user.wechat_unionid:
        user.wechat_unionid = unionid
    if not user.display_name:
        user.display_name = default_display_name
    return _save_user_with_conflict_retry(db, user, openid, unionid)


@router.post("/login", response_model=TokenOut)
def admin_login(payload: AdminLoginIn, db: Session = Depends(get_db)) -> TokenOut:
    user = db.scalar(select(User).where(User.username == payload.username))
    if not user or not user.password_hash:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    if not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    if user.role == UserRole.admin.value:
        # 管理员强制使用复杂账号与强密码（弱口令需先重置）
        validate_admin_username(user.username or "")
        validate_admin_password_strength(payload.password)
    token = create_access_token(subject=str(user.id))
    return TokenOut(access_token=token)


@router.post("/wechat", response_model=TokenOut)
def wechat_login(payload: WechatLoginIn, db: Session = Depends(get_db)) -> TokenOut:
    wechat_auth = exchange_login_code(payload.code)
    user = _resolve_wechat_user(
        db,
        openid=wechat_auth["openid"],
        unionid=wechat_auth.get("unionid"),
        default_role=UserRole.customer.value,
        default_display_name="微信用户",
    )
    if user.photographer and user.photographer.status == PhotographerStatus.approved.value:
        if user.role != UserRole.photographer.value:
            user.role = UserRole.photographer.value
            db.commit()
    token = create_access_token(subject=str(user.id))
    return TokenOut(access_token=token)


@router.post("/wechat/studio", response_model=TokenOut)
def wechat_studio_login(payload: WechatLoginIn, db: Session = Depends(get_db)) -> TokenOut:
    wechat_auth = exchange_login_code(payload.code)
    user = _resolve_wechat_user(
        db,
        openid=wechat_auth["openid"],
        unionid=wechat_auth.get("unionid"),
        default_role=UserRole.photographer.value,
        default_display_name="微信摄影师",
    )
    if user.role != UserRole.photographer.value:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="当前微信账号未绑定摄影师")
    if not user.photographer:
        from app.db.models import Photographer  # 避免循环导入

        db.add(Photographer(user_id=user.id, tags="", is_accepting_orders=False, service_radius_m=5000))
        db.commit()
        db.refresh(user)
    token = create_access_token(subject=str(user.id))
    return TokenOut(access_token=token)


@router.post("/dev/create-admin", response_model=TokenOut)
def dev_create_admin(username: str, password: str, db: Session = Depends(get_db)) -> TokenOut:
    """
    开发便利：创建后台管理员账号。
    生产环境应移除或加严格保护。
    """
    validate_admin_username(username)
    validate_admin_password_strength(password)
    exists = db.scalar(select(User).where(User.username == username))
    if exists:
        raise HTTPException(status_code=400, detail="username already exists")
    user = User(role=UserRole.admin.value, username=username, password_hash=hash_password(password), display_name=username)
    db.add(user)
    db.commit()
    db.refresh(user)
    token = create_access_token(subject=str(user.id))
    return TokenOut(access_token=token)


@router.post("/dev/create-photographer", response_model=TokenOut)
def dev_create_photographer(username: str, password: str, db: Session = Depends(get_db)) -> TokenOut:
    """
    开发便利：创建摄影师后台账号 + 对应 photographer profile。
    """
    exists = db.scalar(select(User).where(User.username == username))
    if exists:
        raise HTTPException(status_code=400, detail="username already exists")
    user = User(
        role=UserRole.photographer.value,
        username=username,
        password_hash=hash_password(password),
        display_name=username,
    )
    db.add(user)
    db.flush()
    from app.db.models import Photographer  # 避免循环导入

    db.add(Photographer(user_id=user.id, tags="", is_accepting_orders=False, service_radius_m=5000))
    db.commit()
    db.refresh(user)
    token = create_access_token(subject=str(user.id))
    return TokenOut(access_token=token)

