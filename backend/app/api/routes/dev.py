from __future__ import annotations

import random

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_password
from app.db.models import Package, Photographer, PortfolioItem, User, UserRole
from app.db.session import get_db

router = APIRouter()


@router.post("/seed")
def seed(
    lat: float = 31.2304,
    lng: float = 121.4737,
    n: int = 10,
    db: Session = Depends(get_db),
) -> dict:
    if settings.env != "dev":
        raise HTTPException(status_code=403, detail="seed is dev-only")

    n = min(max(n, 1), 50)
    created = 0
    usernames: list[str] = []
    for i in range(n):
        username = f"p{int(random.random()*1_000_000)}"
        u = User(
            role=UserRole.photographer.value,
            display_name=f"摄影师{i+1}",
            username=username,
            password_hash=hash_password("123456"),
        )
        db.add(u)
        db.flush()
        usernames.append(username)

        # 在中心点附近抖动（大约几公里内）
        dlat = random.uniform(-0.03, 0.03)
        dlng = random.uniform(-0.03, 0.03)
        p = Photographer(
            user_id=u.id,
            bio="擅长人像/情侣/旅拍",
            tags="人像,旅拍,写真",
            is_online=bool(i % 2),
            city="上海",
            lat=lat + dlat,
            lng=lng + dlng,
            service_radius_m=8000,
        )
        db.add(p)
        db.flush()

        db.add_all(
            [
                PortfolioItem(photographer_id=p.id, title="样片1", image_url="https://example.com/1.jpg", sort_order=0, tags="人像"),
                PortfolioItem(photographer_id=p.id, title="样片2", image_url="https://example.com/2.jpg", sort_order=1, tags="旅拍"),
            ]
        )
        db.add_all(
            [
                Package(photographer_id=p.id, name="30分钟快拍", price_cents=19900, duration_minutes=30, description="适合打卡", is_active=True),
                Package(photographer_id=p.id, name="2小时精修", price_cents=79900, duration_minutes=120, description="含精修", is_active=True),
            ]
        )
        created += 1

    db.commit()
    return {"ok": True, "created": created, "default_password": "123456", "usernames": usernames}

