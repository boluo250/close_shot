from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password, verify_password
from app.db.models import User, UserRole
from app.db.session import get_db
from app.schemas.auth import AdminLoginIn, TokenOut, WechatLoginIn

router = APIRouter()


@router.post("/login", response_model=TokenOut)
def admin_login(payload: AdminLoginIn, db: Session = Depends(get_db)) -> TokenOut:
    user = db.scalar(select(User).where(User.username == payload.username))
    if not user or not user.password_hash:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    if not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    token = create_access_token(subject=str(user.id))
    return TokenOut(access_token=token)


@router.post("/wechat", response_model=TokenOut)
def wechat_login(payload: WechatLoginIn, db: Session = Depends(get_db)) -> TokenOut:
    """
    MVP：微信登录 mock。
    真实实现：用 code 换取 openid/session_key，然后绑定用户。
    """
    openid = f"mock_{payload.code}"
    user = db.scalar(select(User).where(User.wechat_openid == openid))
    if not user:
        user = User(role=UserRole.customer.value, wechat_openid=openid, display_name="微信用户")
        db.add(user)
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

